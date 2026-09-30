"""Time-based split into train/val/test/stream using dates in config. Never random.

Owner: A

Run from the project root:
    python -m demand.data.split
    python -m demand.data.split --train tests/fixtures/sample_train.csv --store tests/fixtures/sample_store.csv
"""
import argparse
from pathlib import Path

import pandas as pd

from demand.config import ROOT, load_config
from demand.data.ingest import load_raw_data

# The order matters: each period must start after the previous one ends.
SPLIT_NAMES = ["train", "val", "test", "stream"]


def check_split_dates(split_config: dict) -> None:
    """Stop with an error if the split periods in config overlap or are out of order."""
    previous_end = None
    for split_name in SPLIT_NAMES:
        start_text, end_text = split_config[split_name]
        start_date = pd.Timestamp(start_text)
        end_date = pd.Timestamp(end_text)

        if start_date > end_date:
            raise ValueError(f"split '{split_name}': start {start_text} is after end {end_text}")

        if previous_end is not None and start_date <= previous_end:
            raise ValueError(f"split '{split_name}' starts on {start_text}, before the previous split ends")

        previous_end = end_date


def split_by_date(data: pd.DataFrame, split_config: dict) -> dict[str, pd.DataFrame]:
    """Cut the data into train/val/test/stream by date (start and end dates included)."""
    check_split_dates(split_config)

    splits = {}
    for split_name in SPLIT_NAMES:
        start_text, end_text = split_config[split_name]
        start_date = pd.Timestamp(start_text)
        end_date = pd.Timestamp(end_text)

        in_period = (data["Date"] >= start_date) & (data["Date"] <= end_date)
        split_data = data[in_period].reset_index(drop=True)
        splits[split_name] = split_data

    return splits


def save_splits(splits: dict[str, pd.DataFrame], data_hash: str, output_folder: str | Path) -> None:
    """Save each split as a parquet file, plus the data hash in a text file."""
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    for split_name, split_data in splits.items():
        split_data.to_parquet(output_folder / f"{split_name}.parquet", index=False)

    # Training reads this file and logs the hash to MLflow.
    hash_file = output_folder / "data_hash.txt"
    hash_file.write_text(data_hash, encoding="utf-8")


def main() -> None:
    """Read raw data, split it by date, and save the result to data/processed/."""
    config = load_config()

    parser = argparse.ArgumentParser(description="Split Rossmann data by date.")
    parser.add_argument("--train", default=ROOT / config["paths"]["raw_train"], help="path to train.csv")
    parser.add_argument("--store", default=ROOT / config["paths"]["raw_store"], help="path to store.csv")
    parser.add_argument("--output", default=ROOT / config["paths"]["processed_dir"], help="output folder")
    args = parser.parse_args()

    data, data_hash = load_raw_data(args.train, args.store)
    splits = split_by_date(data, config["split"])
    save_splits(splits, data_hash, args.output)

    print(f"Data hash: {data_hash}")
    for split_name, split_data in splits.items():
        first_day = split_data["Date"].min().date()
        last_day = split_data["Date"].max().date()
        print(f"{split_name:>6}: {len(split_data):>9,} rows  ({first_day} to {last_day})")

    rows_in_splits = 0
    for split_data in splits.values():
        rows_in_splits = rows_in_splits + len(split_data)
    rows_not_used = len(data) - rows_in_splits
    print(f"Rows outside every split period: {rows_not_used}")


if __name__ == "__main__":
    main()
