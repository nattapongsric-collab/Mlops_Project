# รายงาน: API พยากรณ์ใน Docker (feat/serving-predict) — 1 ต.ค. 2569

## ทำอะไรไป
1. **`src/demand/serving/schemas.py`** รูปแบบ request/response
   - request: `store`, `date`, `open`, `promo`, `state_holiday`, `school_holiday` (ส่งแค่ข้อมูลของวันนั้น ข้อมูลร้านอยู่ในโมเดลแล้ว)
   - ตรวจชนิดข้อมูล, ค่า 0/1, วันหยุดต้องเป็น "0"/"a"/"b"/"c", ฟิลด์แปลกๆ (เช่น `customers`) ถูกปฏิเสธ
2. **`src/demand/serving/app.py`** FastAPI
   - `POST /predict` พยากรณ์ 1 ร้าน 1 วัน พร้อม 3 ฟีเจอร์ที่มีผลมากที่สุด
   - **Cascade:** `open = 0` ตอบ 0 ทันทีโดยไม่เรียกโมเดล
   - ร้านที่ไม่มีจริง, วันที่ที่ผ่านมาแล้ว, วันที่ไกลเกิน 7 วัน → 422 พร้อมข้อความอธิบาย
   - `GET /health` 200 เมื่อมีโมเดล / 503 เมื่อยังไม่มี (API ไม่ล่มแม้ MLflow ยังไม่พร้อม)
   - `GET /model-info`, `POST /reload`, `GET /metrics` (Prometheus + ตัวนับ `demand_predictions_total` แยกว่าตอบด้วยโมเดลหรือ cascade)
3. **โมเดล** (`training/model_wrapper.py`, `training/explain.py`, `training/train.py`)
   - เก็บข้อมูลร้าน (`store_info.parquet`) ไว้ในโมเดลด้วย API จึงไม่ต้องอ่าน `store.csv`
   - top-3 features ใช้ `pred_contrib` ของ LightGBM (ค่า SHAP จากต้นไม้โดยตรง เร็วพอสำหรับ API)
4. **Docker**
   - API รัน 8 worker (`API_WORKERS` ใน `docker-compose.yml`), `OMP_NUM_THREADS=1`, `/metrics` รวมตัวเลขทุก worker
   - `POST /reload` ไปถึง worker เดียว จึงให้ worker นั้นแตะไฟล์สัญญาณ แล้ว worker อื่นโหลดใหม่ตาม
   - MLflow 3 ปฏิเสธ request จากชื่อ host `mlflow:5000` (กัน DNS rebinding) แก้ด้วย `--allowed-hosts`
5. **`loadtest/locustfile.py`** ผู้จัดการร้าน 50 คน ถามทุก 1–3 วินาที (90% ร้านเปิด, 10% ร้านปิด)
6. **test ใหม่ 15 ข้อ** ใน `tests/test_api.py` ใช้โมเดลปลอม รันได้โดยไม่ต้องมี MLflow

## ปัญหาที่เจอระหว่างทำ และแก้แล้ว
| ปัญหา | สาเหตุ | แก้ |
|---|---|---|
| `/health` ตอบ 503 "Invalid Host header" | MLflow 3 ไม่รับชื่อ host `mlflow` | เพิ่ม `--allowed-hosts` ใน docker-compose |
| load test p95 = 3.2 วินาที | API มี worker เดียว รับได้ ~19 request/วินาที | เพิ่มเป็น 8 worker |
| `/reload` เปลี่ยนโมเดลแค่ worker เดียว | request ไปถึงแค่ worker เดียว | ไฟล์สัญญาณให้ทุก worker โหลดใหม่ |

## วิธีรันและทดสอบ
```
docker compose up -d --build mlflow api
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"store\":1,\"date\":\"2015-06-02\",\"promo\":1}"
```
เปิดหน้าทดลองได้ที่ http://localhost:8000/docs | load test: `make loadtest` | test: `make test`

## ผลลัพธ์
- **What-if:** ร้าน 1 วันที่ 2 มิ.ย. 2015 ไม่มีโปร 4,561 → มีโปร 5,761 (Promo มีผล +864)
- **Input เสียทุกแบบได้ 422 พร้อมข้อความ:** ร้าน 9999, `store: "abc"`, `state_holiday: "x"`, วันที่ในอดีต, JSON ขาดครึ่ง
- **Load test (50 ผู้ใช้, 1 นาที):** p50 65 ms, **p95 130 ms**, p99 200 ms, 23.5 request/วินาที, **error 0%** → ผ่าน SLO (รายละเอียดใน `docs/slo.md`)
- **Reload/rollback:** เปลี่ยน champion เป็น v5 แล้ว `POST /reload` → เรียก `/model-info` 40 ครั้งเห็น v5 ทั้ง 40 ครั้ง, ย้อนกลับ v4 ก็เห็น v4 ทั้ง 40 ครั้ง
- **ความปลอดภัยตอน reload:** ลองชี้ champion ไปที่ v3 (โมเดลรุ่นเก่าที่ไม่มีข้อมูลร้าน) → reload ล้มเหลวพร้อมข้อความ แต่ API ยังใช้ v4 ต่อไม่ล่ม
- ruff ผ่าน, pytest 41 passed

## สถานะใน MLflow ตอนนี้
- `@champion` = version 4 (LightGBM, run `d3b71192`)
- version 1–3 เป็นรุ่นระหว่างพัฒนา (1–2 ช้า, 1–3 ใช้กับ API ใหม่ไม่ได้เพราะไม่มีข้อมูลร้าน), version 5 = Ridge ที่ใช้ทดสอบ reload

## ปัญหาที่ยังค้างและขั้นต่อไป
- ความจุสูงสุด ~100 request/วินาที ถ้าต้องมากกว่านี้ต้องทำให้การสร้างฟีเจอร์เร็วขึ้น (ตอนนี้ ~50 ms ต่อ request)
- API รับได้ครั้งละ 1 ร้าน 1 วัน การพยากรณ์ทุกร้านเป็นงานของ batch (`serving/batch.py`) ที่ยังไม่ได้ทำ
- วันที่พยากรณ์ได้คือ 1–7 มิ.ย. 2015 เท่านั้น จนกว่าจะอัปเดตประวัติยอดขาย (งาน stream/retrain วันที่ 4)
- `make rollback` ยังไม่มีโค้ด (ทดสอบข้างบนตั้ง alias ด้วยมือ)
- **ครบเป้าหมายวันที่ 1 แล้ว:** ข้อมูล → โมเดล → API ใน Docker วิ่งครบเส้น
