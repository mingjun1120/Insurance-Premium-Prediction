"""Training pipeline entry point.

Two functions do the same work. `main()` runs the pipeline on its own.
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


def read_data_version():
    """Read the md5 DVC recorded for data/, so a run knows which data it used.

    Returns:
        str: The md5 from data.dvc, or "unknown" if it is missing or unreadable.
    """
    pointer = PROJECT_ROOT / "data.dvc"

    try:
        with open(pointer, encoding="utf-8") as file:
            return yaml.safe_load(file)["outs"][0]["md5"]
    except (OSError, yaml.YAMLError, KeyError, IndexError, TypeError):
        # A broken pointer file must not throw away an hour of training.
        return "unknown"


def read_uncommitted_changes():
    """Warn when the code on disk no longer matches the commit MLflow logged.

    Returns:
        str:
            "yes" when there are unsaved edits, so the commit is a rough guide only.
            "no" when the commit is trustworthy.
            "unknown" if git could not be reached.
    """
    # Untracked files are ignored: a stray scratch file did not change the run.
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


def main():
    """Run the pipeline without MLflow tracking.

    Returns:
        None: Results are printed.
    """
    trainer, _, train_metrics, test_metrics = run_pipeline()

    print_results(trainer.model_name, "Train", train_metrics)
    print_results(trainer.model_name, "Test", test_metrics)


def train_with_mlflow():
    """Run the pipeline and record the run in MLflow.

    Logs the parameters, metrics, model, config.yml, the data version and
    whether the code was committed - enough to rebuild the run later.
    """
    config = load_config()
    mlflow_config = config["mlflow"]

    # Set this by hand: MLflow URL-encodes the path, and ours has spaces and "&".
    # Same reason for as_posix() below - Path.as_uri() would re-encode it.
    tracking_db = PROJECT_ROOT / mlflow_config["tracking_db"]
    tracking_db.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_db.as_posix()}")

    # An experiment's artifact folder is fixed at creation, so pass it here.
    experiment_name = mlflow_config["experiment_name"]
    if mlflow.get_experiment_by_name(experiment_name) is None:
        artifacts = PROJECT_ROOT / mlflow_config["artifact_location"]
        artifacts.mkdir(parents=True, exist_ok=True)
        mlflow.create_experiment(experiment_name, artifact_location=f"file:{artifacts.as_posix()}")

    mlflow.set_experiment(experiment_name)

    # Otherwise MLflow invents a random name like "classy-wren-675".
    run_name = f"{config['model']['name']}-{datetime.now():%Y%m%d-%H%M%S}"

    with mlflow.start_run(run_name=run_name) as run:
        trainer, params, train_metrics, test_metrics = run_pipeline()

        rmse, mae, r2, mape = test_metrics

        mlflow.set_tag("Model developer", mlflow_config["developer"])
        mlflow.set_tag("Model name", trainer.model_name)
        mlflow.set_tag("Tuned", str(trainer.tune))
        mlflow.set_tag("Uncommitted changes", read_uncommitted_changes())

        mlflow.log_params(params)
        mlflow.log_param("use_log_target", trainer.use_log_target)
        mlflow.log_param("data_md5", read_data_version())

        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("mae", mae)
        mlflow.log_metric("r2", r2)
        mlflow.log_metric("mape", mape)

        # cloudpickle: MLflow's default (skops) cannot save LightGBM,
        # XGBoost or CatBoost.
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
