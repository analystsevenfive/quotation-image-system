# Sevenfive Product Scanner — Design System

เอกสารระบบการออกแบบ (Design System Specification) สำหรับระบบ **Sevenfive Product Scanner**
ไฟล์สไตล์ชีตหลัก: [`public/design.css`](file:///u:/25.WEBSITE/product-scanner/product-scanner/public/design.css)
หน้าเว็บหลัก: [`public/index.html`](file:///u:/25.WEBSITE/product-scanner/product-scanner/public/index.html)

---

## 1. ปรัชญาการออกแบบ (Design Philosophy)

1. **Mobile-First & Warehouse-Ready**: ออกแบบให้ใช้งานสะดวกที่สุดบนสมาร์ทโฟนและแท็บเล็ตในคลังสินค้า ด้วยปุ่มสัมผัสขนาดใหญ่ (Touch Targets ≥ 44px) และคอนทราสต์ที่ชัดเจนแม้อยู่ในที่แสงจ้า
2. **Speed & Clarity**: แสดงข้อมูลราคาสินค้า, สต็อก, และโมเดลอย่างรวดเร็ว ชัดเจน ไม่รกรุงรัง
3. **Elevated Industrial Aesthetic**: ผสมผสานความเป็นมืออาชีพของอุปกรณ์ครัวเชิงพาณิชย์ (Seven Five) ด้วยโทนสีเขียว Forest Emerald ตัดกับสีทอง Brass Accent บนพื้นผิวกระจกที่นุ่มนวล (Subtle Glassmorphism)

---

## 2. โทนสีและ Design Tokens

กำหนดไว้ใน `:root` ของ [`public/design.css`](file:///u:/25.WEBSITE/product-scanner/product-scanner/public/design.css):

### 2.1 Brand & Primary Colors (เขียวมรกต)
| Token | HEX / Value | ตัวอย่างการใช้งาน |
| :--- | :--- | :--- |
| `--brand` | `#0c7255` | สีหลักของแบรนด์, ปุ่มหลัก (Primary Button), ไฮไลต์ข้อความสำคัญ |
| `--brand-strong` | `#095a43` | สถานะ Hover/Active ของปุ่มหลัก |
| `--brand-dark` | `#0b3b31` | สี Header Bar, Theme-color บนมือถือ |
| `--brand-soft` | `#e8f5ef` | พื้นหลังของ Badge และกล่องข้อความสำคัญ |

### 2.2 Accent Color (ทองเหลือง / ทองอ่อน)
| Token | HEX / Value | ตัวอย่างการใช้งาน |
| :--- | :--- | :--- |
| `--accent` | `#d8a85d` | แถบราคาพิเศษ, แสง Gradient พื้นหลัง, แถบขอบประดับ |

### 2.3 Surface & Neutral Colors (พื้นผิวและตัวอักษร)
| Token | HEX / Value | ตัวอย่างการใช้งาน |
| :--- | :--- | :--- |
| `--background` | `#f2f5f3` | สีพื้นหลังหลักของทั้งหน้าเว็บ |
| `--surface` | `#ffffff` | พื้นหลังของการ์ดและโมดอล |
| `--surface-soft` | `#f7f9f8` | พื้นหลังของช่อง Input และตารางข้อมูล |
| `--text` | `#13231e` | สีตัวอักษรหลัก (High Contrast) |
| `--muted` | `#66756f` | สีคำอธิบายย่อย และ Label |
| `--border` | `#dce5e1` | เส้นขอบการ์ดและเส้นแบ่งตาราง |

### 2.4 Semantic Status Colors (สถานะระบบ)
| สถานะ | Token พื้นหน้า | Token พื้นหลัง | การใช้งาน |
| :--- | :--- | :--- | :--- |
| **Success** | `--success` (`#087443`) | `--success-soft` (`#eaf8f0`) | สแกนพบสินค้า, สัญญาณออนไลน์, พร้อมใช้งาน |
| **Danger** | `--danger` (`#b42318`) | `--danger-soft` (`#fff0ee`) | ไม่พบสินค้า, เกิดข้อผิดพลาด, ออกจากระบบ |
| **Warning** | `--warning` (`#9a6700`) | `--warning-soft` (`#fff7df`) | สินค้าไม่มีสต็อก, อยู่นอกพื้นที่ Geofence |

### 2.5 Radius & Elevation (ความโค้งมนและเงา)
```css
--radius-xl: 26px; /* ขอบการ์ดหลัก (Main Cards) */
--radius-lg: 20px; /* ขอบโมดอล และกล่องสแกนเนอร์ */
--radius-md: 14px; /* ขอบปุ่ม และช่อง Input */
--shadow: 0 20px 60px rgba(11, 35, 27, 0.05), 0 4px 18px rgba(11, 35, 27, 0.015);
```

---

## 3. ระบบตัวอักษร (Typography)

ระบบใช้ฟอนต์สากลและฟอนต์ภาษาไทยที่ให้ความคมชัดและอ่านง่ายในทุกขนาดหน้าจอ:

* **Latin Typography**: `"Plus Jakarta Sans"`
* **Thai Typography**: `"Noto Sans Thai"`
* **Fallback**: `system-ui, -apple-system, sans-serif`

### ลำดับชั้นขนาดตัวอักษร (Hierarchy)
- **H1 (Page Title)**: `1.6rem - 2.0rem` (Bold 800)
- **H2 / Card Title**: `1.2rem - 1.4rem` (Semi-bold 600/700)
- **Price / Hero Number**: `2.2rem - 2.8rem` (Extra-bold 800, Font: Plus Jakarta Sans)
- **Body Text**: `0.95rem - 1.0rem` (Regular 400 / Medium 500)
- **Caption & Labels**: `0.75rem - 0.85rem` (Medium 500, Uppercase tracking เมื่อเป็นภาษาอังกฤษ)

---

## 4. มาตรฐานคอมโพเนนต์ (Component Library)

### 4.1 Header Bar & Topbar
* มีโลโก้แบรนด์ Seven Five (`/logo/CI_logo_75_2026-01.avif`) และข้อความระบุเวอร์ชันระบบ
* แถบ User Bar ด้านบนสุด แสดงสถานะการเข้าสู่ระบบ (Guest / Staff) พร้อมไฟแสดงสถานะ Dot สีเขียว/แดง

### 4.2 Scanner Viewport
* กรอบสแกนกล้องรองรับความโค้งมนมน `--radius-lg`
* มีแสงเลเซอร์สแกนแนวนอนจำลอง (Scanning Line Animation)
* ปุ่มควบคุมไฟฉาย (Flash / Torch) และปุ่มสลับกล้องหน้า-หลัง

### 4.3 Input Group & Action Buttons
* **Primary Action**: พื้นหลัง `--brand`, ข้อความสีขาว, มี Hover lift effect นุ่มนวล
* **Quick Discount Buttons**: ปุ่มลัดคำนวณส่วนลด 20%, 30%, 40%, 50% วางเรียงในแนวนอน แสดงราคาสุทธิหลังหักส่วนลดทันที

### 4.4 Result Card (แสดงผลสินค้า)
* **Product Hero**: แสดงรหัส SKU ขนาดใหญ่ พร้อมปุ่ม One-click Copy to Clipboard
* **Price Badge**: แสดงราคาขายล่าสุดเด่นชัด
* **Data Table**: ตารางรายละเอียดสินค้า (ชื่อรุ่น, แบรนด์, กลุ่มสินค้า, สถานะสต็อก)

---

## 5. การเคลื่อนไหวและการเข้าถึง (Animation & Accessibility)

* **Micro-animations**: มี Floating Box Animation และ Rotating Gears ในสถานะพัก (Idle State) เพื่อให้หน้าเว็บดูมีชีวิตชีวา
* **Haptic Feedback**: มีการสั่นเตือนเบาๆ (`navigator.vibrate`) เมื่อสแกนโค้ดสำเร็จ
* **Reduced Motion**: รองรับ `@media (prefers-reduced-motion: reduce)` ปิดเอฟเฟกต์การเคลื่อนไหวอัตโนมัติสำหรับผู้ใช้ที่ตั้งค่าลดการเคลื่อนไหว
