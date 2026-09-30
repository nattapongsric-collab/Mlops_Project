FROM python:3.12-slim
WORKDIR /app
# LightGBM needs the OpenMP library (libgomp1), which the slim image does not include.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml .
COPY configs/ configs/
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .

# API_WORKERS: how many copies of the API run in parallel (set in docker-compose.yml).
# OMP_NUM_THREADS=1: each prediction is tiny, so one CPU thread per worker is fastest.
# PROMETHEUS_MULTIPROC_DIR: lets /metrics add up the numbers from every worker.
ENV API_WORKERS=1 \
    OMP_NUM_THREADS=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
# Empty the metrics folder on every start, then run the API with API_WORKERS workers.
CMD rm -rf "$PROMETHEUS_MULTIPROC_DIR" && mkdir -p "$PROMETHEUS_MULTIPROC_DIR" && \
    uvicorn demand.serving.app:app --host 0.0.0.0 --port 8000 --workers "$API_WORKERS"
