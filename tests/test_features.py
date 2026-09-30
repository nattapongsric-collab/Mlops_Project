"""Features are deterministic; Customers never present; same output for train and serve paths.

Owner: B/F
"""
import pandas as pd
import pytest

from demand.config import ROOT, load_config
from demand.data.ingest import load_raw_data
from demand.features.build_features import (
    build_features,
    get_feature_columns,
    make_store_weekday_mean,
)
from demand.training.evaluate import compute_metrics

SAMPLE_TRAIN = ROOT / "tests" / "fixtures" / "sample_train.csv"
SAMPLE_STORE = ROOT / "tests" / "fixtures" / "sample_store.csv"


@pytest.fixture
def sample_data() -> pd.DataFrame:
    data, _ = load_raw_data(SAMPLE_TRAIN, SAMPLE_STORE)
    return data


@pytest.fixture
def config() -> dict:
    return load_config()


def make_features_for_may_2015(data: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = data[(data["Date"] >= "2015-05-01") & (data["Date"] <= "2015-05-31")]
    history = data[data["Date"] <= "2015-05-31"]
    weekday_mean = make_store_weekday_mean(data[data["Date"] <= "2014-12-31"])
    return build_features(rows, history, weekday_mean, config)


def test_customers_is_never_a_feature(sample_data, config):
    features = make_features_for_may_2015(sample_data, config)
    assert "Customers" not in features.columns
    assert "Customers" not in get_feature_columns(config)


def test_sales_is_never_a_feature(sample_data, config):
    features = make_features_for_may_2015(sample_data, config)
    assert "Sales" not in features.columns


def test_features_are_deterministic(sample_data, config):
    first = make_features_for_may_2015(sample_data, config)
    second = make_features_for_may_2015(sample_data, config)
    pd.testing.assert_frame_equal(first, second)


def test_no_empty_sales_features_after_fallback(sample_data, config):
    features = make_features_for_may_2015(sample_data, config)
    for column in features.columns:
        if column.startswith("sales_"):
            assert features[column].isna().sum() == 0, column


def test_lag_7_is_sales_from_7_days_before(sample_data, config):
    rows = sample_data[(sample_data["Store"] == 1) & (sample_data["Date"] == "2015-05-12")]
    history = sample_data[sample_data["Date"] <= "2015-05-31"]
    weekday_mean = make_store_weekday_mean(sample_data[sample_data["Date"] <= "2014-12-31"])
    features = build_features(rows, history, weekday_mean, config)

    week_before = sample_data[(sample_data["Store"] == 1) & (sample_data["Date"] == "2015-05-05")]
    assert features["sales_lag_7"].iloc[0] == week_before["Sales"].iloc[0]


def test_future_sales_do_not_change_features(sample_data, config):
    """Changing sales in the last 6 days before a date must not change its features (no leakage)."""
    target_day = pd.Timestamp("2015-05-20")
    rows = sample_data[sample_data["Date"] == target_day]
    weekday_mean = make_store_weekday_mean(sample_data[sample_data["Date"] <= "2014-12-31"])

    history = sample_data[sample_data["Date"] <= "2015-05-31"].copy()
    normal_features = build_features(rows, history, weekday_mean, config)

    # Multiply sales from 14 May to 31 May by 10. The features for 20 May may only use
    # sales up to 13 May (7 days before), so nothing should change.
    changed_history = history.copy()
    recent = changed_history["Date"] >= target_day - pd.Timedelta(days=6)
    changed_history.loc[recent, "Sales"] = changed_history.loc[recent, "Sales"] * 10
    changed_features = build_features(rows, changed_history, weekday_mean, config)

    pd.testing.assert_frame_equal(normal_features, changed_features)


def test_row_order_is_kept(sample_data, config):
    rows = sample_data[sample_data["Date"] == "2015-05-20"].iloc[::-1]  # reversed order
    history = sample_data[sample_data["Date"] <= "2015-05-31"]
    weekday_mean = make_store_weekday_mean(sample_data[sample_data["Date"] <= "2014-12-31"])
    features = build_features(rows, history, weekday_mean, config)
    assert list(features["Store"]) == list(rows["Store"])


def test_lag_shorter_than_horizon_is_rejected(sample_data, config):
    config["features"]["lags"] = [1, 7]
    with pytest.raises(ValueError):
        make_features_for_may_2015(sample_data, config)


def test_wape_counts_only_open_days_with_sales():
    actual = pd.Series([100.0, 200.0, 0.0, 50.0])
    predicted = pd.Series([110.0, 180.0, 999.0, 999.0])
    is_open = pd.Series([1, 1, 1, 0])
    metrics = compute_metrics(actual, predicted, is_open)
    # Only the first two rows count: (10 + 20) / (100 + 200) = 0.1
    assert metrics["wape"] == pytest.approx(0.1)
    assert metrics["rows_scored"] == 2
