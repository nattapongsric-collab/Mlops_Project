"""Locust load test for POST /predict. Report p50, p95, throughput to docs/slo.md.

Owner: C

Run (API must be running on port 8000):
    locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 1m --host http://localhost:8000 --csv artifacts/loadtest
Results are written to artifacts/loadtest_stats.csv.
"""
import random

from locust import HttpUser, between, task

# Dates inside the forecast window of the current champion (sales known up to 2015-05-31).
FORECAST_DATES = [
    "2015-06-01",
    "2015-06-02",
    "2015-06-03",
    "2015-06-04",
    "2015-06-05",
    "2015-06-06",
    "2015-06-07",
]
NUMBER_OF_STORES = 1115


class StoreManager(HttpUser):
    """A store manager trying what-if questions: one request every 1-3 seconds.

    50 managers like this send about 25 requests per second, our expected peak.
    (The nightly batch forecast covers the bulk of predictions, not this API.)
    """

    wait_time = between(1, 3)

    @task(9)
    def predict_open_store(self) -> None:
        request_body = {
            "store": random.randint(1, NUMBER_OF_STORES),
            "date": random.choice(FORECAST_DATES),
            "open": 1,
            "promo": random.randint(0, 1),
            "state_holiday": "0",
            "school_holiday": random.randint(0, 1),
        }
        self.client.post("/predict", json=request_body, name="/predict (open)")

    @task(1)
    def predict_closed_store(self) -> None:
        request_body = {
            "store": random.randint(1, NUMBER_OF_STORES),
            "date": random.choice(FORECAST_DATES),
            "open": 0,
        }
        self.client.post("/predict", json=request_body, name="/predict (closed, cascade)")
