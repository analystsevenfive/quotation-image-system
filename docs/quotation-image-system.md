# Quotation Image Automation System

## 1. Goal
Build an internal web application that automatically adds product images into quotation PDFs.

Primary workflow:

```text
Upload quotation PDF
→ Detect quotation items
→ Detect SKU/model
→ Match Product Master
→ Load Shopify CDN image
→ Review
→ Generate final PDF
→ Download
```

The application will be used by multiple staff members, so prioritize simple UX, reliability, maintainability, and clear error handling.

---

## 2. Tech Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- PDF.js or react-pdf

### Backend
- Python
- FastAPI
- PyMuPDF / `fitz`
- httpx

### Database / Auth / Storage
- PostgreSQL / Supabase
- Supabase Auth
- Google OAuth
- Supabase Storage for original and generated PDFs

### Product Images
Use existing Shopify CDN URLs from the Product Master.
Do not create a second permanent image repository for the MVP.

---

## 3. Product Master

Current spreadsheet columns:

```text
good_id
sku
winspeed
product_url
link_image
```

Example:

```text
good_id: 1656
sku: BER1-BMCFP4
winspeed: BER1-BMCFP4
product_url: https://www.sevenfive.co.th/products/...
link_image: https://cdn.shopify.com/s/files/.../BER1-BMCFP4.jpg?v=...
```

Target table:

```text
products
- id
- good_id
- sku
- winspeed
- model
- product_url
- image_url
- image_status
- created_at
- updated_at
```

`image_status`:
```text
available
missing
broken
```

Do not query Google Sheets for every quotation request.
Preferred flow:

```text
Google Sheets
→ periodic sync
→ PostgreSQL
→ quotation processing
```

---

## 4. SKU / Model Matching

Priority:

```text
1. Exact SKU
2. Exact winspeed
3. Normalized SKU
4. Model match
5. Manual review
```

Example:

```text
Database SKU: BER1-BMCFP4
Quotation value: BER1-BMCFP4
```

or:

```text
Quotation value: BMCFP4
```

Store model separately when possible:

```text
sku: BER1-BMCFP4
model: BMCFP4
```

Statuses:

```text
matched
needs_review
missing
manual
```

Match methods:

```text
exact_sku
winspeed
normalized_sku
model
manual
```

Also store `match_confidence`.

Never auto-accept ambiguous matches.

---

## 5. SKU Normalization

Create a dedicated testable normalization function.

It may:
- trim whitespace
- uppercase values
- normalize Unicode dash characters
- remove accidental line breaks
- preserve meaningful hyphens
- support safe brand-prefix/model extraction

Do not normalize so aggressively that false matches become likely.

---

## 6. PDF Processing

Most quotation PDFs contain selectable text.

Use PyMuPDF first.
Do not use OCR by default.

Extract:
- page number
- words
- text
- bounding boxes
- coordinates

Example:

```text
CSHL550
x0 = 143
y0 = 460
x1 = 205
y1 = 473
```

---

## 7. Quotation Item Detection

Typical table:

```text
ITEM
DESCRIPTION
QTY
PRICE
NET PRICE
```

Detect:
- item number
- item description
- SKU/model candidate
- page number
- item vertical range

Do not hardcode fixed Y coordinates.

Bad:

```text
Item 1 = Y500
Item 2 = Y700
```

Correct approach:

```text
Item 1
start_y = 450
end_y = 600

Item 2
start_y = 600
end_y = 742
```

When appropriate, use the next item's `start_y` as the previous item's `end_y`.

For the last item on a page, use the table/footer boundary.

---

## 8. Image Placement

Product images belong inside the DESCRIPTION column, normally toward the right side.

Rules:
- preserve aspect ratio
- never stretch
- stay inside a configurable bounding box
- never overlap QTY / PRICE / NET PRICE
- avoid important description text
- scale down automatically when available height is small
- support JPG/JPEG/PNG/WEBP where practical
- handle transparent PNG correctly

Do not rasterize the whole PDF.
Preserve original text and vector quality.

---

## 9. Quotation Templates

Do not permanently hardcode all coordinates.

Prepare a `quotation_templates` concept.

Possible fields:

```text
id
name
description_x0
description_x1
item_column_x0
item_column_x1
qty_column_x0
footer_y
image_max_width
image_max_height
image_alignment
```

This allows support for different quotation layouts later.

---

## 10. Image Retrieval

Flow:

```text
SKU/model
→ find product
→ get image_url
→ HTTP GET
→ validate
→ fit image
→ insert into PDF
```

Use `httpx`.

Implement:
- connection/read timeouts
- limited retries
- max image size
- status-code validation
- Content-Type validation
- actual image decode validation

One broken image must not fail the entire quotation.

---

## 11. Main UX

Normal staff workflow:

```text
Upload PDF
→ Process automatically
→ Review
→ Generate PDF
→ Download
```

Do not require normal users to understand:
- PDF coordinates
- database IDs
- Shopify URLs
- file paths
- matching internals

---

## 12. Upload Page

Suggested UI:

```text
┌───────────────────────────────────────┐
│       Add Images to Quotation         │
│                                       │
│     Drag & Drop Quotation PDF         │
│                                       │
│          [ Upload PDF ]               │
│                                       │
│          PDF files only               │
└───────────────────────────────────────┘
```

After upload, start processing automatically.

Progress states:
```text
Uploading PDF
Reading quotation
Detecting products
Matching images
Preparing preview
```

---

## 13. Review Page

Desktop layout:

```text
┌────────────────────────┬──────────────────────┐
│                        │ Product Matches      │
│                        │                      │
│      PDF Preview       │ CSHL550              │
│                        │ ✓ Matched            │
│                        │ [thumbnail]          │
│                        │                      │
│                        │ DB-CW76-DRG          │
│                        │ ✓ Matched            │
│                        │                      │
│                        │ DB-PP120-GY          │
│                        │ ⚠ Image Missing      │
└────────────────────────┴──────────────────────┘
```

Summary example:

```text
20 Items
18 Matched
1 Needs Review
1 Missing
```

When a user clicks a product:
- scroll preview to its page/item
- highlight the corresponding item if practical

For matched items:
- show image thumbnail
- show SKU/model
- show status
- allow `Replace Image`

For `needs_review`:
- show candidate products/images
- let user select one

Manual selection should set:
```text
match_status = manual
match_method = manual
```

---

## 14. Generate PDF

Primary button:

```text
Generate PDF
```

If images are missing:

```text
1 product image is missing.

You can still generate the PDF.

[ Review Missing ]
[ Generate Anyway ]
```

Missing images must not block generation.

---

## 15. Success Page

Example:

```text
✓ PDF Ready

QT0926-00287

20 Products
19 Images Added
1 Image Missing

[ Download PDF ]
[ Process Another PDF ]
```

---

## 16. History

History should show:
- quotation number
- original filename
- created date
- created by
- item count
- matched count
- missing count
- processing status

Statuses:

```text
processing
ready
failed
```

Allow reopening completed quotations.

---

## 17. Database Design

### profiles
```text
id
email
display_name
role
created_at
```

### products
```text
id
good_id
sku
winspeed
model
product_url
image_url
image_status
created_at
updated_at
```

### quotations
```text
id
quotation_number
original_filename
original_file_path
output_file_path
status
created_by
created_at
completed_at
```

### quotation_items
```text
id
quotation_id
item_number
description
detected_sku
detected_model
matched_product_id
match_status
match_method
match_confidence
page_number
x0
y0
x1
y1
selected_image_url
created_at
updated_at
```

### product_image_mappings
```text
id
detected_value
product_id
created_by
created_at
updated_at
```

### processing_jobs
```text
id
quotation_id
status
progress
error_code
error_message
started_at
completed_at
```

---

## 18. Suggested API

```http
POST /api/quotations
GET  /api/quotations/{id}
POST /api/quotations/{id}/analyze
POST /api/quotations/{id}/generate
GET  /api/quotations/{id}/download

GET  /api/quotations/{id}/items

POST /api/items/{id}/select-product
POST /api/items/{id}/replace-image

GET  /api/products/search
GET  /api/history
```

---

## 19. Frontend Routes

```text
/
 /upload
 /quotations/[id]/review
 /quotations/[id]/success
 /history
 /settings
```

---

## 20. Admin Settings

Keep technical settings away from normal users.

Possible admin settings:
- image max width
- image max height
- image alignment
- DESCRIPTION column boundaries
- matching behavior
- quotation template rules

---

## 21. Security

Treat uploaded quotation PDFs as private company documents.

Requirements:
- authenticated access
- authorization checks
- safe filenames
- randomized storage keys
- file type validation
- max upload size
- secure download handling
- never trust extensions alone
- never expose Supabase service-role keys to frontend code
- never show raw backend stack traces to users

---

## 22. Error Handling

Handle:
- no selectable PDF text
- image-only PDF
- SKU not found
- multiple candidates
- missing image URL
- broken Shopify CDN image
- image timeout
- unsupported image
- multi-page quotations
- long quotations
- PDF generation failure

Do not fail an entire quotation because one image is unavailable.

---

## 23. OCR Policy

Primary path:

```text
PyMuPDF text extraction
```

Do not use OCR by default.

OCR may be added later only as an isolated fallback for image-only PDFs.

---

## 24. MVP Architecture

Use:

```text
Next.js
→ FastAPI
→ PyMuPDF
→ PostgreSQL / Supabase
→ Shopify CDN
```

Do not initially add:
- Kubernetes
- microservices
- Redis
- Celery

---

## 25. Suggested Monorepo

```text
project/
├─ AGENTS.md
├─ README.md
├─ apps/
│  ├─ web/
│  └─ api/
├─ packages/
│  └─ shared/
└─ docs/
   └─ quotation-image-system.md
```

Possible backend layout:

```text
apps/api/
├─ app/
│  ├─ api/
│  ├─ core/
│  ├─ db/
│  ├─ models/
│  ├─ schemas/
│  ├─ services/
│  │  ├─ pdf/
│  │  ├─ matching/
│  │  ├─ images/
│  │  └─ products/
│  └─ main.py
└─ tests/
```

---

## 26. Testing

Unit tests should cover:

### SKU normalization
```text
BER1-BMCFP4
ber1-bmcfp4
BER1–BMCFP4
BER1-BMCFP4\n
```

### Matching
- exact SKU
- exact winspeed
- normalized SKU
- model
- ambiguous model
- missing product

### PDF item detection
- variable item heights
- multiple items per page
- final item before footer
- multiple pages

### Image fitting
- landscape
- portrait
- square
- transparent PNG
- very small item area

---

## 27. Development Phases

### Phase 1 — PDF Engine Proof of Concept

Implement only:

```text
One real quotation PDF
→ Detect items
→ Detect SKU/model
→ Match sample Product Master
→ Download Shopify image
→ Insert image
→ Export final PDF
```

Deliver:
- PyMuPDF extraction prototype
- item boundary detection
- SKU/model detector
- matching module
- image downloader
- image fitting
- PDF output
- tests

Do not implement authentication, history, or admin yet.

### Phase 2 — Basic Web UX
- upload
- processing state
- review
- generate
- download

### Phase 3 — Product Master
- PostgreSQL products table
- spreadsheet sync
- product search
- manual mapping persistence

### Phase 4 — Authentication + History
- Google login
- profiles
- history
- reopen quotation

### Phase 5 — Admin + Templates
- template configuration
- layout settings
- matching settings

---

## 28. First Coding Prompt

Use this when starting work with Cursor, Claude Code, Codex, or another coding agent:

```text
Read AGENTS.md and docs/quotation-image-system.md.

Understand the project requirements before coding.

Implement Phase 1 only.

Requirements:
1. Accept one quotation PDF.
2. Use PyMuPDF to extract item numbers, description text, SKU/model candidates, page numbers, and coordinates.
3. Match detected products against sample Product Master data.
4. Retrieve the selected product image from image_url.
5. Insert the image into the DESCRIPTION column without overlapping QTY, PRICE, or NET PRICE.
6. Preserve aspect ratio and original PDF quality.
7. Export the processed PDF.
8. Add unit tests for SKU normalization, matching, item boundary detection, and image fitting.

Do not implement authentication, history, admin settings, Redis, Celery, Kubernetes, or microservices.

Before coding:
- explain the proposed implementation plan
- show the proposed file structure
- list assumptions
- identify PDF-layout risks

Do not silently guess uncertain PDF coordinates.
Make layout rules configurable.
```

---

## 29. MVP Success Criteria

A normal staff member can:

```text
1. Upload a real quotation PDF
2. Wait for automatic processing
3. Review detected products and images
4. Resolve incorrect/missing matches if needed
5. Generate the quotation
6. Download a PDF with correctly positioned product images
```

The user should not need to understand PDF internals, SKU matching logic, Shopify URLs, or database structure.
