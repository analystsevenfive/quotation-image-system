"""Shopify Catalog Synchronization Service for Supabase.

Adapted from Google Apps Script 'synWebForCostDepartment.js' and 'property.js'.
Fetches all products and variants from Shopify via Bulk Operations GraphQL API,
transforms them into product catalog records, and upserts them into Supabase PostgreSQL.
"""

import argparse
import datetime
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.matching.normalizer import extract_model_from_sku, normalize_image_url

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Automatically load .env if present
for env_file in [Path('.env'), Path('../../.env'), Path('../../../.env')]:
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

# Configuration & Credentials (Read from environment / .env)
DEFAULT_SHOP = os.environ.get("SHOPIFY_SHOP", "sevenfive-4062.myshopify.com")
DEFAULT_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "696e1e9162c702cc07c2f94a1beacf8a")
DEFAULT_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
DEFAULT_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")


BULK_QUERY = """
mutation BulkQuery($query: String!) {
  bulkOperationRunQuery(query: $query) {
    bulkOperation {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

INNER_PRODUCTS_QUERY = """
{
  products {
    edges {
      node {
        id
        title
        handle
        vendor
        status
        productType
        tags
        featuredImage {
          url
        }
        goodId: metafield(namespace: "custom", key: "good_id") {
          value
        }
        partType: metafield(namespace: "custom", key: "part_type") {
          value
        }
        powerType: metafield(namespace: "custom", key: "power_type") {
          value
        }
        spapartOrProduct: metafield(namespace: "custom", key: "spapart_or_product") {
          value
        }
        variants {
          edges {
            node {
              id
              sku
              price
              compareAtPrice
              inventoryQuantity
              image {
                url
              }
            }
          }
        }
      }
    }
  }
}
"""


class ShopifyClient:
    """Manages Shopify GraphQL and OAuth communications."""

    def __init__(
        self,
        shop: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        self.shop = shop or os.environ.get("SHOPIFY_SHOP", DEFAULT_SHOP)
        self.client_id = client_id or os.environ.get("SHOPIFY_CLIENT_ID", DEFAULT_CLIENT_ID)
        self.client_secret = client_secret or os.environ.get("SHOPIFY_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
        self.access_token = access_token or os.environ.get("SHOPIFY_ACCESS_TOKEN", DEFAULT_ACCESS_TOKEN)
        self._token_expiry: float = 0

    def get_valid_token(self) -> str:
        """Return valid access token, generating a fresh 24h token via OAuth client_credentials grant."""
        now = time.time()
        # 1. Reuse existing valid token if not expiring within 5 minutes
        if self.access_token and now < self._token_expiry - 300:
            return self.access_token

        # 2. Always auto-generate fresh token via CLIENT_ID + CLIENT_SECRET (valid 24h)
        if self.client_id and self.client_secret:
            logger.info("Auto-generating fresh 24h Shopify access token via client_credentials...")
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            res = httpx.post(
                f"https://{self.shop}/admin/oauth/access_token",
                data=data,
                timeout=25.0,
            )
            if res.status_code == 200:
                res_data = res.json()
                new_token = res_data.get("access_token")
                if new_token:
                    expires_in = int(res_data.get("expires_in", 86400))
                    self.access_token = new_token
                    self._token_expiry = now + expires_in
                    logger.info(f"Fresh 24h token acquired successfully (valid for {expires_in}s / ~{expires_in // 3600}h)")
                    return self.access_token
            logger.warning(f"Failed to generate OAuth token: {res.status_code} - {res.text}")

        # 3. Fallback to pre-configured access token if client_credentials not provided
        if self.access_token:
            return self.access_token

        raise RuntimeError("No valid Shopify access token and unable to generate one with CLIENT_ID/CLIENT_SECRET")

    def graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Shopify Admin API."""
        token = self.get_valid_token()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        res = httpx.post(
            f"https://{self.shop}/admin/api/2025-01/graphql.json",
            json=payload,
            headers={"X-Shopify-Access-Token": token},
            timeout=45.0,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"GraphQL HTTP Error {res.status_code}: {res.text[:300]}")

        data = res.json()
        if "errors" in data and data["errors"]:
            raise RuntimeError(f"GraphQL Error: {json.dumps(data['errors'], ensure_ascii=False)}")
        return data

    def check_current_bulk_operation(self) -> Optional[Dict[str, Any]]:
        """Check status of currently running or recent bulk operation."""
        query = """
        {
          currentBulkOperation(type: QUERY) {
            id
            status
            url
            objectCount
            errorCode
            createdAt
            completedAt
          }
        }
        """
        data = self.graphql(query)
        return data.get("data", {}).get("currentBulkOperation")

    def start_bulk_query(self) -> str:
        """Start a new Shopify Bulk Operation query."""
        data = self.graphql(BULK_QUERY, {"query": INNER_PRODUCTS_QUERY})
        run_res = data.get("data", {}).get("bulkOperationRunQuery", {})
        user_errors = run_res.get("userErrors", [])
        if user_errors:
            raise RuntimeError(f"Bulk query userErrors: {json.dumps(user_errors, ensure_ascii=False)}")

        op = run_res.get("bulkOperation")
        if not op or not op.get("id"):
            raise RuntimeError(f"Failed to start bulk operation: {data}")
        return op["id"]

    def poll_bulk_operation(self, op_id: str, max_wait_sec: int = 900, poll_interval_sec: int = 8) -> Tuple[str, str, int]:
        """Poll bulk operation until status is COMPLETED or FAILED."""
        query = """
        query CheckOp($id: ID!) {
          node(id: $id) {
            ... on BulkOperation {
              id
              status
              url
              errorCode
              objectCount
            }
          }
        }
        """
        start_time = time.time()
        while True:
            data = self.graphql(query, {"id": op_id})
            node = data.get("data", {}).get("node")
            if not node:
                raise RuntimeError(f"Bulk operation {op_id} not found")

            status = node.get("status")
            object_count = int(node.get("objectCount") or 0)
            logger.info(f"Bulk Operation [{status}] - {object_count} objects processed...")

            if status == "COMPLETED":
                url = node.get("url")
                if not url:
                    raise RuntimeError("Bulk operation completed but no download URL returned")
                return status, url, object_count
            elif status in ("FAILED", "CANCELED"):
                error_code = node.get("errorCode")
                raise RuntimeError(f"Bulk operation {status} with error: {error_code}")

            if time.time() - start_time > max_wait_sec:
                raise TimeoutError(f"Bulk operation timed out after {max_wait_sec}s")

            time.sleep(poll_interval_sec)


def process_jsonl_stream(download_url: str) -> List[Dict[str, Any]]:
    """Download JSONL output and transform into flat product/variant records."""
    logger.info("Downloading Bulk Operation JSONL stream from Shopify...")
    products: Dict[str, Dict[str, Any]] = {}
    variants: Dict[str, List[Dict[str, Any]]] = {}

    with httpx.stream("GET", download_url, timeout=120.0) as resp:
        if resp.status_code >= 400:
            raise RuntimeError(f"Failed to download JSONL: {resp.status_code}")

        total_lines = 0
        for line in resp.iter_lines():
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                obj = json.loads(line)
                gid = obj.get("id", "")
                parent_id = obj.get("__parentId")

                if "/Product/" in gid and not parent_id:
                    products[gid] = obj
                elif "/ProductVariant/" in gid and parent_id:
                    if parent_id not in variants:
                        variants[parent_id] = []
                    variants[parent_id].append(obj)
            except Exception:
                pass

    logger.info(f"Downloaded & parsed {total_lines} lines ({len(products)} products, {sum(len(v) for v in variants.values())} variants)")

    records: List[Dict[str, Any]] = []
    seen_good_ids = set()

    for pid, p in products.items():
        # Parse GoodID metafield
        raw_good_id = (p.get("goodId") or {}).get("value")
        good_id = None
        if raw_good_id is not None and str(raw_good_id).strip():
            good_id = str(raw_good_id).strip()
            # Clean numeric format if like '31021.0'
            try:
                good_id = str(int(float(good_id)))
            except (ValueError, TypeError):
                pass

        handle = p.get("handle")
        product_url = f"https://www.sevenfive.co.th/products/{handle}" if handle else None

        featured_image = (p.get("featuredImage") or {}).get("url")
        part_type = (p.get("partType") or {}).get("value")
        power_type = (p.get("powerType") or {}).get("value")
        spapart_or_product = (p.get("spapartOrProduct") or {}).get("value")
        tags = ", ".join(p.get("tags") or [])
        product_type = p.get("productType")
        title = p.get("title")
        vendor = p.get("vendor")
        status = p.get("status")

        p_variants = variants.get(pid, [])
        # If no variants, fallback to product level
        if not p_variants:
            p_variants = [{}]

        for idx, v in enumerate(p_variants):
            sku = (v.get("sku") or "").strip()
            if not sku and not good_id:
                continue

            # Unique good_id resolution
            variant_good_id = good_id
            if not variant_good_id:
                # Fallback to variant ID or SKU
                variant_id = (v.get("id") or "").split("/")[-1]
                variant_good_id = f"V{variant_id}" if variant_id else (sku or f"P{pid.split('/')[-1]}_{idx}")

            if variant_good_id in seen_good_ids:
                # Duplicate good_id across variants; suffix with variant index
                variant_good_id = f"{variant_good_id}_{idx+1}"
            seen_good_ids.add(variant_good_id)

            model = extract_model_from_sku(sku) if sku else (title or "")
            raw_image = (v.get("image") or {}).get("url") or featured_image
            image_url = normalize_image_url(raw_image) if raw_image else None
            image_status = "available" if image_url else "missing"

            records.append({
                "good_id": variant_good_id,
                "sku": sku or variant_good_id,
                "winspeed": sku or variant_good_id,
                "model": model,
                "product_url": product_url,
                "image_url": image_url,
                "image_status": image_status,
                "title": title,
                "vendor": vendor,
                "status": status,
                "product_type": product_type,
                "tags": tags,
                "part_type": part_type,
                "power_type": power_type,
                "spapart_or_product": spapart_or_product,
                "inventory_quantity": v.get("inventoryQuantity"),
                "price": str(v.get("price")) if v.get("price") is not None else None,
                "compare_at_price": str(v.get("compareAtPrice")) if v.get("compareAtPrice") is not None else None,
                "good_bill_name": None,
            })

    logger.info(f"Assembled {len(records)} catalog records ready for database upsert.")
    return records


def upsert_to_supabase(records: List[Dict[str, Any]], database_url: str, batch_size: int = 5000) -> int:
    """Upsert catalog records into Supabase PostgreSQL."""
    import psycopg

    sql = """
    INSERT INTO products (
        good_id, sku, winspeed, model, product_url, image_url, image_status,
        title, vendor, status, product_type, tags, part_type, power_type,
        spapart_or_product, inventory_quantity, price, compare_at_price,
        good_bill_name, last_sync_at, updated_at
    ) VALUES (
        %(good_id)s, %(sku)s, %(winspeed)s, %(model)s, %(product_url)s, %(image_url)s, %(image_status)s,
        %(title)s, %(vendor)s, %(status)s, %(product_type)s, %(tags)s, %(part_type)s, %(power_type)s,
        %(spapart_or_product)s, %(inventory_quantity)s, %(price)s, %(compare_at_price)s,
        %(good_bill_name)s, now(), now()
    )
    ON CONFLICT (good_id) DO UPDATE SET
        sku = EXCLUDED.sku,
        winspeed = EXCLUDED.winspeed,
        model = EXCLUDED.model,
        product_url = EXCLUDED.product_url,
        image_url = EXCLUDED.image_url,
        image_status = EXCLUDED.image_status,
        title = EXCLUDED.title,
        vendor = EXCLUDED.vendor,
        status = EXCLUDED.status,
        product_type = EXCLUDED.product_type,
        tags = EXCLUDED.tags,
        part_type = EXCLUDED.part_type,
        power_type = EXCLUDED.power_type,
        spapart_or_product = EXCLUDED.spapart_or_product,
        inventory_quantity = EXCLUDED.inventory_quantity,
        price = EXCLUDED.price,
        compare_at_price = EXCLUDED.compare_at_price,
        good_bill_name = COALESCE(products.good_bill_name, EXCLUDED.good_bill_name),
        last_sync_at = now(),
        updated_at = now();
    """


    total_synced = 0
    total_records = len(records)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # Create sync_logs entry
            cur.execute(
                "INSERT INTO sync_logs (sync_source, status, started_at) VALUES ('shopify', 'running', now()) RETURNING id;"
            )
            log_id = cur.fetchone()[0]
            conn.commit()

            try:
                for i in range(0, total_records, batch_size):
                    chunk = records[i:i + batch_size]
                    cur.executemany(sql, chunk)
                    conn.commit()
                    total_synced += len(chunk)
                    logger.info(f"  Upserted {total_synced}/{total_records} products to Supabase...")

                # Mark sync_logs as success
                cur.execute(
                    "UPDATE sync_logs SET status = 'success', rows_synced = %s, completed_at = now() WHERE id = %s;",
                    (total_synced, log_id),
                )
                conn.commit()
            except Exception as exc:
                cur.execute(
                    "UPDATE sync_logs SET status = 'failed', error_message = %s, completed_at = now() WHERE id = %s;",
                    (str(exc)[:500], log_id),
                )
                conn.commit()
                raise

    logger.info(f"Successfully upserted {total_synced} products to Supabase PostgreSQL.")
    return total_synced


def update_json_snapshot(records: List[Dict[str, Any]], target_path: str = ".data/products.json"):
    """Update local development JSON snapshot."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = []
    for idx, r in enumerate(records, 1):
        snapshot.append({
            "id": idx,
            "good_id": r["good_id"],
            "sku": r["sku"],
            "winspeed": r["winspeed"],
            "model": r["model"],
            "title": r.get("title"),
            "good_bill_name": r.get("good_bill_name"),
            "product_url": r["product_url"],
            "image_url": r["image_url"],
            "image_status": r["image_status"],
        })
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(snapshot)} products to local snapshot: {target_path}")


def sync_shopify_to_supabase(database_url: Optional[str] = None, update_json: bool = True) -> int:
    """End-to-end sync function: runs bulk query, parses results, and updates Supabase."""
    db_url = database_url or os.environ.get("DATABASE_URL")
    client = ShopifyClient()

    logger.info(f"Starting Shopify sync for store: {client.shop}")

    # Check if a bulk query is already running or completed recently
    current_op = client.check_current_bulk_operation()
    op_id = None
    download_url = None

    if current_op and current_op.get("status") in ("RUNNING", "CREATED"):
        op_id = current_op["id"]
        logger.info(f"Waiting for already running bulk operation ({op_id})...")
    elif current_op and current_op.get("status") == "COMPLETED" and current_op.get("url"):
        # If completed within the last 15 minutes, we can reuse the downloaded URL to save time
        completed_at_str = current_op.get("completedAt")
        if completed_at_str:
            try:
                completed_at = datetime.datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
                age_sec = (datetime.datetime.now(datetime.timezone.utc) - completed_at).total_seconds()
                if age_sec < 900:  # 15 minutes
                    logger.info(f"Reusing recent completed bulk operation from {int(age_sec)}s ago...")
                    download_url = current_op["url"]
            except Exception:
                pass

    if not download_url:
        if not op_id:
            op_id = client.start_bulk_query()
            logger.info(f"Started new Shopify Bulk Operation (ID: {op_id})")

        _, download_url, object_count = client.poll_bulk_operation(op_id)
        logger.info(f"Shopify Bulk Operation finished ({object_count} objects)")

    # Download & parse JSONL
    records = process_jsonl_stream(download_url)

    # Upsert to Supabase
    synced_count = 0
    if db_url:
        synced_count = upsert_to_supabase(records, db_url)
    else:
        logger.warning("DATABASE_URL not set; skipping Supabase upsert.")

    # Update local JSON snapshot
    if update_json:
        snapshot_file = os.environ.get("PRODUCTS_JSON", ".data/products.json")
        update_json_snapshot(records, snapshot_file)

    return synced_count


_sync_lock = threading.Lock()
_is_syncing = False


def is_sync_running() -> bool:
    """Return True if a synchronization is currently in progress in this process."""
    return _is_syncing


def get_last_sync_status(database_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent sync record from Supabase sync_logs table."""
    db_url = database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, sync_source, status, rows_synced, started_at, completed_at, error_message "
                    "FROM sync_logs ORDER BY started_at DESC LIMIT 1;"
                )
                row = cur.fetchone()
                if row:
                    res = dict(row)
                    if res.get("started_at"):
                        res["started_at"] = res["started_at"].isoformat()
                    if res.get("completed_at"):
                        res["completed_at"] = res["completed_at"].isoformat()
                    return res
    except Exception as e:
        logger.warning(f"Failed to query sync_logs: {e}")
    return None


def run_sync_background(database_url: Optional[str] = None, refresh_service: Any = None) -> bool:
    """Run sync in background with a concurrency lock to avoid duplicate parallel runs."""
    global _is_syncing
    if not _sync_lock.acquire(blocking=False):
        logger.warning("Shopify sync is already running in background.")
        return False

    _is_syncing = True
    try:
        count = sync_shopify_to_supabase(database_url=database_url, update_json=False)
        logger.info(f"Background Shopify sync completed: {count} products updated.")
        if refresh_service and getattr(refresh_service, "catalog", None):
            db_url = database_url or os.environ.get("DATABASE_URL")
            if db_url:
                try:
                    from app.services.catalog import Catalog
                    refresh_service.catalog = Catalog.from_postgres(db_url)
                    logger.info("Refreshed in-memory Catalog after sync.")
                except Exception as e:
                    logger.warning(f"Could not refresh in-memory catalog: {e}")
        return True
    except Exception as exc:
        logger.error(f"Background Shopify sync error: {exc}", exc_info=True)
        return False
    finally:
        _is_syncing = False
        _sync_lock.release()


def main():
    parser = argparse.ArgumentParser(description="Sync Shopify catalog into Supabase PostgreSQL database.")
    parser.add_argument("--dry-run", action="store_true", help="Download and parse without writing to database")
    parser.add_argument("--no-json", action="store_true", help="Skip updating local JSON snapshot")
    args = parser.parse_args()

    try:
        db_url = None if args.dry_run else os.environ.get("DATABASE_URL")
        count = sync_shopify_to_supabase(database_url=db_url, update_json=not args.no_json)
        print(f"Sync finished successfully. Total records: {count}")
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

