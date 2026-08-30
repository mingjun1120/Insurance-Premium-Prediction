Plan verified against the diffs. Four corrections to your mapping first, then the chapters.

## Corrections

**1. `e97d024` is Chapter 2, not Chapter 4.** It touches only `notebooks/01_load_data.ipynb` and `notebooks/02_eda_and_preprocessing.ipynb` — one line each, `Path.cwd().parents` → `[Path.cwd(), *Path.cwd().parents]`. `steps/__init__.py` uses `Path(__file__).resolve().parent.parent` and never had the bug.

**2. `33ab27a` must split across Chapters 4 and 6.** It adds `pyyaml` + `joblib` + `mlflow` in one commit and sits *before* `f9a8335` in history. `steps/__init__.py` imports `yaml`; `train.py` and `predict.py` import `joblib`. Chapter 4 cannot run without them. Give Ch4 `uv add pyyaml joblib`, Ch6 `uv add mlflow`.

**3. `0a521b5` belongs in Chapter 3.** Notebook 03 ends in `joblib.dump(artefact, model_path)` → `models/random_forest_insurance_model.pkl`. Name it in Ch3 and say plainly it is a dead end: nothing in the finished project ever loads it (`steps/predict.py` reads `models/model.pkl`), or the learner will assume Ch7 serves it.

**4. `e736443` cannot be applied verbatim in Chapter 7.** Its diff removes `dvc[azure]` from `dependencies` and re-adds it under `dev`. Your learner never installed DVC. Their version: move `mlflow`, `matplotlib`, `seaborn`, `plotly`, `shap`, `sweetviz` to `dev`, add `uvicorn`, no dvc lines either side.

Also: `bd09355` (`models/model.pkl`) is not a learner step — they generate that file by running Chapter 5.

---

## Chapter 1 — Set up the project
**Commits:** `4d3cf59`, `571dfc5`
**Builds:** uv project, `.python-version` (3.12), `pyproject.toml` with the ML stack and a `dev` group, `.gitignore`, an empty `steps/` package, placeholder `main.py`. The Kaggle CSV lands at `data/insurance.csv`.
**Skip from `4d3cf59`:** `notebooks/load.ipynb` (4,286 lines, deleted wholesale at `6ec6191`) and the `steps/predict.py` stub, which holds a misplaced copy of `Ingestion` and gets rewritten at `6a7fd62`. Create empty `steps/*.py` files instead.
**Deliberate deviation:** pin `pandas>=2.3.3,<3` here rather than inheriting `>=3.0.5`. History pins it at `33ab27a` because mlflow 3.x requires it — but that lands mid-tutorial and silently downgrades pandas under notebooks the learner already ran. Pin once, up front.
**Command:** `uv run main.py`
**Output:** `Hello from insurance-premium-prediction!`
**Tag:** `ch01-setup`
**Prereq:** none, beyond a Kaggle account for the dataset.
**Length:** ~120 lines. Fine.

## Chapter 2 — Get the data and look at it
**Commits:** `6ec6191`, `ed468ad`, **`e97d024`** (moved here)
**Builds:** notebook 01 (business framing, schema, the no-join decision, writes `merged_data.csv`); notebook 02 (EDA 2.2.1–2.2.9, then six cleaning rules 3.2.1–3.2.6, writes `cleaned_data.csv`).
**Kaggle path confirmed by reading notebook 01:** cell 5 resolves `PROJECT_ROOT` by walking up for `pyproject.toml`; cell 8 is `pd.read_csv(DATA_DIR / "insurance.csv")`; cell 16 writes `DATA_DIR / "merged_data.csv"`. No DVC anywhere in the notebook. The path works.
**Command:** `uv run python -c "import pandas as pd; print(pd.read_csv('data/merged_data.csv').shape, pd.read_csv('data/cleaned_data.csv').shape)"`
**Output:** `(1338, 7) (1337, 7)`
**Tag:** `ch02-data`
**Prereq:** Ch1 — `data/insurance.csv` and the `dev` group's jupyterlab.
**Length:** ⚠️ **over.** 405 lines of code across 21 cells, plus 25 markdown cells. **Split at the section boundary:** 2a = notebook 01 + EDA (section 2.2); 2b = the cleaning rules (section 3.2). The outliers-kept argument alone needs real prose.

## Chapter 3 — Train five models, pick one
**Commits:** `7e83f63`, `0a521b5`
**Builds:** notebook 03 — the raw-vs-log target decision measured on the training split (4.3), five models cross-validated and GridSearchCV-tuned (4.4–4.13), comparison (4.14), SHAP (4.15), and the six-key artefact saved at 4.16.
**Sidebar — what went wrong (`f7c61f8`):** CatBoost defaults to `use_best_model=True` whenever an `eval_set` is passed, so it kept only the first 167 of 300 trees — the trees chosen by the *test* split. Section 4.8.3 claimed the eval set was monitoring only. `use_best_model=False` restores an honest overfit gap: −$4 → +$156. The notebook was re-run, so all outputs move with the fix.
**Also flag:** notebook 03 reads `cleaned_data.csv`, but the Chapter 4 pipeline reads `merged_data.csv` and re-cleans it. Say so here, or Ch4 reads as a bug.
**Command:** `uv run python -c "import joblib; print(sorted(joblib.load('models/random_forest_insurance_model.pkl')))"`
**Output:** `['categorical_features', 'feature_order', 'model', 'model_name', 'target', 'use_log_target']`
**Tag:** `ch03-notebook-model`
**Prereq:** Ch2 — `data/cleaned_data.csv`.
**Length:** ⚠️ **badly over.** 999 lines of code across 55 cells, 58 markdown cells. **Split three ways:** 3a = target transform + the first two models; 3b = remaining three models + tuning (CatBoost sidebar lives here); 3c = comparison, SHAP, saving the bundle.

## Chapter 4 — Move it out of the notebook
**Commits:** `f9a8335`, `6a7fd62`, plus the `pyyaml`/`joblib` half of `33ab27a`
**Builds:** `config.yml` (128), `steps/__init__.py` (53), `ingest.py` (50), `clean.py` (402), `train.py` (292), `predict.py` (98).
**⚠️ This chapter does not end runnable on its own.** `main.py` at `6a7fd62` is still the six-line `Hello from...` stub — there is no entry point until Chapter 5. Either say so and use the synthetic check below, or pull `main()` forward. I'd keep the split and use the check; Chapter 5 is otherwise too thin to stand alone.
**Command:**
```
uv run python -c "from steps import load_config; from steps.ingest import Ingestion; from steps.clean import Cleaner; c=load_config(); print(Cleaner(c['data']['target']).clean_data(Ingestion().load_data()).shape)"
```
**Output:** `(1337, 7)`, after the cleaner's INFO logs (each rule prints its diagnostic table; only `remove_duplicate_rows` drops anything).
**Tag:** `ch04-steps`
**Prereq:** Ch2 — `data/merged_data.csv`. *Not* Ch3; the pipeline re-cleans from `merged_data.csv`.
**Length:** ⚠️ **badly over.** 895 lines of Python. **Split two ways:** 4a = `config.yml` + `__init__.py` + `ingest.py` + `clean.py` (the seven rules, in notebook 02's order); 4b = `train.py` + `predict.py` — the model registry, preprocessing-derived-from-model-name, and the six-key bundle. 4b is where the log-transform argument belongs and it needs the room.

## Chapter 5 — One command to train
**Commits:** `a159478` (`print_results`, `run_pipeline`, `main` — lines 27–99 and the `__main__` block)
**Builds:** `main.py` as a real entry point.
**Deliberate deviation:** the shipped `a159478` puts `import mlflow` and `import mlflow.sklearn` at module top, so their file would not import without mlflow. Chapter 5 writes `main.py` with neither import and `__main__` calling `main()`. Chapter 6 adds them.
**Command:** `uv run main.py`
**Output:** two blocks —
```
============= Model Evaluation Results (Train Set) ==============
Model          : RandomForestRegressor
RMSE           : $4,193
MAE            : $1,864
R2 Score       : 0.8716
MAPE           : 0.1513
=================================================================
```
then the Test block: RMSE `$4,193`, MAE `$1,974`, R2 `0.9043`, MAPE `0.1655`.
**Worth one line of prose:** train and test RMSE both printing `$4,193` is a genuine coincidence (4192.76 vs 4192.93), not a mislabelled split. Verified against the shipped model. Learners will assume they broke something.
**Tag:** `ch05-train-cli`
**Prereq:** Ch4. Writes `models/model.pkl`, which every later chapter needs.

## Chapter 6 — Track experiments with MLflow
**Commits:** `a159478` (`train_with_mlflow`, lines 101–199), mlflow half of `33ab27a`, `d23a231`
**Builds:** `train_with_mlflow()` sharing `run_pipeline()` with `main()`; the explicit SQLite tracking URI and explicit artifact location; `mlflow/` gitignored.
**The point of the chapter:** the URI is built with `as_posix()` and a plain `file:` prefix, not `Path.as_uri()`, because this project's path contains a space and an `&` — MLflow's default percent-encodes it into a real folder called `Personal%20Project`. Models log with `cloudpickle` because the default serializer refuses LightGBM, XGBoost and CatBoost.
**Command:** `uv run main.py` (with `main()` now commented out and `train_with_mlflow()` live)
**Output:** the same two evaluation blocks, preceded by `MLFLOW TRACKING COMPLETED SUCCESSFULLY!!!` and a `mlflow/mlflow.db` on disk.
**Tag:** `ch06-mlflow`
**Prereq:** Ch5.
**Length:** ~100 lines. Fine.
**Note:** the entry point is toggled by commenting a line (`main.py:200-203`). Flag it as a known wart, not a pattern to copy.

## Chapter 7 — Serve it: FastAPI + Docker
**Commits:** `e736443` (adapted — see correction 4), `7fccc6d`, `b709a84`, `6ac9a5e`
**Builds:** the serving/dev dependency split plus `uvicorn`; `Predictor.predict_records()`, which also adds `feature_order` and `categorical_features` to `__init__` (Ch4's `Predictor` reads only three of the bundle's six keys — these two arrive here); `app.py` with the `Person` bounds taken from the training data; the two-stage `Dockerfile`.
**Command:** with `docker run --rm -p 8000:8000 insurance-premium` up —
```
curl -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d "{\"age\":19,\"sex\":\"female\",\"bmi\":27.9,\"children\":0,\"smoker\":\"yes\",\"region\":\"southwest\"}"
```
**Output:** `{"predicted_premium":18095.88,"currency":"USD","model":"RandomForestRegressor"}` — verified against the shipped `models/model.pkl` in this working tree.
**Tag:** `ch07-serve`
**Prereq:** Ch5 or Ch6 — `models/model.pkl` must exist on disk before `docker build`, because `COPY models/ ./models/` is the only way it enters the image.
**Two adjustments for the DVC-free path:** the Dockerfile's header comment tells the reader to run `uv run dvc pull` — rewrite it to point at Chapter 5. And `models/` will still hold `random_forest_insurance_model.pkl` from Ch3, adding a dead 2.7 MB to the image; either delete it or say why it is there.
**Length:** ⚠️ **borderline over,** ~245 lines of code but the Docker half carries four non-obvious decisions that each need a paragraph (`--no-dev` dropping 217 of 257 packages; the `nvidia-nccl-cu13` uninstall reclaiming 288 MB and why it must be the same `RUN`; `libgomp1`; why `dvc pull` stays outside the build). **Split:** 7a = deps split + `predict_records` + `app.py`, ending at `uv run uvicorn app:app` and the same curl against `127.0.0.1:8000`; 7b = the Dockerfile.

---

**Net:** 7 chapters as scoped, but 4 of them (2, 3, 4, 7) exceed ~350 lines and want splitting into 11 written units. Every chapter ends runnable except Chapter 4, which has no entry point until Chapter 5 — the synthetic one-liner covers it.
