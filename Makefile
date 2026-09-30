.PHONY: setup sample-data data validate pipeline serve test lint loadtest drift rollback up down

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt && pip install --no-deps -e .

sample-data:
	python scripts/make_sample_data.py

data:
	bash scripts/download_data.sh

validate:
	python -m demand.data.schema

pipeline:
	python -m demand.pipeline.flow

serve:
	uvicorn demand.serving.app:app --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check src tests scripts

loadtest:
	locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 1m --host http://localhost:8000 --csv artifacts/loadtest

drift:
	python -m demand.monitoring.simulate_drift && python -m demand.monitoring.drift

rollback:
	python -m demand.registry.rollback

up:
	docker compose up --build -d

down:
	docker compose down
