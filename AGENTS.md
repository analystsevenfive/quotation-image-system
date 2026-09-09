# AGENTS.md

## Project
Quotation Image Automation System

## Required Reading
Before making architectural changes or implementing major features, read:
- `docs/quotation-image-system.md`

## Core Stack
- Frontend: Next.js + TypeScript + Tailwind CSS + shadcn/ui
- PDF Preview: PDF.js or react-pdf
- Backend: Python + FastAPI
- PDF Engine: PyMuPDF (`fitz`)
- HTTP Client: httpx
- Database: PostgreSQL / Supabase
- Auth: Supabase Auth + Google OAuth
- PDF Storage: Supabase Storage
- Product Images: existing Shopify CDN URLs from `products.image_url`

## Architecture
Preferred initial architecture:

```text
Next.js
   ↓
FastAPI
   ↓
PyMuPDF
   ↓
PostgreSQL / Supabase
   ↓
Shopify CDN
```

Do not add Kubernetes, microservices, Redis, or Celery unless there is a proven need.

## Highest Priority
Build and validate the PDF engine first:

```text
Upload PDF
→ Extract ITEM + SKU/model + coordinates
→ Match Product Master
→ Retrieve image_url
→ Insert image into correct item area
→ Export PDF
```

Do not build authentication, history, admin settings, or advanced batch processing before this works reliably with real quotation PDFs.

## PDF Rules
- Use PyMuPDF for selectable-text PDFs.
- Do not use OCR by default.
- Do not rasterize the whole PDF.
- Preserve original PDF text/vector quality.
- Never hardcode fixed Y positions for item rows.
- Detect the real vertical range of each quotation item.
- Keep product images inside the DESCRIPTION column.
- Never overlap QTY, PRICE, or NET PRICE.
- Preserve image aspect ratio.
- Scale images down when item height is small.
- Keep layout rules configurable for future quotation templates.

## Matching Rules
Priority:
1. Exact SKU
2. Exact winspeed
3. Normalized SKU
4. Model
5. Manual review

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

Never auto-accept ambiguous matches.

## Product Master
Existing spreadsheet columns:
```text
good_id
sku
winspeed
product_url
link_image
```

Target database fields:
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

Google Sheets can remain a source of truth, but quotation processing should query PostgreSQL instead of reading the sheet for every request.

## UX Rules
Normal user flow:
```text
Upload PDF
→ Auto Process
→ Review
→ Generate PDF
→ Download
```

Review page:
```text
Left:  PDF Preview
Right: Product Match List
```

Do not expose PDF coordinates or technical matching internals to normal staff.
Missing images must not block PDF generation.

## Security
- Treat quotation PDFs as private company documents.
- Validate file type and size.
- Use safe/randomized storage keys.
- Never expose Supabase service-role keys to frontend code.
- Never show raw Python stack traces to users.

## Code Quality
- Keep PDF parsing, matching, image retrieval, and PDF rendering in separate modules.
- Keep business logic separate from API/controller code.
- Add unit tests for:
  - SKU normalization
  - SKU/model matching
  - Item boundary detection
  - Image fitting calculations

## OCR / AI Policy
Do not introduce OCR or AI for deterministic tasks PyMuPDF can solve.
OCR may be added later only as an isolated fallback for image-only PDFs.

## Development Workflow
Before implementing a major phase:
1. Read the specification.
2. Explain the implementation plan.
3. List assumptions and risks.
4. Define affected files/modules.
5. Implement incrementally.
6. Add tests.
7. Validate with real quotation samples.

Do not silently guess PDF layout behavior. Make uncertain rules configurable.
