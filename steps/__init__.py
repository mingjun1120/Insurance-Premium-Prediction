"""Shared helpers for the training pipeline.

`PROJECT_ROOT` is resolved from this file's own location rather than from the
working directory, so `python main.py`, `python steps/train.py` and a call from
another folder all find the same `config.yml`. Resolving it once here also keeps
the three step modules from each carrying their own copy of the logic.
"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yml"


def load_config(path=CONFIG_PATH):
    """Read the pipeline configuration.

    Args:
        path (pathlib.Path, optional): Configuration file to read. Defaults to
            `config.yml` beside this package.

    Returns:
        dict: The parsed configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist. The message
            names the absolute path that was tried, which is more useful than a
            bare "config.yml not found" when the working directory is the
            suspect.

    Examples:
        >>> load_config()["data"]["target"]
        'charges'
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"No configuration file at {path}")

    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve(relative_path):
    """Turn a config path such as `data/merged_data.csv` into an absolute one.

    Args:
        relative_path (str): Path relative to the project root.

    Returns:
        pathlib.Path: The absolute path.
    """
    return PROJECT_ROOT / relative_path
