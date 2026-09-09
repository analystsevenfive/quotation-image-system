# Quotation Image Automation System
## สถานะโครงการและคู่มือการพัฒนาต่อ (Project Progress & Handover)

> **ปรับปรุงล่าสุด:** วันที่ 9 กันยายน 2026  
> **สถานะปัจจุบัน:** ✅ **Phase 1: Core PDF Engine เสร็จสมบูรณ์ 100%** (ผ่านการทดสอบกับไฟล์จริงทั้งหมด)  
> **ขั้นตอนถัดไป:** 🚀 **Phase 2: Basic Web UX (FastAPI Backend + Next.js Frontend)**

---

## 1. สรุปสิ่งที่ทำเสร็จแล้ว (Completed Milestones)

### Phase 1: Core PDF Engine Proof of Concept (เสร็จแล้ว)
ได้สร้าง Core Engine ด้วย Python + PyMuPDF ตามข้อกำหนดใน `AGENTS.md` และ `docs/quotation-image-system.md` โดยทดสอบและยืนยันผลกับไฟล์จริงของบริษัท:
1. **ไฟล์ใบเสนอราคาจริง:** `QT_test.pdf` (QT0926-00287 จำนวน 8 หน้า)
2. **ไฟล์แคตตาล็อกสินค้าจริง:** `web sevenfive 75.xlsx` (40,237 รายการ)
3. **ผลลัพธ์ที่ได้:** สร้างไฟล์ `QT_test_with_images.pdf` (632 KB) ดึงรูปสินค้าจาก Shopify CDN ใส่ในใบเสนอราคาครบทั้ง 18 รายการสำเร็จ 100%

### รายละเอียดฟังก์ชันที่พัฒนาแล้ว:
- **PyMuPDF Selectable-Text Parser (`apps/api/app/services/pdf/parser.py`):**
  - ตรวจจับหัวตาราง (`ITEM`, `DESCRIPTION`, `QTY`, `PRICE`, `NET PRICE`) ด้วยระบบ Line Grouping แม่นยำ ไม่สับสนกับคำว่า DESCRIPTION หรือ PRICE ในเนื้อหาหรือท้ายหน้า
  - คำนวณขอบเขตแถวของสินค้าแต่ละรายการแบบ Dynamic Y-range (ไม่ใช้วิธี Hardcode ความสูงแถว)
  - ดึงรหัส Model / SKU อัตโนมัติด้วย Regular Expression รองรับทั้ง `MODEL: ...`, `#...`, และรหัสสินค้า
- **SKU Normalizer & Matcher (`apps/api/app/services/matching/`):**
  - ปรับ Format รหัสสินค้า (จัดการ Unicode Dash, เว้นวรรค, ตัวพิมพ์ใหญ่)
  - ลำดับความสำคัญในการจับคู่: Exact SKU → Exact Winspeed → Normalized SKU → Model Match → Manual Review
  - สามารถ Match กับข้อมูลใน `web sevenfive 75.xlsx` Column D (`GoodBillName`) และดึง URL รูปภาพจาก Column F (`link image`)
- **Fault-Tolerant Image Downloader (`apps/api/app/services/images/downloader.py`):**
  - ดึงรูปภาพจาก Shopify CDN ผ่าน `httpx` พร้อม Timeout และ Retry
  - ตรวจสอบความถูกต้องของรูปภาพด้วย `Pillow` (ตรวจ Header รูป, ขนาดรูป)
  - ถ้ารูปภาพโหลดไม่ได้หรือ URL เสีย ระบบจะไม่แครช แต่จะบันทึกสถานะ `missing` และดำเนินการสร้าง PDF ต่อไป
- **Geometry & Image Fitting (`apps/api/app/services/pdf/fitter.py`):**
  - จัดวางรูปกึ่งกลางตามแนวนอนที่ `CenterX = 350.0 pt` ภายในคอลัมน์ `DESCRIPTION` (ตามตัวอย่างที่ระบุ)
  - ขนาดรูปสูงสุด: กว้างไม่เกิน `110 pt`, สูงไม่เกิน `100 pt`, ช่องรูปขั้นต่ำ `95 pt` สำหรับแถวสั้น
  - รักษาสัดส่วนรูปภาพเดิม (Aspect Ratio) 100% โดยไม่บิดเบี้ยว
  - รับประกันความปลอดภัย: ขอบขวารูปจะไม่เกิน `x = 410 pt` ทำให้ **ไม่ทับซ้อนคอลัมน์ QTY (x=413 pt), PRICE, หรือ NET PRICE** เด็ดขาด
- **Vector PDF Renderer (`apps/api/app/services/pdf/renderer.py`):**
  - แทรกรูปภาพด้วย Native PyMuPDF XObject (`page.insert_image`)
  - ไม่ทำ Rasterize ทั้งหน้า ทำให้ตัวหนังสือ เวกเตอร์ และตารางต้นฉบับคมชัดสูงสุด

---

## 2. โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

```text
quotation-image-system-starter/
├── AGENTS.md                          # กฎและข้อกำหนดหลักของสถาปัตยกรรมระบบ
├── README.md                          # คำอธิบายภาพรวมโครงการ
├── PROGRESS.md                        # [ไฟล์นี้] สรุปสถานะและคู่มือการเริ่มงานใน env ใหม่
├── requirements.txt                   # รายการ Python dependencies สำหรับติดตั้ง
├── run_full_excel_test.py             # สคริปต์รันเทสทั้งกระบวนการ (PDF + Excel 40k rows -> PDF พร้อมรูป)
├── test_excel_match.py                # สคริปต์เทสเฉพาะการ Match SKU กับ Excel
│
├── docs/
│   └── quotation-image-system.md      # ข้อกำหนดทางเทคนิคฉบับสมบูรณ์ (PRD)
│
├── apps/
│   └── api/
│       ├── requirements.txt
│       ├── app/
│       │   ├── cli.py                 # Command Line Interface สำหรับรันแปลงไฟล์
│       │   ├── core/
│       │   │   ├── config.py          # ค่า Settings (Timeouts, Thresholds)
│       │   │   └── template.py        # ค่าพิกัดแม่แบบตาราง (SEVEN_FIVE_TEMPLATE)
│       │   ├── models/
│       │   │   ├── product.py         # Data models (Product, ImageStatus)
│       │   │   └── quotation.py       # Data models (QuotationItem, BoundingBox)
│       │   └── services/
│       │       ├── images/downloader.py # โมดูลดาวน์โหลดและแคชรูป
│       │       ├── matching/normalizer.py # โมดูลจัดรูปแบบ SKU
│       │       ├── matching/matcher.py    # โมดูลค้นหาและจับคู่สินค้า
│       │       ├── pdf/parser.py          # โมดูลวิเคราะห์เอกสาร PDF
│       │       ├── pdf/fitter.py          # โมดูลคำนวณตำแหน่งและสัดส่วนรูป
│       │       ├── pdf/renderer.py        # โมดูลแทรกรูปลง PDF
│       │       └── pipeline.py            # Pipeline เชื่อมโยงการทำงานทั้งหมด
│       └── tests/
│           ├── test_boundary_detection.py # ยูนิตเทสตรวจจับขอบเขตตาราง
│           ├── test_image_fitting.py      # ยูนิตเทสการคำนวณตำแหน่งรูป
│           ├── test_matching.py           # ยูนิตเทสอัลกอริทึม Match สินค้า
│           └── test_sku_normalization.py  # ยูนิตเทสการ Clean SKU
│
└── [ไฟล์ข้อมูลสำหรับทดสอบ]
    ├── QT_test.pdf                    # ใบเสนอราคาตัวอย่างจริง 8 หน้า (QT0926-00287)
    ├── web sevenfive 75.xlsx          # ฐานข้อมูลสินค้าจริง 40,237 แถว
    └── QT_test_with_images.pdf        # ไฟล์ผลลัพธ์ที่สร้างสำเร็จแล้ว
```

---

## 3. วิธีการติดตั้งและรันใน Environment ใหม่ (Setup in New Environment)

เมื่อนำโปรเจกต์นี้ไปเปิดในเครื่องใหม่ หรือ VM / Server ใหม่ สามารถทำตามขั้นตอนต่อไปนี้ได้ทันที:

### ขั้นตอนที่ 1: เตรียม Environment
- ติดตั้ง **Python 3.10 ขึ้นไป** (แนะนำ 3.11 หรือ 3.12)
- สร้างและเปิดใช้งาน Virtual Environment:

```bash
# บน Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

# บน Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
```

### ขั้นตอนที่ 2: ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

*(หรือติดตั้งแพ็กเกจหลัก: `pip install pymupdf httpx pillow pydantic openpyxl`)*

### ขั้นตอนที่ 3: รัน Unit Tests ตรวจสอบความถูกต้อง
```bash
python -m unittest discover -s apps/api/tests -p "test_*.py"
```
*ผลลัพธ์ที่ถูกต้อง: ต้องผ่านครบทั้ง 20 tests (`Ran 20 tests in ... OK`)*

### ขั้นตอนที่ 4: รันประมวลผลไฟล์จริง (Full Integration Test)
```bash
python run_full_excel_test.py
```
*สคริปต์จะอ่าน `QT_test.pdf` จับคู่กับ `web sevenfive 75.xlsx` ดาวน์โหลดรูปจาก Shopify และบันทึกเป็น `QT_test_with_images.pdf`*

---

## 4. ข้อควรระวังและค่าพิกัดสำคัญ (Technical Gotchas & Geometry Rules)

สำหรับผู้พัฒนาที่มาทำต่อ ห้ามแก้ไขค่าเหล่านี้โดยไม่เข้าใจเงื่อนไข:

1. **พิกัดตารางใบเสนอราคา Seven Five (`SEVEN_FIVE_TEMPLATE`):**
   - หัวตาราง (Header) สิ้นสุดที่ `y = 277.7 pt` (ห้ามใส่ Positive Padding เช่น `+4 pt` เด็ดขาด เพราะจะทำให้สินค้าลำดับที่ 1 หายไป)
   - ท้ายตาราง (Footer) เริ่มที่ `y = 588.1 pt`
   - คอลัมน์ `DESCRIPTION`: `x = 60.0` ถึง `410.0 pt`
   - คอลัมน์ `QTY`: `x = 413.0` ถึง `455.0 pt`
   - คอลัมน์ `PRICE`: `x = 458.0` ถึง `515.0 pt`
   - คอลัมน์ `NET PRICE`: `x = 518.0` ถึง `580.0 pt`
2. **การจัดวางขนาดรูปภาพ (`app/services/pdf/fitter.py`):**
   - แนวนอน: วางตรงกลางที่ `CenterX = 350.0 pt` (ขอบภาพจะอยู่ช่วง x ≈ 295 - 405 pt ปลอดภัยจาก QTY แน่นอน)
   - แนวตั้ง: `max_height = 100.0 pt`, `min_slot_height = 95.0 pt` สำหรับรายการที่มีข้อความสั้น เพื่อให้ภาพมีขนาดชัดเจนสวยงามตามตัวอย่าง
3. **การอ่านไฟล์ Excel (`web sevenfive 75.xlsx`):**
   - Column D (`GoodBillName`) ใน Excel มีสูตรคำนวณ `=VLOOKUP(...)` ดังนั้นเวลาเปิดด้วย `openpyxl` **ต้องใส่ `data_only=True` เสมอ** มิฉะนั้นจะได้ค่า String สูตรแทนที่จะได้ชื่อสินค้า
4. **Encoding ใน Windows CLI:**
   - หลีกเลี่ยงการใช้ Unicode อักขระพิเศษอย่าง `✓` หรือ emoji ใน console output ให้ใช้ `[OK]` / `[--]` เพื่อไม่ให้ติดปัญหา CP874 / CP1252

---

## 5. แผนการพัฒนาต่อไป (Roadmap & Next Steps)

ผู้พัฒนาสามารถหยิบงานไปทำต่อได้ตามลำดับความสำคัญนี้:

### 🚀 ก้าวถัดไป: Phase 2 — สร้าง Web Application (FastAPI + Next.js)

#### งานฝั่ง Backend (`apps/api/app/main.py`):
1. สร้าง FastAPI App พร้อม CORS Middleware
2. สร้าง Endpoint:
   - `POST /api/quotations/upload`: รับไฟล์ PDF วิเคราะห์และส่งคืน JSON รายการสินค้าพร้อมรูปภาพตัวอย่าง
   - `GET /api/products/search?q=...`: สำหรับให้ User ค้นหาสินค้ากรณีต้องการเปลี่ยนรูป
   - `POST /api/quotations/generate`: รับค่า ID/รายการที่ยืนยันแล้ว และสร้าง PDF ฉบับเสร็จสมบูรณ์
   - `GET /api/quotations/{id}/download`: ดาวน์โหลดไฟล์ PDF

#### งานฝั่ง Catalog Performance:
- ปัจจุบันการโหลด Excel 40,000 แถวด้วย `openpyxl` ใช้เวลา ~15 วินาที
- **สิ่งที่ต้องทำ:** นำข้อมูลใน Excel ไปแปลงเก็บเป็น **SQLite Database** (`catalog.db`) หรือ PostgreSQL เพื่อให้การค้นหาทำได้ในเวลา < 0.05 วินาที

#### งานฝั่ง Frontend (`apps/web/` - Next.js + Tailwind + shadcn/ui):
1. **หน้า Upload:** มี Drag & Drop Zone สวยงาม พนักงานลากไฟล์ PDF วางแล้วระบบประมวลผลทันที
2. **หน้า Review (Split View):**
   - ฝั่งซ้าย: ดูตัวอย่างเอกสาร PDF
   - ฝั่งขวา: รายการสินค้าแต่ละลำดับ แสดงรูปที่ Match ได้ มี Badge สถานะ (`Matched` สีเขียว, `Missing` สีส้ม) มีปุ่มกดค้นหาเพื่อเปลี่ยนรูปได้
3. **หน้า Download:** กดปุ่ม "สร้างและดาวน์โหลด PDF" ได้รับไฟล์ทันที
