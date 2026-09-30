"""The CI sample data has the Kaggle columns and covers every split period."""
import pandas as pd

from demand.config import ROOT, load_config

FIXTURES = ROOT / "tests" / "fixtures"

TRAIN_COLUMNS = [
    "Store", "DayOfWeek", "Date", "Sales", "Customers",
    "Open", "Promo", "StateHoliday", "SchoolHoliday",
]
STORE_COLUMNS = [
    "Store", "StoreType", "Assortment", "CompetitionDistance",
    "CompetitionOpenSinceMonth", "CompetitionOpenSinceYear",
    "Promo2", "Promo2SinceWeek", "Promo2SinceYear", "PromoInterval",
]


def test_sample_train_has_kaggle_columns():
    sample_train = pd.read_csv(FIXTURES / "sample_train.csv", dtype={"StateHoliday": str})
    assert list(sample_train.columns) == TRAIN_COLUMNS


def test_sample_store_has_kaggle_columns():
    sample_store = pd.read_csv(FIXTURES / "sample_store.csv")
    assert list(sample_store.columns) == STORE_COLUMNS


def test_sample_train_covers_every_split_period():
    config = load_config()
    sample_train = pd.read_csv(FIXTURES / "sample_train.csv", dtype={"StateHoliday": str})

    for split_name, (start_date, end_date) in config["split"].items():
        in_period = (sample_train["Date"] >= start_date) & (sample_train["Date"] <= end_date)
        rows_in_period = int(in_period.sum())
        assert rows_in_period > 0, f"no sample rows for split '{split_name}'"
