"""Register model version in MLflow and move @champion alias if gating passed.

Owner: D

Run from the project root:
    python -m demand.registry.promote --run-id <run id from train.py>

NOTE (day 1 skeleton): gating is not written yet, so this script promotes
the model directly. On day 3, call demand.training.gating here first and only
move @champion when every gate passes.
"""
import argparse

import mlflow
from mlflow import MlflowClient

from demand.config import get_mlflow_tracking_uri, load_config


def register_model(run_id: str, model_name: str) -> str:
    """Register the model logged in `run_id`. Returns the new version number."""
    model_uri = f"runs:/{run_id}/model"
    model_version = mlflow.register_model(model_uri, model_name)
    return model_version.version


def set_alias(model_name: str, alias: str, version: str) -> None:
    """Point `alias` (e.g. champion) at `version` of the registered model."""
    client = MlflowClient()
    client.set_registered_model_alias(model_name, alias, version)


def main() -> None:
    """Register a run's model and make it the champion."""
    config = load_config()

    parser = argparse.ArgumentParser(description="Register a model and set @champion.")
    parser.add_argument("--run-id", required=True, help="MLflow run id printed by train.py")
    args = parser.parse_args()

    mlflow.set_tracking_uri(get_mlflow_tracking_uri(config))
    model_name = config["mlflow"]["model_name"]
    champion_alias = config["mlflow"]["champion_alias"]

    version = register_model(args.run_id, model_name)
    set_alias(model_name, champion_alias, version)
    print(f"Registered {model_name} version {version} and set @{champion_alias}")


if __name__ == "__main__":
    main()
