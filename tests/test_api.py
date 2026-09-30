"""Normal request -> 200; unknown store / missing field / wrong type / bad holiday / past date -> 422; Open=0 -> 0.

Owner: C/F

These tests use a small fake model, so they run without MLflow.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from demand.config import load_config
from demand.serving import app as app_module


class FakeModel:
    """Acts like DemandModel: knows stores 1-3 and sales up to 2015-05-31."""

    def __init__(self):
        self.config = load_config()
        self.was_called = False

    def known_stores(self) -> set[int]:
        return {1, 2, 3}

    def last_history_date(self) -> pd.Timestamp:
        return pd.Timestamp("2015-05-31")

    def predict_with_explanation(self, daily_rows: pd.DataFrame, top_n: int = 3):
        self.was_called = True
        predictions = pd.Series([5000.0] * len(daily_rows))
        top_features = [[{"feature": "Promo", "effect": 800.0}]] * len(daily_rows)
        return predictions, top_features


GOOD_REQUEST = {
    "store": 1,
    "date": "2015-06-02",
    "open": 1,
    "promo": 1,
    "state_holiday": "0",
    "school_holiday": 0,
}


@pytest.fixture
def fake_model(monkeypatch) -> FakeModel:
    model = FakeModel()
    monkeypatch.setitem(app_module.model_state, "model", model)
    monkeypatch.setitem(app_module.model_state, "version", "99")
    return model


@pytest.fixture
def client() -> TestClient:
    # No `with` block, so the startup step (loading from MLflow) does not run.
    return TestClient(app_module.app)


def request_with(**changes) -> dict:
    body = dict(GOOD_REQUEST)
    for key, value in changes.items():
        body[key] = value
    return body


def test_normal_request_returns_prediction(client, fake_model):
    response = client.post("/predict", json=GOOD_REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["predicted_sales"] == 5000.0
    assert body["model_version"] == "99"
    assert body["top_features"][0]["feature"] == "Promo"


def test_closed_store_returns_zero_without_calling_model(client, fake_model):
    response = client.post("/predict", json=request_with(open=0))
    assert response.status_code == 200
    assert response.json()["predicted_sales"] == 0.0
    assert fake_model.was_called is False


def test_unknown_store_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(store=9999))
    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]


def test_missing_field_is_422(client, fake_model):
    body = dict(GOOD_REQUEST)
    del body["store"]
    response = client.post("/predict", json=body)
    assert response.status_code == 422
    assert "store: Field required" in response.json()["details"]


def test_wrong_type_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(store="abc"))
    assert response.status_code == 422
    assert response.json()["details"][0].startswith("store:")


def test_bad_holiday_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(state_holiday="x"))
    assert response.status_code == 422
    assert response.json()["details"][0].startswith("state_holiday:")


def test_bad_date_format_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(date="02/06/2015"))
    assert response.status_code == 422


def test_past_date_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(date="2015-05-20"))
    assert response.status_code == 422
    assert "in the past" in response.json()["detail"]


def test_date_too_far_ahead_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(date="2015-06-30"))
    assert response.status_code == 422
    assert "too far ahead" in response.json()["detail"]


def test_extra_field_like_customers_is_422(client, fake_model):
    response = client.post("/predict", json=request_with(customers=500))
    assert response.status_code == 422


def test_predict_without_model_is_503(client, monkeypatch):
    monkeypatch.setitem(app_module.model_state, "model", None)
    response = client.post("/predict", json=GOOD_REQUEST)
    assert response.status_code == 503


def test_health_is_503_without_model(client, monkeypatch):
    monkeypatch.setitem(app_module.model_state, "model", None)
    assert client.get("/health").status_code == 503


def test_health_is_200_with_model(client, fake_model):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_info_shows_version(client, fake_model):
    response = client.get("/model-info")
    assert response.json()["version"] == "99"
    assert response.json()["last_known_sales_date"] == "2015-05-31"


def test_metrics_endpoint_works(client, fake_model):
    client.post("/predict", json=GOOD_REQUEST)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "demand_predictions_total" in response.text
