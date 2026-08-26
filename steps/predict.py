"""Model evaluation: load the saved artefact and score it, always in dollars."""

import logging

import joblib
import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)

from steps import load_config, resolve


class Predictor:
    """Load `models/model.pkl` and score it on a split.

    The artefact saved by `steps.train` is a bundle, not a bare model. This class
    reads `use_log_target` out of it and inverts the transform before scoring, so
    every number it returns is in dollars no matter which space the model was
    fitted in. That is the whole reason the flag travels with the pickle.
    """

    def __init__(self):
        self.config = load_config()
        self.model_path = resolve(self.config["model"]["store_path"]) / "model.pkl"

        self.artefact = self.load_model()
        self.model = self.artefact["model"]
        self.model_name = self.artefact["model_name"]
        self.use_log_target = self.artefact["use_log_target"]

    def load_model(self):
        """Read the saved artefact bundle.

        Returns:
            dict: The bundle, holding the model plus `model_name`,
            `use_log_target`, `target`, `feature_order` and
            `categorical_features`.

        Raises:
            FileNotFoundError: If no artefact has been saved yet.
        """
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No model at {self.model_path}. Run main.py to train one first."
            )

        artefact = joblib.load(self.model_path)
        logging.info(
            "   - Loaded %s (%s, log target: %s)",
            self.model_path.name, artefact["model_name"], artefact["use_log_target"],
        )
        return artefact

    def predict(self, X):
        """Predict charges in dollars.

        Args:
            X (pandas.DataFrame): Features, with the same columns the model was
                fitted on. Categorical columns must carry the `category` dtype.

        Returns:
            numpy.ndarray: Predicted charges, in dollars.
        """
        predicted = self.model.predict(X)
        return np.expm1(predicted) if self.use_log_target else predicted

    def evaluate_model(self, X, y):
        """Score the model on one split, in dollars.

        Args:
            X (pandas.DataFrame): Features for the split.
            y (pandas.Series): True charges, in dollars.

        Returns:
            tuple[float, float, float, float]: `rmse, mae, r2, mape`.

            **RMSE** is the primary metric and punishes large misses hardest.
            **MAE** is the typical miss in dollars. **R2** is the share of
            variance explained. **MAPE** is the typical miss as a proportion,
            which is the metric the log transform improves most.

        Examples:
            >>> rmse, mae, r2, mape = Predictor().evaluate_model(X_test, y_test)
            >>> round(rmse)
            4193
        """
        predicted = self.predict(X)

        return (
            float(np.sqrt(mean_squared_error(y, predicted))),
            float(mean_absolute_error(y, predicted)),
            float(r2_score(y, predicted)),
            float(mean_absolute_percentage_error(y, predicted)),
        )
