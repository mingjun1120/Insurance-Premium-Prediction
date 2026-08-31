# Commands

Every command this project accepts. All of them run from the project root.

Dependencies are managed by [uv](https://docs.astral.sh/uv/). `uv run` executes
inside the project virtualenv, so nothing needs activating first.

## The full set

| Command | Requires first | Writes |
| --- | --- | --- |
| `uv sync` | `pyproject.toml`, `uv.lock` | `.venv/` — all 257 packages, dev group included |
| `uv sync --frozen` | the same | the same; fails instead of resolving if `uv.lock` disagrees with `pyproject.toml` |
| `uv sync --frozen --no-dev` | the same | `.venv/` with 40 packages, dev group omitted |
| `uv run ruff check .` | `uv sync` | nothing |
| `uv run python main.py` | `data/merged_data.csv` | `models/model.pkl`, `mlflow/mlflow.db`, `mlflow/mlruns/` |
| `uv run pytest` | `uv sync` | nothing |
| `uv run pytest -m slow` | `models/model.pkl` and `data/merged_data.csv` | nothing |
| `uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db` | `mlflow/mlflow.db` | nothing; serves on `127.0.0.1:5000` |
| `uv run uvicorn app:app --reload` | `models/model.pkl` | nothing; serves on `127.0.0.1:8000` |
| `uv run jupyter lab notebooks/<name>.ipynb` | `uv sync` | depends on the notebook |
| `uv run dvc pull` | a credential in `.dvc/config.local` | `data/` (4 files), `models/` (2 files), `.dvc/cache/` |
| `uv run dvc add data models` | those directories on disk | `data.dvc`, `models.dvc`, `.dvc/cache/` |
| `uv run dvc push` | `dvc add` already run | nothing locally; uploads to the Azure remote |
| `uv run dvc checkout` | `.dvc/cache/` populated | `data/`, `models/` — restored to match the current commit |
| `uv run dvc status --cloud` | a credential | nothing |
| `uv run dvc remote modify --local azureremote connection_string "<string>"` | — | `.dvc/config.local` |
| `docker build -t insurance-premium .` | `models/model.pkl` on disk | a local image, 1.02 GB |
| `docker run --rm -p 8000:8000 insurance-premium` | that image | nothing; serves on `0.0.0.0:8000` in the container |

---

## Notes per command

### `uv sync`

Installs from `uv.lock`. `--frozen` is what CI and the Dockerfile use
(`ci.yml:38-39`, `Dockerfile:34-36`): it refuses to re-resolve, so a lock file
that has drifted from `pyproject.toml` fails the run rather than silently
installing something else.

`--no-dev` omits the `[dependency-groups] dev` block — DVC, MLflow, JupyterLab,
SHAP, seaborn, sweetviz, matplotlib, plotly, evidently, pytest, ruff, ipykernel.
Only the Dockerfile passes it.

### `uv run python main.py`

Runs ingestion, cleaning, training and scoring, then prints both splits. Which
model it trains comes from `model.name` in `config.yml`; see
[configuration.md](configuration.md).

The file has two entry points and selects between them by comment
(`main.py:200-203`):

```python
if __name__ == "__main__":
    # Comment out whichever one you do not want.
    # main()
    train_with_mlflow()
```

As committed, `train_with_mlflow()` runs, so the command always writes to
`mlflow/`. `main()` runs the same pipeline through `run_pipeline()`
(`main.py:50`) and writes only `models/model.pkl`.

`models/model.pkl` is overwritten in place each run.

### `uv run pytest`

`addopts = "-m 'not slow'"` (`pyproject.toml:57`) applies automatically. 109
tests are collected, 1 is deselected, 108 run. Counts and skip behaviour are in
[test-suite.md](test-suite.md).

`-v` is worth adding when reading a log rather than a terminal; CI passes it so
each skip and its reason appear individually (`ci.yml:44-47`).

### `uv run pytest -m slow`

Inverts the default marker filter: 1 test is collected, 108 deselected. It
retrains nothing — it re-cleans the real data, rebuilds the same split, and
scores the shipped artefact against fixed expected values
(`tests/test_predict.py:149-176`).

### `uv run mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db`

The `--backend-store-uri` is required. Without it MLflow looks for a default
store, not the SQLite file named at `config.yml:127`. Opens at
<http://127.0.0.1:5000>.

### `uv run uvicorn app:app --reload`

`app:app` is the `FastAPI` object at `app.py:21`. Importing the module builds
`Predictor()` at `app.py:27`, so a missing `models/model.pkl` raises
`FileNotFoundError` before the server binds a port. Interactive docs at
<http://127.0.0.1:8000/docs>. Endpoints are in [api.md](api.md).

### The DVC commands

The remote is `azureremote`, `azure://dvcstore`, account `insurancedvc`
(`.dvc/config`). No credential is committed; `dvc remote modify --local` writes
one to `.dvc/config.local`, which `.dvc/.gitignore` excludes.

`dvc pull` and `dvc checkout` are not the same. `pull` fetches from Azure into
`.dvc/cache/` and then materialises the working files; `checkout` only
materialises, from whatever the cache already holds.

`dvc status --cloud` prints one line when everything has been pushed:

```
Cache and remote 'azureremote' are in sync.
```

The two pointer files record what should be there:

| File | Size | Files |
| --- | ---: | ---: |
| `data.dvc` | 179,490 bytes | 4 |
| `models.dvc` | 5,420,143 bytes | 2 |

### `docker build` / `docker run`

Both forms are recorded in the Dockerfile header (`Dockerfile:4-5`).

`COPY models/ ./models/` (`Dockerfile:63`) is the only way the artefact enters
the image, so it has to exist on disk before the build. `dvc pull` deliberately
does not run inside the build (`Dockerfile:7-10`).

`.dockerignore` keeps `.venv`, `.git`, `.dvc`, `*.dvc`, `mlflow/`, `data/`,
`notebooks/`, `main.py` and `README.md` out of the build context.

The container's own start command is
`uvicorn app:app --host 0.0.0.0 --port 8000` (`Dockerfile:70`), with `EXPOSE
8000`. `--host 0.0.0.0` rather than the uvicorn default, or the port would not be
reachable from outside the container.

---

## Where these run unattended

`ci.yml` runs `uv sync --frozen`, `uv run ruff check .` and `uv run pytest -v`.
`cd.yml` adds `uv run dvc pull`, `uv run pytest -m slow`, `az acr login`,
`docker build`, `docker push` and `az containerapp update`. Full step lists are
in [workflows.md](workflows.md).
