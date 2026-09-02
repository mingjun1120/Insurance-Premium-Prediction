"""Tests for `steps.predict` - above all, that answers come back in dollars.

The model is fitted on `log1p(charges)`. If anything ever removes the `expm1`
that undoes it, `predict` returns about 9.7 where the answer is $16,000. It
would not crash. It would not warn. It would just be wrong by a factor of a
thousand-odd, forever, until a human noticed.

That is what most of this file guards.

Most tests here build their own model through the `fake_bundle` fixture, so
they run on a fresh clone with no `dvc pull`. The few that check the real
shipped artefact are marked `requires_model`.
"""

import numpy as np
import pytest

from steps.predict import Predictor
from tests.conftest import CATEGORICAL, TARGET, requires_data, requires_model

ONE_PERSON = {
    "age": 19, "sex": "female", "bmi": 27.9,
    "children": 0, "smoker": "yes", "region": "southwest",
}


@pytest.fixture
def predictor(fake_bundle, monkeypatch):
    """A Predictor pointed at the temp bundle instead of models/model.pkl."""
    monkeypatch.setattr(
        "steps.predict.load_config",
        lambda: {"model": {"store_path": str(fake_bundle)}},
    )
    return Predictor()


class TestLoadModel:
    def test_bundle_fields_are_read_onto_the_instance(self, predictor):
        assert predictor.model_name == "RandomForestRegressor"
        assert predictor.use_log_target is True
        # `target` travels in the bundle for provenance only. Predictor unpacks
        # the other five keys onto itself and never needs this one, so assert it
        # on the bundle rather than on the instance.
        assert predictor.artefact["target"] == TARGET
        assert predictor.categorical_features == CATEGORICAL

    def test_missing_model_says_what_to_do(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "steps.predict.load_config",
            lambda: {"model": {"store_path": str(tmp_path)}},
        )

        with pytest.raises(FileNotFoundError, match="Run main.py"):
            Predictor()


class TestPredictionsAreInDollars:
    def test_a_single_prediction_is_a_plausible_premium(self, predictor):
        """The whole point. log1p space would return roughly 9-11."""
        premium = predictor.predict_records([ONE_PERSON])[0]

        assert premium > 1000, (
            f"got {premium:.2f} - looks like log dollars, not dollars. "
            "Has the expm1 in Predictor.predict been removed?"
        )
        assert premium < 200_000, f"got {premium:.2f} - implausibly large"

    def test_expm1_actually_runs(self, predictor):
        """Compare against the raw pipeline output, which is still in log space."""
        import pandas as pd

        frame = pd.DataFrame([ONE_PERSON], columns=predictor.feature_order)
        for column in predictor.categorical_features:
            frame[column] = frame[column].astype("category")

        raw = predictor.model.predict(frame)[0]
        returned = predictor.predict(frame)[0]

        assert returned == pytest.approx(np.expm1(raw))
        assert returned > raw * 100, "the transform was clearly not applied"

    def test_the_flag_is_obeyed_when_false(self, predictor, monkeypatch):
        """A model trained on raw dollars must not be exponentiated."""
        import pandas as pd

        monkeypatch.setattr(predictor, "use_log_target", False)
        frame = pd.DataFrame([ONE_PERSON], columns=predictor.feature_order)
        for column in predictor.categorical_features:
            frame[column] = frame[column].astype("category")

        raw = predictor.model.predict(frame)[0]

        assert predictor.predict(frame)[0] == pytest.approx(raw)


class TestPredictRecords:
    def test_key_order_does_not_matter(self, predictor):
        """Column order comes from the bundle, not from the caller's dict."""
        shuffled = {k: ONE_PERSON[k] for k in reversed(list(ONE_PERSON))}

        assert predictor.predict_records([ONE_PERSON]) == predictor.predict_records(
            [shuffled]
        )

    def test_extra_keys_are_ignored(self, predictor):
        """An API caller sending a spare field should not break anything."""
        with_extra = {**ONE_PERSON, "favourite_colour": "blue"}

        assert predictor.predict_records([with_extra]) == pytest.approx(
            predictor.predict_records([ONE_PERSON])
        )

    def test_many_records_come_back_in_order(self, predictor):
        older = {**ONE_PERSON, "age": 60, "smoker": "no"}
        results = predictor.predict_records([ONE_PERSON, older, ONE_PERSON])

        assert len(results) == 3
        assert results[0] == pytest.approx(results[2])

    def test_results_are_plain_floats(self, predictor):
        """numpy scalars do not serialise to JSON; FastAPI would fail on them."""
        for value in predictor.predict_records([ONE_PERSON]):
            assert type(value) is float

    def test_smoking_costs_more(self, predictor):
        smoker = predictor.predict_records([{**ONE_PERSON, "smoker": "yes"}])[0]
        non_smoker = predictor.predict_records([{**ONE_PERSON, "smoker": "no"}])[0]

        assert smoker > non_smoker


@requires_model
class TestTheRealArtefact:
    """Checks against the model actually shipped in models/model.pkl."""

    def test_it_loads_and_declares_itself(self):
        predictor = Predictor()

        assert predictor.model_name
        assert isinstance(predictor.use_log_target, bool)
        assert len(predictor.feature_order) == 6

    def test_it_predicts_in_dollars(self):
        premium = Predictor().predict_records([ONE_PERSON])[0]

        assert 1000 < premium < 200_000, f"got {premium:.2f}"


@requires_model
@requires_data
@pytest.mark.slow
def test_golden_rmse_has_not_moved():
    """The shipped model still scores what the README claims.

    This is the guard for the class of bug the CatBoost test-set leak was: a
    silent change in behaviour that breaks no test and raises no error, and is
    only visible by comparing a number against one written down earlier.

    Marked `slow` because it runs the whole pipeline. It is skipped by default;
    run it with `uv run pytest -m slow` after changing anything about training.

    Update the expected values here deliberately, as part of a commit that says
    why they changed.
    """
    from steps.clean import Cleaner
    from steps.ingest import Ingestion
    from steps.train import Trainer

    data = Cleaner(target=TARGET).clean_data(Ingestion().load_data())
    trainer = Trainer()
    features, target = trainer.feature_target_separator(data)
    _, X_test, _, y_test = trainer.train_test_split_data(features, target)

    rmse, mae, r2, mape = Predictor().evaluate_model(X_test, y_test)

    assert rmse == pytest.approx(4193, abs=1)
    assert mae == pytest.approx(1974, abs=1)
    assert r2 == pytest.approx(0.9043, abs=0.0001)
    assert mape == pytest.approx(0.1655, abs=0.0001)
