# Quotation Image Automation System

Updated: 2026-09-10

## สถานะปัจจุบัน (Current Status)

ระบบพร้อมสำหรับการใช้งานจริง (Production Ready) ครอบคลุม **Phase 1, Phase 2, และ Phase 3** ครบถ้วน:
- **Phase 1**: PDF Engine (PyMuPDF coordinate detection, boundary detection, image insertion)
- **Phase 2**: Quotation Studio Web Application (PDF preview, Canva-style inline crop, drag/resize, Ctrl+Z/Ctrl+Y undo-redo, spacebar pan, single & batch delete)
- **Phase 3**: Product Mapping Persistence (ระบบจดจำ SKU ที่เคยจับคู่ข้ามเอกสารอัตโนมัติ พร้อมหน้าต่าง "คู่สินค้าที่จำไว้" และป้าย "จำจากประวัติ")
- **Phase 4**: (Quotation History / PDF storage) ถูกพักไว้ตามคำสั่ง เพื่อเปิดให้ผู้ใช้เริ่มใช้งานระบบจริงก่อน

---

## ผลการทดสอบ (Verified)

- **47 Backend Unit Tests ผ่าน 100%**:
  - `python -m unittest discover -s apps/api/tests`
- **8 Playwright End-to-End Test Suites ผ่าน 100%**:
  1. `workflow.spec.ts`: อัปโหลดเอกสาร, ตรวจสอบสินค้า, เลือกสินค้าด้วยตนเอง, สร้างและดาวน์โหลด PDF
  2. `saved-mappings.spec.ts`: ตรวจสอบการจำ SKU ข้ามเอกสาร, การแสดงผลในหน้าต่าง "คู่สินค้าที่จำไว้", ป้าย "จำจากประวัติ"
  3. `image-editor.spec.ts`: ลากย้ายรูป, ย่อ-ขยายรูป, ปรับตำแหน่ง, วางรูปจากคลิปบอร์ด (Ctrl+V)
  4. `image-crop.spec.ts`: ครอบตัดรูปภาพบนหน้า PDF แบบ inline สไตล์ Canva
  5. `undo-redo.spec.ts`: ปุ่มย้อนกลับ/ทำซ้ำ, คีย์ลัด Ctrl+Z / Ctrl+Y
  6. `pan-view.spec.ts`: กด Spacebar เลื่อนดูเอกสาร, เครื่องมือ Hand Tool
  7. `delete-image.spec.ts` (Single Delete): ลบรูปรายชิ้น, ปุ่มลัด Delete, กู้คืนรูป
  8. `delete-image.spec.ts` (Batch Delete): ติ๊ก Checkbox หลายรายการ, Shift+Click, แถบเครื่องมือกลุ่ม, ลบพร้อมกันในคลิกเดียว
- **Next.js Production Build**: คอมไพล์ผ่านสมบูรณ์ 100% ไร้ข้อผิดพลาด

---

## วิธีการเปิดใช้งานบน Production (How to Run in Production)

### วิธีที่ 1: ดับเบิลคลิกไฟล์สคริปต์
- **`start-production.bat`** (Windows Batch): ดับเบิลคลิกเพื่อเริ่มระบบทั้ง Backend และ Frontend ได้ทันที

### วิธีที่ 2: รันผ่าน PowerShell
- **`.\start-production.ps1`**: สคริปต์จะเริ่มระบบพร้อมแสดง IP Address ของเครื่องสำหรับแชร์ให้ผู้อื่นในองค์กรเข้าใช้งาน

### ลิงก์เข้าใช้งาน
- สำหรับเครื่องเซิร์ฟเวอร์: `http://127.0.0.1:3000`
- สำหรับเครื่องอื่นๆ ในเครือข่ายภายใน (LAN): `http://<IP_ของเซิร์ฟเวอร์>:3000`
