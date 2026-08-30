# Facts

Raw material for the documentation work. Not documentation itself — nothing here
is written for a reader who does not already have the repo open.

Gathered on the `dev` branch at `13ed746`. Every claim below carries a
`file:line` citation. Where a claim is an inference rather than a citation, it
says so.

---

## 1. What was read, and what was not

**Read in full:** `config.yml`, `main.py`, `app.py`, all five modules in `steps/`,
`tests/conftest.py`, `Dockerfile`, `pyproject.toml`, `.dvc/config`, `data.dvc`,
`models.dvc`, `.gitignore`, `.github/workflows/ci.yml`, `.github/workflows/cd.yml`,
all 41 commit subjects.

**Read partially:** `tests/test_*.py` — module docstrings and the first ~25 lines
of each. Each docstring states the file's intent explicitly, which is what a facts
file needs; the individual assertions are not.

**Not read:**

| Skipped | Why |
|---|---|
| Notebook cell *contents* (195 cells across 4 files) | Headings and counts were extracted instead. The pipeline logic was ported into `steps/`, which was read in full. Chapter writing will need specific cells; facts gathering did not. |
| `uv.lock` | Generated. `pyproject.toml` is the source of truth. |
| `reports/`, `mlflow/` | Generated output, git-ignored. |
| `.dockerignore`, `.dvcignore` | Not load-bearing for any documentation claim. |

---

## 2. The map

| File | Lines | Job |
|---|---|---|
| `config.yml` | 128 | Every pipeline knob. Model chosen at `config.yml:22`. |
| `main.py` | 203 | Training entry point. Two of them. |
| `app.py` | 116 | FastAPI service. |
| `steps/__init__.py` | 53 | `PROJECT_ROOT`, `load_config`, `resolve`. |
| `steps/ingest.py` | 50 | Read the raw CSV. |
| `steps/clean.py` | 402 | Seven cleaning rules, ported from notebook 02. |
| `steps/train.py` | 292 | Build pipeline, fit, save bundle. |
| `steps/predict.py` | 131 | Load bundle, predict, score. |
| `tests/` | 812 across 6 files | Two kinds — see section 7. |
| `Dockerfile` | 70 | Two-stage serving image. |
| `.github/workflows/ci.yml` | 47 | Lint and test, no secrets. |
| `.github/workflows/cd.yml` | 128 | Test, build, deploy, smoke test. |

Total application code: 2,402 lines including tests.

---

## 3. Trace A — one prediction, HTTP in to dollars out

A `POST /predict` carrying
`{"age":19,"sex":"female","bmi":27.9,"children":0,"smoker":"yes","region":"southwest"}`.

1. **FastAPI validates against `Person`** (`app.py:30-56`, the fields at 49-56). Every bound comes from
   the training data, not a guess — `age` 18 to 64, `bmi` 15 to 55, `children` 0 to
   5, with `sex`, `smoker` and `region` as `Literal` enums. Anything outside returns
   **422 before any project code runs**.
2. **`predict()` is entered** (`app.py:91`).
3. **`person.model_dump()`** turns the validated model into a plain dict, passed as
   a one-item list (`app.py:110`).
4. **`Predictor.predict_records()`** (`steps/predict.py:74`) builds a DataFrame with
   `columns=self.feature_order` — the column order read out of the saved bundle, not
   written down anywhere in `app.py`.
5. Each name in `self.categorical_features` is cast to the `category` dtype. LightGBM,
   XGBoost and CatBoost require that dtype; the list also comes from the bundle.
6. **`self.predict(frame)`** (`steps/predict.py:61`) calls the fitted sklearn
   `Pipeline`, which applies whatever preprocessing that particular model needed.
7. **`np.expm1(predicted)`** (`steps/predict.py:72`) undoes the log transform.
   **This is the only place in the codebase where it is undone.**
8. Back in `app.py:110`, rounded to 2 decimal places and wrapped in a `Prediction`
   response model.

**The model loads once, not per request.** `predictor = Predictor()` sits at module
level (`app.py:27`), so importing `app` loads it. A missing `models/model.pkl` fails
the import immediately rather than on the first request — deliberate, and explained
in the module docstring (`app.py:1-12`).

---

## 4. Trace B — one training run

`uv run main.py`.

1. **`__main__`** (`main.py:200`) currently calls `train_with_mlflow()`
   (`main.py:203`). `main()` sits commented out on the line above (`main.py:202`).
2. **`train_with_mlflow()`** (`main.py:101`) points MLflow at an explicit SQLite path
   and creates the experiment with an explicit artifact location. The reason is in the
   comments (`main.py:110-121`): the project path contains a space and an `&`, and
   MLflow's default URI construction URL-encodes the working directory, producing a
   real folder named `Personal%20Project`.
3. **`run_pipeline()`** (`main.py:50`) — shared by both entry points so the two
   cannot drift apart.
4. `load_config()` reads `config.yml` (`steps/__init__.py`), resolved from the package
   location rather than the working directory.
5. **`Ingestion().load_data()`** (`steps/ingest.py`) reads `data.data_path`, which is
   `data/merged_data.csv` (`config.yml:9`).
6. **`Cleaner(target).clean_data()`** (`steps/clean.py`) runs seven rules in notebook
   02's order: convert dtypes, missing values, low variance, outliers, high
   cardinality, correlated columns, duplicate rows.
7. **`Trainer()`** reads `model.name` (`config.yml:22`), looks it up in
   `MODEL_REGISTRY` (`steps/train.py:39`) and builds the matching pipeline.
8. `feature_target_separator`, then `train_test_split_data` — 80/20
   (`config.yml:14`), target still in dollars.
9. **`train_model()`** (`steps/train.py:198`). `np.log1p(y_train)` is applied at
   `steps/train.py:217`. **This is the only place the log transform is applied.**
10. **`save_model()`** (`steps/train.py:257`) writes the bundle — see section 5.
11. **`Predictor()`** loads that bundle straight back off disk and scores both splits.
    Every metric comes back in dollars because `expm1` runs first.
12. MLflow logs the parameters, four metrics, the model itself using `cloudpickle`
    rather than the default (three of the five models are not scikit-learn and the
    default serializer refuses them), and `config.yml` as an artifact. Then it
    registers the model.

---

## 5. The artefact bundle is the linchpin

`joblib.dump` writes a **dict of six keys**, not a bare model
(`steps/train.py:279-285`):

```
model, model_name, use_log_target, target, feature_order, categorical_features
```

`Predictor.__init__` unpacks all six (`steps/predict.py:31-36`).

**Why this matters more than anything else in the repo:** the model is fitted on
`log1p(charges)`. Anyone who loads the pickle and calls `.predict()` without knowing
that gets **about 9.7 where the answer is about $16,000**. It does not crash. It does
not warn. The `use_log_target` flag travelling inside the artefact is what prevents
it, and `feature_order` plus `categorical_features` are what stop `app.py` drifting
away from how the model was actually fitted.

The CD pipeline guards this explicitly at `cd.yml:117-119`, asserting the live
prediction lands between 1,000 and 200,000, with the comment *"log1p dollars would
come back around 9.8 rather than five figures"*.

---

## 6. Configuration surface

- **One line switches the model**: `config.yml:22`, under a banner comment at
  `config.yml:21`.
- Five models are registered (`steps/train.py:39-45`): `RandomForestRegressor`,
  `LGBMRegressor`, `XGBRegressor`, `CatBoostRegressor`, `LinearRegression`.
- Each carries its own `params` and `tuning_params` block, because the libraries
  disagree on names — CatBoost says `random_seed`, `depth` and `iterations` where the
  others say `random_state`, `max_depth` and `n_estimators` (`config.yml:37-45`).
- `model.tune: false` (`config.yml:27`) fits once. `true` runs GridSearchCV, which the
  comment on the same line records as roughly 44 times slower.
- **Preprocessing is deliberately not configurable** — see section 10.

---

## 7. Tests come in two kinds

`tests/conftest.py:1-17` states the split. Mechanically it is two skip markers:

- `requires_model` (`tests/conftest.py:33-36`) skips when `models/model.pkl` is
  absent, with the reason *"run `uv run dvc pull`"*.
- `requires_data` (`tests/conftest.py:37-40`) does the same for
  `data/merged_data.csv`.

Self-contained tests build their own fixtures. `tidy_frame` is twelve hand-written
rows (`tests/conftest.py:46-67`). `fake_training_data` is fifty generated rows with a
real signal baked in — older, heavier and smoking all cost more
(`tests/conftest.py:70-106`). `fake_bundle` trains a five-tree forest and saves a
genuine six-key bundle to `tmp_path` (`tests/conftest.py:109-145`), which is how the
prediction tests exercise the log-transform logic with no `dvc pull`.

`tests/test_api.py` carries `pytestmark = requires_model` at module level, so the
whole file skips on a fresh clone — because `app.py` builds its `Predictor` at import
time.

A `slow` marker exists and is excluded by default (`pyproject.toml`,
`addopts = "-m 'not slow'"`). `uv run pytest -m slow` runs the full pipeline against
the real data.

---

## 8. Docker

Two stages (`Dockerfile:14` and `Dockerfile:48`). Four decisions that are not obvious:

1. `uv sync --frozen --no-dev` drops **217 of 257 packages** — MLflow, DVC, SHAP,
   seaborn, sweetviz and JupyterLab (`Dockerfile:38-40`).
2. `uv pip uninstall nvidia-nccl-cu13` reclaims **288 MB**. XGBoost's Linux wheel
   declares it, but NCCL only does multi-GPU communication and this container has no
   GPU. It has to happen in the same `RUN` or the files stay in the layer below and
   nothing is reclaimed (`Dockerfile:41-46`).
3. `apt-get install libgomp1` (`Dockerfile:52-55`). All three boosting libraries link
   against OpenMP. `python:3.12-slim` does not ship it, and the failure is a bare
   `libgomp.so.1: cannot open shared object file` that explains nothing.
4. **`dvc pull` never runs inside the build** (`Dockerfile:7-10`). It would bake the
   Azure connection string into an image layer. `COPY models/ ./models/`
   (`Dockerfile:64`) means the artefact must already exist on disk before
   `docker build` is run.

---

## 9. DVC, CI and CD

**DVC** (`.dvc/config`): remote `azureremote`, `url = azure://dvcstore`,
`account_name = insurancedvc`. **No credential is stored in the repo.** `data/` is
175,490 bytes across 4 files (`data.dvc`); `models/` is 5,420,143 bytes across 2
(`models.dvc`). Both directories are git-ignored (`.gitignore`, `/data` and
`/models`).

**CI** (`ci.yml`) needs no secrets, by design (`ci.yml:3-6`). It triggers on a push to
`master` (`ci.yml:14`) and on any pull request (`ci.yml:15`).

> **Consequence of the new `dev` branch:** a direct push to `dev` runs **no workflow
> at all**. CI fires only on a pull request or a push to `master`. CD is `master`-only
> (`cd.yml:17`), which is correct — but on `dev` the safety net is the pull request,
> not the push.

**CD** (`cd.yml`) stores zero secrets. `azure/login@v3` exchanges a GitHub-signed OIDC
token, and the three `vars` are identifiers rather than passwords (`cd.yml:3-6`). DVC
needs no credential either: with only `account_name` set it falls back to
`DefaultAzureCredential`, which picks up the `az login` that just happened
(`cd.yml:8-11`).

Two gates block a bad model. `uv run pytest -m slow` recomputes RMSE against the real
data (`cd.yml:69-70`), and the deployed app must return a real dollar figure before
the run goes green (`cd.yml:95-120`).

---

## 10. Three things that contradict a typical MLOps tutorial

**1. Preprocessing is deliberately not in the config.**
The standard move is to put every knob in the YAML. Here `config.yml:41-44` says
outright that preprocessing is derived from the model name instead, and
`steps/train.py:1-20` gives the reason: the three boosting libraries read category
columns natively, the forest needs one-hot encoding, and the linear model needs
one-hot plus scaling plus term expansion. Exposing that as configuration would mean
hand-maintaining a rule you cannot get right without reading `train.py` anyway.

**2. Outliers are found and deliberately kept.**
`steps/clean.py` `remove_outliers` logs the IQR-flagged rows and removes none.
Notebook 02 established that they are high-cost smokers — roughly 10% of the data and
about half of all smokers. They are not measurement errors; they are the expensive
customers the model exists to price. The tutorial default of dropping them trains a
model that has never seen the cases that matter most.

**3. The saved artefact is a bundle, not a model.**
Most tutorials call `joblib.dump(model)`. This one saves six keys (section 5), because
a bare pickle of a log-fitted model is a silent thousand-fold error waiting for the
next person who loads it.

**Bonus, same spirit:** the test suite *skips* rather than *fails* when the DVC
artefacts are absent (`tests/conftest.py:33-40`). Most tutorial repositories ship a
suite that simply cannot run on a fresh clone.

---

## 11. Surprises, inconsistencies, and things worth a second look

1. **The training entry point is toggled by commenting out code**
   (`main.py:200-203`). It works, and the README documents it, but it means
   `uv run main.py` always goes through MLflow. A command-line flag would be the
   conventional answer. Not broken — noted because a tutorial has to explain it.
2. **Two model pickles.** `models/model.pkl` is 2,710,118 bytes;
   `models/random_forest_insurance_model.pkl` is 2,710,025 bytes. Only the first is
   ever loaded (`steps/predict.py:29`). Nothing in the codebase references the second.
   Inference, not citation: it looks like a leftover from notebook 03 section 4.16.
3. **Four CSVs in `data/`, one of them read.** The pipeline reads only
   `merged_data.csv` (`config.yml:9`). `cleaned_data.csv` is written by notebook 02 and
   is *not* the pipeline's input, because `steps/clean.py` does the cleaning itself.
   Intentional (`steps/ingest.py` class docstring) but it reads as a trap.
4. **`samples.json`** is described at `README.md:126` and `README.md:544` but is
   referenced by no code and no test.
5. **A fresh clone cannot run the API, the full test suite, or a Docker build.** All
   three need `models/model.pkl`, which is DVC-tracked, git-ignored, and sitting behind
   a private Azure remote. The README's fallback (`README.md:62-69`) requires a Kaggle
   account, JupyterLab, and a full training run first.

---

## 12. Notebook structure

| Notebook | Cells (md/code) | Covers |
|---|---|---|
| `01_load_data.ipynb` | 17 (13/4) | Business framing, join strategy, writes `merged_data.csv` |
| `02_eda_and_preprocessing.ipynb` | 45 (24/21) | EDA 2.2.1 to 2.2.9, then the six cleaning rules 3.2.1 to 3.2.6 |
| `03_model_training.ipynb` | 113 (58/55) | Target-transform decision 4.3, all five models 4.4 to 4.13, comparison 4.14, SHAP 4.15 |
| `04_monitoring.ipynb` | 20 (12/8) | Evidently: healthy baseline 5.5 against the alarm 5.6 |

Notebook 02's cleaning subsections map one-to-one onto `steps/clean.py` methods, in
the same order — stated at `steps/clean.py:1-10`.

Notebook 03 section 4.3 is the origin of `use_log_target` (`config.yml:16-19` cites
"notebook 03 section 4.3"), and section 4.12.2 is the origin of the linear model's
`degree: 2` (`config.yml:105-107`).
