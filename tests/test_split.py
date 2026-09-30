"""Splits don't overlap and respect date order.

Owner: A/F
"""
import pandas as pd
import pytest

from demand.config import ROOT, load_config
from demand.data.ingest import load_raw_data
from demand.data.split import SPLIT_NAMES, check_split_dates, split_by_date

SAMPLE_TRAIN = ROOT / "tests" / "fixtures" / "sample_train.csv"
SAMPLE_STORE = ROOT / "tests" / "fixtures" / "sample_store.csv"


@pytest.fixture
def sample_splits() -> dict[str, pd.DataFrame]:
    config = load_config()
    data, _ = load_raw_data(SAMPLE_TRAIN, SAMPLE_STORE)
    return split_by_date(data, config["split"])


def test_every_split_has_rows(sample_splits):
    for split_name in SPLIT_NAMES:
        assert len(sample_splits[split_name]) > 0


def test_splits_are_in_date_order_and_do_not_overlap(sample_splits):
    for index in range(len(SPLIT_NAMES) - 1):
        this_split = sample_splits[SPLIT_NAMES[index]]
        next_split = sample_splits[SPLIT_NAMES[index + 1]]
        assert this_split["Date"].max() < next_split["Date"].min()


def test_splits_match_config_dates(sample_splits):
    config = load_config()
    for split_name in SPLIT_NAMES:
        start_text, end_text = config["split"][split_name]
        split_data = sample_splits[split_name]
        assert split_data["Date"].min() >= pd.Timestamp(start_text)
        assert split_data["Date"].max() <= pd.Timestamp(end_text)


def test_no_row_is_lost_or_duplicated(sample_splits):
    data, _ = load_raw_data(SAMPLE_TRAIN, SAMPLE_STORE)
    total_rows_in_splits = 0
    for split_data in sample_splits.values():
        total_rows_in_splits = total_rows_in_splits + len(split_data)
    assert total_rows_in_splits == len(data)


def test_overlapping_dates_in_config_are_rejected():
    bad_split_config = {
        "train": ["2013-01-01", "2015-02-28"],  # ends after val starts
        "val": ["2015-01-01", "2015-04-30"],
        "test": ["2015-05-01", "2015-05-31"],
        "stream": ["2015-06-01", "2015-07-31"],
    }
    with pytest.raises(ValueError):
        check_split_dates(bad_split_config)
