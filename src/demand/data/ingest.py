"""Read raw train.csv + store.csv, merge, compute data hash (used as data version).

Owner: A
"""
import hashlib
from pathlib import Path

import pandas as pd

# Read these columns as text. StateHoliday mixes 0 (number) and "a"/"b"/"c"
# in the Kaggle file, so reading it as text keeps every value the same type.
TEXT_COLUMNS = {
    "StateHoliday": str,
    "StoreType": str,
    "Assortment": str,
    "PromoInterval": str,
}


def read_train(train_path: str | Path) -> pd.DataFrame:
    """Read the daily sales file (train.csv) and turn Date into a real date."""
    train = pd.read_csv(train_path, dtype=TEXT_COLUMNS)
    train["Date"] = pd.to_datetime(train["Date"], format="%Y-%m-%d")
    return train


def read_store(store_path: str | Path) -> pd.DataFrame:
    """Read the store information file (store.csv)."""
    store = pd.read_csv(store_path, dtype=TEXT_COLUMNS)
    return store


def merge_train_and_store(train: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Add store information to every sales row.

    We use a left join so no sales row is lost. A store that is missing from
    store.csv gets empty store columns; the Pandera schema will catch it.
    """
    merged = train.merge(store, on="Store", how="left", validate="many_to_one")

    # Sort by store and date so later steps (lags, rolling) see days in order.
    merged = merged.sort_values(["Store", "Date"])
    merged = merged.reset_index(drop=True)
    return merged


def compute_data_hash(file_paths: list[str | Path]) -> str:
    """Return one SHA-256 hash for all given files.

    If any byte in any file changes, the hash changes. We log this hash to
    MLflow so every model is linked to the exact data it was trained on.
    """
    hasher = hashlib.sha256()
    for file_path in file_paths:
        with open(file_path, "rb") as data_file:
            # Read 1 MB at a time so a big file does not fill up memory.
            while True:
                chunk = data_file.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def load_raw_data(train_path: str | Path, store_path: str | Path) -> tuple[pd.DataFrame, str]:
    """Read both raw files, merge them, and return (merged data, data hash)."""
    train = read_train(train_path)
    store = read_store(store_path)
    merged = merge_train_and_store(train, store)
    data_hash = compute_data_hash([train_path, store_path])
    return merged, data_hash
