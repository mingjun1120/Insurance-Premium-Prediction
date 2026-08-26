"""Model training: build the right pipeline for the configured model, fit it, save it.

Which model runs is decided by `model.name` in config.yml. The preprocessing is
*not* configured; it is derived from the model name, because the two families
genuinely need different treatment:

    LGBMRegressor, XGBRegressor, CatBoostRegressor
        read category columns natively - no encoding at all

    RandomForestRegressor
        scikit-learn cannot read a category column, so one-hot encoding

    LinearRegression
        one-hot, plus scaling and term expansion, because a linear model cannot
        discover the smoker x bmi interaction on its own (notebook 03, 4.12.2)

Putting that in config.yml would mean the user hand-maintaining a rule they
cannot get right without reading this file anyway.
"""

import logging

import catboost as cb
import joblib
import lightgbm as lgb
import numpy as np
import xgboost as xgb
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures, StandardScaler

from steps import load_config, resolve

# Model name -> (class, which preprocessing it needs)
MODEL_REGISTRY = {
    "RandomForestRegressor": (RandomForestRegressor, "onehot"),
    "LGBMRegressor": (lgb.LGBMRegressor, "native"),
    "XGBRegressor": (xgb.XGBRegressor, "native"),
    "CatBoostRegressor": (cb.CatBoostRegressor, "native"),
    "LinearRegression": (LinearRegression, "linear"),
}


class Trainer:
    """Build, fit and save the model named in config.yml."""

    def __init__(self):
        self.config = load_config()

        self.target = self.config["data"]["target"]
        self.test_size = self.config["train"]["test_size"]
        self.random_state = self.config["train"]["random_state"]
        self.use_log_target = self.config["train"]["use_log_target"]

        self.model_name = self.config["model"]["name"]
        if self.model_name not in MODEL_REGISTRY:
            raise ValueError(
                f"Unknown model '{self.model_name}'. "
                f"config.yml must name one of: {', '.join(MODEL_REGISTRY)}"
            )

        self.tune = self.config["model"]["tune"]
        self.model_path = resolve(self.config["model"]["store_path"])
        self.kfold_params = self.config["model"]["k_fold"]

        model_block = self.config["models"][self.model_name]
        self.model_params = model_block["params"]
        self.tuning_params = model_block["tuning_params"]

        self.model = None
        self.feature_order = None
        self.categorical_features = None
        self.pipeline = self.create_pipeline()

    def create_pipeline(self):
        """Build the pipeline this model needs, preprocessing included.

        Returns:
            sklearn.pipeline.Pipeline: An unfitted pipeline whose final step is
            always named `model`, so the tuning grids in config.yml can use the
            `model__` prefix regardless of which model is active.

        Examples:
            >>> Trainer().create_pipeline().steps[-1][0]
            'model'
        """
        model_class, preprocessing = MODEL_REGISTRY[self.model_name]

        if preprocessing == "linear":
            # For this model the configured params belong to the term expansion,
            # not to the regressor. Plain least squares has nothing to tune.
            return Pipeline([
                ("prepare", self._make_encoder(scale_numeric=True)),
                ("expand", PolynomialFeatures(include_bias=False, **self.model_params)),
                # A second scaler, because product terms land on wilder scales
                # than the columns they were built from
                ("rescale", StandardScaler()),
                ("model", LinearRegression()),
            ])

        model = model_class(**self.model_params)

        if preprocessing == "onehot":
            return Pipeline([
                ("prepare", self._make_encoder(scale_numeric=False)),
                ("model", model),
            ])

        # native: the boosting libraries read the raw frame themselves
        return Pipeline([("model", model)])

    @staticmethod
    def _make_encoder(scale_numeric):
        """Build a one-hot encoder that adapts to whatever columns survive cleaning.

        Columns are selected by dtype rather than by name, so a column dropped by
        `steps.clean` does not break the pipeline.

        Args:
            scale_numeric (bool): If True, put the numeric columns through
                `StandardScaler`. A forest does not need it - it splits on order,
                not magnitude - but a linear model's coefficients are only
                comparable when its inputs share a scale.

        Returns:
            sklearn.compose.ColumnTransformer: An unfitted transformer. It is
            fitted inside the pipeline, once per fold, so no encoding leaks from
            one fold into another.
        """
        return ColumnTransformer([
            ("categorical", OneHotEncoder(drop="first", sparse_output=False),
             make_column_selector(dtype_include="category")),
            ("numeric", StandardScaler() if scale_numeric else "passthrough",
             make_column_selector(dtype_include=np.number)),
        ])

    def feature_target_separator(self, data):
        """Split the cleaned frame into features and target.

        Args:
            data (pandas.DataFrame): The cleaned frame.

        Returns:
            tuple[pandas.DataFrame, pandas.Series]: Features and the target, the
            target still in dollars. The log transform is applied later, inside
            `train_model`, so that everything outside this class works in dollars.

        Raises:
            KeyError: If the target column is missing from the frame.
        """
        if self.target not in data.columns:
            raise KeyError(f"Target column '{self.target}' is not in the cleaned data.")

        X = data.drop(columns=[self.target])
        y = data[self.target]
        return X, y

    def train_test_split_data(self, X, y):
        """Hold out a test split.

        There is no `stratify` here, unlike the classification reference this
        pipeline is modelled on: stratification balances classes, and a
        continuous target has none.

        Args:
            X (pandas.DataFrame): Features.
            y (pandas.Series): Target, in dollars.

        Returns:
            tuple: `X_train, X_test, y_train, y_test`, targets still in dollars.
        """
        return train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )

    def _fit_kwargs(self, X):
        """Extra arguments this particular model needs at fit time.

        Args:
            X (pandas.DataFrame): The training features.

        Returns:
            dict: Keyword arguments for `pipeline.fit`. Only CatBoost needs any:
            it refuses a `category` column unless it is told which columns are
            categorical, while LightGBM and XGBoost detect them on their own.
        """
        if self.model_name == "CatBoostRegressor":
            return {
                "model__cat_features":
                    X.select_dtypes(include="category").columns.tolist()
            }
        return {}

    def train_model(self, X_train, y_train):
        """Fit the model, tuning first if `model.tune` is true.

        Args:
            X_train (pandas.DataFrame): Training features.
            y_train (pandas.Series): Training target, in dollars. It is
                converted to log space here when `use_log_target` is set, and
                nowhere else.

        Returns:
            dict: The parameters the fitted model actually ended up with. These
            are what `main.py` logs to MLflow, so the run record matches the
            model rather than matching config.yml's wishes.
        """
        self.feature_order = X_train.columns.tolist()
        self.categorical_features = (
            X_train.select_dtypes(include="category").columns.tolist()
        )

        y_fit = np.log1p(y_train) if self.use_log_target else y_train
        fit_kwargs = self._fit_kwargs(X_train)

        if not self.tune:
            logging.info("   - Fitting %s with the parameters from config.yml.",
                         self.model_name)
            self.pipeline.fit(X_train, y_fit, **fit_kwargs)
            self.model = self.pipeline
            return dict(self.model_params)

        logging.info("   - Tuning %s with GridSearchCV...", self.model_name)

        # Parallelism belongs in exactly one place. The search already runs folds
        # across every core, so the model inside must not also claim them all -
        # that is roughly 30% slower, not faster.
        tuning_pipeline = clone(self.pipeline)
        if "n_jobs" in self.model_params:
            tuning_pipeline.set_params(model__n_jobs=1)

        search = GridSearchCV(
            estimator=tuning_pipeline,
            param_grid=self.tuning_params,
            cv=KFold(**self.kfold_params),
            scoring="neg_root_mean_squared_error",
            n_jobs=-1,
        )
        search.fit(X_train, y_fit, **fit_kwargs)

        self.model = search.best_estimator_
        best_params = {
            name.split("__", 1)[1]: value
            for name, value in search.best_params_.items()
        }

        logging.info("   - Combinations tried : %s", len(search.cv_results_["params"]))
        logging.info("   - Best parameters    : %s", best_params)
        logging.info("   - Best CV RMSE       : %.4f (model space)", abs(search.best_score_))

        return {**self.model_params, **best_params}

    def save_model(self):
        """Save the fitted model together with everything needed to use it.

        The pickle holds more than the model. A model fitted on `log1p(charges)`
        returns roughly 9.7 where the real answer is about $16,000, so anything
        loading it without knowing that is wrong by a factor of thousands. The
        target treatment therefore travels *with* the model, along with the
        column order and the categorical column names needed to rebuild an input
        frame.

        Returns:
            pathlib.Path: Where the artefact was written.

        Raises:
            RuntimeError: If called before `train_model`.
        """
        if self.model is None:
            raise RuntimeError("No fitted model to save. Call train_model first.")

        self.model_path.mkdir(parents=True, exist_ok=True)
        artefact_path = self.model_path / "model.pkl"

        joblib.dump({
            "model": self.model,
            "model_name": self.model_name,
            "use_log_target": self.use_log_target,
            "target": self.target,
            "feature_order": self.feature_order,
            "categorical_features": self.categorical_features,
        }, artefact_path)

        logging.info(
            "   - Saved %s (%.0f KB)",
            artefact_path.name, artefact_path.stat().st_size / 1024,
        )
        return artefact_path
