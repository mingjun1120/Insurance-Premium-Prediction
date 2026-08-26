"""Tests for `steps.clean`, one per cleaning rule.

Each test starts from `tidy_frame` - twelve rows that should trip nothing - and
plants exactly one problem. When a test fails, there is only one thing it can
mean.

The real insurance data triggers almost none of these rules: it arrives with no
gaps, no constant columns and no high-cardinality columns. Testing against it
would prove the code runs, not that it works.
"""

import numpy as np
import pandas as pd

from steps.clean import Cleaner
from tests.conftest import TARGET


def cleaner():
    """A Cleaner shielding the project's real target column."""
    return Cleaner(target=TARGET)


class TestConvertDataTypes:
    def test_text_columns_become_category(self, tidy_frame):
        result = cleaner().convert_data_types(tidy_frame)

        for column in ["sex", "smoker", "region"]:
            assert result[column].dtype == "category"

    def test_numeric_columns_are_left_alone(self, tidy_frame):
        result = cleaner().convert_data_types(tidy_frame)

        for column in ["age", "bmi", "children", TARGET]:
            assert pd.api.types.is_numeric_dtype(result[column])


class TestHandleMissingValues:
    def test_mostly_empty_column_is_dropped(self, tidy_frame):
        # 10 of 12 empty, past the 50% bar
        tidy_frame["barely_recorded"] = [1.0, 2.0] + [np.nan] * 10

        result = cleaner().handle_missing_values(tidy_frame)

        assert "barely_recorded" not in result.columns

    def test_a_few_gaps_are_filled_not_dropped(self, tidy_frame):
        tidy_frame.loc[0, "bmi"] = np.nan
        tidy_frame.loc[1, "age"] = np.nan

        result = cleaner().handle_missing_values(tidy_frame)

        assert not result.isnull().any().any()
        assert len(result) == 12, "rows should be imputed, not deleted"

    def test_categorical_gap_is_filled_with_the_mode(self, tidy_frame):
        frame = cleaner().convert_data_types(tidy_frame)
        frame.loc[0, "smoker"] = None  # "no" is the mode, 8 of 12

        result = cleaner().handle_missing_values(frame)

        assert result.loc[0, "smoker"] == "no"

    def test_the_target_is_never_imputed_away(self, tidy_frame):
        # A row missing the target is useless for supervised learning, so it
        # should be dropped in stage 3 rather than quietly filled in.
        tidy_frame.loc[0, TARGET] = np.nan

        result = cleaner().handle_missing_values(tidy_frame)

        assert len(result) == 11
        assert not result[TARGET].isnull().any()

    def test_a_clean_frame_is_returned_untouched(self, tidy_frame):
        result = cleaner().handle_missing_values(tidy_frame)

        pd.testing.assert_frame_equal(result, tidy_frame)


class TestRemoveLowVarianceFeatures:
    def test_constant_numeric_column_is_dropped(self, tidy_frame):
        tidy_frame["policy_version"] = 1

        result = cleaner().remove_low_variance_constant_features(tidy_frame)

        assert "policy_version" not in result.columns

    def test_constant_categorical_column_is_dropped(self, tidy_frame):
        tidy_frame["country"] = "US"
        frame = cleaner().convert_data_types(tidy_frame)

        result = cleaner().remove_low_variance_constant_features(frame)

        assert "country" not in result.columns

    def test_numeric_column_just_under_the_bar_survives(self, tidy_frame):
        # 10 of 12 the same is 83%, below the 90% numeric limit
        tidy_frame["mostly_zero"] = [0] * 10 + [1, 2]

        result = cleaner().remove_low_variance_constant_features(tidy_frame)

        assert "mostly_zero" in result.columns

    def test_the_target_survives_even_if_constant(self, tidy_frame):
        tidy_frame[TARGET] = 5000.0

        result = cleaner().remove_low_variance_constant_features(tidy_frame)

        assert TARGET in result.columns


class TestRemoveOutliers:
    def test_nothing_is_removed(self, tidy_frame):
        # Notebook 02 decided the outliers are high-cost smokers - the customers
        # the model exists to price - so this step reports and keeps.
        tidy_frame.loc[0, "bmi"] = 200.0

        result = cleaner().remove_outliers(tidy_frame)

        assert len(result) == 12
        assert result.loc[0, "bmi"] == 200.0


class TestHighCardinality:
    def test_rare_categories_are_folded_into_other(self, tidy_frame):
        # 11 distinct values, city_0 repeated: past the limit of 10.
        # Categories are kept in frequency order until they cover 95% of rows,
        # which here means 10 of them; the last is folded away.
        tidy_frame["city"] = [f"city_{i}" for i in range(11)] + ["city_0"]
        frame = cleaner().convert_data_types(tidy_frame)

        result = cleaner().handle_high_cardinality_features(frame)

        original = {f"city_{i}" for i in range(11)}
        survivors = original & set(result["city"])

        assert "Other" in set(result["city"])
        assert len(survivors) == 10, "exactly one rare category should be folded away"

    def test_a_column_at_the_limit_is_left_alone(self, tidy_frame):
        # Exactly 10 distinct values - the rule needs *more* than 10
        tidy_frame["plan"] = [f"plan_{i}" for i in range(10)] + ["plan_0", "plan_1"]
        frame = cleaner().convert_data_types(tidy_frame)

        result = cleaner().handle_high_cardinality_features(frame)

        assert "Other" not in set(result["plan"])
        assert result["plan"].nunique() == 10

    def test_the_real_columns_are_never_grouped(self, tidy_frame):
        frame = cleaner().convert_data_types(tidy_frame)

        result = cleaner().handle_high_cardinality_features(frame)

        assert result["region"].nunique() == 4


class TestRemoveHighlyCorrelated:
    def test_one_of_a_duplicated_pair_is_dropped(self, tidy_frame):
        tidy_frame["age_in_months"] = tidy_frame["age"] * 12

        result = cleaner().remove_highly_correlated_features(tidy_frame)

        survivors = {"age", "age_in_months"} & set(result.columns)
        assert len(survivors) == 1, "exactly one of the pair should remain"

    def test_unrelated_columns_both_survive(self, tidy_frame):
        result = cleaner().remove_highly_correlated_features(tidy_frame)

        for column in ["age", "bmi", "children"]:
            assert column in result.columns

    def test_the_target_is_not_dropped_for_correlating(self, tidy_frame):
        # charges correlates strongly with smoking status and age; the target
        # must never be a candidate for removal.
        tidy_frame["charges_copy"] = tidy_frame[TARGET]

        result = cleaner().remove_highly_correlated_features(tidy_frame)

        assert TARGET in result.columns


class TestRemoveDuplicateRows:
    def test_repeated_row_is_removed(self, tidy_frame):
        doubled = pd.concat([tidy_frame, tidy_frame.iloc[[0]]], ignore_index=True)

        result = cleaner().remove_duplicate_rows(doubled)

        assert len(result) == 12

    def test_distinct_rows_are_kept(self, tidy_frame):
        result = cleaner().remove_duplicate_rows(tidy_frame)

        assert len(result) == 12


class TestCleanDataEndToEnd:
    def test_every_step_runs_in_order(self, tidy_frame):
        messy = tidy_frame.copy()
        messy["country"] = "US"                        # constant
        messy["age_in_months"] = messy["age"] * 12     # duplicated information
        messy.loc[0, "bmi"] = np.nan                   # a gap to impute
        messy = pd.concat([messy, messy.iloc[[1]]], ignore_index=True)  # duplicate row

        result = cleaner().clean_data(messy)

        assert "country" not in result.columns
        assert len({"age", "age_in_months"} & set(result.columns)) == 1
        assert not result.isnull().any().any()
        assert not result.duplicated().any()
        assert TARGET in result.columns

    def test_a_tidy_frame_survives_unchanged(self, tidy_frame):
        result = cleaner().clean_data(tidy_frame.copy())

        assert len(result) == 12
        assert set(result.columns) == set(tidy_frame.columns)
