import openpyxl
import re
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.services.pdf.parser import QuotationPDFParser

print("Parsing QT_test.pdf...")
parser = QuotationPDFParser()
items = parser.parse("QT_test.pdf")
print(f"Detected {len(items)} items in PDF.")

print("Loading web sevenfive 75.xlsx (Column D: GoodBillName, Column F: link image)...")
wb = openpyxl.load_workbook("web sevenfive 75.xlsx", data_only=True, read_only=True)
ws = wb.active

catalog = []
for row in ws.iter_rows(min_row=2, values_only=True):
    d_val = row[3]  # Column D: GoodBillName
    f_val = row[5]  # Column F: link image
    if d_val:
        catalog.append({
            "good_id": str(row[0] or ""),
            "sku": str(row[1] or ""),
            "winspeed": str(row[2] or ""),
            "good_bill_name": str(d_val).strip(),
            "image_url": str(f_val).strip() if f_val else None,
        })

print(f"Loaded {len(catalog)} rows from Excel.\n")
print(f"{'Item':<6} {'Detected SKU':<15} {'Status':<12} {'Image':<6} {'Matched Column D (GoodBillName)'}")
print("-" * 90)

matched_count = 0
image_found_count = 0

for item in items:
    sku_cand = item.detected_sku
    if not sku_cand:
        print(f"#{item.item_number:<5} {'(No SKU)':<15} {'SKIPPED':<12} {'NO':<6} Remark / Terms row")
        continue

    matched = []
    pattern = r"(?:\b|_)" + re.escape(sku_cand) + r"(?:\b|_)"
    for entry in catalog:
        if re.search(pattern, entry["good_bill_name"], re.IGNORECASE):
            matched.append(entry)

    if matched:
        matched_count += 1
        # Prefer entry with image_url
        with_img = [e for e in matched if e["image_url"]]
        chosen = with_img[0] if with_img else matched[0]
        has_img = "YES" if chosen["image_url"] else "NO"
        if chosen["image_url"]:
            image_found_count += 1
        status = "MATCHED" if len(matched) == 1 else f"MULTI({len(matched)})"
        print(f"#{item.item_number:<5} {sku_cand:<15} {status:<12} {has_img:<6} {chosen['good_bill_name'][:50]}")
    else:
        print(f"#{item.item_number:<5} {sku_cand:<15} {'MISSING':<12} {'NO':<6} Not found in Column D")

print("-" * 90)
print(f"Summary: {matched_count}/18 product items matched. {image_found_count}/18 have Shopify image URLs in Column F.")
