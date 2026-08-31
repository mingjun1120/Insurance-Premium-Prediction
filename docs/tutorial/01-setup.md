# 1. Set up the project

You start with an empty folder. You finish with a Python project that has every
library the next eleven units need, and the raw dataset sitting on disk.

Nothing here is specific to machine learning yet. It is the floor everything
else stands on.

## 1. Install uv

uv is the tool that manages the project: it installs Python, installs the
libraries, and runs your code inside them. You install it once, on your machine,
and never think about virtual environments again.

Windows, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close the terminal and open a new one, so it picks up the new command. Then
check it:

```bash
uv --version
```

```
uv 0.11.17 (a33a629d6 2026-05-28 x86_64-pc-windows-msvc)
```

Your numbers will differ. Any version that prints is fine.

The uv install page is at
<https://docs.astral.sh/uv/getting-started/installation/> if your setup needs
something other than the two commands above.

## 2. Create the project

```bash
uv init insurance-premium-prediction --python 3.12
```

```
Initialized project `insurance-premium-prediction` at `...\insurance-premium-prediction`
```

If you do not have Python 3.12, uv downloads it first and says so. That is
expected, and it does not touch any other Python you have installed.

Move into the new folder. Everything from here on happens inside it.

```bash
cd insurance-premium-prediction
```

uv has made six things:

| | |
| --- | --- |
| `pyproject.toml` | The project file. What it depends on. You edit this next. |
| `.python-version` | Holds `3.12`. Pins the Python this project runs on. |
| `main.py` | A placeholder that prints a greeting. Unit 5 turns it into the training command. |
| `README.md` | Empty. |
| `.gitignore` | Keeps `.venv` and `__pycache__` out of git. |
| `.git/` | A git repository, already initialised. Nothing is committed yet. |

## 3. Add the libraries

Open `pyproject.toml` and replace it with this:

```toml
[project]
name = "insurance-premium-prediction"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "catboost>=1.2.10",
    "fastapi>=0.141.1",
    "lightgbm>=4.7.0",
    "matplotlib>=3.11.1",
    # Capped below 3. MLflow, which arrives in unit 6, requires it. Pinning it
    # now means pandas is not downgraded halfway through the tutorial,
    # underneath notebooks you have already run.
    "pandas>=2.3.3,<3",
    "plotly>=6.9.0",
    "scikit-learn>=1.9.0",
    "seaborn>=0.13.2",
    "shap>=0.52.0",
    "sweetviz>=2.3.3",
    "xgboost>=3.4.1",
]

[dependency-groups]
dev = [
    # Pinned below 7 - ipykernel 7 hangs on kernel restart in VS Code
    # https://github.com/microsoft/vscode-jupyter/issues/17410
    "ipykernel>=6.29.5,<7",
    "jupyterlab>=4.6.3",
    "pytest>=9.1.1",
    "ruff>=0.16.3",
]
```

Two lists, and the split between them matters later. `dependencies` is what the
finished service needs in order to answer a request. `dev` is what you need in
order to build it — JupyterLab for the notebooks in units 2 and 3, pytest and
ruff for checking your work. Unit 7b builds a container from the first list
only, and that is where the split earns its keep.

`>=1.2.10` means "this version or newer". Two lines also set a ceiling, and
both say why in a comment above them: pandas and ipykernel.

## 4. Install everything

```bash
uv sync
```

```
Using CPython 3.12.9 interpreter at: ...
Creating virtual environment at: .venv
Resolved 135 packages in 1.06s
Installed 130 packages in 9.21s
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
 + anyio==4.14.2
```

Then another 127 lines of the same. Eleven libraries plus four dev tools pull in
130 packages between them; most of what you see is something else's dependency.

The first run downloads a lot and can take a few minutes. uv keeps what it
downloads, so later runs are seconds.

Two new things are on disk now. `.venv/` holds the installed libraries, and it
is already in `.gitignore`. `uv.lock` records the exact version of all 130
packages, so the same command a year from now installs the same thing. That file
does belong in git.

You never activate the virtual environment by hand. Prefix a command with
`uv run` and uv finds it for you.

## 5. Make the two folders you will need

```bash
uv run python -c "import pathlib; pathlib.Path('data').mkdir(exist_ok=True); s = pathlib.Path('steps'); s.mkdir(exist_ok=True); [(s / f).touch() for f in ('__init__.py', 'ingest.py', 'clean.py', 'train.py', 'predict.py')]"
```

It prints nothing. That is the whole of it working.

`data/` is where the dataset goes in the next step. `steps/` is a Python
package, currently five empty files, that units 4a and 4b fill in one at a time:
one file to read the data, one to clean it, one to train, one to predict. The
`__init__.py` is what makes the folder importable as `steps`.

## 6. Get the data

The dataset is
[US Health Insurance](https://www.kaggle.com/datasets/teertha/ushealthinsurancedataset)
on Kaggle, uploaded by *teertha*. Sign in, download it, and unzip it. Inside is
one file, `insurance.csv`.

Put that file at `data/insurance.csv`.

It has seven columns and 1,338 rows:

```
age,sex,bmi,children,smoker,region,charges
19,female,27.9,0,yes,southwest,16884.924
18,male,33.77,1,no,southeast,1725.5523
```

Six things about a person, and what their insurance actually cost. Predicting
that last column from the other six is the whole job.

## 7. Run it

```bash
uv run main.py
```

```
Hello from insurance-premium-prediction!
```

That is uv's placeholder, running inside the environment you just built. Unit 5
replaces it with the command that trains the model.

## Done when

One command, which reads the dataset through three of the libraries you just
installed:

```bash
uv run python -c "import catboost, lightgbm, xgboost, pandas as pd; print(pd.read_csv('data/insurance.csv').shape)"
```

```
(1338, 7)
```

Those are the rows and columns of the file. If you see them, the environment
works and the data is where the next unit expects it.

The checkpoint for this unit is the tag **`ch01-setup`** on the project
repository. It marks the same state your folder is in now: the project file, the
locked dependencies, the empty `steps/` package and the placeholder `main.py`.
If a later unit stops matching what you read, that tag is what to compare
against.

Next: [02a-load-and-explore](02a-load-and-explore.md).
