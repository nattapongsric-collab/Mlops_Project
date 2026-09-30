"""Seasonal naive baseline: prediction = sales on same weekday last week.

Owner: B

If the store was closed (or had no data) on that day last week, we use the
store's average sales for that weekday instead, so one closed day does not
make the baseline predict 0 for an open day.
"""
import pandas as pd

from demand.features.build_features import build_features


def seasonal_naive_predict(
    rows: pd.DataFrame,
    sales_history: pd.DataFrame,
    store_weekday_mean: pd.DataFrame,
    config: dict,
) -> pd.Series:
    """Predict sales for `rows` as last week's sales on the same weekday."""
    # Reuse the shared feature code so the baseline sees exactly the same lag values.
    features = build_features(rows, sales_history, store_weekday_mean, config)

    # Use float so we can put averages (with decimals) into it below.
    prediction = features["sales_lag_7"].astype(float)

    # Closed last week -> use the store's normal sales for this weekday.
    closed_last_week = prediction == 0
    prediction[closed_last_week] = features.loc[closed_last_week, "store_weekday_mean_sales"]

    # Still empty (brand-new store) -> 0. Closed today -> 0 (cascade rule).
    prediction = prediction.fillna(0)
    prediction[features["Open"] == 0] = 0
    return prediction.reset_index(drop=True)
