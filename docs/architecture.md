# Architecture

`Guide 2 of 5` · [Getting started](getting-started.md) → **Architecture** →
[Model development](model-development.md) → [Operations](operations.md) →
[Deployment](deployment.md)

This page explains how data becomes a prediction. The current code is the
source of truth; the project was inspired by
[`prsdm/mlops-project`](https://github.com/prsdm/mlops-project) and an earlier
loan-risk project, but it has its own training, serving, tracking, and delivery
decisions.

## System map

![Insurance premium prediction system map](assets/architecture.png)

The large map is also available as an
[interactive HTML view](assets/architecture.html). Download or open it locally
to switch themes, search nodes, and inspect the linked source locations.

There are three paths to remember:

- **Train:** CSV → cleaning → fitted model bundle → MLflow record.
- **Serve:** JSON → validation → shared predictor → premium in dollars.
- **Ship:** GitHub Actions → tests → Docker image → Azure Container Apps.

## Trace A: one training run

![Training flow](diagrams/training-flow.svg)

`main.py` owns the order. The individual steps do not call each other.

| Order | Code | Job |
| ---: | --- | --- |
| 1 | [`run_pipeline()`](../main.py#L50) | Orchestrate one complete run. |
| 2 | [`Ingestion.load_data()`](../steps/ingest.py#L23) | Read the configured CSV. |
| 3 | [`Cleaner.clean_data()`](../steps/clean.py#L43) | Apply the seven cleaning rules. |
| 4 | [`Trainer.train_model()`](../steps/train.py#L198) | Fit once or run grid search. |
| 5 | [`Trainer.save_model()`](../steps/train.py#L257) | Save the model and its context together. |
| 6 | [`Predictor.evaluate_model()`](../steps/predict.py#L104) | Report RMSE, MAE, R², and MAPE in dollars. |
| 7 | [`train_with_mlflow()`](../main.py#L101) | Log parameters, metrics, model, and config. |

Two entry points share `run_pipeline()`:

- `main()` prints the result only.
- `train_with_mlflow()` prints and records the same result.

The committed `__main__` block selects `train_with_mlflow()`.

## Trace B: one prediction request

![Prediction request sequence](diagrams/prediction-request.svg)

Important details:

1. [`Predictor()`](../app.py#L27) is created when `app.py` is imported. A
   missing bundle stops startup instead of failing on the first real request.
2. [`Person`](../app.py#L30) checks all six fields before project code runs.
3. [`predict_records()`](../steps/predict.py#L74) restores the saved column
   order and categorical data types.
4. [`predict()`](../steps/predict.py#L61) applies `expm1` when the model was
   trained on `log1p(charges)`.
5. [`POST /predict`](../app.py#L90) rounds the final dollar value and returns
   the model name stored in the bundle.

This shared predictor is a safety feature. Training evaluation and the API
cannot quietly use different post-processing.

## The model file is a bundle

`models/model.pkl` is not only a fitted estimator. It stores:

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

The model name, transform flag, and input shape travel with the model. This
reduces the chance that serving code interprets a correct prediction in the
wrong way.

## What each storage tool owns

| Tool | Stores | Why it exists |
| --- | --- | --- |
| Git | Code, config, tests, DVC pointers | Reviewable project history. |
| DVC + Azure Blob | `data/` and `models/` | Large-file versions without large Git commits. |
| MLflow + SQLite | Runs, parameters, metrics, model copy, config copy | Experiment comparison and reproducibility. |
| Azure Container Registry | Images tagged by commit SHA and `latest` | Trace a deployed image to its code. |
| Azure Container Apps | The running FastAPI container | Public HTTPS serving. |

DVC and MLflow solve different problems. DVC answers “which data and bundle go
with this Git commit?” MLflow answers “what happened during this training run?”

## What is automated today

| Area | Current state |
| --- | --- |
| Code quality | Ruff and fast tests run in CI. |
| Model quality gate | CD runs the slow real-data golden test before building. |
| Packaging | A multi-stage Dockerfile builds the serving image. |
| Deployment | A push to `master` updates Azure Container Apps. |
| Drift analysis | A notebook creates reports from simulated current data. |
| Retraining | Manual. |
| Rollback | Possible with old Container Apps revisions, but not automated. |
| API access control | Not implemented; suitable for a portfolio demo only. |

Next: [Model development](model-development.md) - the notebooks, cleaning rules,
and model comparison behind these two traces.
