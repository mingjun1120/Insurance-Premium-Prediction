"""Data ingestion: read the raw dataset named in config.yml."""

import logging

import pandas as pd

from steps import load_config, resolve


class Ingestion:
    """Load the raw dataset that the rest of the pipeline works on.

    Reads `data.data_path` from the configuration. That points at the raw file
    rather than at `data/cleaned_data.csv` on purpose, so that `steps.clean`
    does the cleaning and the pipeline never depends on a notebook having been
    run first.
    """

    def __init__(self):
        self.config = load_config()
        self.data_path = resolve(self.config["data"]["data_path"])

    def load_data(self):
        """Read the raw dataset from disk.

        Returns:
            pandas.DataFrame: The raw data, exactly as stored. No type
            conversion happens here; `steps.clean.Cleaner.convert_data_types`
            owns that, so every transformation of the data lives in one module.

        Raises:
            FileNotFoundError: If the configured data file is missing.

        Examples:
            >>> Ingestion().load_data().shape
            (1338, 7)
        """
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"No data file at {self.data_path}. Run notebook 01 to create it."
            )

        data = pd.read_csv(self.data_path)
        logging.info(
            "   - Loaded %s: %s rows and %s columns.",
            self.data_path.name,
            data.shape[0],
            data.shape[1],
        )
        return data
