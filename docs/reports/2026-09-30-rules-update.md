# รายงาน: รีวิวโปรเจคและปรับกฎใน CLAUDE.md (30 ก.ย. 2569)

## ทำอะไรไป
1. รีวิวโปรเจคทั้งโฟลเดอร์แบบอ่านอย่างเดียว พบว่าเป็นโครง (scaffold) ที่ยังไม่มีโค้ดทำงานจริง
2. ถามคำถามสำคัญ 8 ข้อ ทีมเลือกตัวเลือกที่แนะนำทุกข้อ
3. ปรับ `CLAUDE.md` ตามคำตอบ และเพิ่มกฎสไตล์โค้ดแบบ Junior dev กับการทำรายงานหลังจบทุกขั้นตอน

## ไฟล์ที่เพิ่ม/แก้
- แก้ `CLAUDE.md`: กฎเหล็กข้อ 10 (ย้อนอย่างน้อย 7 วัน), ข้อ 2.1 การจัดการข้อมูล, ข้อ 4 Docker/Windows/`MLFLOW_TRACKING_URI`, ข้อ 5 WAPE และ gating, ข้อ 6 ประวัติยอดขายตอน serve + `POST /reload` + 503, ข้อ 10 `docs/reports/`, ข้อ 11 การ approve PR, ข้อ 12 ทีม 7 คน, ข้อ 14.1 และ 14.2
- เพิ่ม `docs/reports/2026-09-30-rules-update.md` (ไฟล์นี้)

## วิธีรันและทดสอบ
ขั้นนี้แก้เฉพาะเอกสาร ไม่มีโค้ดให้รัน

## ผลลัพธ์
กฎของโปรเจคตรงกับการตัดสินใจของทีมแล้ว

## ปัญหาที่ยังค้างและขั้นต่อไป
- โฟลเดอร์นี้ยังไม่ใช่ git repo ต้องเชื่อมกับ GitHub และตั้ง branch protection บน `main`
- ยังไม่มี `requirements.txt` / `requirements-dev.txt` (pin เวอร์ชัน) และ `pyproject.toml`
- ยังไม่มี `tests/fixtures/sample_train.csv` ที่ CI ต้องใช้
- ขั้นต่อไป (วันที่ 1): ทำระบบให้วิ่งครบเส้นแบบง่ายใน Docker (ข้อมูล → โมเดล → API)

<!-- ccr-projects-attribution -->
_Requested by **Kim**_

## สรุปการเปลี่ยนแปลง
ปรับกฎใน CLAUDE.md ตามที่ทีมตกลงกัน 8 ข้อ: เพิ่มกฎกัน leakage (ย้อนอย่างน้อย 7 วัน), การจัดการข้อมูล, Docker/Windows, WAPE และ gating, การดึงประวัติยอดขายตอน serve และ POST /reload, การ approve PR, สไตล์โค้ดแบบ Junior dev และการทำรายงานทุกขั้นตอน พร้อมรายงานใน docs/reports/ และบันทึกใน docs/ai_usage.md

## ส่วนงาน
- [x] Docs

## เช็กลิสต์
- [ ] `make lint test` ผ่าน (ไม่มีโค้ดเปลี่ยน)
- [x] ไม่ได้ใช้ `Customers` เป็นฟีเจอร์ / ไม่ได้แบ่งข้อมูลแบบสุ่ม
- [x] ถ้าใช้ AI ช่วยเขียน ได้บันทึกใน `docs/ai_usage.md` แล้ว

🤖 Generated with [Claude Code](https://claude.com/claude-code)