# Test suite

`tests/`, run with pytest. Configuration is in `[tool.pytest.ini_options]`
(`pyproject.toml:52-60`).

| Setting | Value | Line |
| --- | --- | --- |
| `testpaths` | `["tests"]` | 53 |
| `addopts` | `-m 'not slow'` | 57 |
| `markers` | `slow: runs the full pipeline on the real dataset (needs \`dvc pull\`)` | 58-60 |

## The counts

`addopts` applies to every invocation, so a bare `uv run pytest` never runs the
whole collection.

| | |
| --- | ---: |
| Collected | 109 |
| Deselected by `addopts` | 1 |
| Run by `uv run pytest` | 108 |
| Of those 108, skipped without the DVC artefacts | 28 |

Two outcomes, depending on whether `models/model.pkl` and
`data/merged_data.csv` are on disk:

```
108 passed, 1 deselected                 # artefacts present
80 passed, 28 skipped, 1 deselected      # fresh clone
```

`uv run pytest -m slow` inverts the filter: 1 collected, 108 deselected.

The deselected test is `tests/test_predict.py::test_golden_rmse_has_not_moved`.
It is the only test carrying the `slow` marker.

## The files

Seven files. `tests/__init__.py` is empty and exists so `from tests.conftest
import ...` resolves.

| File | Lines | Tests | Guards |
| --- | ---: | ---: | --- |
| `conftest.py` | 145 | — | Fixtures and the two skip markers |
| `test_api.py` | 139 | 26 | `app.py` — both endpoints, the six field constraints, the generated docs |
| `test_clean.py` | 217 | 22 | `steps/clean.py` — one test class per cleaning rule |
| `test_config.py` | 100 | 26 | `config.yml` still holds every key the code indexes by name |
| `test_predict.py` | 176 | 13 | `steps/predict.py` — that answers come back in dollars |
| `test_train.py` | 180 | 22 | `steps/train.py` — pipeline shape per model, plus one real fit |
| `__init__.py` | 0 | — | — |

### `test_api.py` — 26

| Class | Tests |
| --- | ---: |
| `TestHealth` | 2 |
| `TestPredict` | 4 |
| `TestValidation` | 18 |
| `TestDocs` | 2 |

Uses FastAPI's `TestClient`, which calls the app in-process — no server, no port.
It needs `httpx`, which arrives with fastapi.

`pytestmark = requires_model` at `test_api.py:16` applies the marker to the whole
module, because `app.py` builds its `Predictor` at import time.

### `test_clean.py` — 22

| Class | Tests | Method under test |
| --- | ---: | --- |
| `TestConvertDataTypes` | 2 | `convert_data_types` (`clean.py:73`) |
| `TestHandleMissingValues` | 5 | `handle_missing_values` (`clean.py:94`) |
| `TestRemoveLowVarianceFeatures` | 4 | `remove_low_variance_constant_features` (`clean.py:183`) |
| `TestRemoveOutliers` | 1 | `remove_outliers` (`clean.py:230`) |
| `TestHighCardinality` | 3 | `handle_high_cardinality_features` (`clean.py:268`) |
| `TestRemoveHighlyCorrelated` | 3 | `remove_highly_correlated_features` (`clean.py:331`) |
| `TestRemoveDuplicateRows` | 2 | `remove_duplicate_rows` (`clean.py:380`) |
| `TestCleanDataEndToEnd` | 2 | `clean_data` (`clean.py:43`) |

Every test starts from `tidy_frame` and plants exactly one problem.

### `test_config.py` — 26

Thirteen test functions. The other thirteen items come from parametrisation over
section and key names.

| Test | Checks |
| --- | --- |
| `test_config_file_exists` | `CONFIG_PATH` exists |
| `test_config_is_valid_yaml` | parses |
| `test_top_level_sections_are_present` | 5 sections |
| `test_data_keys` | 2 keys |
| `test_train_keys` | 3 keys |
| `test_model_keys` | 3 keys |
| `test_mlflow_keys` | 5 keys |
| `test_active_model_is_one_the_code_can_build` | `config["model"]["name"] in MODEL_REGISTRY` |
| `test_every_registry_model_has_a_config_block` | a block with `params` and `tuning_params` per registry entry |
| `test_tuning_grids_use_the_pipeline_prefix` | every grid key is prefixed with a pipeline step name |
| `test_use_log_target_is_a_boolean` | type |
| `test_tune_is_a_boolean` | type |
| `test_resolve_returns_absolute_paths` | `resolve()` |

`config.yml` is not imported by anything — it is read at runtime by key — so a
typo surfaces as a `KeyError` deep in a training run without these
(`test_config.py:1-7`).

### `test_predict.py` — 13

| Class or test | Tests | Marker |
| --- | ---: | --- |
| `TestLoadModel` | 2 | — |
| `TestPredictionsAreInDollars` | 3 | — |
| `TestPredictRecords` | 5 | — |
| `TestTheRealArtefact` | 2 | `requires_model` (`test_predict.py:129`) |
| `test_golden_rmse_has_not_moved` | 1 | `requires_model`, `requires_data`, `slow` (`test_predict.py:146-148`) |

The first ten build their own model through `fake_bundle`, so they run on a fresh
clone.

### `test_train.py` — 22

| Class | Tests |
| --- | ---: |
| `TestPipelineShape` | 15 |
| `TestEncoder` | 4 |
| `TestFeatureTargetSeparator` | 1 |
| `TestRealFit` | 2 |

`TestPipelineShape` holds five methods, three of them parametrised over model
name: two across all five models and one across the three native-categorical
models, which is 15 items. `TestEncoder` and `TestRealFit` both use
`fake_training_data`.

---

## The markers

### `requires_model` and `requires_data`

Both are `pytest.mark.skipif`, defined at `tests/conftest.py:33-40` against paths
built from `PROJECT_ROOT` at `conftest.py:30-31`.

| Marker | Condition | Reason string |
| --- | --- | --- |
| `requires_model` | `models/model.pkl` absent | `models/model.pkl is DVC-tracked and absent here - run \`uv run dvc pull\`` |
| `requires_data` | `data/merged_data.csv` absent | `data/ is DVC-tracked and absent here - run \`uv run dvc pull\`` |

They are `skipif` conditions, not registered marker names, so they cannot be
selected with `-m`.

The 28 skips on a fresh clone are all 26 of `test_api.py` plus the 2 in
`TestTheRealArtefact`. `test_golden_rmse_has_not_moved` carries both markers as
well, but it is deselected by `addopts` before either is evaluated.

### `slow`

Registered at `pyproject.toml:58-60` and excluded by `addopts`. One test carries
it. It runs `Ingestion` → `Cleaner` → `Trainer` against the real data, then
scores `models/model.pkl` on the test split against four fixed values
(`test_predict.py:173-176`). `cd.yml:69-70` runs it before anything is built.

---

## Fixtures

All three are in `conftest.py`. Two module-level constants back them:
`TARGET = "charges"` and `CATEGORICAL = ["sex", "smoker", "region"]`
(`conftest.py:42-43`).

| Fixture | Line | Returns |
| --- | --- | --- |
| `tidy_frame` | 46-67 | `pandas.DataFrame` |
| `fake_training_data` | 70-106 | `tuple[DataFrame, Series]` |
| `fake_bundle` | 109-145 | `pathlib.Path` |

### `tidy_frame`

12 rows, 7 columns — the six features plus `charges`. Hand-written literals, no
randomness. Nothing in it trips any cleaning rule: no gaps, no constant column,
no high-cardinality column, no duplicate row.

| Column | dtype as constructed | Range or values |
| --- | --- | --- |
| `age` | int64 | 19–61 |
| `sex` | object | `female`, `male` — alternating |
| `bmi` | float64 | 21.6–35.4 |
| `children` | int64 | 0–3 |
| `smoker` | object | 3 `yes`, 9 `no` |
| `region` | object | all four, repeated 3x |
| `charges` | float64 | 1,725.6–38,711.0 |

### `fake_training_data`

50 rows, generated with `numpy.random.default_rng(0)`, so it is the same every
run. Charges are built from a stated relationship rather than sampled at random:

```python
charges = (250 * age + 300 * bmi + np.where(smoker == "yes", 22000, 0)
           + rng.normal(0, 1500, n)).clip(1000)
```

`age` is drawn from 18–64, `bmi` uniform on 18–45 rounded to 2 places, `smoker`
30/70, `children` 0–5, `region` uniform over the four. The three categorical
columns are cast to the `category` dtype before the fixture returns
(`conftest.py:103-104`).

### `fake_bundle`

Fits a `RandomForestRegressor(n_estimators=5, random_state=0)` inside a two-step
pipeline — `Trainer._make_encoder(scale_numeric=False)` then the forest — on
`np.log1p(charges)` from `fake_training_data`, and `joblib.dump`s a real six-key
bundle into pytest's `tmp_path`. Returns the directory, not the file.

| Key | Value written |
| --- | --- |
| `model` | the fitted `Pipeline` |
| `model_name` | `"RandomForestRegressor"` |
| `use_log_target` | `True` |
| `target` | `"charges"` |
| `feature_order` | the six feature columns |
| `categorical_features` | `["sex", "smoker", "region"]` |

Because the keys match what `Trainer.save_model` writes
(`steps/train.py:279-285`), the prediction tests exercise the same unpacking path
as the shipped artefact. `tests/test_predict.py:27-34` monkeypatches
`steps.predict.load_config` to point `store_path` at that directory.

---

## Known defect: `tests/test_predict.py:41`

```python
assert predictor.target == TARGET if hasattr(predictor, "target") else True
```

This assertion can never fail.

The conditional expression binds looser than the comparison, so the statement
parses as `assert ((predictor.target == TARGET) if hasattr(...) else True)` —
the whole `IfExp` is the assertion's argument, not just the comparison.

`Predictor.__init__` unpacks five of the bundle's six keys
(`steps/predict.py:32-36`) and never assigns `target`. Its instance attributes
are `artefact`, `categorical_features`, `config`, `feature_order`, `model`,
`model_name`, `model_path`, `use_log_target`. So `hasattr(predictor, "target")`
is `False`, the `else` branch is taken, and the statement reduces to
`assert True`.

The test containing it,
`TestLoadModel::test_bundle_fields_are_read_onto_the_instance`, still checks
`model_name`, `use_log_target` and `categorical_features` on lines 39, 40 and 42.
Only line 41 is inert.

`target` is written to the artefact at `steps/train.py:283` and read by nothing.
See [artefact-bundle.md](artefact-bundle.md).

---

## Related

- Running the suite and updating the golden numbers:
  [../how-to/run-the-tests.md](../how-to/run-the-tests.md)
- Why the suite skips rather than fails:
  [../explanation/the-test-suite.md](../explanation/the-test-suite.md)
- The two workflow steps that run it: [workflows.md](workflows.md)
- The values `test_golden_rmse_has_not_moved` asserts: [results.md](results.md)
