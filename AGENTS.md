# AGENTS.md

## Project
**Quotation Image Automation System**  
Automated extraction and insertion of product images into quotation PDFs using PyMuPDF and Next.js.

## Current Project Status
- **Phase 1 (PDF Engine & Matching)**: ✅ Complete. Tested with 40,194 catalog products.
- **Phase 2 (Quotation Web Studio & Editor)**: ✅ Complete. Drag/resize, Canva-style crop, undo/redo (Ctrl+Z/Y), paste image (Ctrl+V), single & batch delete.
- **Phase 3 (Product Mapping Persistence)**: ✅ Complete. Remembers user-selected SKU mappings cross-document with "Saved Mappings" dialog.
- **Cloud Deployment**: ✅ Complete.
  - Web: `https://quotation-image-system.vercel.app` (Vercel)
  - API: `https://quotation-api-h4ta.onrender.com` (Render)
- **Phase 4 (History & Supabase Auth & Storage)**: ⏳ Deferred per instruction until initial production usage is established.

---

## Required Reading
Before making architectural changes or implementing major features, read:
- `docs/quotation-image-system.md`
- `docs/development.md`
- `PROGRESS.md`

---

## Core Stack & Architecture

```text
Next.js (Vercel)
   ↓ (Reverse Proxy /api/*)
FastAPI (Render)
   ↓
PyMuPDF (`fitz`) Engine + Pillow
   ↓
PostgreSQL / Supabase (Catalog & Saved Mappings)
   ↓
Shopify CDN (Product Images)
```

- **Frontend**: Next.js 16 (App Router, Turbopack, TypeScript, Tailwind CSS, Lucide icons, PDF.js preview)
- **Backend API**: Python 3.10+ (FastAPI, Uvicorn, PyMuPDF, Pillow, HTTPX)
- **Database / Platform**: Supabase / PostgreSQL (40k+ products, migrations in `apps/api/migrations/001_products.sql`)
- **Image Source**: Shopify CDN URLs (`cdn.shopify.com`)

*Architecture Directive: Keep it simple. Do not add Kubernetes, microservices, Redis, Celery, or heavy message queues unless there is a proven bottleneck.*

---

## Repository Structure Map

```text
quotation-image-system-starter/
├── AGENTS.md                  # Instructions for AI coding agents (this file)
├── PROGRESS.md                # Progress tracker and environment migration guide
├── README.md                  # Quickstart documentation
├── render.yaml                # Infrastructure configuration for Render backend
├── requirements.txt           # Top-level Python requirements (points to apps/api)
├── start-production.bat       # Windows one-click local production launcher
├── start-production.ps1       # PowerShell local production launcher with IP display
├── test_render_upload.py      # Cloud deployment E2E upload verification script
│
├── apps/
│   ├── api/                   # Backend FastAPI Application
│   │   ├── requirements.txt   # Backend dependencies
│   │   ├── migrations/        # SQL migration files for PostgreSQL/Supabase
│   │   ├── app/
│   │   │   ├── main.py        # FastAPI factory, CORS, session & error middleware
│   │   │   ├── import_catalog.py # Catalog importer (Excel/JSON/PostgreSQL)
│   │   │   ├── core/          # Template definitions & config
│   │   │   ├── models/        # Pydantic data models
│   │   │   └── services/      # Core business logic:
│   │   │       ├── pdf/       # PyMuPDF boundary detection, text collision & renderer
│   │   │       ├── matching/  # 5-tier catalog matcher & saved mappings store
│   │   │       ├── images/    # Shopify CDN downloader & upload handler
│   │   │       ├── editor.py  # Image placement & Canva-style crop calculations
│   │   │       └── history.py # Undo / Redo state management
│   │   └── tests/             # 47 unit & integration tests (100% passing)
│   │
│   └── web/                   # Frontend Next.js Application
│       ├── package.json       # Web dependencies & scripts
│       ├── next.config.ts     # Turbopack config & /api/* proxy rewrite rules
│       ├── src/
│       │   ├── app/           # Next.js App Router (layout, globals.css, page.tsx)
│       │   ├── components/    # UI components (pdf-preview.tsx, mappings-dialog.tsx)
│       │   └── lib/           # Client API client (api.ts) & placement math
│       └── tests/             # 8 Playwright E2E test suites (100% passing)
│
├── .data/
│   └── products.json          # Local JSON snapshot of 40,194 catalog products
└── docs/
    ├── development.md         # Detailed local development & database guide
    └── quotation-image-system.md # Original business and functional specifications
```

---

## Quickstart & Verification Commands

### 1. Run Backend Unit Tests (47 tests)
```bash
python -m unittest discover -s apps/api/tests -p "test_*.py"
```

### 2. Run Next.js Build
```bash
cd apps/web
npm run build
cd ../..
```

### 3. Run End-to-End Tests (Playwright)
```bash
cd apps/web
# Ensure backend (port 8000) and frontend (port 3000) are running
npx playwright test
cd ../..
```

### 4. Test Cloud Deployment Upload
```bash
python test_render_upload.py
```

### 5. Local Development Startup
* **Backend:**
  ```powershell
  $env:PYTHONPATH = "apps/api"
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```
* **Frontend:**
  ```powershell
  cd apps/web
  npm run dev
  ```

---

## Strict Rules & Invariants for Agents

### PDF Processing
- **Use PyMuPDF (`fitz`) only**: Do not introduce OCR by default. OCR is reserved as a future fallback for scanned non-selectable PDFs only.
- **Never rasterize the PDF**: Preserve 100% of original vector text and quality.
- **Never hardcode Y coordinates**: Item heights vary. Always detect vertical boundaries dynamically using `apps/api/app/services/pdf/boundary.py`.
- **Strict Column Boundaries**: Images must reside strictly inside the `DESCRIPTION` column. Never overlap `QTY`, `PRICE`, or `NET PRICE`.
- **Preserve Aspect Ratio**: Images must never be stretched or distorted. Use `fitter.py` to calculate safe aspect-ratio bounds and avoid text collisions.

### Catalog Matching
Hierarchy must strictly follow:
1. Exact SKU (`confidence = 1.0`)
2. Exact Winspeed (`confidence = 0.95`)
3. Normalized SKU (`confidence = 0.90`)
4. Model Match (`confidence = 0.80`, or `needs_review` if multiple candidates)
5. Missing / Manual Review (`confidence = 0.0`)
*Never auto-accept ambiguous matches.*

### Architecture & Security
- **Quotation Privacy**: Quotation PDFs are private company documents. Sessions are identified by cryptographically random 64-character tokens.
- **Cookie Security**: Set `HttpOnly=True`, `SameSite=None` on HTTPS (or `Lax` on HTTP), and `Secure=True` on HTTPS.
- **Cross-Origin & CORS**: Requests routed via Next.js `/api/*` rewrites avoid third-party cookie blocking. Allowed origins must be handled safely via `ALLOWED_ORIGINS`.
- **Zero Raw Stack Traces**: Never return internal server errors or Python stack traces directly to the client.

### Separation of Concerns
- Keep PDF coordinate math, boundary detection, image retrieval, and matching in distinct modules under `apps/api/app/services/`.
- Do not place heavy business logic directly inside FastAPI route handlers (`main.py`).
- Maintain existing tests whenever modifying services.
