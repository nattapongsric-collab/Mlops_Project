# การใช้เครื่องมือ AI ช่วยเขียนโค้ด

| ไฟล์/ส่วน | ใช้ AI ช่วยอะไร | ผู้ตรวจและอธิบายได้ |
|---|---|---|
| `CLAUDE.md`, `docs/reports/2026-09-30-rules-update.md` | Claude รีวิวโปรเจค ถามคำถามเรื่องกฎ และร่างการแก้กฎตามคำตอบของทีม | Kim |
| `requirements*.txt`, `pyproject.toml`, `src/demand/config.py`, `scripts/make_sample_data.py`, `tests/test_config.py`, `tests/test_fixtures.py`, Dockerfile, CI | Claude pin เวอร์ชันไลบรารี ตั้งค่า package/ruff/pytest เพิ่ม env override และเขียนสคริปต์ข้อมูลตัวอย่างกับ test | Kim (รอตรวจ) |
