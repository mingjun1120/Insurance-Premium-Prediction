"""Tests for `dataset.py`, the step that builds the canonical training table.

All of these are self-contained. `dataset.py` is the one thing in the project a
person runs when they *cannot* `dvc pull`, so its tests must not need the DVC
files either - otherwise the code that exists for people without the data could
only be checked by people with it.

The failure worth guarding is `index=False`. Pandas writes the row numbers as an
unnamed first column unless told not to, and the next `read_csv` picks them back
up as a real feature called "Unnamed: 0". Nothing crashes. The pipeline simply
trains on a row counter.
"""

import pandas as pd
import pytest

from dataset import build_dataset, main

RAW_ROWS = [
    {"age": 19, "sex": "female", "bmi": 27.9, "children": 0,
     "smoker": "yes", "region": "southwest", "charges": 16884.924},
    {"age": 18, "sex": "male", "bmi": 33.77, "children": 1,
     "smoker": "no", "region": "southeast", "charges": 1725.5523},
    {"age": 28, "sex": "male", "bmi": 33.0, "children": 3,
     "smoker": "no", "region": "southeast", "charges": 4449.462},
]


@pytest.fixture
def raw_frame():
    """Three rows in the real schema, straight from the Kaggle file."""
    return pd.DataFrame(RAW_ROWS)


class TestBuildDataset:
    def test_every_row_and_column_survives(self, raw_frame):
        """Consolidation is a pass-through today, so nothing may be lost."""
        built = build_dataset(raw_frame)

        assert built.shape == raw_frame.shape
        assert list(built.columns) == list(raw_frame.columns)

    def test_values_are_unchanged(self, raw_frame):
        """No cleaning happens here - `steps/clean.py` owns that."""
        pd.testing.assert_frame_equal(build_dataset(raw_frame), raw_frame)


class TestMain:
    @pytest.fixture
    def wired(self, tmp_path, raw_frame, monkeypatch):
        """Point `main()` at a temp folder instead of the real `data/`."""
        source = tmp_path / "insurance.csv"
        raw_frame.to_csv(source, index=False)

        monkeypatch.setattr(
            "dataset.load_config",
            lambda: {"data": {"source_path": "insurance.csv",
                              "data_path": "merged_data.csv"}},
        )
        monkeypatch.setattr("dataset.resolve", lambda relative: tmp_path / relative)
        return tmp_path

    def test_it_writes_the_configured_file(self, wired):
        written = main()

        assert written == wired / "merged_data.csv"
        assert written.exists()

    def test_no_index_column_comes_back(self, wired, raw_frame):
        """The whole reason `to_csv` is called with index=False."""
        reread = pd.read_csv(main())

        assert list(reread.columns) == list(raw_frame.columns)
        assert not any(c.startswith("Unnamed") for c in reread.columns)

    def test_the_round_trip_preserves_the_data(self, wired, raw_frame):
        reread = pd.read_csv(main())

        pd.testing.assert_frame_equal(reread, raw_frame)

    def test_a_missing_source_says_where_to_get_it(self, tmp_path, monkeypatch):
        """A first-time reader has no idea this data comes from Kaggle."""
        monkeypatch.setattr(
            "dataset.load_config",
            lambda: {"data": {"source_path": "insurance.csv",
                              "data_path": "merged_data.csv"}},
        )
        monkeypatch.setattr("dataset.resolve", lambda relative: tmp_path / relative)

        with pytest.raises(FileNotFoundError, match="Kaggle"):
            main()
