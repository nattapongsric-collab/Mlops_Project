"""FastAPI: POST /predict, GET /health, GET /metrics, GET /model-info. Cascade: Open==0 -> return 0 without calling model. Loads models:/<name>@champion.

Owner: C

Run locally (MLflow must be running):
    set MLFLOW_TRACKING_URI=http://localhost:5000
    uvicorn demand.serving.app:app --port 8000
Then open http://localhost:8000/docs

Endpoints
  POST /predict     forecast one store for one day (+ top 3 reasons)
  GET  /health      200 when a model is loaded, 503 when not
  GET  /model-info  which model version is serving
  POST /reload      load the current @champion again (after promote or rollback)
  GET  /metrics     numbers for Prometheus
"""
from contextlib import asynccontextmanager

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mlflow import MlflowClient
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

from demand.config import get_mlflow_tracking_uri, load_config
from demand.serving.schemas import PredictRequest, PredictResponse

CONFIG = load_config()

# Everything about the model that is currently serving. Tests replace "model" with a fake.
model_state = {
    "model": None,  # a DemandModel (see training/model_wrapper.py)
    "version": None,
    "run_id": None,
    "load_error": None,
}

PREDICTIONS_TOTAL = Counter(
    "demand_predictions_total",
    "Number of /predict answers, by how they were made",
    ["answered_by"],  # "model" or "cascade_closed"
)


def load_champion() -> None:
    """Load models:/<name>@champion from MLflow into model_state. Never raises."""
    model_name = CONFIG["mlflow"]["model_name"]
    alias = CONFIG["mlflow"]["champion_alias"]
    try:
        mlflow.set_tracking_uri(get_mlflow_tracking_uri(CONFIG))
        version_info = MlflowClient().get_model_version_by_alias(model_name, alias)
        loaded_model = mlflow.pyfunc.load_model(f"models:/{model_name}@{alias}")

        model_state["model"] = loaded_model.unwrap_python_model()
        model_state["version"] = str(version_info.version)
        model_state["run_id"] = version_info.run_id
        model_state["load_error"] = None
        print(f"Loaded {model_name} version {version_info.version} (@{alias})")
    except Exception as error:  # noqa: BLE001 - the API must start even without a model
        # Keep the old model (if any) so a failed reload does not take the API down.
        model_state["load_error"] = f"{type(error).__name__}: {error}"
        print(f"WARNING: could not load @{alias}: {model_state['load_error']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the champion once when the API starts."""
    load_champion()
    yield


app = FastAPI(title="Rossmann Daily Demand API", version="0.1.0", lifespan=lifespan)

# Adds request count / latency metrics and the GET /metrics endpoint.
Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.exception_handler(RequestValidationError)
async def readable_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """Turn pydantic's error list into short sentences like 'store: Input should be a valid integer'."""
    messages = []
    for problem in error.errors():
        # loc looks like ("body", "store"); skip the "body" part.
        field_path = []
        for part in problem["loc"]:
            if part != "body":
                field_path.append(str(part))
        field_name = ".".join(field_path)
        if field_name == "":
            field_name = "request"
        messages.append(f"{field_name}: {problem['msg']}")
    return JSONResponse(status_code=422, content={"error": "invalid input", "details": messages})


def check_store_and_date(request: PredictRequest, model) -> None:
    """Stop with 422 if the store is unknown or the date is outside the forecast window."""
    if request.store not in model.known_stores():
        raise HTTPException(status_code=422, detail=f"store {request.store} does not exist")

    last_known_day = model.last_history_date().date()
    horizon_days = model.config["features"]["horizon_days"]
    last_allowed_day = last_known_day + pd.Timedelta(days=horizon_days).to_pytimedelta()

    if request.date <= last_known_day:
        raise HTTPException(
            status_code=422,
            detail=f"date {request.date} is in the past; sales are already known up to {last_known_day}",
        )
    if request.date > last_allowed_day:
        raise HTTPException(
            status_code=422,
            detail=f"date {request.date} is too far ahead; we forecast up to {horizon_days} days, "
            f"so the last allowed date is {last_allowed_day}",
        )


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    """Forecast sales for one store on one day, with the 3 features that mattered most."""
    model = model_state["model"]

    if model is not None:
        check_store_and_date(request, model)

    # Cascade: a closed store sells nothing, so answer 0 without calling the model.
    if request.open == 0:
        PREDICTIONS_TOTAL.labels(answered_by="cascade_closed").inc()
        return PredictResponse(
            store=request.store,
            date=request.date,
            predicted_sales=0.0,
            model_version=model_state["version"],
            top_features=[],
            note="store is closed (open = 0), so sales are 0; the model was not called",
        )

    if model is None:
        raise HTTPException(status_code=503, detail="no model loaded yet; train and promote a model, then POST /reload")

    daily_row = pd.DataFrame(
        [
            {
                "Store": request.store,
                "DayOfWeek": request.date.isoweekday(),  # 1 = Monday ... 7 = Sunday, same as Kaggle
                "Date": pd.Timestamp(request.date),
                "Open": request.open,
                "Promo": request.promo,
                "StateHoliday": request.state_holiday,
                "SchoolHoliday": request.school_holiday,
            }
        ]
    )
    predictions, top_features = model.predict_with_explanation(daily_row, top_n=3)
    PREDICTIONS_TOTAL.labels(answered_by="model").inc()

    return PredictResponse(
        store=request.store,
        date=request.date,
        predicted_sales=round(float(predictions.iloc[0]), 2),
        model_version=model_state["version"],
        top_features=top_features[0],
    )


@app.get("/health")
def health() -> JSONResponse:
    """200 when a model is loaded and ready, 503 when not (Docker uses this)."""
    if model_state["model"] is None:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": model_state["load_error"] or "no model loaded"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "model_version": model_state["version"]})


@app.get("/model-info")
def model_info() -> dict:
    """Which model is serving, and the last day of sales it knows."""
    model = model_state["model"]
    last_known_day = None
    if model is not None:
        last_known_day = str(model.last_history_date().date())
    return {
        "model_name": CONFIG["mlflow"]["model_name"],
        "alias": CONFIG["mlflow"]["champion_alias"],
        "version": model_state["version"],
        "run_id": model_state["run_id"],
        "last_known_sales_date": last_known_day,
        "load_error": model_state["load_error"],
    }


@app.post("/reload")
def reload_model() -> dict:
    """Load @champion again, e.g. after promote or rollback, without restarting the container."""
    load_champion()
    if model_state["load_error"] is not None:
        raise HTTPException(status_code=503, detail=f"reload failed: {model_state['load_error']}")
    return model_info()
