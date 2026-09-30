# SLO และผลการวัด

วัดเมื่อ 1 ต.ค. 2569 บนเครื่อง Windows 16 core, API ใน Docker (8 workers), โมเดล `rossmann_demand` version 4 (LightGBM)
Locust รันบนเครื่องเดียวกัน 50 ผู้ใช้ 1 นาที ผู้ใช้แต่ละคนส่ง request ทุก 1–3 วินาที (ประมาณ 25 request/วินาที = ช่วงพีคที่คาดไว้)
ผลดิบ: `artifacts/loadtest_stats.csv` (สร้างใหม่ได้ด้วย `make loadtest`)

| ตัวชี้วัด | SLO | ผลจริง | ผ่าน? |
|---|---|---|---|
| API p50 | - | 65 ms | - |
| API p95 | < 200 ms | 130 ms | ✅ |
| API p99 | - | 200 ms | - |
| Throughput | - | 23.5 request/วินาที (1,394 request ใน 1 นาที) | - |
| Error rate | < 0.5% | 0% (0 จาก 1,394) | ✅ |
| Batch เสร็จ | ก่อน 06:00 | ยังไม่ได้วัด (ยังไม่มี batch) | - |

## ความจุสูงสุด (stress test)
ถ้าผู้ใช้ส่งถี่ขึ้นเป็นทุก 0.1–0.5 วินาที (ต้องการมากกว่า 100 request/วินาที) API จะรับได้เต็มที่ประมาณนี้ และ p95 จะเกิน SLO:

| จำนวน worker | Throughput สูงสุด | p95 |
|---|---|---|
| 1 | 19 request/วินาที | 3,200 ms |
| 4 | 66 request/วินาที | 680 ms |
| 8 | 100 request/วินาที | 550 ms |

ถ้ายิงทีละ request (ไม่มีคิว) p95 = 67 ms เวลาส่วนใหญ่อยู่ที่การสร้างฟีเจอร์ด้วย pandas (~50 ms ต่อ request)
