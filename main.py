"""Training pipeline entry point.

Two functions do the same work. `main()` runs the pipeline on its own;
`train_with_mlflow()` runs it inside an MLflow run so the parameters, metrics,
model and config are recorded. Comment out whichever one you do not want at the
bottom of this file.

Both call `print_results` rather than carrying their own copy of it, so the two
paths cannot drift apart.
"""

import logging
from datetime import datetime

import mlflow
import mlflow.sklearn

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


def train_with_mlflow():
    """Run the pipeline inside an MLflow run, recording everything about it.

    Logs the parameters the model actually ended up with, the four test metrics,
    the fitted model, and `config.yml` itself as an artefact. That last one is
    what makes a run reproducible: the metrics tell you how it went, the config
    tells you how to do it again.

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

        mlflow.log_params(params)
        mlflow.log_param("use_log_target", trainer.use_log_target)
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
