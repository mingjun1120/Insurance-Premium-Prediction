# The artefact bundle

`models/model.pkl` is a Python dictionary of six keys written by `joblib.dump`,
not a bare model object.

| | |
| --- | --- |
| Path | `models/model.pkl` (from `model.store_path`, `config.yml:29`) |
| Size | 2,710,118 bytes for the shipped `RandomForestRegressor` |
| Written by | `Trainer.save_model`, `steps/train.py:257` |
| The `joblib.dump` call | `steps/train.py:279-286` |
| Read by | `Predictor.load_model` / `Predictor.__init__`, `steps/predict.py:27-36` |
| Tracked by | DVC, not git — see [../explanation/data-outside-git.md](../explanation/data-outside-git.md) |

`models/` holds two files (`models.dvc`, 5,420,143 bytes across 2). Only
`model.pkl` is ever loaded; the path is built by name at `steps/predict.py:29`.

## The six keys

Values shown are those in the artefact currently on disk.

| Key | Type | Value in the shipped artefact | Written | Read |
| --- | --- | --- | --- | --- |
| `model` | `sklearn.pipeline.Pipeline` | steps `['prepare', 'model']`; final estimator `RandomForestRegressor` | `train.py:280` | `predict.py:32` |
| `model_name` | `str` | `'RandomForestRegressor'` | `train.py:281` | `predict.py:33` |
| `use_log_target` | `bool` | `True` | `train.py:282` | `predict.py:34` |
| `target` | `str` | `'charges'` | `train.py:283` | — |
| `feature_order` | `list[str]` | `['age', 'sex', 'bmi', 'children', 'smoker', 'region']` | `train.py:284` | `predict.py:35` |
| `categorical_features` | `list[str]` | `['sex', 'smoker', 'region']` | `train.py:285` | `predict.py:36` |

`target` is written but not read back. `Predictor.__init__` unpacks the other
five into attributes and does not assign `target`;
`tests/test_predict.py:41` checks it only if the attribute exists.

## What reads each key at runtime

| Key | Used for |
| --- | --- |
| `model` | `Predictor.predict` calls `self.model.predict(X)` (`predict.py:71`) |
| `model_name` | Reported by `GET /` and in the `model` field of every prediction; logged at `predict.py:57` |
| `use_log_target` | Gates `np.expm1` at `predict.py:72` |
| `feature_order` | Column order for the DataFrame built in `predict_records` (`predict.py:98`) |
| `categorical_features` | Columns cast to the pandas `category` dtype in `predict_records` (`predict.py:99-100`) |

## Shape of the `model` value

The pipeline's steps depend on which model was trained. The final step is always
named `model`.

| `model.name` | Pipeline steps |
| --- | --- |
| `RandomForestRegressor` | `prepare`, `model` |
| `LGBMRegressor`, `XGBRegressor`, `CatBoostRegressor` | `model` |
| `LinearRegression` | `prepare`, `expand`, `rescale`, `model` |

Built by `Trainer.create_pipeline` (`steps/train.py:79`). Which preprocessing
each model gets, and why it is not configurable, is
[../explanation/preprocessing-is-not-configurable.md](../explanation/preprocessing-is-not-configurable.md).

## Reading the bundle directly

```python
import joblib
bundle = joblib.load("models/model.pkl")
bundle["use_log_target"]   # True
```

A model fitted with `use_log_target: true` predicts in log space. Calling
`bundle["model"].predict(...)` returns log dollars; `np.expm1` converts them
back. What that costs when it is missed is
[../explanation/the-bundle.md](../explanation/the-bundle.md).

## Fixtures

`tests/conftest.py:109-145` builds `fake_bundle`: a five-tree
`RandomForestRegressor` fitted on generated rows and saved with the same six
keys into a temporary directory. It is a genuine bundle, so the prediction tests
exercise the same unpacking path without needing the real artefact.
