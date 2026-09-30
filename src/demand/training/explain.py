"""SHAP / feature importance. Return top-3 drivers per prediction.

Owner: B

For LightGBM we use `pred_contrib=True`, which gives SHAP values straight
from the trees. It is much faster than the shap library, so the API stays
under the 200 ms latency target.
"""
import pandas as pd
from sklearn.pipeline import Pipeline


def top_features_for_rows(pipeline: Pipeline, features: pd.DataFrame, top_n: int = 3) -> list[list[dict]]:
    """For each row, return the `top_n` features that moved the prediction the most.

    Each item looks like {"feature": "Promo", "effect": 812.4}.
    effect > 0 means this feature pushed the predicted sales up, < 0 means down.
    Returns an empty list per row for models that are not LightGBM.
    """
    model = pipeline.named_steps["model"]
    if model.__class__.__name__ != "LGBMRegressor":
        empty_result = []
        for _ in range(len(features)):
            empty_result.append([])
        return empty_result

    # One column per feature + one last column for the base value (average prediction).
    contributions = model.predict(features, pred_contrib=True)
    feature_names = list(features.columns)

    result = []
    for row_contributions in contributions:
        feature_effects = []
        for feature_index, feature_name in enumerate(feature_names):
            effect = float(row_contributions[feature_index])
            feature_effects.append({"feature": feature_name, "effect": round(effect, 1)})

        # Biggest effect first, no matter if it pushed up or down.
        feature_effects.sort(key=lambda item: abs(item["effect"]), reverse=True)
        result.append(feature_effects[:top_n])
    return result
