# Insurance Premium Prediction

Predicting individual medical insurance charges from six features - age, sex, BMI,
number of children, smoking status and region - on the Kaggle US Health Insurance
dataset (1,338 rows).

The project follows CRISP-DM across three notebooks, then hardens the result into a
configurable training pipeline with experiment tracking.

## Pipeline

```
config.yml
    |
    v
steps/ingest.py   ->  steps/clean.py  ->  steps/train.py  ->  steps/predict.py
  read raw CSV        7 cleaning steps     fit + save          score in dollars
    |
    v
main.py  ->  models/model.pkl  +  MLflow run (params, metrics, model, config)
                    |
                    v
              app.py (FastAPI)  ->  Dockerfile  ->  container on port 8000
```

## Getting started

### 1. Install

Dependencies are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### 2. Get the data and models

`data/` and `models/` are **not in git**. They are versioned with DVC and stored in Azure
Blob Storage, so a fresh clone contains only the pointer files `data.dvc` and `models.dvc`.
Pull the real files:

```bash
uv run dvc pull
```

This needs Azure credentials - see [Data and model versioning](#data-and-model-versioning).

Without them, start from the raw data instead: download the Kaggle US Health Insurance
dataset to `data/insurance.csv`, then run notebook 01, which writes `data/merged_data.csv`
- the file the pipeline actually reads.

```bash
uv run jupyter lab notebooks/01_load_data.ipynb
```

### 3. Train

```bash
uv run python main.py
```

This loads the data, cleans it, trains the model named in `config.yml`, saves it to
`models/model.pkl` and records the run in MLflow.

The script has two entry points. Comment out whichever you do not want at the bottom
of `main.py`:

```python
if __name__ == "__main__":
    # main()               # no MLflow tracking
    train_with_mlflow()    # with MLflow tracking
```

### 4. View the experiments

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db
```

Then open <http://127.0.0.1:5000>.

Everything MLflow writes lives under `mlflow/` - the run metadata in `mlflow/mlflow.db` and the
saved models in `mlflow/mlruns/`. Both paths are named in `config.yml`.

## Serving the model

`app.py` puts the trained model behind an HTTP API.

```bash
uv run uvicorn app:app --reload
```

Then open <http://127.0.0.1:8000/docs> for an interactive page where you can fill in a
form and see the prediction - no curl needed.

| Endpoint | What it does |
| --- | --- |
| `GET /` | Health check. Reports the model name and whether the log transform is on. |
| `POST /predict` | One person in, one premium out. |

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":19,"sex":"female","bmi":27.9,"children":0,"smoker":"yes","region":"southwest"}'
```

```json
{"predicted_premium": 18095.88, "currency": "USD", "model": "RandomForestRegressor"}
```

`samples.json` holds three real rows - the cheapest, the median and the dearest customer
in the dataset - so there is always something valid to paste in.

### Input is checked against the training data

The API rejects anything outside the range the model was actually fitted on, with a `422`
and a reason:

| Field | Accepted | Where the limit comes from |
| --- | --- | --- |
| `age` | 18-64 | exact range in the data |
| `bmi` | 15-55 | data covers 15.96-53.13, widened slightly |
| `children` | 0-5 | exact range in the data |
| `sex` | `female`, `male` | the only values present |
| `smoker` | `yes`, `no` | the only values present |
| `region` | the four US regions | the only values present |

A model asked about a 90 year old has never seen one and would answer confidently anyway.
Refusing is more honest than returning a number nobody should trust.

### The API and the pipeline share one prediction path

`app.py` does not load the pickle itself. It calls `Predictor.predict_records()` in
`steps/predict.py`, the same class `main.py` uses for scoring. That class owns undoing the
log transform, ordering the columns and setting the `category` dtype - all driven by the
saved bundle rather than by anything hardcoded.

This matters because of the log transform. A model fitted on `log1p(charges)` returns
about `9.7` where the answer is `$16,000`. An API that forgot to call `expm1` would not
crash; it would return a plausible number that is wrong by a factor of 1,600.

## Docker

```bash
uv run dvc pull                          # models/model.pkl must exist first
docker build -t insurance-premium .
docker run --rm -p 8000:8000 insurance-premium
```

The image is **1.02 GB** and holds 40 packages, against 257 in the development
environment. Three things keep it down:

- **`--no-dev`** leaves out MLflow, DVC, SHAP, seaborn, sweetviz and JupyterLab. An API
  never logs an experiment or draws a chart.
- **A two-stage build** means uv (58 MB) builds the virtualenv and is then left behind.
- **`nvidia-nccl-cu13` is uninstalled** - 288 MB of CUDA that XGBoost's Linux wheel pulls
  in for multi-GPU training. There is no GPU here, and XGBoost predicts fine without it.

LightGBM, XGBoost and CatBoost all stay in, even though they are most of the remaining
size. Any of the five models in `config.yml` could be the one inside `model.pkl`, and
unpickling it needs the library it came from. Dropping them would save around 500 MB and
quietly break "switch models by editing one line".

`dvc pull` is not run inside the build on purpose - it would bake the Azure connection
string into an image layer, readable by anyone who has the image.

## Data and model versioning

`data/` and `models/` are tracked by [DVC](https://dvc.org), not git. Git holds two small text
pointers - `data.dvc` and `models.dvc` - while the real files live in Azure Blob Storage.

The reason is `models/model.pkl`: it is 2.7 MB of binary and it is rewritten on **every**
training run. Committing it would add 2.7 MB to the repository each time, permanently, with no
way to shrink it afterwards. `data/` rides along for consistency, though at 168 KB it would have
been fine in git.

| | Where it lives |
| --- | --- |
| `.dvc/config` | committed - the container URL and storage account name |
| `.dvc/config.local` | **never committed** - the connection string, gitignored by DVC |

### Setting up credentials

```bash
uv run dvc remote modify --local azureremote connection_string "<your connection string>"
```

Get the string from the Azure portal: storage account `insurancedvc` -> Security + networking
-> Access keys -> Show -> Connection string.

### Everyday commands

```bash
uv run dvc pull              # download data/ and models/ from Azure
uv run dvc add data models   # record the current version after changing them
uv run dvc push              # upload the new version to Azure
uv run dvc checkout          # restore the version matching the current git commit
uv run dvc status --cloud    # check whether the remote has everything
```

### After every training run

`main.py` rewrites `models/model.pkl`. Git will not notice, because `models/` is
ignored now - so the new version has to be recorded by hand. Three steps, in this
order:

```bash
uv run python main.py           # model.pkl changes

uv run dvc add data models      # 1. DVC:   note the new version
git add models.dvc              # 2. git:   save the new pointer
git commit -m "..."
uv run dvc push                 # 3. Azure: store the new file
```

**Skipping step 3 is the mistake to watch for.** The commit still succeeds, so nothing
looks wrong locally - but `models.dvc` now points at a file that exists only on your
machine. The next person to run `dvc pull` gets an error, and so will you on your next
computer.

If you are ever unsure whether a push went through:

```bash
uv run dvc status --cloud
```

`Cache and remote 'azureremote' are in sync.` means everything is safely in Azure.
Anything else lists what is still missing, and the fix is `dvc push`.

> **Trial expiry.** The Azure storage account sits on a free trial with $200 of credit, valid
> 30 days from sign-up (check the exact date in the portal - around 2026-09-25). When the trial
> lapses, Azure decommissions the resources and `dvc pull` stops working. Upgrade to
> pay-as-you-go before then; at 5.5 MB the ongoing cost is a fraction of a cent per month.

## Switching models

Change **one line** in `config.yml`:

```yaml
model:
  name: RandomForestRegressor
```

Valid names: `RandomForestRegressor`, `LGBMRegressor`, `XGBRegressor`,
`CatBoostRegressor`, `LinearRegression`.

Each model keeps its own `params` and `tuning_params` block, because they do not share
parameter names - CatBoost says `random_seed` / `depth` / `iterations` where the others
say `random_state` / `max_depth` / `n_estimators`.

Preprocessing is **not** configured. `steps/train.py` derives it from the model name:

| Model | Preprocessing |
| --- | --- |
| LightGBM, XGBoost, CatBoost | none - they read `category` columns natively |
| Random Forest | one-hot encoding |
| Linear Regression | one-hot, scaling, term expansion, rescaling |

### Tuning

`tune: false` fits once with the parameters in `config.yml`, which are already the tuned
winners from notebook 03. `tune: true` runs `GridSearchCV` over `tuning_params` - about
44x slower, and worth doing when the data has changed.

## Results

Test-set performance, from notebook 03 and reproduced by the pipeline:

| Model | RMSE | MAE | R2 | MAPE |
| --- | ---: | ---: | ---: | ---: |
| **Random Forest** | **$4,193** | $1,974 | 0.9043 | 0.1655 |
| XGBoost | $4,345 | $2,032 | 0.8972 | 0.1643 |
| LightGBM | $4,351 | $2,027 | 0.8970 | 0.1628 |
| CatBoost | $4,399 | $2,180 | 0.8947 | 0.1772 |
| Linear Regression | $4,942 | $2,577 | 0.8671 | 0.1806 |

Linear Regression is the baseline. The distance between it and the winner is what the
tree ensembles are actually worth.

### The target is log-transformed

`charges` is heavily right-skewed. RMSE squares the error **in dollars**, so training on
raw dollars chases the few expensive customers and neglects the many cheap ones. Fitting
on `log1p(charges)` turns squared error in dollars into roughly squared error in
*percent*, so a 20% miss counts the same at every price. Notebook 03 section 4.3 measures
this rather than assuming it.

Every metric above is still reported in **dollars** - the pipeline inverts the transform
before scoring.

### The saved artefact is a bundle, not a bare model

`models/model.pkl` holds a dictionary:

```python
{
    "model": <fitted sklearn Pipeline>,
    "model_name": "RandomForestRegressor",
    "use_log_target": True,
    "target": "charges",
    "feature_order": ["age", "sex", "bmi", "children", "smoker", "region"],
    "categorical_features": ["sex", "smoker", "region"],
}
```

A model fitted on `log1p(charges)` returns about 9.7 where the real answer is $16,000.
Anything loading it without knowing that is wrong by a factor of thousands, so the flag
travels **with** the model.

## Layout

```
config.yml                  every pipeline setting
main.py                     entry point, with and without MLflow
app.py                      FastAPI service
Dockerfile                  two-stage serving image
samples.json                three real rows for testing the API
.dvc/config                 DVC remote: Azure container and account name
data.dvc                    pointer to the DVC-tracked data/ folder
models.dvc                  pointer to the DVC-tracked models/ folder
steps/
    __init__.py             PROJECT_ROOT and load_config
    ingest.py               read the raw CSV
    clean.py                7 cleaning steps, mirroring notebook 02 section 3.2
    train.py                model registry, pipelines, tuning, saving
    predict.py              scoring, always in dollars
notebooks/
    01_load_data.ipynb              data loading
    02_eda_and_preprocessing.ipynb  EDA and data preparation
    03_model_training.ipynb         modelling, comparison, SHAP
data/                       insurance.csv, merged_data.csv, cleaned_data.csv - DVC-tracked
models/                     model.pkl and the notebook's winning model - DVC-tracked
mlflow/                     MLflow output, gitignored
    mlflow.db               run metadata
    mlruns/                 saved models and config snapshots
```

## Not built yet

Evidently drift monitoring, CI/CD and tests.
