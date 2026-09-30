"""sklearn preprocessing (imputation, outlier clipping, encoding) packaged inside the model Pipeline.

Owner: B

Putting preprocessing inside the sklearn Pipeline means the saved model
carries it along, so serving cannot forget a step (no training-serving skew).
"""
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Columns that are categories, not amounts. Ridge needs them one-hot encoded.
CATEGORY_COLUMNS = [
    "DayOfWeek",
    "month",
    "state_holiday_code",
    "store_type_code",
    "assortment_code",
]


def make_ridge_pipeline(feature_columns: list[str], config: dict) -> Pipeline:
    """Ridge regression: fill gaps, scale numbers, one-hot encode categories."""
    number_columns = []
    for column in feature_columns:
        # Store id is just a label, not an amount, so Ridge should not use it as a number.
        if column not in CATEGORY_COLUMNS and column != "Store":
            number_columns.append(column)

    number_steps = Pipeline(
        steps=[
            ("fill_missing", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    category_steps = OneHotEncoder(handle_unknown="ignore")

    preprocessor = ColumnTransformer(
        transformers=[
            ("numbers", number_steps, number_columns),
            ("categories", category_steps, CATEGORY_COLUMNS),
        ]
    )

    model = Ridge(alpha=config["models"]["ridge"]["alpha"])
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def make_lightgbm_pipeline(config: dict) -> Pipeline:
    """LightGBM handles missing values and number-coded categories by itself."""
    lightgbm_settings = config["models"]["lightgbm"]
    model = LGBMRegressor(
        n_estimators=lightgbm_settings["n_estimators"],
        learning_rate=lightgbm_settings["learning_rate"],
        num_leaves=lightgbm_settings["num_leaves"],
        random_state=config["seed"],
        verbose=-1,
    )
    return Pipeline(steps=[("model", model)])


def make_model_pipeline(model_name: str, feature_columns: list[str], config: dict) -> Pipeline:
    """Return an untrained sklearn Pipeline for 'ridge' or 'lightgbm'."""
    if model_name == "ridge":
        return make_ridge_pipeline(feature_columns, config)
    if model_name == "lightgbm":
        return make_lightgbm_pipeline(config)
    raise ValueError(f"unknown model name: {model_name}")
