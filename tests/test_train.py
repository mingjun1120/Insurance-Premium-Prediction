"""Tests for `steps.train`, mostly about pipeline shape.

`create_pipeline` branches on the model name to decide preprocessing, and a
wrong branch is the worst kind of bug here: nothing crashes, the model just
trains on badly prepared data and scores a bit worse than it should. Checking
the shape catches that in milliseconds.

One real fit runs at the end, on fifty invented rows, to prove the pieces
actually work together.
"""

import numpy as np
import pytest
from sklearn.pipeline import Pipeline

from steps.train import MODEL_REGISTRY, Trainer


def trainer_for(model_name, monkeypatch):
    """Build a Trainer pinned to one model, without editing config.yml.

    Args:
        model_name (str): A key of `MODEL_REGISTRY`.
        monkeypatch: pytest's monkeypatch fixture.

    Returns:
        steps.train.Trainer: Configured for that model.
    """
    trainer = Trainer()
    monkeypatch.setattr(trainer, "model_name", model_name)
    monkeypatch.setattr(
        trainer, "model_params", trainer.config["models"][model_name]["params"]
    )
    return trainer


ALL_MODELS = list(MODEL_REGISTRY)
NATIVE_MODELS = [n for n, (_, kind) in MODEL_REGISTRY.items() if kind == "native"]


class TestPipelineShape:
    @pytest.mark.parametrize("model_name", ALL_MODELS)
    def test_final_step_is_always_called_model(self, model_name, monkeypatch):
        """The `model__` prefix in every tuning grid depends on this name."""
        pipeline = trainer_for(model_name, monkeypatch).create_pipeline()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[-1][0] == "model"

    @pytest.mark.parametrize("model_name", NATIVE_MODELS)
    def test_boosting_models_get_no_preprocessing(self, model_name, monkeypatch):
        """LightGBM, XGBoost and CatBoost read `category` columns themselves."""
        pipeline = trainer_for(model_name, monkeypatch).create_pipeline()

        assert [name for name, _ in pipeline.steps] == ["model"]

    def test_random_forest_gets_one_hot_encoding(self, monkeypatch):
        """scikit-learn cannot split on a category dtype, so it needs encoding."""
        pipeline = trainer_for("RandomForestRegressor", monkeypatch).create_pipeline()

        assert [name for name, _ in pipeline.steps] == ["prepare", "model"]

    def test_linear_regression_gets_scaling_and_expansion(self, monkeypatch):
        """Least squares needs a shared scale, and interaction terms to bend."""
        pipeline = trainer_for("LinearRegression", monkeypatch).create_pipeline()

        assert [name for name, _ in pipeline.steps] == [
            "prepare", "expand", "rescale", "model"
        ]

    @pytest.mark.parametrize("model_name", ALL_MODELS)
    def test_pipeline_is_not_fitted_yet(self, model_name, monkeypatch):
        """Fitting belongs to `train_model`, once, on the training split."""
        from sklearn.exceptions import NotFittedError
        from sklearn.utils.validation import check_is_fitted

        pipeline = trainer_for(model_name, monkeypatch).create_pipeline()

        with pytest.raises(NotFittedError):
            check_is_fitted(pipeline)


class TestEncoder:
    @staticmethod
    def steps_of(scale_numeric):
        """Map step name to transformer for one encoder.

        `ColumnTransformer.transformers` holds `(name, transformer, columns)`
        triples, so it cannot go straight into `dict()`.

        Args:
            scale_numeric (bool): Passed through to `Trainer._make_encoder`.

        Returns:
            dict: Step name to the transformer registered under it.
        """
        encoder = Trainer._make_encoder(scale_numeric=scale_numeric)
        return {name: transformer for name, transformer, _ in encoder.transformers}

    def test_numeric_columns_are_scaled_only_when_asked(self):
        """A forest splits on order; a linear model needs a shared scale."""
        assert self.steps_of(scale_numeric=False)["numeric"] == "passthrough"

        scaled = self.steps_of(scale_numeric=True)["numeric"]
        assert type(scaled).__name__ == "StandardScaler"

    @pytest.mark.parametrize("scale_numeric", [True, False])
    def test_categorical_columns_are_one_hot_encoded_either_way(self, scale_numeric):
        categorical = self.steps_of(scale_numeric)["categorical"]

        assert type(categorical).__name__ == "OneHotEncoder"
        assert categorical.drop == "first", "one level must be dropped to avoid collinearity"

    def test_columns_are_chosen_by_dtype_not_by_name(self, fake_training_data):
        """A column dropped by steps.clean must not break the pipeline."""
        features, _ = fake_training_data
        encoder = Trainer._make_encoder(scale_numeric=False)

        encoder.fit(features)
        reduced = features.drop(columns=["region"])

        # Refitting on fewer columns should simply work
        Trainer._make_encoder(scale_numeric=False).fit(reduced)


class TestFeatureTargetSeparator:
    def test_target_is_split_off(self, tidy_frame):
        from tests.conftest import TARGET

        features, target = Trainer().feature_target_separator(tidy_frame)

        assert TARGET not in features.columns
        assert target.name == TARGET
        assert len(features) == len(target) == 12


class TestRealFit:
    def test_random_forest_trains_and_predicts(self, fake_training_data, monkeypatch):
        """Fifty invented rows, five trees - proof the parts fit together."""
        features, charges = fake_training_data
        trainer = trainer_for("RandomForestRegressor", monkeypatch)
        monkeypatch.setattr(
            trainer, "model_params", {"n_estimators": 5, "random_state": 0}
        )

        pipeline = trainer.create_pipeline()
        pipeline.fit(features, np.log1p(charges))
        predicted = np.expm1(pipeline.predict(features))

        assert len(predicted) == len(features)
        assert (predicted > 0).all(), "charges cannot be negative"

    def test_a_smoker_is_priced_above_an_identical_non_smoker(
        self, fake_training_data, monkeypatch
    ):
        """The strongest signal in the data should survive the pipeline."""
        import pandas as pd

        features, charges = fake_training_data
        trainer = trainer_for("RandomForestRegressor", monkeypatch)
        monkeypatch.setattr(
            trainer, "model_params", {"n_estimators": 25, "random_state": 0}
        )

        pipeline = trainer.create_pipeline()
        pipeline.fit(features, np.log1p(charges))

        pair = pd.DataFrame({
            "age": [40, 40], "sex": ["male", "male"], "bmi": [30.0, 30.0],
            "children": [1, 1], "smoker": ["yes", "no"],
            "region": ["southeast", "southeast"],
        })
        for column in ["sex", "smoker", "region"]:
            pair[column] = pair[column].astype(
                pd.CategoricalDtype(features[column].cat.categories)
            )

        smoker, non_smoker = np.expm1(pipeline.predict(pair))

        assert smoker > non_smoker
