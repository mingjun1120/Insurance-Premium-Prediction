# Configuration

`config.yml`, 128 lines, at the project root. It is the only settings file the
pipeline reads.

Nothing imports it. `load_config()` (`steps/__init__.py:17`) parses it with
`yaml.safe_load` and returns a plain dict, which the code then indexes by key.
The path is `PROJECT_ROOT / "config.yml"` (`steps/__init__.py:14`), resolved from
the package location rather than the working directory, so the file is found the
same way from any folder.

Values below are the ones in the file as committed.

---

## `data`

| Key | Type | Value | Effect | Read at |
| --- | --- | --- | --- | --- |
| `data_path` | string | `data/merged_data.csv` | The CSV `Ingestion.load_data` reads. Relative to the project root, passed through `resolve()`. | `steps/ingest.py:21` |
| `target` | string | `charges` | Column treated as the target: never dropped or imputed by the cleaner, split off by the trainer, written into the artefact. | `main.py:68`, `steps/train.py:54` |

`data_path` points at `merged_data.csv`, not `cleaned_data.csv`. `steps/clean.py`
does its own cleaning, so the pipeline reads the raw join. See
[project-layout.md](project-layout.md).

## `train`

| Key | Type | Value | Effect | Read at |
| --- | --- | --- | --- | --- |
| `test_size` | float | `0.2` | Fraction held out by `train_test_split`. | `steps/train.py:55` |
| `random_state` | integer | `42` | Seed for that split. | `steps/train.py:56` |
| `use_log_target` | boolean | `true` | Fits on `np.log1p(y_train)` and writes the flag into the artefact, which is what makes `Predictor` invert it. | `steps/train.py:57` |

`use_log_target` is applied at `steps/train.py:217` and undone at
`steps/predict.py:72`. Those are the only two lines in `steps/` that touch it.
Asserted to be a boolean by `tests/test_config.py:88`.

## `model`

| Key | Type | Value | Effect | Read at |
| --- | --- | --- | --- | --- |
| `name` | string | `RandomForestRegressor` | Selects the entry in `MODEL_REGISTRY` (`steps/train.py:39-45`), which decides both the estimator class and the preprocessing. An unknown name raises `ValueError` in `Trainer.__init__`. | `steps/train.py:59` |
| `tune` | boolean | `false` | `false` fits once with `params`. `true` runs `GridSearchCV` over `tuning_params`. The comment at `config.yml:26` records tuning as roughly 44x slower. | `steps/train.py:66` |
| `store_path` | string | `models/` | Directory the artefact is written to and read from. `model.pkl` is appended to it in both places. | `steps/train.py:67`, `steps/predict.py:29` |
| `k_fold.n_splits` | integer | `5` | Folds for the tuning search. | `steps/train.py:68` |
| `k_fold.shuffle` | boolean | `true` | Shuffle before splitting folds. | same |
| `k_fold.random_state` | integer | `42` | Seed for that shuffle. | same |

The whole `k_fold` block is passed straight through as `KFold(**self.kfold_params)`
(`steps/train.py:239`) and is read only when `tune` is true.

`name` is the line the banner comment at `config.yml:20-21` points at. The five
accepted values:

```
RandomForestRegressor  LGBMRegressor  XGBRegressor  CatBoostRegressor  LinearRegression
```

`tests/test_config.py:60` asserts the configured name is one of them.

## `models`

One block per registry entry, each with a `params` and a `tuning_params` key.
`Trainer.__init__` reads only the block whose name matches `model.name`
(`steps/train.py:70-72`); the other four are inert.

| Key | Consumed by |
| --- | --- |
| `params` | `model_class(**self.model_params)` (`steps/train.py:105`), or `PolynomialFeatures(include_bias=False, **self.model_params)` for `LinearRegression` (`steps/train.py:98`) |
| `tuning_params` | `param_grid` of the `GridSearchCV` (`steps/train.py:238`) |

`tests/test_config.py:66-68` asserts that every registry model has a block and
that each block has both keys.

### The `model__` prefix

Every key in a `tuning_params` grid is prefixed with the name of the pipeline step
it targets. `create_pipeline` always names the final step `model`
(`steps/train.py:79-115`), so `model__max_depth` reaches the estimator whichever
model is active. `LinearRegression` is the exception: its grid targets the
`expand` step, because plain least squares has no hyperparameters.
`tests/test_config.py:79` checks the prefixes.

### Parameter names differ between libraries

The blocks cannot share keys, because the libraries do not agree on them.

| Concept | Most models | CatBoost |
| --- | --- | --- |
| Seed | `random_state` | `random_seed` |
| Tree depth | `max_depth` | `depth` |
| Number of trees | `n_estimators` | `iterations` |

`min_samples_leaf` exists only on the forest. Recorded at `config.yml:36-39`.

### `RandomForestRegressor` (`config.yml:47-57`)

| `params` | Value |
| --- | --- |
| `random_state` | `42` |
| `n_jobs` | `-1` |
| `n_estimators` | `300` |
| `max_depth` | `8` |
| `min_samples_leaf` | `8` |

| `tuning_params` | Grid |
| --- | --- |
| `model__n_estimators` | `[300, 600]` |
| `model__max_depth` | `[null, 8, 12]` |
| `model__min_samples_leaf` | `[1, 4, 8]` |

### `LGBMRegressor` (`config.yml:59-71`)

| `params` | Value |
| --- | --- |
| `objective` | `regression` |
| `random_state` | `42` |
| `n_jobs` | `-1` |
| `verbose` | `-1` |
| `n_estimators` | `100` |
| `learning_rate` | `0.05` |
| `max_depth` | `3` |

| `tuning_params` | Grid |
| --- | --- |
| `model__n_estimators` | `[100, 300]` |
| `model__learning_rate` | `[0.01, 0.05, 0.1]` |
| `model__max_depth` | `[3, 5, -1]` |

### `XGBRegressor` (`config.yml:73-87`)

| `params` | Value |
| --- | --- |
| `objective` | `reg:squarederror` |
| `random_state` | `42` |
| `n_jobs` | `-1` |
| `enable_categorical` | `true` |
| `tree_method` | `hist` |
| `n_estimators` | `100` |
| `learning_rate` | `0.05` |
| `max_depth` | `3` |

`enable_categorical` and `tree_method: hist` are both required before XGBoost
accepts a `category` column (`config.yml:78`).

| `tuning_params` | Grid |
| --- | --- |
| `model__n_estimators` | `[100, 300]` |
| `model__learning_rate` | `[0.01, 0.05, 0.1]` |
| `model__max_depth` | `[3, 5, 7]` |

### `CatBoostRegressor` (`config.yml:89-102`)

| `params` | Value |
| --- | --- |
| `loss_function` | `RMSE` |
| `random_seed` | `42` |
| `verbose` | `0` |
| `allow_writing_files` | `false` |
| `iterations` | `300` |
| `learning_rate` | `0.05` |
| `depth` | `7` |

`allow_writing_files: false` stops CatBoost creating a `catboost_info/` folder on
every fit (`config.yml:94`).

| `tuning_params` | Grid |
| --- | --- |
| `model__iterations` | `[100, 300]` |
| `model__learning_rate` | `[0.01, 0.05, 0.1]` |
| `model__depth` | `[3, 5, 7]` |

CatBoost also gets one fit-time argument that is not configurable:
`Trainer._fit_kwargs` (`steps/train.py:180`) passes `model__cat_features` with
the `category` columns, because CatBoost refuses them otherwise. LightGBM and
XGBoost detect them on their own.

### `LinearRegression` (`config.yml:104-113`)

These configure `PolynomialFeatures`, not the regressor.

| `params` | Value |
| --- | --- |
| `degree` | `2` |
| `interaction_only` | `false` |

| `tuning_params` | Grid |
| --- | --- |
| `expand__degree` | `[1, 2]` |
| `expand__interaction_only` | `[true, false]` |

`degree: 2` comes from notebook 03 section 4.12.2 (`config.yml:105-107`).

## `mlflow`

Read only by `train_with_mlflow()`. `main()` ignores the whole section.

| Key | Type | Value | Effect | Read at |
| --- | --- | --- | --- | --- |
| `experiment_name` | string | `Insurance Premium Prediction` | Experiment created or selected. | `main.py:134` |
| `registered_model_name` | string | `insurance_premium_model` | Name under which the run registers the model. | `main.py:192` |
| `developer` | string | `lim_ming_jun` | Value of the `Model developer` run tag. | `main.py:159` |
| `tracking_db` | string | `mlflow/mlflow.db` | SQLite file behind the tracking URI. Parent directory is created if absent. | `main.py:126` |
| `artifact_location` | string | `mlflow/mlruns` | Artifact root, passed to `create_experiment`. Fixed at experiment creation and not changeable afterwards. | `main.py:136` |

Both paths are set explicitly rather than left to MLflow's defaults. MLflow builds
its default URI by URL-encoding the working directory, and this project's path
contains a space and an `&`, which produces real folders named `Personal%20Project`
(`config.yml:120-126`, `main.py:110-121`). `main.py` builds the URIs with
`as_posix()` and a plain `file:` prefix rather than `Path.as_uri()`, which would
percent-encode again.

---

## What is not in this file

Preprocessing. It is derived from `model.name` inside `Trainer.create_pipeline`
rather than configured — see
[../explanation/preprocessing-is-not-configurable.md](../explanation/preprocessing-is-not-configurable.md).

---

## Dependency pins that are constraints

Most version specifiers in `pyproject.toml` are floors. Three upper bounds are
not preferences; something else requires them.

| Pin | Line | Required by |
| --- | --- | --- |
| `pandas>=2.3.3,<3` | `pyproject.toml:21` | mlflow 3.15.1 declares `pandas<3` |
| `plotly>=5.24,<6` | `pyproject.toml:44` | evidently 0.7.21 declares `plotly<6,>=5.10.0`, as does every 0.7.x release |
| `ipykernel>=6.29.5,<7` | `pyproject.toml:37` | ipykernel 7 hangs on kernel restart in VS Code ([vscode-jupyter#17410](https://github.com/microsoft/vscode-jupyter/issues/17410)) |

The first two are checked by reading the installed distributions' metadata:

```bash
uv run python -c "from importlib.metadata import requires; print([r for r in requires('mlflow') if 'pandas' in r])"
```

The notebooks use only `px.bar`/`box`/`histogram`/`scatter`,
`go.Figure`/`Heatmap`/`Scatter` and `pio.renderers`, all unchanged since plotly 4,
so the cap costs nothing (`pyproject.toml:41-43`).

`ruff` is pinned in `[tool.ruff]` rather than left to defaults, so a ruff upgrade
cannot turn CI red on untouched code: `line-length = 100`, `select = ["E", "F",
"I", "W", "UP", "B"]`, `extend-exclude = ["notebooks"]`
(`pyproject.toml:62-78`). `known-third-party = ["mlflow"]` is stated outright
because the local `mlflow/` folder makes ruff sort `import mlflow` as
first-party.

## Related

- What the configured model writes into the artefact:
  [artefact-bundle.md](artefact-bundle.md)
- Test-suite settings (`testpaths`, `addopts`, `markers`):
  [test-suite.md](test-suite.md)
- Changing `model.name`: [../how-to/switch-models.md](../how-to/switch-models.md)
