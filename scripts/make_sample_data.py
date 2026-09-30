"""Create small fake Rossmann-like data for tests and CI.

The real Kaggle data is large and cannot be committed, so CI uses this
small sample instead. It has the same columns as train.csv / store.csv and
covers the full date range, so the time split in config.yaml still works.

Run from the project root:
    python scripts/make_sample_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

from demand.config import ROOT, load_config

NUMBER_OF_STORES = 10
START_DATE = "2013-01-01"
END_DATE = "2015-07-31"
OUTPUT_FOLDER = ROOT / "tests" / "fixtures"

# Store 3 has no data in the second half of 2014, like ~180 real stores.
STORE_WITH_GAP = 3
GAP_START = "2014-07-01"
GAP_END = "2014-12-31"


def make_store_table(random_generator: np.random.Generator) -> pd.DataFrame:
    """Build a fake store.csv table with one row per store."""
    rows = []
    for store_id in range(1, NUMBER_OF_STORES + 1):
        has_promo2 = int(random_generator.integers(0, 2))

        # Promo2 columns are empty when the store does not join Promo2 (like Kaggle).
        if has_promo2 == 1:
            promo2_since_week = int(random_generator.integers(1, 53))
            promo2_since_year = int(random_generator.integers(2009, 2015))
            promo_interval = "Jan,Apr,Jul,Oct"
        else:
            promo2_since_week = np.nan
            promo2_since_year = np.nan
            promo_interval = np.nan

        row = {
            "Store": store_id,
            "StoreType": random_generator.choice(["a", "b", "c", "d"]),
            "Assortment": random_generator.choice(["a", "b", "c"]),
            "CompetitionDistance": float(random_generator.integers(50, 20000)),
            "CompetitionOpenSinceMonth": float(random_generator.integers(1, 13)),
            "CompetitionOpenSinceYear": float(random_generator.integers(2000, 2015)),
            "Promo2": has_promo2,
            "Promo2SinceWeek": promo2_since_week,
            "Promo2SinceYear": promo2_since_year,
            "PromoInterval": promo_interval,
        }
        rows.append(row)

    store_table = pd.DataFrame(rows)

    # Real store.csv has missing competition info for some stores.
    store_table.loc[store_table["Store"] == 5, "CompetitionDistance"] = np.nan
    store_table.loc[store_table["Store"] == 5, "CompetitionOpenSinceMonth"] = np.nan
    store_table.loc[store_table["Store"] == 5, "CompetitionOpenSinceYear"] = np.nan
    return store_table


def make_sales_table(random_generator: np.random.Generator) -> pd.DataFrame:
    """Build a fake train.csv table with one row per store per day."""
    all_dates = pd.date_range(START_DATE, END_DATE, freq="D")
    rows = []

    for store_id in range(1, NUMBER_OF_STORES + 1):
        # Each store has its own normal sales level.
        base_sales = float(random_generator.integers(3000, 9000))

        for date in all_dates:
            day_of_week = date.dayofweek + 1  # Kaggle uses 1 = Monday ... 7 = Sunday

            # Promo runs in the first two weeks of each month, weekdays only.
            if date.day <= 14 and day_of_week <= 5:
                promo = 1
            else:
                promo = 0

            # A few fixed public holidays: "a" = public, "b" = Easter, "c" = Christmas.
            if date.month == 1 and date.day == 1:
                state_holiday = "a"
            elif date.month == 5 and date.day == 1:
                state_holiday = "a"
            elif date.month == 4 and date.day in (1, 2):
                state_holiday = "b"
            elif date.month == 12 and date.day in (25, 26):
                state_holiday = "c"
            else:
                state_holiday = "0"

            if date.month in (7, 8) or date.month == 12 and date.day >= 20:
                school_holiday = 1
            else:
                school_holiday = 0

            # Stores close on Sundays and public holidays.
            if day_of_week == 7 or state_holiday != "0":
                is_open = 0
            else:
                is_open = 1

            if is_open == 1:
                # Mondays sell more, promo adds 25%, December adds 20%, plus noise.
                sales = base_sales
                if day_of_week == 1:
                    sales = sales * 1.15
                if promo == 1:
                    sales = sales * 1.25
                if date.month == 12:
                    sales = sales * 1.20
                noise = random_generator.normal(loc=1.0, scale=0.08)
                sales = int(round(sales * noise))
                customers = int(round(sales / 9.5))
            else:
                sales = 0
                customers = 0

            row = {
                "Store": store_id,
                "DayOfWeek": day_of_week,
                "Date": date.strftime("%Y-%m-%d"),
                "Sales": sales,
                "Customers": customers,
                "Open": is_open,
                "Promo": promo,
                "StateHoliday": state_holiday,
                "SchoolHoliday": school_holiday,
            }
            rows.append(row)

    sales_table = pd.DataFrame(rows)

    # Remove the second half of 2014 for one store (missing data like the real set).
    is_gap_store = sales_table["Store"] == STORE_WITH_GAP
    is_in_gap = (sales_table["Date"] >= GAP_START) & (sales_table["Date"] <= GAP_END)
    sales_table = sales_table[~(is_gap_store & is_in_gap)]

    # Real data has a few days where the store is open but sold nothing.
    open_rows = sales_table[sales_table["Open"] == 1]
    zero_sales_index = open_rows.sample(n=5, random_state=42).index
    sales_table.loc[zero_sales_index, "Sales"] = 0
    sales_table.loc[zero_sales_index, "Customers"] = 0

    return sales_table


def main() -> None:
    """Create both sample files in tests/fixtures/."""
    config = load_config()
    random_generator = np.random.default_rng(config["seed"])

    store_table = make_store_table(random_generator)
    sales_table = make_sales_table(random_generator)

    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
    store_path = OUTPUT_FOLDER / "sample_store.csv"
    train_path = OUTPUT_FOLDER / "sample_train.csv"
    store_table.to_csv(store_path, index=False)
    sales_table.to_csv(train_path, index=False)

    print(f"Wrote {len(store_table)} stores to {store_path}")
    print(f"Wrote {len(sales_table)} sales rows to {train_path}")


if __name__ == "__main__":
    main()
