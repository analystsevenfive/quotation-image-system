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

- **Daily Schedule**: Runs automatically every day at **21:07 Bangkok Time** (ICT, UTC+7), which corresponds to **14:07 UTC** (`7 14 * * *`).
- **Data Extracted**:
  - `GoodID` (`metafield(namespace: "custom", key: "good_id")`)
  - `Variant SKU` / `sku` / `winspeed`
  - `Model` (auto-extracted from SKU prefix)
  - `Title`
  - `Image URL` (with `&width=200` optimization parameter)
  - `Website URL` (`https://www.sevenfive.co.th/products/{handle}`)
  - `GoodBillName` (preserved from legacy / Google Sheets)
  - `last_sync_at` (timestamp)

---

## 2. Triggering the Sync

### Option A: Automatic Daily Schedule (GitHub Actions)
Runs automatically every day at **21:07 ICT** (`7 14 * * *`).
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
Streamlined catalog schema:
- `id` (bigint, primary key)
- `good_id` (text, unique Shopify custom metafield)
- `sku` (text, variant SKU)
- `winspeed` (text, matching code)
- `model` (text, extracted product model)
- `title` (text, Shopify product title)
- `product_url` (text, public web store URL)
- `image_url` (text, optimized CDN image URL)
- `image_status` (text)
- `good_bill_name` (text, billing product name from legacy/Google Sheets)
- `last_sync_at` (text, Thai local time formatted as `DD/MM/YYYY HH:MI`)
- `created_at` / `updated_at` (timestamptz)

### Table: `sync_logs`
Tracks execution history of syncs with Thai local time formatting:
- `id` (bigint, primary key)
- `sync_source` (text, default 'shopify')
- `status` ('running' | 'success' | 'failed')
- `rows_synced` (integer)
- `started_at` (text, Thai time `DD/MM/YYYY HH:MI`)
- `completed_at` (text, Thai time `DD/MM/YYYY HH:MI`)
- `duration` (text, e.g. '3 นาที 25 วินาที')
- `error_message` (text)

---

## 4. Automatic 24h Token Renewal & GitHub Secrets Setup

Shopify Custom App access tokens expire after **24 hours**. 
The system automatically generates a fresh 24h token before each run using OAuth `client_credentials` grant with `CLIENT_ID` and `CLIENT_SECRET`. You never need to manually copy or rotate `SHOPIFY_ACCESS_TOKEN`.

### GitHub Secrets Configuration
To enable the scheduled sync at 21:07 ICT:
1. Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Add the following repository secrets:
   - **`DATABASE_URL`**:
     `postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
   - **`SHOPIFY_CLIENT_SECRET`**:
     *(Get from Shopify App Credentials or .env)*
   - *(Optional)* `SHOPIFY_CLIENT_ID`:
     `696e1e9162c702cc07c2f94a1beacf8a` (already has default in code)

