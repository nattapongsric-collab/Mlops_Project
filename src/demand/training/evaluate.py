"""WAPE, bias, per-store metrics. WAPE computed on open days only.

Owner: B

Rows counted in every metric: Open == 1 AND Sales > 0 (team decision 2).
"""
import numpy as np
import pandas as pd


def rows_to_score(actual_sales: pd.Series, is_open: pd.Series) -> pd.Series:
    """True for rows we count in the metrics: store open and sales above 0."""
    return (is_open == 1) & (actual_sales > 0)


def wape(actual_sales: np.ndarray, predicted_sales: np.ndarray) -> float:
    """Weighted Absolute Percentage Error = sum(|actual - predicted|) / sum(actual)."""
    total_error = np.abs(actual_sales - predicted_sales).sum()
    total_sales = actual_sales.sum()
    return float(total_error / total_sales)


def bias(actual_sales: np.ndarray, predicted_sales: np.ndarray) -> float:
    """sum(predicted - actual) / sum(actual). Positive = we predict too high."""
    total_difference = (predicted_sales - actual_sales).sum()
    total_sales = actual_sales.sum()
    return float(total_difference / total_sales)


def under_forecast_rate(actual_sales: np.ndarray, predicted_sales: np.ndarray) -> float:
    """Share of store-days where we predicted too low (risk of running out of stock)."""
    too_low = predicted_sales < actual_sales
    return float(too_low.mean())


def over_forecast_value(actual_sales: np.ndarray, predicted_sales: np.ndarray) -> float:
    """Total sales value we predicted above the actual (extra stock we would buy)."""
    extra = predicted_sales - actual_sales
    extra = np.clip(extra, 0, None)
    return float(extra.sum())


def compute_metrics(actual_sales: pd.Series, predicted_sales: pd.Series, is_open: pd.Series) -> dict:
    """Return all metrics as a dict, using only open days with sales > 0."""
    keep = rows_to_score(actual_sales, is_open).to_numpy()
    actual = actual_sales.to_numpy(dtype=float)[keep]
    predicted = np.asarray(predicted_sales, dtype=float)[keep]

    metrics = {
        "wape": wape(actual, predicted),
        "bias": bias(actual, predicted),
        "under_forecast_rate": under_forecast_rate(actual, predicted),
        "over_forecast_value": over_forecast_value(actual, predicted),
        "rows_scored": int(keep.sum()),
    }
    return metrics
