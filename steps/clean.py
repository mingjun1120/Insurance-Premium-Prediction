"""Data cleaning, ported from notebook 02 section 3.2.

Each method mirrors one subsection of the notebook, in the same order, so the
pipeline and the notebook tell the same story. On the insurance dataset most of
these steps find nothing to do - the data arrives with no gaps, no constant
columns and no high-cardinality columns. They are here for the data you have not
seen yet: a cleaning pipeline that only handles today's data stops working the
first time the data changes.
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats

# Thresholds, matching notebook 02 exactly
MISSING_COLUMN_DROP_SHARE = 0.5  # a column emptier than this is dropped, not imputed
LOW_VARIANCE_NUMERIC = 90.0  # one value covering this share makes a numeric column useless
LOW_VARIANCE_CATEGORICAL = 95.0  # the same idea, at a higher bar for categoricals
CARDINALITY_THRESHOLD = 10  # more categories than this and the rare ones get grouped
CATEGORY_COVERAGE_TO_KEEP = 0.95  # keep categories until they cover this share of rows
CORRELATION_THRESHOLD = 0.8  # above this, two numeric columns say the same thing


class Cleaner:
    """Run notebook 02's cleaning steps over a raw DataFrame.

    The target column is shielded from every removal rule. Dropping rows or
    columns because of the thing you are trying to predict is how a pipeline
    quietly teaches itself a different problem from the one it was given.
    """

    def __init__(self, target):
        """
        Args:
            target (str): Name of the target column, read from
                `config['data']['target']`. It is never dropped, never imputed
                away and never used as grounds for removing a row.
        """
        self.target = target

    def clean_data(self, data):
        """Run every cleaning step, in notebook 02's order.

        Args:
            data (pandas.DataFrame): The raw frame from `steps.ingest`.

        Returns:
            pandas.DataFrame: The cleaned frame.

        Raises:
            Exception: Re-raised after logging, so a failure names the step it
                came from rather than surfacing far from its cause.

        Examples:
            >>> Cleaner("charges").clean_data(raw).shape
            (1337, 7)
        """
        try:
            data = self.convert_data_types(data)
            data = self.handle_missing_values(data)
            data = self.remove_low_variance_constant_features(data)
            data = self.remove_outliers(data)
            data = self.handle_high_cardinality_features(data)
            data = self.remove_highly_correlated_features(data)
            data = self.remove_duplicate_rows(data)
        except Exception as error:
            logging.error("Error while cleaning data: %s", error)
            raise
        return data

    def convert_data_types(self, data):
        """Convert every text column to the `category` dtype.

        LightGBM, XGBoost and CatBoost read this dtype natively, and the
        encoders used for the other two models expect it as well.

        Args:
            data (pandas.DataFrame): The raw frame.

        Returns:
            pandas.DataFrame: The same frame with object columns re-typed.
        """
        logging.info(" 1. CONVERTING DATA TYPES...")

        converted = data.select_dtypes(include="object").columns.tolist()
        for column in converted:
            data[column] = data[column].astype("category")

        logging.info("   - Converted to category: %s", converted or "nothing to convert")
        return data

    def handle_missing_values(self, data):
        """Fill or remove missing values, in three stages (notebook 02, 3.2.1).

        Stage 1 drops any column more than `MISSING_COLUMN_DROP_SHARE` empty,
        because imputing most of a column invents most of it. Stage 2 fills what
        is left: numeric columns by sampling their own distribution, categorical
        columns with the mode. Stage 3 drops any row still incomplete, which by
        then can only mean the target itself is missing.

        Args:
            data (pandas.DataFrame): The frame to fill.

        Returns:
            pandas.DataFrame: A frame with no missing values.
        """
        logging.info(" 2. HANDLING MISSING VALUES...")

        total_missing = int(data.isnull().sum().sum())
        if total_missing == 0:
            logging.info("   - No missing values. Nothing to impute or drop.")
            return data

        # Stage 1: drop the columns that are mostly empty
        share = data.isnull().mean()
        mostly_empty = [c for c in share[share > MISSING_COLUMN_DROP_SHARE].index
                        if c != self.target]
        if mostly_empty:
            data = data.drop(columns=mostly_empty)
            logging.info("   - Dropped mostly-empty columns: %s", mostly_empty)

        # Stage 2: fill what remains, by dtype
        for column in [c for c in data.columns[data.isnull().any()] if c != self.target]:
            if pd.api.types.is_numeric_dtype(data[column]):
                how = self._impute_numeric_by_kde(data, column)
            else:
                data[column] = data[column].fillna(data[column].mode().iloc[0])
                how = "mode"
            logging.info("   - Imputed '%s' using %s.", column, how)

        # Stage 3: drop any row that is still incomplete
        still_incomplete = int(data.isnull().any(axis=1).sum())
        if still_incomplete:
            data = data.dropna(axis=0, ignore_index=True)
            logging.info("   - Dropped %s rows that were still incomplete.", still_incomplete)

        logging.info(
            "   - Successfully handled missing values! The dataset now has %s rows and %s columns.",
            data.shape[0], data.shape[1],
        )
        return data

    @staticmethod
    def _impute_numeric_by_kde(data, column, random_state=42):
        """Fill a numeric column by sampling its own distribution.

        Fits a kernel density estimate to the values that are present - a smooth
        curve describing how they are spread out - then draws the replacements
        from that curve. This keeps the shape of the column, which filling with
        the mean or the median does not.

        Note:
            `data` is modified in place. The return value describes what was
            done; it is not the filled frame.

        Args:
            data (pandas.DataFrame): Frame holding the column. Modified in place.
            column (str): Name of the numeric column to fill.
            random_state (int, optional): Seed for the sampler, so a re-run
                produces the same values. Defaults to 42.

        Returns:
            str: Which method was used. Normally "KDE sampling", or
            "median (too few distinct values for KDE)" when the column has fewer
            than two distinct known values, because a density curve cannot be
            fitted to a single point.
        """
        known = data[column].dropna()
        n_missing = int(data[column].isna().sum())

        if known.nunique() < 2:
            data.loc[data[column].isna(), column] = known.median() if len(known) else 0
            return "median (too few distinct values for KDE)"

        kde = stats.gaussian_kde(known)
        data.loc[data[column].isna(), column] = kde.resample(
            size=n_missing, seed=random_state
        )[0]
        return "KDE sampling"

    def remove_low_variance_constant_features(self, data):
        """Drop columns where a single value covers almost every row (3.2.2).

        A column that is nearly always the same value carries almost no
        information for a model. Numeric and categorical columns get different
        bars, because a categorical column can legitimately be more concentrated
        before it stops being useful.

        Args:
            data (pandas.DataFrame): The frame to check.

        Returns:
            pandas.DataFrame: The frame with any such columns removed.
        """
        logging.info(" 3. REMOVING CONSTANT & LOW VARIANCE FEATURES...")

        drop_columns = []
        for columns, limit, label in [
            (data.select_dtypes(include="number").columns, LOW_VARIANCE_NUMERIC, "numeric"),
            (data.select_dtypes(include="category").columns, LOW_VARIANCE_CATEGORICAL,
             "categorical"),
        ]:
            for column in columns:
                if column == self.target:
                    continue
                counts = data[column].value_counts()
                if len(counts) == 0:
                    continue
                dominant_share = counts.iloc[0] / len(data) * 100
                if data[column].nunique() == 1 or dominant_share >= limit:
                    drop_columns.append(column)
                    logging.info(
                        "   - '%s' (%s): one value covers %.2f%% of rows, limit is %.0f%%.",
                        column, label, dominant_share, limit,
                    )

        if drop_columns:
            data = data.drop(columns=drop_columns)
            logging.info("   - Successfully dropped %s", drop_columns)
        else:
            logging.info("   - No constant or low variance columns to drop.")

        logging.info(
            "   - The dataset now has %s rows and %s columns.", data.shape[0], data.shape[1]
        )
        return data

    def remove_outliers(self, data):
        """Report outliers without removing any (notebook 02, 3.2.3).

        This step deliberately removes nothing. Notebook 02 examined the rows an
        IQR rule would flag and found they are high-cost smokers - roughly 10% of
        the data and about half of all smokers. They are not measurement errors;
        they are the expensive customers the model exists to price. Deleting them
        would train a model that has never seen the cases that matter most.

        The counts are still logged, because a sudden jump in flagged rows is
        worth noticing even when nothing is dropped.

        Args:
            data (pandas.DataFrame): The frame to inspect.

        Returns:
            pandas.DataFrame: The frame, unchanged.
        """
        logging.info(" 4. REVIEWING OUTLIERS (nothing is removed)...")

        for column in data.select_dtypes(include="number").columns:
            if column == self.target:
                continue
            q1, q3 = data[column].quantile(0.25), data[column].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            flagged = int(
                ((data[column] < q1 - 1.5 * iqr) | (data[column] > q3 + 1.5 * iqr)).sum()
            )
            logging.info(
                "   - '%s': %s rows outside the IQR whiskers (%.1f%%), kept.",
                column, flagged, flagged / len(data) * 100,
            )

        logging.info("   - Every row is retained, by the decision recorded in notebook 02.")
        return data

    def handle_high_cardinality_features(self, data):
        """Fold rare categories into "Other" where a column has too many (3.2.4).

        A column with many categories produces many near-empty groups, which a
        model cannot learn anything from. Categories are kept in frequency order
        until they cover `CATEGORY_COVERAGE_TO_KEEP` of the rows; the rest become
        a single "Other" level.

        Args:
            data (pandas.DataFrame): The frame to check.

        Returns:
            pandas.DataFrame: The frame with rare categories grouped.
        """
        logging.info(" 5. HANDLING HIGH CARDINALITY FEATURES...")

        high_cardinality = [
            c for c in data.select_dtypes(include="category").columns
            if c != self.target and data[c].nunique() > CARDINALITY_THRESHOLD
        ]

        if not high_cardinality:
            logging.info(
                "   - No column has more than %s categories. Nothing to group.",
                CARDINALITY_THRESHOLD,
            )
            return data

        for column in high_cardinality:
            before = data[column].nunique()
            data[column], kept = self._group_rare_categories(data[column])
            logging.info(
                "   - Grouped '%s': %s categories -> %s, including 'Other'.",
                column, before, kept + 1,
            )

        logging.info(
            "   - The dataset now has %s rows and %s columns.", data.shape[0], data.shape[1]
        )
        return data

    @staticmethod
    def _group_rare_categories(series, coverage=CATEGORY_COVERAGE_TO_KEEP):
        """Keep the most common categories, then label the remainder "Other".

        Args:
            series (pandas.Series): A categorical column.
            coverage (float, optional): Cumulative share of rows the kept
                categories should cover, between 0 and 1. Defaults to
                CATEGORY_COVERAGE_TO_KEEP.

        Returns:
            tuple[pandas.Series, int]: The regrouped column, still of dtype
            `category`, and the number of original categories kept. The result
            holds `kept + 1` levels once "Other" is counted. The single most
            common category is always kept, even when it alone already exceeds
            `coverage`.
        """
        share = series.value_counts(normalize=True)
        keep = list(share.index[share.cumsum() <= coverage]) or [share.index[0]]
        grouped = series.astype("object").where(series.isin(keep), "Other")
        return grouped.astype("category"), len(keep)

    def remove_highly_correlated_features(self, data, threshold=CORRELATION_THRESHOLD):
        """Drop one of every pair of numeric columns that say the same thing (3.2.5).

        Two columns correlated above the threshold carry duplicate information.
        The second of each pair is dropped, keeping the first.

        Args:
            data (pandas.DataFrame): The frame to check.
            threshold (float, optional): Absolute correlation above which a pair
                counts as duplicated. Defaults to CORRELATION_THRESHOLD.

        Returns:
            pandas.DataFrame: The frame with duplicated columns removed.
        """
        logging.info(" 6. REMOVING HIGHLY CORRELATED FEATURES...")

        numeric = data.select_dtypes(include="number").drop(
            columns=[self.target], errors="ignore"
        )
        if numeric.shape[1] < 2:
            logging.info("   - Fewer than two numeric columns. Nothing to compare.")
            return data

        correlation = numeric.corr().abs()
        # Only the upper triangle, so each pair is considered once
        upper = correlation.where(np.triu(np.ones(correlation.shape), k=1).astype(bool))

        drop_columns = []
        for column in upper.columns:
            partners = upper.index[upper[column] > threshold].tolist()
            for partner in partners:
                logging.info(
                    "   - '%s' and '%s' correlate at %.3f, above %.2f.",
                    partner, column, upper.loc[partner, column], threshold,
                )
                if column not in drop_columns:
                    drop_columns.append(column)

        if drop_columns:
            data = data.drop(columns=drop_columns)
            logging.info("   - Successfully dropped %s", drop_columns)
        else:
            logging.info("   - No pair of numeric columns correlates above %.2f.", threshold)

        logging.info(
            "   - The dataset now has %s rows and %s columns.", data.shape[0], data.shape[1]
        )
        return data

    def remove_duplicate_rows(self, data):
        """Drop repeated rows, keeping the first of each (3.2.6).

        Args:
            data (pandas.DataFrame): The frame to check.

        Returns:
            pandas.DataFrame: The frame with duplicates removed and the index
            reset.
        """
        logging.info(" 7. REMOVING DUPLICATE ROWS...")

        duplicate_count = int(data.duplicated().sum())
        if duplicate_count:
            data = data.drop_duplicates(ignore_index=True)
            logging.info("   - Removed %s duplicated rows.", duplicate_count)
        else:
            logging.info("   - No duplicate rows.")

        logging.info(
            "   - The dataset now has %s rows and %s columns.", data.shape[0], data.shape[1]
        )
        return data
