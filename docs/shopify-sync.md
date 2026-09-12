# Shopify Catalog Sync to Supabase

Automated synchronization system transferring product catalog data, images, prices, inventory, and custom metafields from Shopify into Supabase PostgreSQL.

Adapted directly from Google Apps Script `synWebForCostDepartment.js` and `property.js`.

---

## 1. Features & Architecture

```text
Shopify Bulk Operations GraphQL API
            ↓ (JSONL Stream)
Python Sync Engine (`app.services.shopify_sync`)
            ↓
Image Normalization (`&width=200`) & Model Extraction
            ↓ (Batch Upsert 5,000 / batch)
Supabase PostgreSQL (`products` & `sync_logs`)
```

- **Daily Schedule**: Runs automatically every day at **19:00 Bangkok Time** (ICT, UTC+7), which corresponds to **12:00 UTC** (`0 12 * * *`).
- **Data Extracted**:
  - `GoodID` (`metafield(namespace: "custom", key: "good_id")`)
  - `Variant SKU` / `sku` / `winspeed`
  - `Model` (auto-extracted from SKU prefix)
  - `Title`, `Brand` (`vendor`), `Status`
  - `Product Type` (`custom.part_type`)
  - `Power Type` (`custom.power_type`)
  - `Product / Sparepart` (`custom.spapart_or_product`)
  - `Inventory` (`inventoryQuantity`)
  - `Price` & `Compare At Price`
  - `Image URL` (with `&width=200` optimization parameter)
  - `Website URL` (`https://www.sevenfive.co.th/products/{handle}`)
  - `last_sync_at` (timestamp)

---

## 2. Triggering the Sync

### Option A: Automatic Daily Schedule (GitHub Actions)
Runs automatically every day at **19:00 ICT** (`0 12 * * *`).
- Workflow file: `.github/workflows/shopify-sync.yml`
- Manual trigger: Go to GitHub repository -> **Actions** -> **Shopify Catalog Sync to Supabase** -> **Run workflow**.

### Option B: FastAPI Endpoints (Web / Cloud / Render)
1. **Trigger Sync (Runs in Background)**:
   ```http
   POST /api/sync/shopify
   ```
   *Response:*
   ```json
   {
     "status": "started",
     "message": "Shopify catalog synchronization initiated in background"
   }
   ```
2. **Check Sync Status**:
   ```http
   GET /api/sync/status
   ```
   *Response:*
   ```json
   {
     "is_running": false,
     "last_sync": {
       "id": 1,
       "sync_source": "shopify",
       "status": "success",
       "rows_synced": 40194,
       "started_at": "2026-09-12T12:00:00+00:00",
       "completed_at": "2026-09-12T12:01:25+00:00",
       "error_message": null
     }
   }
   ```

### Option C: Manual CLI Command
```bash
# In project root
python -m app.services.shopify_sync
```
Options:
- `--dry-run`: Test download and parse without writing to database.
- `--no-json`: Skip updating local `.data/products.json`.

---

## 3. Database Schema

### Table: `products`
Columns added in `apps/api/migrations/002_shopify_sync.sql`:
- `title` (text)
- `vendor` (text)
- `status` (text)
- `product_type` (text)
- `tags` (text)
- `part_type` (text)
- `power_type` (text)
- `spapart_or_product` (text)
- `inventory_quantity` (integer)
- `price` (text)
- `compare_at_price` (text)
- `last_sync_at` (timestamptz)

### Table: `sync_logs`
Tracks execution history of syncs:
- `id` (bigint)
- `sync_source` (text, default 'shopify')
- `status` ('running' | 'success' | 'failed')
- `rows_synced` (integer)
- `started_at` (timestamptz)
- `completed_at` (timestamptz)
- `error_message` (text)

---

## 4. GitHub Repository Secrets Setup
To enable the GitHub Action to connect to Supabase:
1. Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Name: `DATABASE_URL`
4. Value: `postgresql://postgres.jisvotecloojqivgbktf:KllpKft1D27X6Y3r@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
