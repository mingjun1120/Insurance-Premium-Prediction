# Project layout

Every file in the repository, plus the two directories git does not hold.

```
.github/workflows/
    ci.yml                  ruff and pytest, no credentials
    cd.yml                  test, build, push, deploy, smoke test
config.yml                  every pipeline setting
main.py                     entry point, with and without MLflow
app.py                      FastAPI service
Dockerfile                  two-stage serving image
pyproject.toml              dependencies, pytest and ruff settings
uv.lock                     resolved versions
samples.json                three rows of valid input; read by no code
.dvc/
    config                  DVC remote: Azure container and account name
    config.local            the connection string, gitignored
    cache/                  DVC's content-addressed store, gitignored
data.dvc                    pointer to the DVC-tracked data/ folder
models.dvc                  pointer to the DVC-tracked models/ folder
.dockerignore               what stays out of the build context
.dvcignore                  empty but for comments
.python-version             3.12
tests/
    __init__.py             empty; makes `from tests.conftest import` resolve
    conftest.py             fixtures and the DVC skip markers
    test_clean.py           the 7 cleaning rules
    test_config.py          config.yml keys
    test_train.py           pipeline shape per model
    test_predict.py         predictions are in dollars
    test_api.py             endpoints and validation
steps/
    __init__.py             PROJECT_ROOT, CONFIG_PATH, load_config, resolve
    ingest.py               read the raw CSV
    clean.py                7 cleaning steps, mirroring notebook 02 section 3.2
    train.py                model registry, pipelines, tuning, saving
    predict.py              scoring, always in dollars
notebooks/
    01_load_data.ipynb              data loading
    02_eda_and_preprocessing.ipynb  EDA and data preparation
    03_model_training.ipynb         modelling, comparison, SHAP
    04_monitoring.ipynb             Evidently drift reports
data/                       4 CSVs, DVC-tracked, gitignored
models/                     2 pickles, DVC-tracked, gitignored
reports/                    Evidently HTML output, gitignored
mlflow/                     MLflow output, gitignored
    mlflow.db               run metadata
    mlruns/                 saved models and config snapshots
```

`.gitignore` excludes `/data`, `/models`, `mlflow/`, `reports/`, `.venv`,
`__pycache__/` and `/.claude`. `.dvc/.gitignore` excludes `config.local`, `tmp`
and `cache`.

## Source line counts

| File | Lines |
| --- | ---: |
| `config.yml` | 128 |
| `main.py` | 203 |
| `app.py` | 116 |
| `Dockerfile` | 70 |
| `steps/__init__.py` | 53 |
| `steps/ingest.py` | 50 |
| `steps/clean.py` | 402 |
| `steps/train.py` | 292 |
| `steps/predict.py` | 131 |
| `tests/` | 957 across 6 non-empty files |
| `.github/workflows/ci.yml` | 47 |
| `.github/workflows/cd.yml` | 128 |

---

## `data/` — four CSVs, one of them read by the pipeline

DVC records 179,490 bytes across 4 files (`data.dvc`).

| File | Bytes | Written by | Read by |
| --- | ---: | --- | --- |
| `insurance.csv` | 55,628 | downloaded from Kaggle | notebook 01 |
| `merged_data.csv` | 55,690 | notebook 01 | `steps/ingest.py`, notebook 02, notebook 04 |
| `cleaned_data.csv` | 55,650 | notebook 02 | notebook 03 |
| `production.csv` | 12,522 | notebook 04 | notebook 04 |

**`cleaned_data.csv` is not the pipeline's input.** `data.data_path` is
`data/merged_data.csv` (`config.yml:9`), and `steps/clean.py` re-runs the
cleaning itself. The two paths diverge here: notebook 03 trains from
`cleaned_data.csv`, while `main.py` trains from `merged_data.csv` cleaned in
process. Stated at `config.yml:7-8` and in the `Ingestion` class docstring
(`steps/ingest.py:13`).

`production.csv` holds a simulated production sample with `charges` withheld,
written and then read back by notebook 04.

## `models/` — two pickles, one of them loaded

DVC records 5,420,143 bytes across 2 files (`models.dvc`).

| File | Bytes | Written by | Read by |
| --- | ---: | --- | --- |
| `model.pkl` | 2,710,118 | `Trainer.save_model` (`steps/train.py:257`) | `Predictor.load_model` (`steps/predict.py:29`) |
| `random_forest_insurance_model.pkl` | 2,710,025 | notebook 03, section 4.16 | nothing |

`steps/predict.py:29` builds its path as `resolve(store_path) / "model.pkl"`, a
fixed name. Nothing in `steps/`, `app.py`, `tests/`, the Dockerfile or either
workflow refers to the second file. It is a leftover from notebook 03's
"Save and Load the Winning Model" section and is dead weight — 2.7 MB of the
5.4 MB the DVC remote carries.

Both hold a bundle of the same six keys. `models/model.pkl` is overwritten on
every training run; see [artefact-bundle.md](artefact-bundle.md).

## `samples.json`

Three objects, each a valid `POST /predict` body — the cheapest, median and
dearest customers in the dataset.

```json
[{"age": 18, "sex": "male",   "bmi": 23.21, "children": 0, "smoker": "no",  "region": "southeast"},
 {"age": 51, "sex": "male",   "bmi": 35.97, "children": 1, "smoker": "no",  "region": "southeast"},
 {"age": 54, "sex": "female", "bmi": 47.41, "children": 0, "smoker": "yes", "region": "southeast"}]
```

It is referenced by no code and no test. The only mentions in the repository are
`README.md:126` and `README.md:544`. It is not excluded by `.dockerignore`, so it
does reach the build context, but the Dockerfile never copies it into the image
(`Dockerfile:60-63` copies `app.py`, `config.yml`, `steps/` and `models/`).

---

## What each notebook reads and writes

| Notebook | Cells (md/code) | Reads | Writes |
| --- | ---: | --- | --- |
| `01_load_data.ipynb` | 17 (13/4) | `data/insurance.csv` | `data/merged_data.csv` |
| `02_eda_and_preprocessing.ipynb` | 45 (24/21) | `data/merged_data.csv` | `data/cleaned_data.csv` |
| `03_model_training.ipynb` | 113 (58/55) | `data/cleaned_data.csv` | `models/random_forest_insurance_model.pkl` |
| `04_monitoring.ipynb` | 20 (12/8) | `data/merged_data.csv`, `data/production.csv` | `data/production.csv`, `reports/baseline_drift.html`, `reports/production_drift.html` |

`notebooks/` is excluded from ruff by `extend-exclude` (`pyproject.toml:67`) and
from the Docker build context by `.dockerignore`.

## Directories that are not in git

| Directory | Held by | Present after |
| --- | --- | --- |
| `data/` | DVC | `uv run dvc pull`, or running notebook 01 |
| `models/` | DVC | `uv run dvc pull`, or `uv run python main.py` |
| `reports/` | nothing | running notebook 04 |
| `mlflow/` | nothing | `train_with_mlflow()` |
| `.venv/` | nothing | `uv sync` |

A fresh clone has none of them. `models/model.pkl` is required by
`uv run uvicorn app:app`, `docker build`, `uv run pytest -m slow`, and 28 of the
108 tests a default `pytest` run collects.

## Related

- Every key in `config.yml`: [configuration.md](configuration.md)
- What each command writes: [commands.md](commands.md)
- Which tests need which file: [test-suite.md](test-suite.md)
- Why `data/` and `models/` are outside git:
  [../explanation/data-outside-git.md](../explanation/data-outside-git.md)
