"""Load settings from configs/config.yaml for the whole project."""
import os
from pathlib import Path

import yaml

# Project root folder. This file is src/demand/config.py, so go up 2 folders.
ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = ROOT / "configs" / "config.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """Read the YAML config file and return it as a dict."""
    # Always use utf-8 so the file reads the same on Windows, Mac and Linux.
    with open(path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


def get_mlflow_tracking_uri(config: dict) -> str:
    """Return the MLflow server address.

    The env var MLFLOW_TRACKING_URI wins over config.yaml, because the address
    is different inside Docker (http://mlflow:5000) and on a laptop
    (http://localhost:5000).
    """
    uri_from_env = os.environ.get("MLFLOW_TRACKING_URI")
    if uri_from_env:
        return uri_from_env

    uri_from_config = config["mlflow"]["tracking_uri"]
    return uri_from_config
