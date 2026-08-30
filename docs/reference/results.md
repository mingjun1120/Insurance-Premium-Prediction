# Results

Test-set performance of the five models in `MODEL_REGISTRY`.

## The split

| | |
| --- | --- |
| Source file | `data/merged_data.csv`, 1,338 rows (`config.yml:9`) |
| After cleaning | 1,337 rows — `remove_duplicate_rows` drops one |
| Split | 80 / 20, `test_size: 0.2` (`config.yml:13`) |
| Seed | `random_state: 42` (`config.yml:14`) |
| Train | 1,069 rows |
| Test | 268 rows |
| Stratification | none — the target is continuous (`steps/train.py:162-178`) |

## The metrics

Computed by `Predictor.evaluate_model` (`steps/predict.py:104`), which calls
`self.predict(X)` first. That method applies `np.expm1` when the artefact says
`use_log_target` is true, so scoring happens in dollars rather than in log
space.

| Metric | Meaning | Units |
| --- | --- | --- |
| RMSE | Root mean squared error. Punishes large misses hardest; the primary metric here. | dollars |
| MAE | Mean absolute error — the typical miss. | dollars |
| R2 | Share of variance explained. | unitless, 0 to 1 |
| MAPE | Mean absolute percentage error — the typical miss as a proportion. | proportion |

`evaluate_model` returns them in that order as a plain tuple.

## Five models, test split

| Model | RMSE | MAE | R2 | MAPE |
| --- | ---: | ---: | ---: | ---: |
| **Random Forest** | **$4,193** | $1,974 | 0.9043 | 0.1655 |
| XGBoost | $4,345 | $2,032 | 0.8972 | 0.1643 |
| LightGBM | $4,351 | $2,027 | 0.8970 | 0.1628 |
| CatBoost | $4,399 | $2,180 | 0.8947 | 0.1772 |
| Linear Regression | $4,942 | $2,577 | 0.8671 | 0.1806 |

Each row is that model fitted with the `params` block named after it in
`config.yml` and `model.tune: false`. Source: notebook 03, section 4.14.

`RandomForestRegressor` is the model named at `config.yml:22` and the one inside
the shipped artefact, so its row is the only one reproducible without retraining.
Recomputed from `models/model.pkl` against the same split:

| Split | Rows | RMSE | MAE | R2 | MAPE |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 1,069 | 4192.76 | 1864.29 | 0.8716 | 0.1513 |
| test | 268 | 4192.93 | 1974.39 | 0.9043 | 0.1655 |

`uv run main.py` prints both splits. The table above this one reports the test
split.

## Where these numbers are checked

The four test-split figures are asserted by `tests/test_predict.py:149`, which
carries the `slow` marker and is excluded from a default `pytest` run:

```python
assert rmse == pytest.approx(4193, abs=1)
assert mae == pytest.approx(1974, abs=1)
assert r2 == pytest.approx(0.9043, abs=0.0001)
assert mape == pytest.approx(0.1655, abs=0.0001)
```

`cd.yml:69-70` runs that test before anything is built or pushed. See
[test-suite.md](test-suite.md) and
[../explanation/deploy-gates.md](../explanation/deploy-gates.md).

## Related

- Why every figure is in dollars rather than log dollars:
  [../explanation/the-log-transform.md](../explanation/the-log-transform.md)
- Changing which model produces these numbers:
  [configuration.md](configuration.md)
