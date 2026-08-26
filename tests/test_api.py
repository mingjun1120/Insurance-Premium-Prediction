"""Tests for `app.py`, using FastAPI's TestClient.

`TestClient` calls the app in-process - no server, no port, no waiting. It
needs `httpx`, which arrives with fastapi.

The whole module needs the real `models/model.pkl`, because `app.py` builds its
`Predictor` at import time. That is the right behaviour for a container - a
server that starts without a model would only fail later, on a real request -
but it means these tests skip on a fresh clone until `dvc pull` has run.
"""

import pytest

from tests.conftest import requires_model

pytestmark = requires_model

VALID = {
    "age": 19, "sex": "female", "bmi": 27.9,
    "children": 0, "smoker": "yes", "region": "southwest",
}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import app

    return TestClient(app.app)


class TestHealth:
    def test_root_reports_ok(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_root_names_the_loaded_model(self, client):
        """Read from the artefact, not hardcoded, so it survives a retrain."""
        body = client.get("/").json()

        assert body["model"]
        assert isinstance(body["log_target"], bool)


class TestPredict:
    def test_a_valid_request_returns_a_premium(self, client):
        response = client.post("/predict", json=VALID)

        assert response.status_code == 200
        body = response.json()
        assert body["currency"] == "USD"
        assert body["model"]

    def test_the_premium_is_in_dollars(self, client):
        """The same log-transform guard as test_predict.py, over HTTP."""
        premium = client.post("/predict", json=VALID).json()["predicted_premium"]

        assert premium > 1000, (
            f"got {premium} - looks like log dollars. Does app.py still go "
            "through Predictor.predict_records?"
        )
        assert premium < 200_000

    def test_smoking_costs_more(self, client):
        smoker = client.post("/predict", json={**VALID, "smoker": "yes"}).json()
        non_smoker = client.post("/predict", json={**VALID, "smoker": "no"}).json()

        assert smoker["predicted_premium"] > non_smoker["predicted_premium"]

    def test_the_same_request_gives_the_same_answer(self, client):
        first = client.post("/predict", json=VALID).json()
        second = client.post("/predict", json=VALID).json()

        assert first == second


class TestValidation:
    """Every limit here comes from the training data, not from a guess."""

    @pytest.mark.parametrize(
        "field, value",
        [
            ("age", 17), ("age", 65),
            ("bmi", 14.9), ("bmi", 55.1),
            ("children", -1), ("children", 6),
        ],
    )
    def test_out_of_range_numbers_are_refused(self, client, field, value):
        response = client.post("/predict", json={**VALID, field: value})

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "field, value",
        [
            ("sex", "other"),
            ("smoker", "sometimes"),
            ("region", "mars"),
        ],
    )
    def test_unknown_categories_are_refused(self, client, field, value):
        response = client.post("/predict", json={**VALID, field: value})

        assert response.status_code == 422

    @pytest.mark.parametrize("field", list(VALID))
    def test_every_field_is_required(self, client, field):
        incomplete = {k: v for k, v in VALID.items() if k != field}

        assert client.post("/predict", json=incomplete).status_code == 422

    @pytest.mark.parametrize("value", [18, 64])
    def test_the_edges_of_the_range_are_accepted(self, client, value):
        """18 and 64 are the real min and max in the data - not off by one."""
        response = client.post("/predict", json={**VALID, "age": value})

        assert response.status_code == 200

    def test_the_refusal_says_what_was_wrong(self, client):
        """A 422 with no reason is nearly as unhelpful as a wrong answer."""
        detail = client.post("/predict", json={**VALID, "age": 90}).json()["detail"]

        assert detail
        assert "64" in str(detail), "the message should name the limit"


class TestDocs:
    def test_the_interactive_docs_render(self, client):
        assert client.get("/docs").status_code == 200

    def test_the_schema_lists_the_allowed_regions(self, client):
        """The enum is what turns the docs field into a dropdown."""
        schema = client.get("/openapi.json").json()
        person = schema["components"]["schemas"]["Person"]

        assert "southwest" in str(person)
