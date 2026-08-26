"""Shared fixtures and skip markers.

Tests here come in two kinds, and the difference matters for CI.

**Self-contained tests** build whatever they need - a small DataFrame, or a
model trained on fifty invented rows - and run anywhere, including a fresh
clone with no credentials.

**Artefact tests** need the real `models/model.pkl` or `data/merged_data.csv`.
Both are DVC-tracked and gitignored, so on a fresh checkout they are simply not
there. Those tests carry `requires_model` or `requires_data` and skip with a
reason rather than failing. A skip is loud in pytest's output, so nothing goes
quietly missing.

That split is what lets CI run the suite without an Azure connection string,
and keeps it working after the storage account is gone.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODEL_FILE = PROJECT_ROOT / "models" / "model.pkl"
DATA_FILE = PROJECT_ROOT / "data" / "merged_data.csv"

requires_model = pytest.mark.skipif(
    not MODEL_FILE.exists(),
    reason="models/model.pkl is DVC-tracked and absent here - run `uv run dvc pull`",
)
requires_data = pytest.mark.skipif(
    not DATA_FILE.exists(),
    reason="data/ is DVC-tracked and absent here - run `uv run dvc pull`",
)

TARGET = "charges"
CATEGORICAL = ["sex", "smoker", "region"]


@pytest.fixture
def tidy_frame():
    """Twelve well-formed rows in the project's real schema.

    Nothing here should trip any cleaning rule. Tests that check a rule *fires*
    start from this frame and add exactly one problem, so a failure points at
    one cause rather than at a pile of them.

    Returns:
        pandas.DataFrame: Twelve rows with the six features and `charges`.
    """
    return pd.DataFrame({
        "age": [19, 25, 31, 37, 43, 49, 55, 61, 22, 28, 34, 40],
        "sex": ["female", "male"] * 6,
        "bmi": [27.9, 33.8, 22.7, 28.9, 25.7, 26.2, 30.1, 31.9, 24.3, 29.8, 35.4, 21.6],
        "children": [0, 1, 3, 0, 2, 1, 0, 3, 1, 2, 0, 1],
        "smoker": ["yes", "no", "no", "no", "no", "no",
                   "yes", "no", "no", "no", "yes", "no"],
        "region": ["southwest", "southeast", "northwest", "northeast"] * 3,
        TARGET: [16884.9, 1725.6, 4449.5, 21984.5, 3866.9, 8240.6,
                 38711.0, 10797.3, 2395.2, 4149.7, 36837.5, 3021.8],
    })


@pytest.fixture
def fake_training_data():
    """Fifty invented rows, enough to actually fit a model.

    Charges follow a crude but real relationship - older, heavier and smoking
    all cost more - so a fitted model has some signal to find rather than pure
    noise.

    Returns:
        tuple[pandas.DataFrame, pandas.Series]: Features and charges.
    """
    rng = np.random.default_rng(0)
    n = 50

    age = rng.integers(18, 65, n)
    bmi = rng.uniform(18, 45, n).round(2)
    smoker = rng.choice(["yes", "no"], n, p=[0.3, 0.7])

    charges = (
        250 * age + 300 * bmi + np.where(smoker == "yes", 22000, 0)
        + rng.normal(0, 1500, n)
    ).clip(1000)

    features = pd.DataFrame({
        "age": age,
        "sex": rng.choice(["female", "male"], n),
        "bmi": bmi,
        "children": rng.integers(0, 6, n),
        "smoker": smoker,
        "region": rng.choice(
            ["northeast", "northwest", "southeast", "southwest"], n
        ),
    })
    for column in CATEGORICAL:
        features[column] = features[column].astype("category")

    return features, pd.Series(charges, name=TARGET)


@pytest.fixture
def fake_bundle(tmp_path, fake_training_data):
    """A real artefact bundle, trained here, saved to a temp folder.

    Lets the prediction tests exercise the log-transform logic without needing
    `dvc pull`. The bundle has the same shape `steps.train.save_model` writes,
    including `use_log_target=True` - which is the thing worth guarding.

    Returns:
        pathlib.Path: The directory holding `model.pkl`.
    """
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline

    from steps.train import Trainer

    features, charges = fake_training_data

    pipeline = Pipeline([
        ("prepare", Trainer._make_encoder(scale_numeric=False)),
        ("model", RandomForestRegressor(n_estimators=5, random_state=0)),
    ])
    pipeline.fit(features, np.log1p(charges))

    joblib.dump(
        {
            "model": pipeline,
            "model_name": "RandomForestRegressor",
            "use_log_target": True,
            "target": TARGET,
            "feature_order": list(features.columns),
            "categorical_features": CATEGORICAL,
        },
        tmp_path / "model.pkl",
    )
    return tmp_path
