"""Config loading and the MLFLOW_TRACKING_URI override."""
from demand.config import get_mlflow_tracking_uri, load_config


def test_config_has_seed_42():
    config = load_config()
    assert config["seed"] == 42


def test_customers_is_dropped_in_config():
    config = load_config()
    assert "Customers" in config["features"]["drop"]


def test_mlflow_uri_comes_from_config_when_env_is_empty(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    config = load_config()
    assert get_mlflow_tracking_uri(config) == config["mlflow"]["tracking_uri"]


def test_mlflow_uri_env_var_wins_over_config(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    config = load_config()
    assert get_mlflow_tracking_uri(config) == "http://localhost:5000"
