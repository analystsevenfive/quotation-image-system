"""GoodBillName Synchronization Service.

Synchronizes 'good_bill_name' from Google Sheets ('Main Product' sheet)
into Supabase PostgreSQL 'products' table.

Source formula:
XLOOKUP(good_id, 'Main Product'!A:A, 'Main Product'!E:E)
Spreadsheet ID: 1Z48qT3LXYozhlh_ZBHzn9e4x1kfX_bOLHQtaksj-ZXU
"""
import csv
import io
import logging
import os
import urllib.parse
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_SHEET_ID = "1Z48qT3LXYozhlh_ZBHzn9e4x1kfX_bOLHQtaksj-ZXU"
DEFAULT_SHEET_NAME = "Main Product"


def update_good_bill_names_in_db(
    records: List[Dict[str, str]],
    database_url: Optional[str] = None,
    batch_size: int = 5000,
) -> int:
    """Update good_bill_name in Supabase products table for given good_id mappings."""
    db_url = database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is required")

    import psycopg

    clean_records = []
    for r in records:
        gid = str(r.get("good_id") or "").strip()
        bill_name = str(r.get("good_bill_name") or "").strip()
        if gid and bill_name and bill_name != "0":
            clean_records.append((bill_name, gid))

    if not clean_records:
        return 0

    total_updated = 0
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE IF NOT EXISTS tmp_bill_names (bill_name text, gid text);")
            cur.execute("TRUNCATE tmp_bill_names;")
            for i in range(0, len(clean_records), batch_size):
                chunk = clean_records[i : i + batch_size]
                cur.executemany("INSERT INTO tmp_bill_names (bill_name, gid) VALUES (%s, %s);", chunk)

            cur.execute(
                """
                UPDATE products p
                SET good_bill_name = t.bill_name,
                    updated_at = now()
                FROM tmp_bill_names t
                WHERE p.good_id = t.gid;
                """
            )
            total_updated = cur.rowcount
            conn.commit()

    logger.info(f"Updated good_bill_name for {total_updated} products in Supabase.")
    return total_updated


def fetch_from_google_sheet_csv(
    sheet_id: str = DEFAULT_SHEET_ID,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> Optional[List[Dict[str, str]]]:
    """Fetch Column A (good_id) and Column E (good_bill_name) from Google Sheets CSV export if accessible."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}"
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        if resp.status_code != 200:
            logger.info(f"Google Sheet CSV export returned HTTP {resp.status_code} (Sheet may be private)")
            return None

        content = resp.text
        if "<!DOCTYPE html>" in content or "ServiceLogin" in content:
            logger.info("Google Sheet requires authentication / login.")
            return None

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if len(rows) < 2:
            return None

        results = []
        for r in rows:
            if len(r) >= 5:
                gid = r[0].strip()
                bill_name = r[4].strip()
                if gid and bill_name and bill_name.lower() not in ("goodid", "good_id", "0"):
                    results.append({"good_id": gid, "good_bill_name": bill_name})

        logger.info(f"Fetched {len(results)} GoodBillName mappings from Google Sheets ({sheet_name})")
        return results
    except Exception as e:
        logger.warning(f"Error fetching Google Sheet CSV: {e}")
        return None
