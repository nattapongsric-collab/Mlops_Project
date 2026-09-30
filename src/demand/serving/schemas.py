"""Pydantic request/response models. Invalid input -> 422 with readable message (instructor test cases).

Owner: C

Checks done here (no model needed):
  - every field has the right type, e.g. store must be a whole number
  - open / promo / school_holiday must be 0 or 1
  - state_holiday must be "0", "a", "b" or "c"
  - unknown extra fields (e.g. "customers") are rejected

Checks done in app.py (need the model): the store exists, and the date is
inside the 7-day forecast window.
"""
import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    """One store on one day. Example: 'What if store 1 runs a promo tomorrow?'"""

    # Reject fields we do not know, so a typo like "promo_" is not silently ignored.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "store": 1,
                "date": "2015-06-02",
                "open": 1,
                "promo": 1,
                "state_holiday": "0",
                "school_holiday": 0,
            }
        },
    )

    store: int = Field(ge=1, description="Store id, e.g. 1")
    date: datetime.date = Field(description="Day to forecast, format YYYY-MM-DD")
    open: Literal[0, 1] = Field(default=1, description="1 = store open, 0 = closed")
    promo: Literal[0, 1] = Field(default=0, description="1 = promo running that day")
    state_holiday: Literal["0", "a", "b", "c"] = Field(
        default="0", description='"0" = none, "a" = public, "b" = Easter, "c" = Christmas'
    )
    school_holiday: Literal[0, 1] = Field(default=0, description="1 = school holiday")


class FeatureEffect(BaseModel):
    """How much one feature pushed the prediction up (+) or down (-), in sales units."""

    feature: str
    effect: float


class PredictResponse(BaseModel):
    """Forecast for one store on one day."""

    store: int
    date: datetime.date
    predicted_sales: float
    model_version: str | None
    top_features: list[FeatureEffect]
    note: str | None = None
