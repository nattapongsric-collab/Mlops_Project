# Rossmann Daily Demand Forecasting — MLOps

พยากรณ์ยอดขายรายวันของแต่ละร้านล่วงหน้า 7 วัน (CP413008)

## รันจากเครื่องเปล่า
```bash
git clone <repo-url> && cd rossmann-demand-mlops
cp .env.example .env
bash scripts/download_data.sh          # ต้องมี Kaggle API key
docker compose up --build -d            # mlflow, api, prometheus, grafana
docker compose run --rm pipeline        # รันทั้ง pipeline ด้วยคำสั่งเดียว
curl http://localhost:8000/health
```

| บริการ | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

ดูคำสั่งทั้งหมดใน `Makefile` และบริบทโปรเจคใน `CLAUDE.md`
