# การใช้เครื่องมือ AI ช่วยเขียนโค้ด

| ไฟล์/ส่วน | ใช้ AI ช่วยอะไร | ผู้ตรวจและอธิบายได้ |
|---|---|---|
| `CLAUDE.md`, `docs/reports/2026-09-30-rules-update.md` | Claude รีวิวโปรเจค ถามคำถามเรื่องกฎ และร่างการแก้กฎตามคำตอบของทีม | Kim |
| `requirements*.txt`, `pyproject.toml`, `src/demand/config.py`, `scripts/make_sample_data.py`, `tests/test_config.py`, `tests/test_fixtures.py`, Dockerfile, CI | Claude pin เวอร์ชันไลบรารี ตั้งค่า package/ruff/pytest เพิ่ม env override และเขียนสคริปต์ข้อมูลตัวอย่างกับ test | Kim (รอตรวจ) |
| `src/demand/data/ingest.py`, `src/demand/data/split.py`, `tests/test_ingest.py`, `tests/test_split.py` | Claude เขียนโค้ดอ่าน/รวมข้อมูล คำนวณ data hash แบ่งชุดตามเวลา และ test | สมาชิกบทบาท A (รอตรวจ) |
| `src/demand/features/`, `src/demand/training/` (baselines, evaluate, train, model_wrapper), `src/demand/registry/promote.py`, `tests/test_features.py` | Claude เขียนฟีเจอร์ โมเดลพื้นฐาน 3 แบบ การ log MLflow 6 อย่าง การตั้ง @champion และ test กัน leakage | สมาชิกบทบาท B และ D (รอตรวจ) |
| `src/demand/serving/`, `src/demand/training/explain.py`, `docker/api.Dockerfile`, `docker-compose.yml`, `loadtest/locustfile.py`, `tests/test_api.py` | Claude เขียน API ครบ endpoint, cascade, ข้อความ 422, top-3 features, หลาย worker + reload, load test และ test ของ API | สมาชิกบทบาท C (รอตรวจ) |
