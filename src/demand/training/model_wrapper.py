"""MLflow model that bundles everything serving needs into one package.

Owner: B

What is inside the logged model (team decision 1):
  - the trained sklearn Pipeline (preprocessing + model)
  - sales_history.parquet      recent daily sales per store, for lag/rolling features
  - store_weekday_mean.parquet store x weekday average from train, for missing values
  - store_info.parquet         one row per store from store.csv (StoreType, competition, ...)
  - config.yaml                the settings used at training time

The API only loads `models:/rossmann_demand@champion` and calls predict()
with daily rows (Store, DayOfWeek, Date, Open, Promo, StateHoliday,
SchoolHoliday). Store details and features are added here with the same
code as training.
"""
import joblib
import mlflow.pyfunc
import pandas as pd
import yaml

from demand.features.build_features import build_features
from demand.training.explain import top_features_for_rows

# Columns that describe the store (from store.csv), not the day.
STORE_INFO_COLUMNS = [
    "Store",
    "StoreType",
    "Assortment",
    "CompetitionDistance",
    "CompetitionOpenSinceMonth",
    "CompetitionOpenSinceYear",
    "Promo2",
    "Promo2SinceWeek",
    "Promo2SinceYear",
    "PromoInterval",
]


class DemandModel(mlflow.pyfunc.PythonModel):
    """Daily rows in -> sales predictions out. Closed stores (Open == 0) get 0."""

    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        """Load the pipeline and its data files when the model is loaded."""
        self.pipeline = joblib.load(context.artifacts["sklearn_pipeline"])
        self.sales_history = pd.read_parquet(context.artifacts["sales_history"])
        self.store_weekday_mean = pd.read_parquet(context.artifacts["store_weekday_mean"])
        self.store_info = pd.read_parquet(context.artifacts["store_info"])
        with open(context.artifacts["config"], encoding="utf-8") as config_file:
            self.config = yaml.safe_load(config_file)

    def known_stores(self) -> set[int]:
        """Store ids this model knows about."""
        return set(self.store_info["Store"].tolist())

    def last_history_date(self) -> pd.Timestamp:
        """The last day with known sales inside the model."""
        return self.sales_history["Date"].max()

    def make_features(self, daily_rows: pd.DataFrame) -> pd.DataFrame:
        """Add store details to the daily rows, then build model features."""
        rows = daily_rows.copy()
        rows["Date"] = pd.to_datetime(rows["Date"])

        # Callers send only daily columns; drop any store columns and use our own copy.
        for column in STORE_INFO_COLUMNS:
            if column != "Store" and column in rows.columns:
                rows = rows.drop(columns=column)
        rows = rows.merge(self.store_info, on="Store", how="left")

        return build_features(rows, self.sales_history, self.store_weekday_mean, self.config)

    def predict(self, context, model_input: pd.DataFrame, params: dict | None = None) -> pd.Series:
        """Predict daily sales for each row of `model_input`."""
        features = self.make_features(model_input)
        predictions = pd.Series(self.pipeline.predict(features), name="predicted_sales")

        # Sales can not be negative, and a closed store sells nothing (cascade rule).
        predictions = predictions.clip(lower=0)
        predictions[features["Open"] == 0] = 0
        return predictions

    def predict_with_explanation(self, daily_rows: pd.DataFrame, top_n: int = 3) -> tuple[pd.Series, list]:
        """Return (predictions, top features per row). Used by the API."""
        features = self.make_features(daily_rows)
        predictions = pd.Series(self.pipeline.predict(features), name="predicted_sales")
        predictions = predictions.clip(lower=0)
        predictions[features["Open"] == 0] = 0

        top_features = top_features_for_rows(self.pipeline, features, top_n)
        return predictions, top_features
