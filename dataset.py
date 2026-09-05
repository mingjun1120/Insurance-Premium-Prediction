"""Build the canonical training dataset from the raw source data.

This is the boundary between data engineering and machine learning, and it sits
outside `steps/` on purpose.

In a company, everything upstream of this line usually belongs to a data
engineering team. They would run something like a medallion pipeline - raw data
landing in a bronze layer, conformed in silver, curated in gold - and hand the
gold output to whoever is building the model. The model side then retrieves,
combines and transforms that into one final table it can train on.

This project has no such team, so this file stands in for that work. It reads
the raw Kaggle download and writes the one canonical file the training pipeline
consumes. Everything after it - `steps/ingest.py` onwards - assumes that file
already exists and never asks where it came from.

Notebook 01 explains *why* the dataset looks the way it does: the business
problem, the source, and a column-by-column data dictionary. This file is the
executable half of that notebook. The notebook is the reference; this is the
implementation. That is the same split as notebook 02 to `steps/clean.py` and
notebook 03 to `config.yml`.

Run it with:

    uv run python dataset.py

You only need to run it once, and only if you cannot `dvc pull`. Day to day the
file it writes is restored from the DVC remote instead.
"""

import logging

import pandas as pd

from steps import load_config, resolve

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")


def build_dataset(raw):
    """Consolidate the raw source data into the canonical training table.

    With one source there is nothing to join, so this is a pass-through. It
    still exists as its own function for two reasons: it is the seam a second
    source would be joined at, and it is the part that can be tested without
    touching the disk.

    Notebook 01 section 1.4.1 records the reasoning. The insurance dataset is a
    single flat table of 1,338 rows with no keys and no foreign relationships,
    so consolidation has nothing to do. A second source would be read here and
    merged on whatever key the two share, with row counts compared before and
    after to catch a join that silently dropped or duplicated rows.

    Args:
        raw (pandas.DataFrame): The raw frame, exactly as read from disk.

    Returns:
        pandas.DataFrame: The canonical frame. Today this is `raw` unchanged.

    Examples:
        >>> build_dataset(pd.read_csv("data/insurance.csv")).shape
        (1338, 7)
    """
    return raw


def main():
    """Read the raw source, build the canonical dataset, and write it out.

    Both paths come from `config.yml` rather than being hardcoded, so the same
    rule holds here as everywhere else in the project: a run is reproducible
    from that file plus the code at this commit.

    The write is announced before it happens. `data/` is DVC-tracked, so
    overwriting the file there changes something DVC is watching, and a silent
    overwrite is a bad surprise when the next `dvc status` comes back dirty.

    Returns:
        pathlib.Path: Where the canonical dataset was written.

    Raises:
        FileNotFoundError: If the raw source file is missing. The message names
            the absolute path that was tried and where to get the file, because
            "no such file" alone does not tell a first-time reader that this
            data comes from Kaggle.
    """
    config = load_config()
    source_path = resolve(config["data"]["source_path"])
    output_path = resolve(config["data"]["data_path"])

    if not source_path.exists():
        raise FileNotFoundError(
            f"No raw data at {source_path}. Download the US Health Insurance dataset "
            "from Kaggle and save it there, or run `uv run dvc pull` instead."
        )

    raw = pd.read_csv(source_path)
    logging.info("   - Read %s: %s rows and %s columns.", source_path.name, *raw.shape)

    data = build_dataset(raw)

    logging.info("   - Writing %s (%s rows, %s columns)...", output_path, *data.shape)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # index=False, or the next read picks the written row numbers back up as an
    # "Unnamed: 0" column and the pipeline trains on a feature that is really a
    # row counter.
    data.to_csv(output_path, index=False)

    logging.info("   - Done. %s is ready for `uv run python main.py`.", output_path.name)
    return output_path


if __name__ == "__main__":
    main()
