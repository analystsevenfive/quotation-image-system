# Phase 2: local development

## Run on Windows

From the repository root, install Python dependencies and import the existing workbook once:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = 'apps/api'
python -m app.import_catalog 'web sevenfive 75.xlsx' --json .data/products.json
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd apps/web
npm ci
npm run build
npm start
```

Open http://127.0.0.1:3000. Upload `QT_test.pdf`, inspect the matches,
select a different product if necessary, generate, then download.
Use `npm run dev` instead of build/start while editing the frontend.

The local snapshot contains 40,194 rows with SKU or winspeed from the supplied
workbook. Requests never read Excel. The API loads a catalog index once at startup.
Restart the API after replacing the snapshot or importing a new database catalog.

## PostgreSQL / Supabase

1. Apply `apps/api/migrations/001_products.sql` using a trusted database administrator.
2. Set `DATABASE_URL` in the backend terminal (never `NEXT_PUBLIC_*`).
3. Run the import without `--json`:

```powershell
$env:PYTHONPATH = 'apps/api'
$env:DATABASE_URL = '<your private PostgreSQL connection string>'
python -m app.import_catalog 'web sevenfive 75.xlsx'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The import upserts by `good_id` in one transaction and rejects duplicate/missing IDs.
The supplied workbook has four rows with missing good_id; fill those identifiers before database import. Local JSON mode retains these rows.
It does not delete existing products. SKU, winspeed and model indexes are included.
Row-level security is enabled without public client policies; use a trusted backend
role with access. This phase caches the database catalog in memory until restart.
No database credentials were available during implementation, so live PostgreSQL
integration remains to be verified in the target environment.

## API

- `POST /api/quotations`: multipart field `file`; validates and analyzes immediately.
- `GET /api/quotations/{id}`: review state with candidates and safe display fields.
- `GET /api/quotations/{id}/preview`: original PDF, or latest generated PDF.
- `POST /api/quotations/{id}/items/{index}/select-product`: JSON `product_id`.
- `POST /api/quotations/{id}/generate`: generates with available, safely placed images.
- `GET /api/quotations/{id}/download`: downloads generated PDF.
- `GET /api/products/search?q=...`: at most 30 catalog results.
- `GET /api/products/{id}/image`: validated Shopify thumbnail proxy.
- `GET /api/health`: status and catalog count.

Review and success are stages of the root page. Clicking an item selects its image
and switches the PDF editor to its page. Refreshing the page returns to upload; history/reopening is
deferred. Manual selections apply to this quotation only, not future quotations.
Missing images, download failures and insufficient safe placement space do not
block generation. Staff manipulate images directly instead of entering coordinates.
No local image paths or match confidence values are exposed in the review UI.

## Adjusting and replacing images

1. Upload a quotation. Product images appear immediately on the original PDF.
2. Select a row in the product list or click its image on the document.
3. Drag the image to move it. Drag its bottom-right handle, or use the shrink/enlarge
   buttons, to resize while preserving aspect ratio. Arrow keys move the focused
   image one PDF point; Shift+Arrow moves five points.
4. Click **อัปโหลดรูป** to select a JPG, PNG or WEBP from the computer. You can also
   drop an image file on the PDF editor.
5. Double-click an image on the document (or click **ครอบตัด** on the toolbar /
   **ครอบตัดรูป** on the item in the sidebar) to enter inline Canva-style crop mode.
   Drag the crop frame or any of the 8 corner/edge handles directly on the PDF to frame
   the subject. Click **เสร็จสิ้น** (or press Enter) to apply the crop immediately.
   Press Escape or click **ยกเลิก** to cancel. If an uploaded/cropped image had an original
   catalog product, click **คืนค่ารูป Catalog** to revert to the original image anytime.
6. For a screenshot, use Win+Shift+S to capture an image, return to the app, select
   the destination item and press Ctrl+V. Copy image + Ctrl+V uses the same flow.
   Only image data delivered by the paste event is read; copied text/URLs are not
   fetched as images. The product-search dialog and text inputs retain normal paste.
7. Changes save automatically. **จัดอัตโนมัติ** resets placement while keeping the
   current image. Selecting a catalog product again restores its catalog image.
8. Generate and download. The original PDF is used for every export; images from
   previous exports are never inserted twice.

The dotted frame marks the current item's DESCRIPTION area. Moving/resizing is
constrained to this frame. A placement intersecting text turns red and is reverted
on release. The API independently checks row/column bounds, aspect ratio, minimum
size, finite coordinates and text collisions. Page zoom (100–200%) only affects the
editor display. Saved normalized rectangles convert to native PDF points on export.
PDF page rotation is explicitly rejected until rotated-template support is added.

Uploads are decoded, EXIF-oriented, stripped of metadata and stored as PNG bytes
inside the private quotation session. Limits: 10 MB per input/normalized image,
20 million pixels, 64 MB of image data per quotation on replacement. Uploaded images
do not alter Product Master and are cleared with the temporary quotation session.

Editor endpoints (all enforce quotation session ownership):

- `GET /api/quotations/{id}/original`: unchanged original PDF for the editor background.
- `POST /api/quotations/{id}/items/{index}/image`: multipart `file`, replace image.
- `GET /api/quotations/{id}/items/{index}/image`: current catalog or uploaded image.
- `PUT /api/quotations/{id}/items/{index}/placement`: normalized `{x,y,width,height}`.
- `DELETE /api/quotations/{id}/items/{index}/placement`: restore automatic placement.

Mutation responses include the refreshed editor state and invalidate a generated
download. Rejected edits preserve the previous image, placement and generated file.

## Temporary storage and limits

This phase is a **local development application**, bound to 127.0.0.1. It has no
user login and must not be exposed as a shared production service yet. Quotations
are held in memory under random IDs, with an HttpOnly SameSite session cookie and
ownership checks. A different browser session cannot retrieve another quotation.
Requests from other origins are rejected. Keep one API worker; memory state is
not shared across processes. Restart clears all quotations; sessions expire in 24
hours. Maximum 50 live quotations, 20 MB per PDF and 100 pages. The production
storage/authentication phase will replace this temporary store with Supabase.

The web image proxy accepts only HTTPS `cdn.shopify.com` URLs and does not follow
redirects. Local-image support remains available only in the original offline CLI.
PDFs are not sent to any external service; only product image URLs are fetched.

## Layout

`SEVEN_FIVE_TEMPLATE` remains configurable in `apps/api/app/core/template.py`.
Rows use detected boundaries. Images are constrained to the description column and
real row height; the former `image_min_slot_height` expansion is no longer honored.
When centered placement intersects text, the engine tries the largest text-free
vertical gap in the image slot. If no safe gap exists it skips the image.
Text collision is checked against PDF word boxes. Other templates and complex
drawings inside item rows require validation against real samples before use.

## Verification

```powershell
python -m unittest discover -s apps/api/tests -p 'test_*.py'
python run_full_excel_test.py
cd apps/web
npm run build
npx playwright install chromium
# Start API and web servers first, as above.
npx playwright test
```

The browser tests use the real local quotation and Shopify images; they need network
access and the imported company catalog. It verifies upload, PDF.js preview,
manual replacement, file upload, pointer move/resize, drag after zoom, actual Ctrl+V
image paste, generation, download and mobile overflow. Backend tests use
generated PDFs and stubbed images and can run offline.

Framework setup follows [Next.js installation](https://nextjs.org/docs/app/getting-started/installation),
[FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/) and
[React-PDF worker setup](https://github.com/wojtekmaj/react-pdf).


## Covered text and Unicode product codes

PDF analysis, editor collision geometry and export use the shared
`services/pdf/visible_text.py` extractor. It ignores words whose glyphs are
fully covered by later, opaque, ungrouped rectangular fills. The source PDF is
never redacted or rasterized. Transparent fills, outlines, complex/clipped
shapes and partially covered words are retained conservatively; this is not a
general PDF visibility solver or document sanitization feature.

SKU extraction normalizes Unicode hyphens (including U+00AD), preserves decimal
model codes and prioritizes explicit `SKU:` / `MODEL / SKU:` labels. Model
matching also indexes the full suffix of structured catalog brand SKUs, so an
imported truncated model such as `331` does not prevent matching `331.044`.
Duplicate candidates continue to require manual review.

The local 34-page `QT_TEST_100_EXACT_TEMPLATE (1).pdf` contains text underneath
painted replacement rows. The corrected parser detects 100 visible item rows;
models `SS120-2` and `CSMHDTK145-000` have multiple catalog candidates and must
remain under review. Synthetic regression coverage is in `test_visible_text.py`;
the company PDF is not added as a committed test fixture.
