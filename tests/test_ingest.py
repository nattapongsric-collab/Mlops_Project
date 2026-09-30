"""Reading, merging and hashing the raw data.

Owner: A/F
"""
import shutil

from demand.config import ROOT
from demand.data.ingest import compute_data_hash, load_raw_data, read_train

SAMPLE_TRAIN = ROOT / "tests" / "fixtures" / "sample_train.csv"
SAMPLE_STORE = ROOT / "tests" / "fixtures" / "sample_store.csv"


def test_merge_keeps_every_sales_row():
    train = read_train(SAMPLE_TRAIN)
    merged, _ = load_raw_data(SAMPLE_TRAIN, SAMPLE_STORE)
    assert len(merged) == len(train)


def test_merge_adds_store_columns():
    merged, _ = load_raw_data(SAMPLE_TRAIN, SAMPLE_STORE)
    assert "StoreType" in merged.columns
    assert "CompetitionDistance" in merged.columns


def test_state_holiday_is_read_as_text():
    train = read_train(SAMPLE_TRAIN)
    for value in train["StateHoliday"].unique():
        assert isinstance(value, str)


def test_data_hash_is_the_same_for_the_same_files():
    first_hash = compute_data_hash([SAMPLE_TRAIN, SAMPLE_STORE])
    second_hash = compute_data_hash([SAMPLE_TRAIN, SAMPLE_STORE])
    assert first_hash == second_hash


def test_data_hash_changes_when_data_changes(tmp_path):
    changed_train = tmp_path / "train.csv"
    shutil.copy(SAMPLE_TRAIN, changed_train)
    with open(changed_train, "a", encoding="utf-8") as train_file:
        train_file.write("1,1,2015-08-01,100,10,1,0,0,0\n")

    original_hash = compute_data_hash([SAMPLE_TRAIN, SAMPLE_STORE])
    changed_hash = compute_data_hash([changed_train, SAMPLE_STORE])
    assert original_hash != changed_hash
