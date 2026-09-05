# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Everything runs through `uv`. Python 3.12.

```bash
uv sync                                  # dev + serving deps
uv run dvc pull                          # restore data/ and models/ (gitignored, DVC-tracked)
uv run python dataset.py                 # only if you cannot dvc pull: builds data/merged_data.csv

uv run ruff check .                      # lint, exactly what CI runs
uv run pytest                            # fast suite; `slow` excluded by addopts
uv run pytest -m slow                    # the golden-metric test, needs dvc pull
uv run pytest tests/test_clean.py::TestRemoveOutliers::test_nothing_is_removed  # one test
uv run pytest -rs                        # -rs prints each skip reason (-v alone does not)

uv run python main.py                    # full training run -> models/model.pkl + MLflow
uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db
uv run uvicorn app:app --reload          # API on http://127.0.0.1:8000/docs

docker build -t insurance-premium .      # needs models/model.pkl on disk first
docker run --rm -p 8000:8000 insurance-premium
```

## Architecture

**`config.yml` is the control panel.** Switching models is a one-line edit:

```yaml
model:
  name: RandomForestRegressor   # or LGBMRegressor / XGBRegressor / CatBoostRegressor / LinearRegression
  tune: false                   # true runs GridSearchCV instead — roughly 44x slower
```

Nothing reads the environment (no `os.environ` or `getenv` anywhere), so a run is
reproducible from this file alone — which is why `train_with_mlflow()` logs a copy of it
as an artifact.

**The one exception:** the six cleaning thresholds at `steps/clean.py:18-23`
(`CORRELATION_THRESHOLD`, `CATEGORY_COVERAGE_TO_KEEP`, `CARDINALITY_THRESHOLD`, ...) are
module constants, *not* config. Anyone tuning cleaning behaviour will search `config.yml`
first and find nothing.

**Pipeline flow** — `main.py` calls `run_pipeline()`, which chains four modules in `steps/`:

```
Ingestion.load_data()     data/merged_data.csv (raw; dataset.py writes it)
Cleaner.clean_data()      7 rules, always in notebook 02's order
Trainer.train_model()     build pipeline -> fit -> save_model()
Predictor.evaluate_model()  scores both splits, always in dollars
```

**`dataset.py` sits before all of that, and outside `steps/` on purpose.** It reads
`data.source_path` (the raw Kaggle download) and writes `data.data_path`. That is the
data-engineering boundary: in a company everything upstream of it would belong to another
team, and the model side would start with a dataset already assembled. Nothing runs it
automatically — CI and CD both use `dvc pull`, so the golden test scores the exact
versioned data. It exists for the person who has no access to that remote.

`main.py` has two entry points doing the same work; `train_with_mlflow()` is active and
`main()` is commented out at the bottom. Both call the shared `run_pipeline()` and
`print_results()` so they cannot drift apart.

**Preprocessing is derived, not configured.** `steps/train.py:MODEL_REGISTRY` maps each
model name to `(class, preprocessing)`: the three boosting libraries read `category`
columns natively, `RandomForestRegressor` needs one-hot, `LinearRegression` needs one-hot
plus scaling plus `PolynomialFeatures`. Do not move this into `config.yml` — the rule is
unguessable without reading `steps/train.py`. The final pipeline step is always named
`model`, which is what lets every `tuning_params` grid use the `model__` prefix.

**The artefact is a bundle, not a bare model.** `Trainer.save_model()` writes a dict:
`model`, `model_name`, `use_log_target`, `target`, `feature_order`, `categorical_features`.
Models fit on `log1p(charges)`, so a consumer that loads the pickle without reading
`use_log_target` is wrong by a factor of thousands (~9.7 instead of ~$16,000).
`steps/predict.py` owns the inverse transform, the column ordering and the `category`
dtype — `app.py` deliberately does none of that, so the API cannot disagree with what
`main.py` reports. Keep new prediction logic in `Predictor`.

**`PROJECT_ROOT`** is resolved from `steps/__init__.py`'s own location, so every path in
`config.yml` is relative to the project root regardless of the working directory. Use
`steps.resolve()` for new config paths.

## Tests

Two kinds, and the split is what keeps CI credential-free:

- **Self-contained** — build their own data (`tidy_frame`, `fake_training_data`,
  `fake_bundle` in `tests/conftest.py`). Run anywhere.
- **Artefact** — marked `@requires_model` / `@requires_data`, and *skip* (never fail) when
  `models/model.pkl` or `data/merged_data.csv` are absent.

`tests/test_predict.py::test_golden_rmse_has_not_moved` asserts RMSE 4193 / MAE 1974 /
R² 0.9043 / MAPE 0.1655. **The same four numbers appear in two more places: the README
table and the one in `docs/model-development.md`.** Any retrain that moves them must
update all three, in a commit that says why.

## DVC and secrets

`data/` and `models/` are gitignored and DVC-tracked to Azure Blob (`data.dvc`,
`models.dvc`). `.dvc/config` holds only `account_name`; the connection string lives in
`.dvc/config.local` (gitignored) and is set with `dvc remote modify --local`. Never put it
in a committed file, and never add `dvc pull` to the Dockerfile — it would bake the string
into an image layer.

## Branches

Work happens on `dev`. **A push to `master` triggers `cd.yml`, which deploys to live
Azure Container Apps.** Merge through a PR; do not push straight to `master`. `master` is
also the PR base.

## CI/CD

`ci.yml` and `cd.yml` both fire on push to `master` with **no dependency between them** —
they run in parallel. CD does not rely on CI because it re-gates itself: `pytest`, then
`pytest -m slow`, and only then `docker build`. A model that stops scoring what the README
claims blocks the deploy.

CD uses Azure OIDC (`azure/login` with `vars.AZURE_*`) — there are no secrets in the
workflow. DVC in CI falls back to `DefaultAzureCredential`, picking up that same login.

## Docker

Two stages so `uv` (58 MB) never ships. `uv sync --frozen --no-dev` drops 217 of 257
packages; the same `RUN` uninstalls `nvidia-nccl-cu13` (288 MB, XGBoost pulls it in but
there is no GPU) — splitting it into a second `RUN` reclaims nothing. Runtime installs
`libgomp1`, without which LightGBM/XGBoost/CatBoost fail to import.

The three boosting libraries stay in the main `dependencies` on purpose: any of the five
models can end up in `model.pkl`, and unpickling needs the library it came from.

`.dockerignore` excludes `data/`, `main.py`, `dataset.py`, `notebooks/`, `mlflow/`, `.venv`
and `*.dvc`,
which is what keeps the build context at a few MB. If a change makes the image need a new
file, check `.dockerignore` before wondering why it is missing at runtime.

## Conventions

- Google-style docstrings with `Args` / `Returns` / `Raises` / `Examples` throughout.
  Comments explain *why*, often at length. Match that density.
- Ruff: `line-length = 100`, rules `E,F,I,W,UP,B`, `notebooks/` excluded. `known-first-party
  = ["steps", "tests"]` and `known-third-party = ["mlflow"]` are set because the local
  `mlflow/` folder otherwise fools isort.
- MLflow paths are set explicitly in `main.py` (`as_posix()` + plain `file:` prefix, not
  `Path.as_uri()`) because this project's absolute path contains spaces and an `&`, which
  MLflow would URL-encode into real folders named `Personal%20Project`.
- Docs are five ordered guides plus a lookup page, indexed from the README table. Each page
  carries a path bar at the top. `docs/reference.md` is not part of the reading order.
