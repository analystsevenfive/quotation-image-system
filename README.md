# Quotation Image Automation System

Automated insertion of product images into quotation PDFs using PyMuPDF and Next.js.

---

## 📌 Document Links (สารบัญเอกสารสำคัญ)

* 📖 **[PROGRESS.md](PROGRESS.md)**: สรุปสถานะโครงการล่าสุด, บันทึกการทดสอบ, ขั้นตอนการรันบน Production, และการติดตั้งในเครื่อง/Environment ใหม่
* 🤖 **[AGENTS.md](AGENTS.md)**: คำแนะนำ โครงสร้างโฟลเดอร์ สถาปัตยกรรม และกฎเกณฑ์สำหรับ AI Coding Agents (Cursor, Claude Code, Copilot, Antigravity)
* 🛠️ **[docs/development.md](docs/development.md)**: คู่มือการพัฒนาอย่างละเอียด, การเชื่อมต่อฐานข้อมูล Supabase / PostgreSQL, และการรัน Playwright Tests
* 📋 **[docs/quotation-image-system.md](docs/quotation-image-system.md)**: ข้อกำหนดและสเปกระบบฉบับเต็ม

---

## 🌐 Live System URLs (ระบบที่เปิดใช้งานจริง)

* **Web Application (Vercel):** [https://quotation-image-system.vercel.app](https://quotation-image-system.vercel.app)
* **API Backend (Render):** [https://quotation-api-h4ta.onrender.com](https://quotation-api-h4ta.onrender.com)

---

## ⚡ Quickstart (เริ่มต้นใช้งานด่วนในเครื่องใหม่)

### 1. ติดตั้ง Dependencies
```bash
# Python backend
python -m pip install -r requirements.txt

# Node.js frontend
cd apps/web
npm install
cd ../..
```

### 2. รันระบบ (Local Development)

* **วิธีที่ 1 (สะดวกสุดบน Windows):**  
  ดับเบิลคลิก `start-production.bat` หรือรัน `.\start-production.ps1` ใน PowerShell

* **วิธีที่ 2 (เปิดแยก 2 Terminal):**
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
  * เปิดบราวเซอร์ที่: `http://127.0.0.1:3000`

---

## 🧪 การรันชุดทดสอบ (Running Tests)

```bash
# Backend Unit Tests (47 tests)
python -m unittest discover -s apps/api/tests -p "test_*.py"

# Build Next.js Production
npm --prefix apps/web run build

# Cloud Deployment Verification
python test_render_upload.py
```
