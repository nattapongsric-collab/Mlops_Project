# รายงาน: ฟีเจอร์ โมเดลพื้นฐาน และ MLflow (feat/model-baseline) — 1 ต.ค. 2569

## ทำอะไรไป
1. **ฟีเจอร์ `src/demand/features/build_features.py`** (ที่เดียว ใช้ทั้ง train และ serve)
   - ปฏิทิน: ปี เดือน วันที่ สัปดาห์ของปี / แปลงข้อความเป็นเลข: StateHoliday, StoreType, Assortment (ใช้ตารางแปลงตายตัว)
   - คู่แข่ง: ระยะทาง (ว่าง = 100,000 จาก config) และจำนวนเดือนที่คู่แข่งเปิด / Promo2: เดือนนี้อยู่ในรอบโปรหรือไม่
   - ยอดขายย้อนหลัง: lag 7/14/28 วัน และค่าเฉลี่ย 7/28 วันที่จบก่อนวันพยากรณ์ 7 วัน จับคู่ด้วยวันที่จริง ไม่ใช่ลำดับแถว
   - ค่าว่างเติมด้วยค่าเฉลี่ยร้าน × วันในสัปดาห์จาก train (ตามข้อตกลงข้อ 3) และตัด `Customers` ทิ้งเสมอ
   - ถ้าใน config ตั้ง lag น้อยกว่า 7 วัน จะหยุดพร้อม error (กัน leakage)
2. **`training/baselines.py`** seasonal naive = ยอดวันเดียวกันสัปดาห์ก่อน ถ้าสัปดาห์ก่อนร้านปิดใช้ค่าเฉลี่ยร้าน × วันแทน
3. **`training/evaluate.py`** WAPE, bias, อัตราพยากรณ์ต่ำเกิน (เสี่ยงของขาด), มูลค่าพยากรณ์สูงเกิน (สต็อกเกิน)
4. **`features/preprocess.py`** sklearn Pipeline ของ Ridge (เติมค่าว่าง + scale + one-hot) และ LightGBM (seed 42)
5. **`training/model_wrapper.py`** โมเดล MLflow ที่รวม pipeline + ประวัติยอดขาย 60 วันล่าสุด + ตารางค่าเฉลี่ย + config ไว้ในก้อนเดียว
   API แค่โหลด `models:/rossmann_demand@champion` แล้วส่งข้อมูลดิบเข้าไป (ตามข้อตกลงข้อ 1) ร้านปิดได้ 0 เสมอ
6. **`training/train.py`** เทรน `naive` / `ridge` / `lightgbm` แล้ว log ครบ 6 อย่าง:
   git commit + มีโค้ดยังไม่ commit หรือไม่, data hash, hyperparameters, metrics (val/test), artifacts, `pip_freeze.txt`
7. **`registry/promote.py`** ลงทะเบียนโมเดลและตั้ง `@champion` (ยังไม่มี gating ตั้งใจเพิ่มวันที่ 3)
8. **config**: เพิ่ม `features.competition_distance_fill` และ `models.ridge` / `models.lightgbm`
9. **docker-compose**: pin MLflow server เป็น `v3.16.1` ให้ตรงกับไลบรารี
10. **test ใหม่ 9 ข้อ** ใน `tests/test_features.py` รวมถึง test ที่คูณยอด 6 วันก่อนหน้าด้วย 10 แล้วฟีเจอร์ต้องไม่เปลี่ยน (พิสูจน์ว่าไม่มี leakage)

## ปัญหาที่เจอระหว่างทำ และแก้แล้ว
- naive พังเพราะใส่ค่าทศนิยมลงคอลัมน์ int → แปลงเป็น float ก่อน
- **พยากรณ์ 1 request ใช้เวลา 3.5 วินาที** (เกิน SLO 200 ms มาก) เพราะคำนวณ rolling ของทั้ง 1,115 ร้านทุกครั้ง
  แก้โดยกรองประวัติเฉพาะร้านที่ขอ ตอนนี้ p50 29 ms, p95 38 ms (วัด 50 request ในเครื่อง ยังไม่รวม API)

## วิธีรันและทดสอบ
Windows (เปิด Docker Desktop ก่อน):
```
docker compose up -d mlflow
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
.\.venv\Scripts\python.exe -m demand.data.split
.\.venv\Scripts\python.exe -m demand.training.train --model naive
.\.venv\Scripts\python.exe -m demand.training.train --model ridge
.\.venv\Scripts\python.exe -m demand.training.train --model lightgbm
.\.venv\Scripts\python.exe -m demand.registry.promote --run-id <run id ของ lightgbm>
```
ดูผลที่ http://localhost:5000

## ผลลัพธ์
| โมเดล | WAPE val | Bias val | WAPE test | Bias test | เวลาเทรน |
|---|---|---|---|---|---|
| Seasonal naive | 0.2809 | -1.4% | 0.1878 | +3.0% | ~25 วินาที |
| Ridge | 0.1157 | +0.3% | 0.1277 | -2.5% | ~65 วินาที |
| LightGBM | **0.1055** | +0.7% | **0.1036** | -5.0% | ~95 วินาที |

- `@champion` = `rossmann_demand` version 3 (LightGBM, run `97375210`, commit `d82dd27`, ไม่มีโค้ดค้าง commit)
- ขนาดโมเดล 1.7 MB (เกณฑ์ < 50 MB)
- รันซ้ำได้ค่าเดิมทุกหลัก, ruff ผ่าน, pytest 26 passed
- บันทึกผลลง `docs/experiments.md` แล้ว

## ปัญหาที่ยังค้างและขั้นต่อไป
- **Bias บน test = -5.0% ชนขอบเกณฑ์ 5% พอดี** ถ้าเกณฑ์ใช้ test ตอนทำ gating อาจไม่ผ่าน ต้องดูตอนจูน (รอบ 4)
- version 1 และ 2 ใน registry มาจากการทดสอบระหว่างทำ (version 1 ยังเป็นโค้ดตัวช้า) ลบได้หรือเก็บไว้เป็นหลักฐาน rollback
- ประวัติยอดขายในโมเดลจบที่ 31 พ.ค. 2015 ถ้าพยากรณ์วันที่ไกลกว่า 7 วันหลังจากนั้น lag จะว่างและใช้ค่าเฉลี่ยแทน ต้องอัปเดตประวัติตอนทำ batch/stream
- ตอนนี้ promote ตั้ง champion โดยไม่ผ่าน gating (วันที่ 3)
- ขั้นต่อไป: `feat/serving-predict` ทำ `/predict` และ `/health` ที่โหลด `@champion` ใน Docker
