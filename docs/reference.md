# Reference

`Look-up page` · Not one of the five guides in the reading path.

Use this page to look up a command, file, field, or configuration value. For a
first run, use [Getting started](getting-started.md).

## Commands

Run commands from the project root.

| Command | Purpose | Needs |
| --- | --- | --- |
| `uv sync` | Install serving and development dependencies. | Python 3.12 and uv. |
| `uv run dvc pull` | Restore DVC-tracked data and models. | Azure credential. |
| `uv run python main.py` | Clean, train, save, score, and log to MLflow. | `data/merged_data.csv` |
| `uv run ruff check .` | Lint Python code. | Installed dependencies. |
| `uv run pytest` | Run fast tests. | Installed dependencies. |
| `uv run pytest -m slow` | Check the saved model on real data. | Data and model bundle. |
| `uv run uvicorn app:app --reload` | Start the local API. | Model bundle. |
| `uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db` | Open experiment tracking. | At least one tracked run. |
| `uv run jupyter lab` | Open notebooks. | Installed development dependencies. |
| `docker build -t insurance-premium .` | Build the serving image. | Model bundle. |
| `docker run --rm -p 8000:8000 insurance-premium` | Run the image. | Built image. |

## Configuration

`config.yml` is read from the project root.

| Path | Current value | Meaning |
| --- | --- | --- |
| `data.data_path` | `data/merged_data.csv` | Pipeline input. |
| `data.target` | `charges` | Prediction target. |
| `train.test_size` | `0.2` | Held-out share. |
| `train.random_state` | `42` | Reproducible split. |
| `train.use_log_target` | `true` | Fit on `log1p(charges)`. |
| `model.name` | `RandomForestRegressor` | Active model. |
| `model.tune` | `false` | Fit saved parameters without grid search. |
| `model.store_path` | `models/` | Bundle output directory. |
| `model.k_fold.*` | 5 folds, shuffled, seed 42 | Grid-search cross-validation. |
| `models.<name>.params` | Model-specific | Normal-fit parameters. |
| `models.<name>.tuning_params` | Model-specific | Grid-search values. |
| `mlflow.experiment_name` | `Insurance Premium Prediction` | UI experiment. |
| `mlflow.registered_model_name` | `insurance_premium_model` | MLflow registry name. |
| `mlflow.tracking_db` | `mlflow/mlflow.db` | SQLite run metadata. |
| `mlflow.artifact_location` | `mlflow/mlruns` | Run artefacts. |

Allowed model names:

```text
RandomForestRegressor
LGBMRegressor
XGBRegressor
CatBoostRegressor
LinearRegression
```

## API

### `GET /`

Health response:

```json
{
  "status": "ok",
  "model": "RandomForestRegressor",
  "log_target": true
}
```

### `POST /predict`

Request fields:

| Field | Type | Accepted values |
| --- | --- | --- |
| `age` | integer | 18 to 64 |
| `sex` | string | `female`, `male` |
| `bmi` | number | 15 to 55 |
| `children` | integer | 0 to 5 |
| `smoker` | string | `yes`, `no` |
| `region` | string | `northeast`, `northwest`, `southeast`, `southwest` |

Response fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `predicted_premium` | number | Predicted annual charge. |
| `currency` | string | Always `USD`. |
| `model` | string | Model name read from the bundle. |

Invalid input returns HTTP 422 before prediction code runs.

## Model bundle

`models/model.pkl` is a joblib-serialized dictionary with six keys:

| Key | Used by |
| --- | --- |
| `model` | `Predictor.predict()` |
| `model_name` | Health and prediction responses. |
| `use_log_target` | Decides whether to run `expm1`. |
| `target` | Records the training target for provenance. |
| `feature_order` | Builds inference frames in training order. |
| `categorical_features` | Restores pandas `category` dtypes. |

`Predictor` unpacks the other five keys onto itself. `target` stays inside the
bundle dict and is never read at runtime.

## Project layout

```text
.github/workflows/    CI and CD
app.py                FastAPI service
config.yml            Training and MLflow settings
Dockerfile            Two-stage serving image
main.py               Training entry points
samples.json          Three example bodies to paste into /docs (one at a time)
steps/
  __init__.py          PROJECT_ROOT, load_config(), resolve()
  ingest.py            Read data
  clean.py             Apply seven cleaning rules
  train.py             Build, tune, fit, and save
  predict.py           Predict and evaluate in dollars
notebooks/
  01_load_data.ipynb
  02_eda_and_preprocessing.ipynb
  03_model_training.ipynb
  04_monitoring.ipynb
tests/                 Unit, integration, API, and golden tests
docs/                  Five ordered guides, this reference, and diagram assets
data.dvc               Pointer to data/
models.dvc             Pointer to models/
```

Generated or external paths:

| Path | Owner | Git status |
| --- | --- | --- |
| `data/` | DVC | Ignored |
| `models/` | DVC | Ignored |
| `mlflow/` | MLflow | Ignored |
| `reports/` | Evidently notebook | Ignored |
| `.venv/` | uv | Ignored |
| `.dvc/config.local` | Local DVC credential | Ignored |

## Workflow triggers

| Event | CI | CD |
| --- | --- | --- |
| Push to `master` | Yes | Yes |
| Pull request | Yes | No |
| Push to another branch | No | No |
| Manual dispatch | No | Yes |

## Known limits

- The dataset is small and not suitable for real insurance pricing.
- The API is unauthenticated.
- The live endpoint is temporary.
- Drift data is simulated; there is no traffic capture or alert.
- Retraining and rollback are manual.
- The model explains historical charges, not an approved insurance rate.

## Plain-English glossary

| Term | Meaning here |
| --- | --- |
| Artefact or artifact | A file produced by a run, such as a model or report. |
| Bundle | The fitted model plus the facts needed to use it safely. |
| DVC pointer | A small Git file that identifies large files stored elsewhere. |
| Drift | Current inputs or predictions no longer look like the reference data. |
| Golden test | A real-data check against a known model result. |
| OIDC | A short-lived login from GitHub to Azure without a stored client secret. |
| RMSE | Error in dollars that punishes large misses more heavily. |

Back to [Getting started](getting-started.md) or the [project README](../README.md).
