# Insurance Premium Prediction

Predicting individual medical insurance charges from six features - age, sex, BMI,
number of children, smoking status and region - on the Kaggle US Health Insurance
dataset (1,338 rows).

The project follows CRISP-DM across three notebooks, then hardens the result into a
configurable training pipeline with experiment tracking, a container image, and a
deployment pipeline that ships it.

[![CI](https://github.com/mingjun1120/Insurance-Premium-Prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/mingjun1120/Insurance-Premium-Prediction/actions/workflows/ci.yml)
[![CD](https://github.com/mingjun1120/Insurance-Premium-Prediction/actions/workflows/cd.yml/badge.svg)](https://github.com/mingjun1120/Insurance-Premium-Prediction/actions/workflows/cd.yml)

**Live API:** <https://insurance-premium-api.ambitiousgrass-8ecc70a2.malaysiawest.azurecontainerapps.io/docs>

> Running on an Azure free trial that expires around 25 September 2026. After that the
> URL stops answering. Everything else in this repository still runs locally.

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
                                                          |
                                                          v
push to master -> GitHub Actions -> test -> build -> Azure Container Registry
                                                          |
                                                          v
                                              Azure Container Apps (live URL)
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

## Monitoring for drift

A model is only correct about the world it was trained on. When that world moves, the model
does not notice - it keeps answering, just as confidently. `notebooks/04_monitoring.ipynb` uses
[Evidently](https://docs.evidentlyai.com) to look for that movement.

```bash
uv run jupyter lab notebooks/04_monitoring.ipynb
```

It writes two HTML reports to `reports/` (gitignored, regenerated on every run):

| Report | Compares | Purpose |
| --- | --- | --- |
| `baseline_drift.html` | train split vs test split | the **healthy** case - nothing should have moved |
| `production_drift.html` | train split vs `data/production.csv` | the **alarm** case - things moved on purpose |

Running only the alarm case would be a trap. A report full of red tells you nothing unless you
have seen the same report come back green on data you know is fine.

### The production data is simulated

This project uses a static Kaggle file, so there is no real incoming traffic. Section 5.3 of the
notebook *invents* `data/production.csv` by shifting the data deliberately - an ageing book,
rising BMI, a worse smoking mix, and expansion into one region. **The drift found there is drift
we put there.** That is honest for learning the tool; it is not evidence about the real world.

`charges` is withheld from the production file on purpose. In production you get the features
when someone applies, but you do not learn their real medical costs until much later. That gap
is the central difficulty of monitoring a live model.

### What it found

| | Baseline (expect none) | Production (expect drift) |
| --- | --- | --- |
| Columns drifted | 3 of 8 | **4 of 7** |
| Share | 37.5% - below the 50% line | **57.1% - dataset drift declared** |
| Worst column | `prediction` 0.129 | `prediction` 0.515 |

Two results are worth more than the headline:

- **The healthy baseline was not perfectly clean.** Three columns crossed the 0.1 threshold by a
  hair, on two halves of the same shuffle where nothing changed. That is sampling noise across
  268 rows, and it is why the dataset-level *share* is the number to watch rather than any
  single column.
- **Evidently nearly missed a change we made on purpose.** `smoker` was moved from 20.5% to 32%
  and scored **0.0969 - under the threshold, marked `ok`**. Jensen-Shannon distance on a
  two-value column is blunt. Meanwhile `bmi`, nudged by 3 points, scored 0.45. A drift score is
  evidence, not a verdict.

`prediction` drifting hardest in the production report is the useful signal: nobody touched that
column. It moved because the inputs moved and the model followed them. Where ground truth takes
months to arrive, prediction drift is often the earliest warning available.

### A note on Evidently versions

Both reference projects use the pre-0.7 API (`evidently.report`, `ColumnMapping`), removed in
April 2025. This notebook is written against **0.7.21** - `Dataset`, `DataDefinition`, and
Reports with `include_tests=True`. Evidently pins `plotly<6` in every 0.7.x release, which is
why `plotly` is capped below 6 in `pyproject.toml`.

## Tests

```bash
uv run pytest
```

109 tests, about 7 seconds. `pytest` is configured in `pyproject.toml` to skip the `slow`
marker by default.

| File | Guards |
| --- | --- |
| `test_clean.py` | each of the 7 cleaning rules, one planted problem at a time |
| `test_config.py` | `config.yml` still has every key the code reads |
| `test_train.py` | the right pipeline is built for each of the 5 models |
| `test_predict.py` | **predictions come back in dollars** |
| `test_api.py` | both endpoints, and that bad input is refused |

### Tests are split by what they need

`data/` and `models/` are DVC-tracked and gitignored, so a fresh clone does not have them.
Rather than fail, the tests that need the real artefacts carry a skip marker:

```
with the artefacts present : 108 passed
without them               :  80 passed, 28 skipped
```

Every skip names the reason - `models/model.pkl is DVC-tracked and absent here - run
`uv run dvc pull`` - so nothing goes quietly missing. This is what lets CI run the suite
with no Azure connection string, and keeps it working after the storage account is gone.

The prediction tests mostly avoid the problem entirely: the `fake_bundle` fixture trains a
five-tree forest on fifty invented rows and saves a real bundle to a temp folder. The
log-transform logic is therefore tested everywhere, including on a fresh clone.

### Cleaning tests use invented data

The real dataset triggers almost none of the cleaning rules - it arrives with no gaps, no
constant columns and no high-cardinality columns. Testing against it proves the code *runs*,
not that it *works*. Each test instead starts from twelve well-formed rows and plants exactly
one problem, so a failure has exactly one possible cause.

### The golden-number test

```bash
uv run pytest -m slow
```

One test asserts the shipped model still scores RMSE $4,193, MAE $1,974, R2 0.9043 and MAPE
0.1655. It guards the class of bug the CatBoost test-set leak was: a silent change in
behaviour that breaks nothing and raises nothing, visible only by comparing a number against
one written down earlier. It runs the whole pipeline, so it is excluded from the default run.

If it fails after a deliberate change, update the expected values in the same commit that
caused them to move, and say why.

## Continuous integration and deployment

Two workflows in `.github/workflows/`, split by whether they need credentials.

| Workflow | Trigger | Needs Azure | Duration |
| --- | --- | --- | --- |
| `ci.yml` | every push and every pull request | no | ~30s |
| `cd.yml` | pushes to `master` | yes | ~3.5min |

### CI runs without any credentials

The test suite skips anything requiring `models/model.pkl` or `data/`, both DVC-owned
and git-ignored, so a bare runner still executes 80 of the 109 tests:

```
80 passed, 28 skipped, 1 deselected in 4.57s
```

That is deliberate. CI stays green independently of the Azure subscription, gives pull
requests a check that an expired trial cannot block, and needs no secret to be
configured before someone can fork the repo and run it.

### CD stores no secrets either

Nothing long-lived is kept on either side. `azure/login` uses OIDC: GitHub mints a
token for each run, and Microsoft Entra trades it for an Azure access token only if it
matches a federated credential pinned to this repository and this branch.

```
repo:mingjun1120@54136320/Insurance-Premium-Prediction@1347131480:ref:refs/heads/master
```

A fork cannot match that. Nor can a pull request, or another branch.

`dvc pull` needs no credential either, which is the part worth explaining. The
committed `.dvc/config` carries only `account_name`; the connection string lives in
`.dvc/config.local`, which git ignores and which therefore does not exist on a runner.
Given an account name and no explicit credential, DVC falls through to
`DefaultAzureCredential`, which picks up the `az login` that `azure/login` just
performed.

So the three values in GitHub are repository **variables**, not secrets - they are
identifiers, not passwords:

```
AZURE_CLIENT_ID  AZURE_TENANT_ID  AZURE_SUBSCRIPTION_ID
```

### Three narrow roles instead of Contributor

Most guides grant `Contributor` on the resource group because it is one assignment and
always works. It also means a leak hands over everything in the group.

| Identity | Role | Scope | Why |
| --- | --- | --- | --- |
| the pipeline | `AcrPush` | registry | upload the built image |
| the pipeline | `Storage Blob Data Reader` | storage | let `dvc pull` read the model |
| the pipeline | `Container Apps Contributor` | the app | point it at the new tag |
| the app | `AcrPull` | registry | read its own image at start-up |

The pipeline writes images; the app only reads them. Note that `Owner` and
`Contributor` on a storage account do **not** grant access to the blobs inside it -
that is a separate data-plane role family, and its absence is a `403` that looks
like an authentication bug.

### The deploy refuses to ship a model whose numbers moved

Two steps make this a model pipeline rather than a deploy script.

`pytest -m slow` recomputes RMSE against the real data on the runner and fails the run
if the shipped model no longer scores what [Results](#results) claims - before anything
is built or pushed.

The closing step then asks the deployed URL for a real prediction and rejects an answer
that is not in dollars:

```
predicted premium 18095.88 - looks like dollars
```

A deploy that reports success while the app returns 502, or quietly serves `log1p`
dollars, is worse than one that fails.

### Every revision maps to one commit

Images are tagged with the commit sha rather than `latest`, so the running container
can always be traced back to the code that produced it:

```
insurancemlops.azurecr.io/insurance-api:4a536c32d99c5fcf15708b14da3d4a6b045e3425
```

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
.github/workflows/
    ci.yml                  ruff and pytest, no credentials
    cd.yml                  test, build, push, deploy, smoke test
config.yml                  every pipeline setting
main.py                     entry point, with and without MLflow
app.py                      FastAPI service
Dockerfile                  two-stage serving image
samples.json                three real rows for testing the API
.dvc/config                 DVC remote: Azure container and account name
data.dvc                    pointer to the DVC-tracked data/ folder
models.dvc                  pointer to the DVC-tracked models/ folder
tests/
    conftest.py             fixtures and the DVC skip markers
    test_clean.py           the 7 cleaning rules
    test_config.py          config.yml keys
    test_train.py           pipeline shape per model
    test_predict.py         predictions are in dollars
    test_api.py             endpoints and validation
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
    04_monitoring.ipynb             Evidently drift reports
data/                       insurance.csv, merged_data.csv, cleaned_data.csv - DVC-tracked
models/                     model.pkl and the notebook's winning model - DVC-tracked
reports/                    Evidently HTML output, gitignored
mlflow/                     MLflow output, gitignored
    mlflow.db               run metadata
    mlruns/                 saved models and config snapshots
```

## Not built yet

- **Scheduled retraining.** Training is still triggered by hand. There is no job that
  refits on new data and opens a pull request with the new numbers.
- **Automated drift checks.** `notebooks/04_monitoring.ipynb` is run manually against a
  simulated production sample. Nothing watches real traffic or raises an alert.
- **Rollback.** Container Apps keeps old revisions, so rolling back is possible from
  the portal, but no workflow does it automatically when a deploy goes bad.
- **Authentication on the API.** `/predict` is open to anyone with the URL. Fine for a
  portfolio, not for anything real.
