# CLAUDE.md — Rossmann Daily Demand Forecasting (MLOps)

ไฟล์นี้บอกบริบทของโปรเจคให้ Claude (และสมาชิกทุกคน) อ่านก่อนเริ่มทำงานทุกครั้ง

## 1. โปรเจคนี้คืออะไร
- รายวิชา **CP413008 Machine Learning Engineering for Production** (ภาค 1/2569)
- **ส่งงาน: 5 ต.ค. 2569 เวลา 23:59** | **นำเสนอ: 12 ต.ค. 2569 08:30** (12 นาที + ถามตอบ 3 นาที)
- โจทย์: **พยากรณ์ยอดขายรายวันของแต่ละร้าน ล่วงหน้า 7 วัน** เพื่อให้ผู้จัดการร้าน/ฝ่ายจัดซื้อวางแผนสต็อกและพนักงาน
- ข้อมูล: Kaggle **Rossmann Store Sales** ใช้เฉพาะ `train.csv` (1,115 ร้าน, ม.ค. 2013 – ก.ค. 2015, ~1 ล้านแถว) + `store.csv`
  - `test.csv` ของ Kaggle **ไม่มียอดขาย ห้ามใช้**
- คะแนนทั้งหมดมาจาก**งานวิศวกรรม** ไม่ใช่ความแม่นของโมเดล ให้ความสำคัญกับระบบที่วิ่งครบทั้งเส้นก่อนเสมอ

## 2. กฎเหล็ก (ห้ามละเมิด)
1. **ห้ามใช้คอลัมน์ `Customers` เป็นฟีเจอร์** เพราะตอนพยากรณ์ยังไม่รู้ค่านี้ (data leakage)
2. **แบ่งข้อมูลตามเวลาเท่านั้น ห้ามสุ่ม** ช่วงวันที่อยู่ใน `configs/config.yaml`
   | ชุด | ช่วง |
   |---|---|
   | train | 2013-01-01 – 2014-12-31 |
   | val | 2015-01-01 – 2015-04-30 |
   | test | 2015-05-01 – 2015-05-31 |
   | stream (จำลองข้อมูลหลังขึ้นระบบ) | 2015-06-01 – 2015-07-31 |
3. **โค้ดแปลงข้อมูลมีที่เดียวคือ `src/demand/features/`** ทั้ง training และ serving ต้อง import จากที่นี่ ห้ามเขียนซ้ำใน API (กัน Training-Serving Skew)
4. **ทุกค่าที่ตั้งได้อยู่ใน `configs/config.yaml`** (path, วันที่, seed, threshold, SLO) ห้าม hard-code
5. **Seed = 42 ทุกจุด** และ pin เวอร์ชันไลบรารีใน `requirements.txt`
6. **ทุกการทดลองต้อง log ลง MLflow ครบ 6 อย่าง:** git commit hash, data hash, hyperparameters, metrics, artifacts, environment (`pip freeze`)
7. **ห้าม commit ตรงเข้า `main`** ทุกงานทำใน branch แล้วเปิด Pull Request (อาจารย์ดูประวัติ commit รายคน)
8. ข้อมูลเสียต้องทำให้ pipeline **หยุดและแจ้งเตือน** ห้ามกลืน error เงียบๆ
9. API ต้อง**ไม่ล่ม**กับ input แปลกๆ ต้องตอบ 422 พร้อมข้อความที่อ่านเข้าใจ
10. **ฟีเจอร์ที่ใช้ยอดขายในอดีตต้องย้อนอย่างน้อย 7 วัน (เท่ากับ horizon)** lag ใช้ 7/14/28 และ rolling ต้องคำนวณหลัง `shift(7)` เสมอ ห้ามใช้ `shift(1)` เพราะวัน t+7 จะเห็นยอดที่ยังไม่เกิด (data leakage)

## 2.1 การจัดการข้อมูล (ตกลงแล้ว)
- **ร้านที่ไม่มีข้อมูลครึ่งหลังปี 2014 (~180 ร้าน):** เก็บไว้ ถ้า lag/rolling ไม่มีค่า ให้ใช้ค่าเฉลี่ยยอดขายของร้านนั้นตามวันในสัปดาห์ (คำนวณจาก train เท่านั้น) แทน
- **`StateHoliday`:** อ่านเป็น string เสมอ ค่าที่ถูกต้องคือ `"0"`, `"a"`, `"b"`, `"c"`

## 3. สแตก
| หน้าที่ | เครื่องมือ | ตำแหน่งในโค้ด |
|---|---|---|
| Version Control | GitHub (branch + PR) | `.github/` |
| Container | Docker Compose | `docker-compose.yml`, `docker/` |
| Data Validation | Pandera | `src/demand/data/schema.py` |
| Experiment Tracking + Registry | MLflow (ใช้ **alias** `@champion` / `@challenger` ไม่ใช้ stages) | `src/demand/training/`, `src/demand/registry/` |
| Orchestration | Prefect | `src/demand/pipeline/flow.py` |
| Serving | FastAPI | `src/demand/serving/` |
| Monitoring | Evidently (drift) + Prometheus/Grafana (ระบบ) | `src/demand/monitoring/`, `monitoring/` |
| CI/CD | GitHub Actions | `.github/workflows/ci.yml` |
| Load test | Locust | `loadtest/` |
| Explainability | SHAP / LightGBM feature importance | `src/demand/training/explain.py` |

## 4. คำสั่งหลัก
```bash
make setup        # สร้าง venv + ติดตั้ง requirements
make data         # ดาวน์โหลด/วางข้อมูลลง data/raw
make validate     # ตรวจ schema (Pandera)
make pipeline     # รันทั้ง DAG: ingest → validate → split → train → evaluate → gate → register → deploy
make serve        # เปิด API ที่ http://localhost:8000
make test         # pytest
make lint         # ruff
make loadtest     # Locust → รายงาน p50/p95/throughput
make drift        # จำลอง data drift / concept drift แล้วรันการตรวจ
make rollback     # ย้าย @champion กลับไปเวอร์ชันก่อนหน้า
docker compose up --build   # รันทั้งระบบจากเครื่องเปล่า
```
- **Docker เป็นทางหลัก** เพราะสมาชิกใช้ทั้ง Windows, Mac และ Linux ทุกขั้นตอนต้องรันผ่าน `docker compose` ได้
- คำสั่ง `make` ใช้สะดวกบน Mac/Linux แต่ทุกงานต้องรันได้บน Windows ด้วย เช่น `python -m demand.xxx` สคริปต์ใหม่ให้เขียนเป็น Python แทน bash
- ที่อยู่ MLflow อ่านจาก env `MLFLOW_TRACKING_URI` ก่อน ถ้าไม่มีจึงใช้ค่าใน `config.yaml`

## 5. Metrics, Gating และ SLO
- **Optimizing metric:** WAPE = Σ|y−ŷ| / Σy วัดเฉพาะแถวที่ `Open == 1` **และ** `Sales > 0` (วันที่เปิดแต่ยอดเป็น 0 ไม่นับ)
- **Gating metric:** โมเดลจะได้เป็น `@champion` เมื่อผ่าน**ทุกข้อ**
  - WAPE ดีกว่า seasonal naive (ยอดวันเดียวกันสัปดาห์ก่อน) อย่างน้อย 10%
  - WAPE ไม่แย่กว่า champion ปัจจุบัน โดย**ประเมิน champion ใหม่บน test set เดียวกัน** (ถ้ายังไม่มี champion ถือว่าผ่านข้อนี้)
  - |Bias| ≤ 5%
  - p95 latency < 200 ms และขนาดโมเดล < 50 MB
    - ใน gate วัดเวลาพยากรณ์ของโมเดลแบบ offline (เรียกทีละ request หลายครั้งแล้วดู p95)
    - แล้วยืนยันกับ API จริงด้วย Locust (`make loadtest`) บันทึกผลลง `docs/slo.md`
- **ตัวชี้วัดทางธุรกิจ:** อัตราสินค้าขาดสต็อก (พยากรณ์ต่ำเกิน) และมูลค่าสต็อกส่วนเกิน (พยากรณ์สูงเกิน)
- **SLO:**
  - Batch forecast ทุกคืนต้องเสร็จก่อน 06:00
  - API: p95 < 200 ms, error rate < 0.5%, availability 99.5%

## 6. รูปแบบการให้บริการ (Hybrid + Cascade)
1. **Batch ทุกคืน:** พยากรณ์ทุกร้านล่วงหน้า 7 วัน เขียนลง `data/predictions/`
2. **Real-time API (what-if):** `POST /predict` เช่น "ถ้าพรุ่งนี้จัดโปรโมชัน ยอดจะเป็นเท่าไหร่"
3. **Cascade:** ถ้า `Open == 0` ตอบ 0 ทันทีโดยไม่เรียกโมเดล
- Endpoint: `/predict`, `/health`, `/metrics` (Prometheus), `/model-info`, `POST /reload`
- ทุก response ส่งฟีเจอร์ที่มีผลมากที่สุด 3 อันดับกลับไปด้วย (explainability)
- **ประวัติยอดขายสำหรับ lag/rolling ตอน serve:** ตอนเทรนให้บันทึกไฟล์ประวัติยอดขายล่าสุดของแต่ละร้าน (อย่างน้อย 28 วันบวก horizon) เป็น artifact คู่กับโมเดลใน MLflow แล้ว API โหลดไฟล์นี้มาพร้อมโมเดล ผู้เรียก API ไม่ต้องส่งประวัติมา
  - การสร้างฟีเจอร์ใช้ฟังก์ชันเดียวกันใน `src/demand/features/` ทั้งตอน train และ serve โดยรับข้อมูลแถวที่จะพยากรณ์ + ประวัติยอดขาย
- **การเปลี่ยนโมเดล:** หลังย้าย `@champion` หรือ rollback ให้เรียก `POST /reload` เพื่อให้ API โหลดโมเดลใหม่โดยไม่ต้อง restart container
- ถ้ายังไม่มี `@champion` (เช่นเปิดระบบครั้งแรก) API ต้องไม่ล่ม `/health` ตอบว่ายังไม่พร้อม และ `/predict` ตอบ 503 พร้อมข้อความ

## 7. Monitoring และนโยบายเทรนใหม่
| ประเภท | ตรวจอะไร | เกณฑ์แจ้งเตือน |
|---|---|---|
| Data drift | การกระจายของ input (PSI / KS) | PSI > 0.2 ในฟีเจอร์หลัก |
| Concept drift | WAPE ย้อนหลัง 7 วัน เมื่อยอดจริงเข้ามา (label มาถึงวันถัดไป) | WAPE แย่ลง > 15% จากค่าตอนอนุมัติ |
| System | latency, error rate, uptime | ผิด SLO |

- **นโยบายเทรนใหม่:** ตามรอบทุกสัปดาห์ หรือทันทีเมื่อ drift เกินเกณฑ์ → รัน pipeline → ผ่าน gating → ย้าย alias
- **จำลอง drift:** data drift = เพิ่มความถี่ `Promo` / เพิ่มร้านใหม่, concept drift = ลดยอดขายจริง 20% ทั้งที่ input เดิม (คู่แข่งเปิดข้างร้าน)

## 8. การทดลอง (อย่างน้อย 3 รอบ)
1. Seasonal naive (baseline)
2. Ridge regression
3. LightGBM (ค่าเริ่มต้น)
4. LightGBM (จูนแล้ว)
บันทึกเหตุผลการตัดสินใจแต่ละรอบลง `docs/experiments.md`

## 9. CI/CD (ต้องตรวจ 3 ด้าน)
1. คุณภาพโค้ด: `ruff` + `pytest`
2. ความถูกต้องของข้อมูล: Pandera บน sample data
3. คุณภาพโมเดล: เทรนบน sample แล้วเช็ก gating
- **ต้องเก็บหลักฐานทั้งครั้งที่ผ่านและไม่ผ่าน** (แคปหน้าจอลง `docs/evidence/`)

## 10. โครงสร้างโฟลเดอร์
```
configs/            ค่าตั้งทั้งหมด
data/raw/           ข้อมูลดิบ (ไม่ commit)
data/processed/     ข้อมูลที่แบ่งแล้ว (ไม่ commit)
data/stream/        ข้อมูลจำลองที่ไหลเข้าหลังขึ้นระบบ
data/bad_samples/   ข้อมูลเสียไว้สาธิต (commit ได้)
data/predictions/   ผล batch forecast
src/demand/data/        ingest, split, schema
src/demand/features/    ฟีเจอร์ (ใช้ร่วม train + serve)
src/demand/training/    baselines, train, evaluate, gating, explain
src/demand/registry/    promote, rollback
src/demand/serving/     FastAPI app + request/response schema
src/demand/monitoring/  drift, simulate_drift, retrain_policy
src/demand/pipeline/    Prefect flow
tests/              pytest (รวม test case ข้อมูลผิดปกติ)
loadtest/           Locust
monitoring/         prometheus.yml, grafana dashboards
docker/             Dockerfiles
docs/               AI Canvas, architecture, SLO, experiments, report, ai_usage, evidence
docs/reports/       รายงานหลังจบแต่ละขั้นตอน (ดูข้อ 14.2)
notebooks/          สำรวจข้อมูลเท่านั้น ห้ามมีโค้ดที่ pipeline ใช้
```

## 11. Git workflow
- Branch: `feat/<ส่วนงาน>-<เรื่อง>`, `fix/...`, `docs/...` เช่น `feat/data-schema`
- Commit message: `<type>(<scope>): <สรุป>` เช่น `feat(serving): add /health endpoint`
- PR ต้องผ่าน CI และมี**สมาชิกคนอื่น**รีวิว approve อย่างน้อย 1 คนก่อน merge (ห้าม approve PR ของตัวเอง)

## 12. แบ่งงาน
ทีม 7 คน รับผิดชอบคนละ 1 บทบาท

| บทบาท | ความรับผิดชอบ | โฟลเดอร์หลัก |
|---|---|---|
| A. Data | ingest, split, schema, bad samples | `src/demand/data/` |
| B. Model | features, baseline, การทดลอง, gating, explain | `src/demand/features/`, `training/` |
| C. Serving | API, Docker, load test | `serving/`, `docker/`, `loadtest/` |
| D. Pipeline | Prefect flow, Makefile, registry | `pipeline/`, `registry/` |
| E. Monitoring | drift, Grafana, retrain policy | `monitoring/` |
| F. CI/CD | GitHub Actions, tests | `.github/`, `tests/` |
| G. Docs | Canvas, architecture, report, slides | `docs/` |

## 13. แผน 5 วัน
- **วัน 1 (1 ต.ค.):** ส่งข้อเสนอ, Canvas, repo + ระบบวิ่งทั้งเส้นแบบง่าย (ข้อมูล → โมเดล → API ใน Docker)
- **วัน 2 (2 ต.ค.):** schema + bad data, features, การทดลอง 3–4 รอบใน MLflow
- **วัน 3 (3 ต.ค.):** registry + gating + rollback, API ครบ endpoint, Prefect DAG, load test
- **วัน 4 (4 ต.ค.):** drift + monitoring + retrain loop, CI 3 ด้าน (หลักฐานผ่าน/ไม่ผ่าน)
- **วัน 5 (5 ต.ค.):** ทดสอบบนเครื่องเปล่า, แผนภาพสถาปัตยกรรม, รายงาน — **ส่งก่อน 20:00**

## 14. สำหรับ Claude: วิธีทำงานในโปรเจคนี้
- อ่าน `configs/config.yaml` ก่อนเขียนโค้ดที่ต้องใช้ path/วันที่/threshold
- โค้ดใหม่ต้องมี type hints และ docstring สั้นๆ เป็นภาษาอังกฤษ; คำอธิบายใน `docs/` เป็นภาษาไทยได้
- เพิ่ม/แก้ฟีเจอร์ → แก้ใน `src/demand/features/` ที่เดียว แล้วเพิ่ม test ใน `tests/test_features.py`
- เขียนโค้ดเสร็จ → รัน `make lint test` ก่อนบอกว่าเสร็จ
- เมื่อช่วยเขียนโค้ดส่วนไหน ให้บันทึกลง `docs/ai_usage.md` (โจทย์บังคับให้ระบุ) และอธิบายโค้ดให้สมาชิกเข้าใจทุกบรรทัด
- ถ้าจะเพิ่มไลบรารีใหม่ ต้องเพิ่มใน `requirements.in` แล้ว compile ใหม่ และอธิบายเหตุผล
- ห้ามใช้ `Customers` เป็นฟีเจอร์ ห้ามแบ่งข้อมูลแบบสุ่ม

### 14.1 สไตล์โค้ด: เขียนแบบ Junior dev ให้ไล่อ่านง่าย
- ทำทีละขั้น ตั้งชื่อตัวแปรยาวและบอกความหมาย เช่น `open_days_sales` ไม่ใช่ `ods`
- ฟังก์ชันสั้น ทำอย่างเดียว ใช้ `for` loop และ `if` ธรรมดาเมื่ออ่านง่ายกว่า
- ห้ามใช้ท่ายาก: list comprehension ซ้อนกัน, lambda ยาว, metaclass, decorator ที่เขียนเอง, method chaining ของ pandas ที่ยาวเกิน 3 ขั้น
- ใส่ comment อธิบาย **ทำไม** ก่อนแต่ละขั้นสำคัญ
- ยังต้องมี type hints และ docstring ภาษาอังกฤษตามข้อด้านบน

### 14.2 ทำ Report ทุกครั้งหลังจบแต่ละขั้นตอน
- ทุกครั้งที่ทำงานขั้นหนึ่งเสร็จ (เช่น ทำ schema เสร็จ, ทำ API เสร็จ) ให้เขียนรายงานสั้นเป็นภาษาไทยที่ `docs/reports/<YYYY-MM-DD>-<ขั้นตอน>.md`
- หัวข้อในรายงาน: ทำอะไรไป, ไฟล์ที่เพิ่ม/แก้, วิธีรันและทดสอบ, ผลลัพธ์ (เช่น test ผ่านกี่ข้อ, ค่า metric), ปัญหาที่ยังค้างและขั้นต่อไป
