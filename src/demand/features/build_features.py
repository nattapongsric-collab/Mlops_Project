"""Single source of truth for feature engineering, used by BOTH training and serving (prevents training-serving skew). Drop Customers. Calendar, promo, holiday, competition, lag/rolling features.

Owner: B

How it works
------------
build_features(rows, sales_history, store_weekday_mean, config)
  rows               the days we want to predict (Store, Date, Open, Promo, ... + store columns)
  sales_history      past daily sales (Store, Date, Sales, Open) used for lag/rolling features
  store_weekday_mean average sales per (Store, DayOfWeek) from the train set, used when a
                     lag/rolling value is missing (e.g. stores with no data in late 2014)

Every sales-based feature looks back at least `horizon_days` (7) days, so a
forecast made 7 days ahead never uses sales that have not happened yet.
"""
import pandas as pd

# Fixed text -> number maps. Fixed maps give the same numbers in training and serving.
STATE_HOLIDAY_CODES = {"0": 0, "a": 1, "b": 2, "c": 3}
STORE_TYPE_CODES = {"a": 0, "b": 1, "c": 2, "d": 3}
ASSORTMENT_CODES = {"a": 0, "b": 1, "c": 2}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]


def get_feature_columns(config: dict) -> list[str]:
    """Return the list of feature column names the model uses, in a fixed order."""
    feature_columns = [
        "Store",
        "DayOfWeek",
        "Open",
        "Promo",
        "SchoolHoliday",
        "state_holiday_code",
        "store_type_code",
        "assortment_code",
        "year",
        "month",
        "day_of_month",
        "week_of_year",
        "competition_distance",
        "competition_open_months",
        "Promo2",
        "is_promo2_month",
        "store_weekday_mean_sales",
    ]
    for lag in config["features"]["lags"]:
        feature_columns.append(f"sales_lag_{lag}")
    for window in config["features"]["rolling_windows"]:
        feature_columns.append(f"sales_rolling_mean_{window}")
    return feature_columns


def make_store_weekday_mean(train_data: pd.DataFrame) -> pd.DataFrame:
    """Average sales per (Store, DayOfWeek) on open days. Build it from the TRAIN split only."""
    open_days = train_data[train_data["Open"] == 1]
    mean_table = open_days.groupby(["Store", "DayOfWeek"], as_index=False)["Sales"].mean()
    mean_table = mean_table.rename(columns={"Sales": "store_weekday_mean_sales"})
    return mean_table


def add_calendar_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add year, month, day of month and week of year from the Date column."""
    data["year"] = data["Date"].dt.year
    data["month"] = data["Date"].dt.month
    data["day_of_month"] = data["Date"].dt.day
    data["week_of_year"] = data["Date"].dt.isocalendar().week.astype(int)
    return data


def add_code_features(data: pd.DataFrame) -> pd.DataFrame:
    """Turn text columns (StateHoliday, StoreType, Assortment) into numbers."""
    data["state_holiday_code"] = data["StateHoliday"].map(STATE_HOLIDAY_CODES)
    data["store_type_code"] = data["StoreType"].map(STORE_TYPE_CODES)
    data["assortment_code"] = data["Assortment"].map(ASSORTMENT_CODES)
    return data


def add_competition_features(data: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Distance to the nearest competitor and how many months it has been open."""
    fill_distance = config["features"]["competition_distance_fill"]
    data["competition_distance"] = data["CompetitionDistance"].fillna(fill_distance)

    years_open = data["year"] - data["CompetitionOpenSinceYear"]
    months_open = years_open * 12 + (data["month"] - data["CompetitionOpenSinceMonth"])
    # Unknown opening date -> 0. A competitor that opens in the future -> 0 (not open yet).
    months_open = months_open.fillna(0)
    months_open = months_open.clip(lower=0)
    data["competition_open_months"] = months_open
    return data


def add_promo2_features(data: pd.DataFrame) -> pd.DataFrame:
    """is_promo2_month = 1 when the store runs Promo2 and this month is in its PromoInterval."""
    month_name = data["month"].apply(lambda month_number: MONTH_NAMES[month_number - 1])
    promo_interval = data["PromoInterval"].fillna("")

    is_promo2_month = []
    for name, interval, has_promo2 in zip(month_name, promo_interval, data["Promo2"], strict=True):
        if has_promo2 == 1 and name in interval.split(","):
            is_promo2_month.append(1)
        else:
            is_promo2_month.append(0)
    data["is_promo2_month"] = is_promo2_month
    return data


def add_lag_features(data: pd.DataFrame, sales_history: pd.DataFrame, config: dict) -> pd.DataFrame:
    """sales_lag_N = sales of the same store N days before.

    We match on real dates (not row positions), so missing days stay empty
    instead of taking a value from the wrong day.
    """
    horizon = config["features"]["horizon_days"]
    for lag in config["features"]["lags"]:
        if lag < horizon:
            raise ValueError(f"lag {lag} is shorter than the {horizon}-day horizon (data leakage)")

        lag_table = sales_history[["Store", "Date", "Sales"]].copy()
        # Sales on day D become the lag value for day D + lag.
        lag_table["Date"] = lag_table["Date"] + pd.Timedelta(days=lag)
        lag_table = lag_table.rename(columns={"Sales": f"sales_lag_{lag}"})
        data = data.merge(lag_table, on=["Store", "Date"], how="left")
    return data


def add_rolling_features(data: pd.DataFrame, sales_history: pd.DataFrame, config: dict) -> pd.DataFrame:
    """sales_rolling_mean_W = average sales on open days in the W days that end `horizon` days before.

    Example with W=7, horizon=7: for 15 Jan we average open days from 2 Jan to 8 Jan.
    This is the same as shift(7) then rolling(7), done with real dates.
    """
    horizon = config["features"]["horizon_days"]

    # Only open days count; closed days (Sales = 0) would pull the average down.
    open_history = sales_history[sales_history["Open"] == 1]

    for window in config["features"]["rolling_windows"]:
        rolling_parts = []
        for store_id, store_history in open_history.groupby("Store"):
            daily_sales = store_history.set_index("Date")["Sales"].sort_index()
            # Fill in missing calendar days as empty so "7D" really means 7 calendar days.
            daily_sales = daily_sales.asfreq("D")
            rolling_mean = daily_sales.rolling(f"{window}D", min_periods=1).mean()

            store_rolling = rolling_mean.reset_index()
            store_rolling.columns = ["Date", f"sales_rolling_mean_{window}"]
            store_rolling["Store"] = store_id
            rolling_parts.append(store_rolling)

        rolling_table = pd.concat(rolling_parts, ignore_index=True)
        # The average that ends on day D is used for day D + horizon.
        rolling_table["Date"] = rolling_table["Date"] + pd.Timedelta(days=horizon)
        data = data.merge(rolling_table, on=["Store", "Date"], how="left")
    return data


def fill_missing_sales_features(data: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Fill empty lag/rolling values with the store's average for that weekday (team decision 3)."""
    sales_columns = []
    for lag in config["features"]["lags"]:
        sales_columns.append(f"sales_lag_{lag}")
    for window in config["features"]["rolling_windows"]:
        sales_columns.append(f"sales_rolling_mean_{window}")

    for column in sales_columns:
        data[column] = data[column].fillna(data["store_weekday_mean_sales"])
    return data


def build_features(
    rows: pd.DataFrame,
    sales_history: pd.DataFrame,
    store_weekday_mean: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Build every model feature for `rows`. Returns only the feature columns, same row order."""
    data = rows.copy()

    # Remove columns we must never use as features (Customers = leakage).
    for column in config["features"]["drop"]:
        if column in data.columns:
            data = data.drop(columns=column)

    # Only keep history for the stores we predict. For one API request this
    # turns 1,115 stores into 1 store, which keeps the API fast.
    stores_to_predict = data["Store"].unique()
    sales_history = sales_history[sales_history["Store"].isin(stores_to_predict)]

    # Remember the original order, because merges can reorder rows.
    data["row_order"] = range(len(data))

    data = add_calendar_features(data)
    data = add_code_features(data)
    data = add_competition_features(data, config)
    data = add_promo2_features(data)
    data = data.merge(store_weekday_mean, on=["Store", "DayOfWeek"], how="left")
    data = add_lag_features(data, sales_history, config)
    data = add_rolling_features(data, sales_history, config)
    data = fill_missing_sales_features(data, config)

    data = data.sort_values("row_order").reset_index(drop=True)
    feature_columns = get_feature_columns(config)
    return data[feature_columns]
