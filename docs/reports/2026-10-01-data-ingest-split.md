# รายงาน: อ่านข้อมูลและแบ่งชุดตามเวลา (feat/data-ingest-split) — 1 ต.ค. 2569

## ทำอะไรไป
1. **`src/demand/data/ingest.py`**
   - `read_train()` อ่าน `train.csv` แปลง `Date` เป็นวันที่ และอ่าน `StateHoliday` เป็นข้อความเสมอ (ไฟล์จริงปน 0 กับ "0")
   - `read_store()` อ่าน `store.csv`
   - `merge_train_and_store()` รวมข้อมูลร้านเข้ากับยอดขายแบบ left join (ไม่ทิ้งแถวยอดขาย) แล้วเรียงตามร้านและวันที่
   - `compute_data_hash()` คำนวณ SHA-256 ของไฟล์ดิบทั้งสองไฟล์ ใช้เป็นเวอร์ชันของข้อมูลเพื่อ log ลง MLflow
2. **`src/demand/data/split.py`**
   - `check_split_dates()` หยุดพร้อม error ถ้าช่วงวันที่ใน config ทับกันหรือเรียงผิด
   - `split_by_date()` แบ่งเป็น train / val / test / stream ตามวันที่ใน `configs/config.yaml` (ไม่สุ่ม)
   - `save_splits()` บันทึกแต่ละชุดเป็น parquet และบันทึก data hash ลง `data/processed/data_hash.txt`
   - รันได้ด้วย `python -m demand.data.split` หรือ `make split` และใส่ `--train`/`--store` เพื่อใช้ไฟล์อื่นได้ (เช่นข้อมูลตัวอย่างใน CI)
3. **test ใหม่ 10 ข้อ** ใน `tests/test_split.py` และ `tests/test_ingest.py`
   - ทุกชุดมีข้อมูล, เรียงตามเวลาไม่ทับกัน, อยู่ในช่วงวันที่ของ config, ไม่มีแถวหายหรือซ้ำ, config ที่ทับกันถูกปฏิเสธ
   - merge ไม่ทำแถวหาย, `StateHoliday` เป็นข้อความ, hash เหมือนเดิมเมื่อไฟล์เดิม และเปลี่ยนเมื่อไฟล์เปลี่ยน
4. เพิ่มคำสั่ง `make split`

## ยังไม่ได้ทำในขั้นนี้ (ตั้งใจ)
- ยังไม่ได้ตัดคอลัมน์ `Customers` เพราะข้อมูลดิบต้องมีครบให้ schema ตรวจ การตัดทำที่ `src/demand/features/` ตามกฎข้อ 3
- ยังไม่ได้ตรวจ schema (Pandera) ร้านที่ไม่มีใน `store.csv` จะได้ค่าว่าง แล้ว `schema.py` จะเป็นตัวจับ

## วิธีรันและทดสอบ
Windows:
```
.\.venv\Scripts\python.exe -m demand.data.split
.\.venv\Scripts\ruff.exe check src tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```
Mac/Linux: `make split` และ `make lint test`

## ผลลัพธ์ (ข้อมูลจริงจาก Kaggle)
| ชุด | จำนวนแถว | ช่วงวันที่ |
|---|---:|---|
| train | 780,829 | 2013-01-01 ถึง 2014-12-31 |
| val | 133,800 | 2015-01-01 ถึง 2015-04-30 |
| test | 34,565 | 2015-05-01 ถึง 2015-05-31 |
| stream | 68,015 | 2015-06-01 ถึง 2015-07-31 |
| รวม | 1,017,209 | ตรงกับจำนวนแถวใน `train.csv` ไม่มีแถวหลุด |

- Data hash: `ba70b7b25eac25208a5dcdf7e69b8414afb755cf6a8fa03253b66510cd1d6288`
- ใช้เวลารันประมาณ 3 วินาที
- ruff ผ่านทั้งหมด, pytest 17 passed (ของเดิม 7 + ใหม่ 10)

## ปัญหาที่ยังค้างและขั้นต่อไป
- branch นี้แตกจาก `feat/setup-env` ที่ยังไม่ได้ merge PR ควร merge `feat/setup-env` ก่อน
- ขั้นต่อไป: `feat/model-baseline` (seasonal naive, WAPE/bias, LightGBM ตัวแรก log ลง MLflow)
