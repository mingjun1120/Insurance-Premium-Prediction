# Switch models

You already have `data/merged_data.csv` on disk and `uv sync` done.

## 1. Change the one line

`config.yml:22`, under the banner that marks it:

```yaml
# ============ CHANGE THIS ONE LINE TO SWITCH MODELS ============
model:
  name: LGBMRegressor
```

Five names are valid. They come from `MODEL_REGISTRY` at `steps/train.py:39-45`:

- `RandomForestRegressor`
- `LGBMRegressor`
- `XGBRegressor`
- `CatBoostRegressor`
- `LinearRegression`

Anything else stops the run before it loads data:

```
ValueError: Unknown model 'LightGBM'. config.yml must name one of:
RandomForestRegressor, LGBMRegressor, XGBRegressor, CatBoostRegressor, LinearRegression
```

Leave the `models:` blocks further down alone. Each model keeps its own `params`
and the trainer reads only the block matching the name above. Preprocessing is
not a setting — the trainer derives it from the name, and the reasoning is in
[preprocessing-is-not-configurable.md](../explanation/preprocessing-is-not-configurable.md).

## 2. Re-run training

```bash
uv run main.py
```

About 24 seconds end to end for `LGBMRegressor` with `tune: false`. The fit
itself is a fraction of a second; roughly ten go on MLflow exporting the
environment and registering the model, and the rest on imports.

The lines worth reading:

```
- Fitting LGBMRegressor with the parameters from config.yml.
- Saved model.pkl (83 KB)
- Loaded model.pkl (LGBMRegressor, log target: True)

============= Model Evaluation Results (Test Set) ==============
Model          : LGBMRegressor
RMSE           : $4,351
MAE            : $2,027
R2 Score       : 0.8970
MAPE           : 0.1628
=================================================================
```

`models/model.pkl` is overwritten in place. The size shifts a long way — the
forest's 300 trees are 2.7 MB, LightGBM's are 83 KB — which is the quickest way
to confirm from the outside that the swap took.

Both splits are printed. The test block is the one to compare against
[reference/results.md](../reference/results.md).

## 3. Confirm what is actually loaded

Anything that reads the artefact now reports the new model, including a running
API:

```bash
curl http://127.0.0.1:8000/
```

```json
{"status":"ok","model":"LGBMRegressor","log_target":true}
```

A server started before the retrain is still holding the old model in memory.
`app.py:27` loads once at import. Restart it.

## The golden-number test will now fail

Expected, and not a bug:

```
FAILED tests/test_predict.py::test_golden_rmse_has_not_moved - assert 4350.84... == 4193 ± 1
```

Those four numbers are pinned to the Random Forest. Either put
`RandomForestRegressor` back, or update the assertions using the procedure in
[run-the-tests.md](run-the-tests.md) — same commit, with the reason in the
message.

## Optional: retune instead of reusing the tuned parameters

```yaml
model:
  tune: true
```

`GridSearchCV` over the `tuning_params` block, roughly 44x the runtime of a
single fit. The parameters already in `config.yml` are the tuned winners from
notebook 03, so this earns its cost only when the data has changed. Every key is
listed in [reference/configuration.md](../reference/configuration.md).

## Done when

The `Model` line in the test-set block names the model you chose, and
`GET /` on a freshly started server agrees with it.
