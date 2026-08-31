# Tutorial

Twelve units that build this project from an empty folder.

By the end you will have three things on your own machine:

- **A trained model** — `models/model.pkl`, fitted on 1,337 rows of insurance
  data by a command you can run again whenever you like.
- **A running container** — that model inside a Docker image you built
  yourself, listening on `http://127.0.0.1:8000`.
- **A prediction over HTTP** — a premium in dollars, returned from a request
  you type.

## What you need

A terminal, a free [Kaggle](https://www.kaggle.com/) account for the dataset,
and Docker for the final unit. Nothing else is installed by hand. Unit 1 sets
up a tool called uv, and uv installs Python and every library from there on.

## What you do not need

**No Azure account.** The finished project keeps its data and its trained model
in Azure storage, and deploys the container to Azure. This tutorial does
neither. You download the raw data from Kaggle in unit 1, and you train your own
model in unit 5.

**No DVC.** DVC is the tool the project uses to version the files that are too
large for git. It is not part of this path. Every file you need is one you make.

Both are documented, for when you want them: see
[data-outside-git.md](../explanation/data-outside-git.md) and
[pull-data-and-models.md](../how-to/pull-data-and-models.md).

## The twelve units

| Unit | You build | Time | Tag |
| --- | --- | --- | --- |
| [01-setup](01-setup.md) | A uv project, the ML stack installed, the raw CSV on disk | 30 min | `ch01-setup` |
| [02a-load-and-explore](02a-load-and-explore.md) | Notebook 01, the schema, `data/merged_data.csv` | 30 min | |
| [02b-cleaning-rules](02b-cleaning-rules.md) | Six cleaning rules, `data/cleaned_data.csv` | 30 min | `ch02-data` |
| [03a-target-transform](03a-target-transform.md) | The raw-against-log target decision, the first two models | 45 min | |
| [03b-three-more-models](03b-three-more-models.md) | Three more models, and tuning them | 45 min | |
| [03c-compare-and-save](03c-compare-and-save.md) | The comparison, SHAP, the saved bundle | 30 min | `ch03-notebook-model` |
| [04a-config-and-cleaning](04a-config-and-cleaning.md) | `config.yml`, `steps/ingest.py`, `steps/clean.py` | 45 min | |
| [04b-train-and-predict](04b-train-and-predict.md) | `steps/train.py`, `steps/predict.py` | 45 min | `ch04-steps` |
| [05-train-cli](05-train-cli.md) | `main.py` — one command that trains and writes `models/model.pkl` | 20 min | `ch05-train-cli` |
| [06-mlflow](06-mlflow.md) | Experiment tracking, `mlflow/mlflow.db` | 30 min | `ch06-mlflow` |
| [07a-fastapi](07a-fastapi.md) | `app.py`, and a prediction over HTTP | 30 min | |
| [07b-docker](07b-docker.md) | The two-stage image, and the same prediction from inside it | 45 min | `ch07-serve` |

About seven hours in total. The times are rough, and reading as you go is slower
than typing.

Four of the seven chapters are long enough to need two or three units. Those
units share one checkpoint, so the tag sits on the last unit of the group: unit
2b reaches `ch02-data`, unit 3c reaches `ch03-notebook-model`. Each tag marks
the state of the project repository at the end of that chapter, so you can check
your own folder against it if something has drifted.

## Where this stops

The tutorial ends at Docker, with a container answering on your machine. It
does not cover DVC, the test suite, or the GitHub Actions workflows that deploy
to Azure. Those are operational work rather than building work, and they are
written up as [how-to guides](../how-to/) and
[explanations](../explanation/) instead. There is no unit 8 to look for.

## How to work through it

In order, from unit 1. Each unit assumes the one before it finished, and every
unit ends with a single command that proves it did. Type the code rather than
copying it where you can — the point of the tutorial is the reading you do while
you type.
