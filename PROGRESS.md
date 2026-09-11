# Quotation Image Automation System - Project Progress

> **อัปเดตล่าสุด:** 11 กันยายน 2026  
> **สถานะปัจจุบัน:** พร้อมใช้งานจริง (Production Ready) ครอบคลุม **Phase 1, Phase 2, Phase 3** และการติดตั้งบน **Cloud Deployment (Vercel + Render)** สมบูรณ์

---

## 1. สถานะของแต่ละเฟส (Phase Status Overview)

| เฟส (Phase) | รายละเอียด | สถานะ | หมายเหตุ |
| :--- | :--- | :---: | :--- |
| **Phase 1** | **PDF Engine & Product Matching**<br>ตรวจจับพิกัด PDF, คำนวณขอบเขตบรรทัด, ค้นหาแค็ตตาล็อก 5 ระดับ, ฝังรูปลงช่อง Description โดยไม่ทับตัวหนังสือ | ✅ **เสร็จสมบูรณ์** | PyMuPDF engine, รองรับแค็ตตาล็อก 40,194 รายการ |
| **Phase 2** | **Quotation Studio & Image Editor**<br>เว็บแอป Next.js, พรีวิว PDF, ย้าย/ย่อขยายรูป, ครอบตัดรูปภาพสไตล์ Canva, คีย์ลัด Ctrl+Z/Y, วางรูปจากคลิปบอร์ด, เลือกลบรูปเดี่ยว/กลุ่ม | ✅ **เสร็จสมบูรณ์** | ผ่าน Playwright E2E Tests ครบทุกฟีเจอร์ |
| **Phase 3** | **Product Mapping Persistence**<br>ระบบจดจำ SKU ที่ผู้ใช้จับคู่ข้ามเอกสารอัตโนมัติ พร้อมหน้าต่าง "คู่สินค้าที่จำไว้" และป้าย "จำจากประวัติ" | ✅ **เสร็จสมบูรณ์** | บันทึกประวัติและนำกลับมาจับคู่อัตโนมัติในใบเสนอราคาถัดไป |
| **Cloud Deploy** | **Production Cloud Setup (Vercel + Render)**<br>Frontend บน Vercel, Backend บน Render, ปลดบล็อก CORS/OPTIONS, รองรับ Cookie SameSite=None; Secure, ระบบ Auto Warm-up | ✅ **เสร็จสมบูรณ์** | ทดสอบอัปโหลดสดผ่าน Vercel & Render สำเร็จ (`Status 201`) |
| **Phase 4** | **Quotation History & Supabase Storage / Auth**<br>ระบบประวัติเอกสารย้อนหลัง, เก็บ PDF ลง Supabase Storage, ระบบล็อกอินด้วย Google OAuth | ⏳ **พักไว้ชั่วคราว** | พักไว้ตามแผนเพื่อให้เริ่มใช้งานจริงในองค์กรก่อน |

---

## 2. ลิงก์และข้อมูลระบบบน Cloud (Cloud Deployments)

* **Frontend (Vercel):** [https://quotation-image-system.vercel.app](https://quotation-image-system.vercel.app)
  * Framework: Next.js 16 (Turbopack, App Router, TypeScript, Tailwind CSS)
  * Reverse Proxy: Rewrite `/api/*` ไปยัง Render Backend อัตโนมัติ (Zero-config fallback)
  * Live Status Indicator: มีป้ายแสดงสถานะการเชื่อมต่อ Backend มุมบนขวา พร้อม Auto Warm-up
* **Backend API (Render):** [https://quotation-api-h4ta.onrender.com](https://quotation-api-h4ta.onrender.com)
  * Framework: FastAPI (Python 3.10+, PyMuPDF, Pillow, HTTPX)
  * Database/Catalog: In-memory Catalog Index 40,194 รายการ (รองรับ PostgreSQL/Supabase ผ่าน `DATABASE_URL`)
  * Auto-Deploy: เปิดใช้งานผ่าน GitHub branch `main`

---

## 3. ผลการทดสอบ (Verification & Test Results)

1. **Backend Unit Tests (47/47 ผ่าน 100%):**
   ```bash
   python -m unittest discover -s apps/api/tests -p "test_*.py"
   ```
   * ครอบคลุม: Boundary detection, SKU normalization, Text-collision & gap-fitter, Image editor, Undo-redo stack, Mappings store, Web API endpoints

2. **Frontend End-to-End Tests (Playwright 8/8 Suites ผ่าน 100%):**
   * `workflow.spec.ts`: อัปโหลดเอกสาร, ตรวจสอบสินค้า, เลือกสินค้าด้วยตนเอง, สร้างและดาวน์โหลด PDF
   * `saved-mappings.spec.ts`: ตรวจสอบการจำ SKU ข้ามเอกสาร, การแสดงผลในหน้าต่าง "คู่สินค้าที่จำไว้", ป้าย "จำจากประวัติ"
   * `image-editor.spec.ts`: ลากย้ายรูป, ย่อ-ขยายรูป, ปรับตำแหน่ง, วางรูปจากคลิปบอร์ด (Ctrl+V)
   * `image-crop.spec.ts`: ครอบตัดรูปภาพบนหน้า PDF แบบ inline สไตล์ Canva
   * `undo-redo.spec.ts`: ปุ่มย้อนกลับ/ทำซ้ำ, คีย์ลัด Ctrl+Z / Ctrl+Y
   * `pan-view.spec.ts`: กด Spacebar เลื่อนดูเอกสาร, เครื่องมือ Hand Tool
   * `delete-image.spec.ts` (Single & Batch Delete): เลือกลบรูปทีละชิ้น หรือติ๊ก Checkbox หลายรายการเพื่อลบรูปพร้อมกันเป็นกลุ่ม พร้อมปุ่มกู้คืน

3. **Cloud Integration Test (ทดสอบอัปโหลดจริงผ่าน Internet):**
   ```bash
   python test_render_upload.py
   ```
   * ยิงอัปโหลดไฟล์ `QT_test.pdf` ไปยังทั้ง Vercel (`/api/quotations`) และ Render (`/api/quotations`)
   * ผลลัพธ์: **`Status: 201 Created`** ได้รับพิกัดและรูปสินค้าถูกต้องทั้งสองช่องทาง

---

## 4. วิธีเริ่มใช้งานในสภาพแวดล้อมใหม่ (Setup in a New Environment)

### ข้อกำหนดเบื้องต้น (Prerequisites)
* **Node.js**: v18.0 ขึ้นไป (แนะนำ v20+)
* **Python**: v3.10 ขึ้นไป (รองรับ 3.10, 3.11, 3.12, 3.14)
* **Git**

### ขั้นตอนติดตั้งจากศูนย์ (Step-by-Step)

#### ขั้นตอนที่ 1: Clone และเตรียม Dependencies
```bash
git clone https://github.com/analystsevenfive/quotation-image-system.git
cd quotation-image-system

# ติดตั้ง Python Dependencies
python -m pip install -r requirements.txt

# ติดตั้ง Frontend Dependencies
cd apps/web
npm install
cd ../..
```

#### ขั้นตอนที่ 2: เตรียมข้อมูลแค็ตตาล็อกสินค้า (Product Catalog)
หากต้องการรัน Local Backend ด้วยฐานข้อมูลจำลอง ให้แปลง Excel เป็น snapshot JSON:
```bash
$env:PYTHONPATH = "apps/api"
python -m app.import_catalog "web sevenfive 75.xlsx" --json .data/products.json
```
*(ไฟล์ `.data/products.json` จะถูกสร้างขึ้น มีสินค้า 40,194 รายการ พร้อมใช้งานทันที)*

#### ขั้นตอนที่ 3: เปิดใช้งาน

**แบบที่ 1 — ผ่าน Script ด่วน (Windows):**
* ดับเบิลคลิกไฟล์ `start-production.bat` หรือรัน `.\start-production.ps1` ใน PowerShell
* ระบบจะเปิดทั้ง Backend และ Frontend ให้อัตโนมัติ พร้อมแสดง Local IP สำหรับแชร์ในวง LAN

**แบบที่ 2 — เปิดแยก 2 Terminal สำหรับ Development:**
* **Terminal 1 (Backend):**
  ```powershell
  $env:PYTHONPATH = "apps/api"
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```
* **Terminal 2 (Frontend):**
  ```powershell
  cd apps/web
  npm run dev
  ```
* เปิดเบราว์เซอร์ไปที่: `http://127.0.0.1:3000`

---

## 5. การตั้งค่า Environment Variables

ดูแม่แบบตัวเต็มได้ที่ [`.env.example`](.env.example)

| ตัวแปร | สำหรับ | รายละเอียด | ค่าเริ่มต้น (Default) |
| :--- | :--- | :--- | :--- |
| `PORT` | Backend | พอร์ตที่ API รัน | `8000` |
| `PYTHONPATH` | Backend | ชี้ไปยังโฟลเดอร์โมดูล | `apps/api` |
| `PRODUCTS_JSON` | Backend | ไฟล์แค็ตตาล็อก JSON จำลอง | `.data/products.json` |
| `DATABASE_URL` | Backend | Connection String ของ PostgreSQL / Supabase | *(ไม่ใส่ = ใช้ JSON)* |
| `ALLOWED_HOSTS` | Backend | โฮสต์ที่อนุญาต | `*` |
| `ALLOWED_ORIGINS`| Backend | โดเมนที่อนุญาต CORS | `*` หรือระบุโดเมน Vercel |
| `API_URL` | Frontend | URL ปลายทางของ Backend API | `http://127.0.0.1:8000` (Local) / Auto Render URL (Prod) |

---

## 6. ข้อควรระวังและแนวทางสำหรับ AI Agent หรือนักพัฒนาคนถัดไป

1. **ห้ามทำลายคุณภาพ Vector ใน PDF**:
   * ห้าม Rasterize หรือแปลงหน้า PDF ทั้งหน้าเป็นรูปภาพเด็ดขาด
   * ต้องใช้ `fitz` (PyMuPDF) แทรกรูปภาพเฉพาะจุดเท่านั้น เพื่อให้ข้อความต้นฉบับคมชัดและค้นหา/ก๊อปปี้ได้ 100%
2. **ห้ามใช้พิกัดคงที่ (Hardcoded Coordinates)**:
   * ความสูงแต่ละแถวสินค้าในใบเสนอราคาจะไม่เท่ากัน ต้องคำนวณผ่าน Item Boundary Detector (`apps/api/app/services/pdf/boundary.py`)
3. **การวางรูปภาพ (Image Placement)**:
   * รูปต้องอยู่ภายในขอบเขตคอลัมน์ `DESCRIPTION` เท่านั้น
   * ห้ามทับตัวหนังสือข้อความ (ตรวจเช็คผ่าน `fitter.py` / text collision detection)
   * ห้ามทับคอลัมน์ `QTY`, `PRICE`, `NET PRICE`
4. **การเชื่อมต่อระหว่าง Frontend และ Backend**:
   * โค้ด Frontend เข้าถึง Backend ผ่าน `/api/*` เสมอ โดยให้ Next.js Rewrite เป็นผู้ส่งต่อคำขอ เพื่อหลีกเลี่ยงปัญหา Third-party Cookie ถูกบล็อกบน Safari/Chrome
5. **Render Cold Start**:
   * เซิร์ฟเวอร์ Render Free Tier จะหลับเมื่อไม่มีคนใช้งาน 15 นาที เมื่อมีคนเปิดหน้าเว็บ หน้าบ้านจะส่ง Ping ไปปลุกที่ `/api/health` ทันที ผู้ใช้จะเห็นสถานะ "กำลังเชื่อมต่อเซิร์ฟเวอร์…" ประมาณ 30-50 วินาทีในคำขอแรก จากนั้นจะขึ้นเป็น "ระบบพร้อมใช้งาน"
