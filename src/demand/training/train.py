"""Train model, log all 6 items to MLflow: git commit, data hash, params, metrics, artifacts, pip freeze.

Owner: B

Run from the project root (run `python -m demand.data.split` first):
    python -m demand.training.train --model naive
    python -m demand.training.train --model ridge
    python -m demand.training.train --model lightgbm

The 6 items logged for every run (rule 6):
  1. git commit hash  -> tag "git_commit"
  2. data hash        -> tag "data_hash" (from data/processed/data_hash.txt)
  3. hyperparameters  -> params
  4. metrics          -> val_* and test_* metrics
  5. artifacts        -> the model package + feature list
  6. environment      -> pip_freeze.txt
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import joblib
import mlflow
import mlflow.pyfunc
import pandas as pd
import yaml

from demand.config import ROOT, get_mlflow_tracking_uri, load_config
from demand.features.build_features import (
    build_features,
    get_feature_columns,
    make_store_weekday_mean,
)
from demand.features.preprocess import make_model_pipeline
from demand.training.baselines import seasonal_naive_predict
from demand.training.evaluate import compute_metrics
from demand.training.model_wrapper import DemandModel

MODEL_NAMES = ["naive", "ridge", "lightgbm"]

# How many days of sales history the served model keeps. It needs at least
# biggest lag or rolling window (28) + horizon (7) days; 60 gives some room.
HISTORY_DAYS_FOR_SERVING = 60


def get_git_commit() -> str:
    """Return the current git commit hash, or 'unknown' if git is not available."""
    # Inside Docker there is no .git folder, so allow passing it in as an env var.
    commit_from_env = os.environ.get("GIT_COMMIT")
    if commit_from_env:
        return commit_from_env
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        print("WARNING: could not read git commit hash, logging 'unknown'")
        return "unknown"


def has_uncommitted_changes() -> str:
    """Return 'true' if there are code changes not yet committed, 'false' if clean, 'unknown' without git.

    A run trained on uncommitted code can not be reproduced from its commit hash,
    so we log this next to the commit hash.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    if result.stdout.strip() == "":
        return "false"
    return "true"


def get_pip_freeze() -> str:
    """Return the output of `pip freeze` (the exact library versions of this run)."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True
    )
    return result.stdout


def load_splits(processed_folder: Path) -> dict[str, pd.DataFrame]:
    """Read train/val/test parquet files made by demand.data.split."""
    splits = {}
    for split_name in ["train", "val", "test"]:
        split_path = processed_folder / f"{split_name}.parquet"
        if not split_path.exists():
            raise FileNotFoundError(f"{split_path} not found. Run `python -m demand.data.split` first.")
        splits[split_name] = pd.read_parquet(split_path)
    return splits


def rows_to_train_on(data: pd.DataFrame) -> pd.DataFrame:
    """Train only on open days with sales. Closed days are handled by the cascade rule (Open == 0 -> 0)."""
    keep = (data["Open"] == 1) & (data["Sales"] > 0)
    return data[keep].reset_index(drop=True)


def log_model_package(
    pipeline,
    sales_history: pd.DataFrame,
    store_weekday_mean: pd.DataFrame,
    config: dict,
    input_example: pd.DataFrame,
) -> float:
    """Save the model + its data files as one MLflow pyfunc model. Returns the pipeline size in MB."""
    with tempfile.TemporaryDirectory() as temp_folder:
        temp_folder = Path(temp_folder)

        pipeline_path = temp_folder / "pipeline.joblib"
        history_path = temp_folder / "sales_history.parquet"
        weekday_mean_path = temp_folder / "store_weekday_mean.parquet"
        config_path = temp_folder / "config.yaml"

        joblib.dump(pipeline, pipeline_path)
        sales_history.to_parquet(history_path, index=False)
        store_weekday_mean.to_parquet(weekday_mean_path, index=False)
        with open(config_path, "w", encoding="utf-8") as config_file:
            yaml.safe_dump(config, config_file)

        model_size_mb = pipeline_path.stat().st_size / (1024 * 1024)

        mlflow.pyfunc.log_model(
            name="model",
            python_model=DemandModel(),
            artifacts={
                "sklearn_pipeline": str(pipeline_path),
                "sales_history": str(history_path),
                "store_weekday_mean": str(weekday_mean_path),
                "config": str(config_path),
            },
            code_paths=[str(ROOT / "src" / "demand")],
            input_example=input_example,
        )
    return model_size_mb


def train_and_log(model_name: str, config: dict, processed_folder: Path) -> str:
    """Train one model, evaluate it on val and test, log everything to MLflow. Returns the run id."""
    splits = load_splits(processed_folder)
    train_data = splits["train"]
    val_data = splits["val"]
    test_data = splits["test"]
    data_hash = (processed_folder / "data_hash.txt").read_text(encoding="utf-8").strip()

    # Fallback values come from TRAIN only, so val/test never leak into training.
    store_weekday_mean = make_store_weekday_mean(train_data)

    # History for lag/rolling features: everything up to the end of the period we predict.
    # Every sales feature looks back at least 7 days, so it never sees the day it predicts.
    history_for_train = train_data
    history_for_val = pd.concat([train_data, val_data], ignore_index=True)
    history_for_test = pd.concat([train_data, val_data, test_data], ignore_index=True)

    feature_columns = get_feature_columns(config)
    pipeline = None

    if model_name == "naive":
        val_predictions = seasonal_naive_predict(val_data, history_for_val, store_weekday_mean, config)
        test_predictions = seasonal_naive_predict(test_data, history_for_test, store_weekday_mean, config)
        params = {"model": "naive"}
    else:
        train_rows = rows_to_train_on(train_data)
        train_features = build_features(train_rows, history_for_train, store_weekday_mean, config)
        pipeline = make_model_pipeline(model_name, feature_columns, config)
        print(f"Training {model_name} on {len(train_rows):,} rows ...")
        pipeline.fit(train_features, train_rows["Sales"])

        val_features = build_features(val_data, history_for_val, store_weekday_mean, config)
        test_features = build_features(test_data, history_for_test, store_weekday_mean, config)
        val_predictions = pd.Series(pipeline.predict(val_features)).clip(lower=0)
        test_predictions = pd.Series(pipeline.predict(test_features)).clip(lower=0)
        # Cascade rule: a closed store sells nothing.
        val_predictions[val_features["Open"] == 0] = 0
        test_predictions[test_features["Open"] == 0] = 0

        params = {"model": model_name}
        for setting_name, setting_value in config["models"][model_name].items():
            params[setting_name] = setting_value

    params["seed"] = config["seed"]
    params["lags"] = str(config["features"]["lags"])
    params["rolling_windows"] = str(config["features"]["rolling_windows"])
    params["horizon_days"] = config["features"]["horizon_days"]

    val_metrics = compute_metrics(val_data["Sales"], val_predictions, val_data["Open"])
    test_metrics = compute_metrics(test_data["Sales"], test_predictions, test_data["Open"])

    with mlflow.start_run(run_name=model_name) as run:
        # 1 + 2: code version and data version
        mlflow.set_tag("git_commit", get_git_commit())
        mlflow.set_tag("git_uncommitted_changes", has_uncommitted_changes())
        mlflow.set_tag("data_hash", data_hash)
        mlflow.set_tag("model_type", model_name)
        # 3: hyperparameters
        mlflow.log_params(params)
        # 4: metrics
        for metric_name, metric_value in val_metrics.items():
            mlflow.log_metric(f"val_{metric_name}", metric_value)
        for metric_name, metric_value in test_metrics.items():
            mlflow.log_metric(f"test_{metric_name}", metric_value)
        # 5: artifacts
        mlflow.log_text("\n".join(feature_columns), "feature_columns.txt")
        if pipeline is not None:
            # Serving history = the last 60 days we know (up to the end of the test period).
            last_known_day = history_for_test["Date"].max()
            first_history_day = last_known_day - pd.Timedelta(days=HISTORY_DAYS_FOR_SERVING)
            recent_history = history_for_test[history_for_test["Date"] > first_history_day]
            recent_history = recent_history[["Store", "Date", "Sales", "Open"]]

            input_example = test_data.drop(columns=["Sales", "Customers"]).head(5)
            model_size_mb = log_model_package(
                pipeline, recent_history, store_weekday_mean, config, input_example
            )
            mlflow.log_metric("model_size_mb", model_size_mb)
        # 6: environment
        mlflow.log_text(get_pip_freeze(), "pip_freeze.txt")

        run_id = run.info.run_id

    print(f"Run id: {run_id}")
    print(f"  val  WAPE {val_metrics['wape']:.4f}  bias {val_metrics['bias']:+.4f}")
    print(f"  test WAPE {test_metrics['wape']:.4f}  bias {test_metrics['bias']:+.4f}")
    return run_id


def main() -> None:
    """Parse the command line and train one model."""
    config = load_config()

    parser = argparse.ArgumentParser(description="Train one model and log it to MLflow.")
    parser.add_argument("--model", choices=MODEL_NAMES, required=True)
    parser.add_argument("--processed", default=ROOT / config["paths"]["processed_dir"])
    args = parser.parse_args()

    mlflow.set_tracking_uri(get_mlflow_tracking_uri(config))
    mlflow.set_experiment(config["mlflow"]["experiment"])
    train_and_log(args.model, config, Path(args.processed))


if __name__ == "__main__":
    main()
