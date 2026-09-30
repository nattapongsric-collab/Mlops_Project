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
CMD ["python", "-m", "demand.pipeline.flow"]
