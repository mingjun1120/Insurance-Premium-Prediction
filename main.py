"""Training pipeline entry point.

Two functions do the same work. `main()` runs the pipeline on its own;
`train_with_mlflow()` runs it inside an MLflow run so the parameters, metrics,
model and config are recorded. Comment out whichever one you do not want at the
bottom of this file.

Both call `print_results` rather than carrying their own copy of it, so the two
paths cannot drift apart.
"""

import logging
import subprocess
from datetime import datetime

import mlflow
import mlflow.sklearn
import yaml

from steps import CONFIG_PATH, PROJECT_ROOT, load_config
from steps.clean import Cleaner
from steps.ingest import Ingestion
from steps.predict import Predictor
from steps.train import Trainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")


def print_results(model_name, split, metrics):
    """Print one split's scores.

    Args:
        model_name (str): Name of the model that produced them.
        split (str): "Train" or "Test".
        metrics (tuple[float, float, float, float]): `rmse, mae, r2, mape`, as
            returned by `Predictor.evaluate_model`.

    Returns:
        None: The results are printed.
    """
    rmse, mae, r2, mape = metrics

    print(f"\n============= Model Evaluation Results ({split} Set) ==============")
    print(f"Model          : {model_name}")
    print(f"RMSE           : ${rmse:,.0f}")
    print(f"MAE            : ${mae:,.0f}")
    print(f"R2 Score       : {r2:.4f}")
    print(f"MAPE           : {mape:.4f}")
    print("=================================================================\n")


def run_pipeline():
    """Run ingestion, cleaning and training, then score both splits.

    Shared by both entry points so that neither can quietly diverge from the
    other.

    Returns:
        tuple: `trainer, params, train_metrics, test_metrics`, where `params` is
        what the fitted model actually ended up with.
    """
    config = load_config()

    # Load data
    ingestion = Ingestion()
    data = ingestion.load_data()
    logging.info("DATA INGESTION COMPLETED SUCCESSFULLY!!!\n")

    # Clean data
    cleaner = Cleaner(target=config["data"]["target"])
    data = cleaner.clean_data(data)
    logging.info("DATA CLEANING COMPLETED SUCCESSFULLY!!!\n")

    # Prepare and train model
    trainer = Trainer()
    X, y = trainer.feature_target_separator(data)
    X_train, X_test, y_train, y_test = trainer.train_test_split_data(X, y)
    params = trainer.train_model(X_train, y_train)
    trainer.save_model()
    logging.info("MODEL TRAINING COMPLETED SUCCESSFULLY!!!\n")

    # Evaluate model
    predictor = Predictor()
    train_metrics = predictor.evaluate_model(X_train, y_train)
    test_metrics = predictor.evaluate_model(X_test, y_test)
    logging.info("MODEL EVALUATION COMPLETED SUCCESSFULLY!!!\n")

    return trainer, params, train_metrics, test_metrics


def main():
    """Run the pipeline without MLflow tracking.

    Returns:
        None: Results are printed.
    """
    trainer, _, train_metrics, test_metrics = run_pipeline()

    print_results(trainer.model_name, "Train", train_metrics)
    print_results(trainer.model_name, "Test", test_metrics)


def read_data_version():
    """Read the content hash DVC recorded for the `data/` directory.

    `data.dvc` is a small committed file holding one md5 for everything inside
    `data/`. Logging it puts the dataset version on the run itself, where the
    MLflow UI shows it as a sortable column. Without it a run records only the
    data *path* out of config.yml, and working out which version sat at that
    path means going back through git history for `data.dvc`.

    Returns:
        str: The md5 recorded in `data.dvc`, or `"unknown"` if that file is
        missing or does not parse. This never raises. A run trained on real
        data is still a good run, and throwing away an hour of training
        because a pointer file moved would be a poor trade.

    Examples:
        >>> read_data_version()
        '322756809ac53695367784cbff6cd5b0.dir'
    """
    pointer = PROJECT_ROOT / "data.dvc"

    try:
        with open(pointer, encoding="utf-8") as file:
            return yaml.safe_load(file)["outs"][0]["md5"]
    except (OSError, yaml.YAMLError, KeyError, IndexError, TypeError):
        return "unknown"


def read_uncommitted_changes():
    """Say whether the tracked files on disk still match the last commit.

    MLflow fills in `mlflow.source.git.commit` by itself, but it records the
    last commit without checking that the working tree still matches it. Train
    with edits you have not committed and the run points at code that never
    produced it, with nothing anywhere to say so. This tag is that warning.

    Untracked files are deliberately left out (`--untracked-files=no`). A
    scratch file sitting in the folder does not change what the pipeline did,
    and counting it would mark nearly every run dirty - a warning that fires
    constantly is one nobody reads.

    Returns:
        str: `"yes"`, `"no"`, or `"unknown"` when git cannot be reached at all.
        The serving image has no repository in it, for instance.

    Examples:
        >>> read_uncommitted_changes()
        'no'
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    return "yes" if result.stdout.strip() else "no"


def train_with_mlflow():
    """Run the pipeline inside an MLflow run, recording everything about it.

    Logs the parameters the model actually ended up with, the four test metrics,
    the fitted model, and `config.yml` itself as an artefact. The metrics tell
    you how the run went; the config tells you how to do it again.

    Rebuilding a run needs three things, though, and config.yml is only one of
    them:

        settings   config.yml, logged as an artefact
        code       mlflow.source.git.commit, which MLflow fills in itself
        data       the `data_md5` param below

    The config alone is not enough, because not every setting lives in it - the
    six cleaning thresholds are module constants in `steps/clean.py`. Change one
    and config.yml looks identical while the model is different. Only the commit
    tells those two runs apart, which is why the `Uncommitted changes` tag
    matters: it says whether that commit describes the code that actually ran.

    Returns:
        None: Results are printed and recorded.
    """
    config = load_config()
    mlflow_config = config["mlflow"]

    # Point MLflow at the database explicitly.
    #
    # Left alone, MLflow builds its own tracking URI from the working directory
    # and URL-encodes it. This project's path contains spaces and an "&", which
    # become "%20" and "%26" - and SQLAlchemy then reads those as ordinary
    # characters rather than decoding them back. The result is a real folder
    # called "Personal%20Project" appearing next to the real one.
    #
    # Note the paths below are built with as_posix() and a plain "file:" prefix
    # rather than Path.as_uri(), because as_uri() percent-encodes and would
    # reintroduce exactly that problem.
    tracking_db = PROJECT_ROOT / mlflow_config["tracking_db"]
    tracking_db.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_db.as_posix()}")

    # Where the saved models and config snapshots go. An experiment's artifact
    # folder is fixed when the experiment is first created and cannot be changed
    # afterwards, so it has to be passed here - `set_experiment` alone would
    # silently fall back to MLflow's default location.
    experiment_name = mlflow_config["experiment_name"]
    if mlflow.get_experiment_by_name(experiment_name) is None:
        artifacts = PROJECT_ROOT / mlflow_config["artifact_location"]
        artifacts.mkdir(parents=True, exist_ok=True)
        mlflow.create_experiment(experiment_name, artifact_location=f"file:{artifacts.as_posix()}")

    mlflow.set_experiment(experiment_name)

    # Name the run after the model and the moment it started.
    #
    # Left to itself MLflow invents a random label such as "classy-wren-675",
    # which says nothing about what was trained. The timestamp keeps repeat runs
    # of the same model apart, and sorts them in order.
    #
    # The name does not carry the hyperparameters. They are logged separately by
    # `mlflow.log_params` below, so the UI can show them as sortable columns -
    # far more useful for comparing runs than a long name would be. Turn them on
    # with the "Columns" button in the runs table.
    run_name = f"{config['model']['name']}-{datetime.now():%Y%m%d-%H%M%S}"

    with mlflow.start_run(run_name=run_name) as run:
        trainer, params, train_metrics, test_metrics = run_pipeline()

        rmse, mae, r2, mape = test_metrics

        mlflow.set_tag("Model developer", mlflow_config["developer"])
        mlflow.set_tag("Model name", trainer.model_name)
        mlflow.set_tag("Tuned", str(trainer.tune))

        # Sits beside MLflow's own mlflow.source.git.* tags and qualifies them:
        # "yes" means the recorded commit does not describe what actually ran.
        mlflow.set_tag("Uncommitted changes", read_uncommitted_changes())

        mlflow.log_params(params)
        mlflow.log_param("use_log_target", trainer.use_log_target)

        # config.yml records where the data was read from. This records what was
        # there at the time, which is the half a path cannot capture.
        mlflow.log_param("data_md5", read_data_version())
        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("mae", mae)
        mlflow.log_metric("r2", r2)
        mlflow.log_metric("mape", mape)

        # Save the model with "cloudpickle" instead of MLflow's default.
        #
        # MLflow 3 saves models using a tool called "skops". For safety, skops
        # only knows how to save a fixed list of model types. Everything on that
        # list comes from scikit-learn.
        #
        # Three of our five models are NOT from scikit-learn - LightGBM,
        # XGBoost and CatBoost are separate libraries. skops does not know them,
        # so it refuses to save them and the run fails.
        #
        # "cloudpickle" has no such list. It can save any model. We already save
        # our own model with a similar tool in steps/train.py, so this does not
        # make the project any less safe than it already was.
        mlflow.sklearn.log_model(
            trainer.model, name="model", serialization_format="cloudpickle"
        )

        # The config that produced this run, so it can be replayed exactly
        mlflow.log_artifact(str(CONFIG_PATH))

        mlflow.register_model(
            model_uri=f"runs:/{run.info.run_id}/model",
            name=mlflow_config["registered_model_name"],
        )
        logging.info("MLFLOW TRACKING COMPLETED SUCCESSFULLY!!!\n")

        print_results(trainer.model_name, "Train", train_metrics)
        print_results(trainer.model_name, "Test", test_metrics)


if __name__ == "__main__":
    # Comment out whichever one you do not want.
    # main()
    train_with_mlflow()
