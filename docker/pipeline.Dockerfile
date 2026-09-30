FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml .
COPY configs/ configs/
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .
CMD ["python", "-m", "demand.pipeline.flow"]
