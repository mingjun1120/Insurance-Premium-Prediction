# Getting started

`Guide 1 of 5` · **Getting started** → [Architecture](architecture.md) →
[Model development](model-development.md) → [Operations](operations.md) →
[Deployment](deployment.md)

Use this page when you want one working prediction with the existing repository.
You do not need to read the notebooks first.

![Quick-start path](diagrams/quick-start.svg)

## What you need

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Git
- Azure access for the DVC remote, or your own copy of the raw dataset

Run every command from the project root.

## 1. Install the project

```bash
uv sync
```

This creates `.venv/` and installs both serving and development tools. You do
not need to activate the environment; `uv run` uses it automatically.

## 2. Get the data and saved model

The large files are stored with DVC, not Git. A clone contains only
`data.dvc` and `models.dvc` pointers.

```bash
uv run dvc pull
```

After the pull, check that these files exist:

```text
data/merged_data.csv
models/model.pkl
```

If DVC asks for Azure access, save the connection string locally:

```bash
uv run dvc remote modify --local azureremote connection_string "<connection-string>"
uv run dvc pull
```

The credential goes to `.dvc/config.local`, which is ignored by Git. Never put
the connection string in `.dvc/config`, a Dockerfile, or a commit.

No Azure access? Download the Kaggle US Health Insurance dataset to
`data/insurance.csv`, then run notebook 01. It creates the file used by the
pipeline.

```bash
uv run jupyter lab notebooks/01_load_data.ipynb
```

## 3. Check the repository

```bash
uv run ruff check .
uv run pytest
```

The normal test command skips the one slow golden-model test. Tests that need
DVC files are skipped when those files are missing.

## 4. Choose: use or retrain the model

To use the model downloaded by DVC, skip to step 5.

To retrain it:

```bash
uv run python main.py
```

The committed entry point runs with MLflow tracking. It:

1. reads `data/merged_data.csv`;
2. cleans the data;
3. trains the model named in `config.yml`;
4. overwrites `models/model.pkl`;
5. records parameters, metrics, the model, and `config.yml` in `mlflow/`.

## 5. Start the API

```bash
uv run uvicorn app:app --reload
```

Open <http://127.0.0.1:8000/docs>. Choose `POST /predict`, select **Try it
out**, paste this JSON, and select **Execute**:

```json
{
  "age": 19,
  "sex": "female",
  "bmi": 27.9,
  "children": 0,
  "smoker": "yes",
  "region": "southwest"
}
```

The response has this shape:

```json
{
  "predicted_premium": 18095.88,
  "currency": "USD",
  "model": "RandomForestRegressor"
}
```

Your number can change after retraining. It should still be a positive amount
in US dollars.

## Common problems

| What you see | Meaning | Fix |
| --- | --- | --- |
| `No model at .../models/model.pkl` | The API loads the model at startup. | Run `uv run dvc pull` or train the model. |
| DVC returns `403` | Azure accepted the identity but it cannot read the blob container. | Add `Storage Blob Data Reader` or use a valid local connection string. |
| API returns `422` | One or more fields are missing or outside the training range. | Read the reason in the response and correct the input. |
| MLflow cannot find runs | The UI is using a different store. | Start it with the command below. |

## Useful next commands

```bash
# View experiments
uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db

# Run the real-data model check
uv run pytest -m slow

# Open the notebooks
uv run jupyter lab
```

Next: [Architecture](architecture.md) - how the training run, the prediction
request, and the storage tools connect.
