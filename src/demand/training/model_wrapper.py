"""MLflow model that bundles everything serving needs into one package.

Owner: B

What is inside the logged model (team decision 1):
  - the trained sklearn Pipeline (preprocessing + model)
  - sales_history.parquet      recent daily sales per store, for lag/rolling features
  - store_weekday_mean.parquet store x weekday average from train, for missing values
  - config.yaml                the settings used at training time

The API only loads `models:/rossmann_demand@champion` and calls predict()
with raw rows. Features are built here with the same code as training.
"""
import joblib
import mlflow.pyfunc
import pandas as pd
import yaml

from demand.features.build_features import build_features


class DemandModel(mlflow.pyfunc.PythonModel):
    """Raw rows in -> sales predictions out. Closed stores (Open == 0) get 0."""

    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        """Load the pipeline, sales history and fallback table when the model is loaded."""
        self.pipeline = joblib.load(context.artifacts["sklearn_pipeline"])
        self.sales_history = pd.read_parquet(context.artifacts["sales_history"])
        self.store_weekday_mean = pd.read_parquet(context.artifacts["store_weekday_mean"])
        with open(context.artifacts["config"], encoding="utf-8") as config_file:
            self.config = yaml.safe_load(config_file)

    def predict(self, context, model_input: pd.DataFrame, params: dict | None = None) -> pd.Series:
        """Predict daily sales for each row of `model_input`."""
        rows = model_input.copy()
        rows["Date"] = pd.to_datetime(rows["Date"])

        features = build_features(rows, self.sales_history, self.store_weekday_mean, self.config)
        predictions = pd.Series(self.pipeline.predict(features), name="predicted_sales")

        # Sales can not be negative, and a closed store sells nothing (cascade rule).
        predictions = predictions.clip(lower=0)
        predictions[features["Open"] == 0] = 0
        return predictions
