import io
import openpyxl
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.core.template import SEVEN_FIVE_TEMPLATE
from app.models.quotation import BoundingBox, QuotationItem
from app.services.images.downloader import ImageDownloader
from app.services.pdf.parser import QuotationPDFParser
from app.services.pdf.renderer import QuotationPDFRenderer

print("1. Parsing 'QT_test.pdf'...")
parser = QuotationPDFParser(template=SEVEN_FIVE_TEMPLATE)
items = parser.parse("QT_test.pdf")
print(f"   Found {len(items)} items across pages.")

print("\n2. Loading 'web sevenfive 75.xlsx'...")
t0 = time.time()
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
print(f"   Loaded {len(catalog)} rows in {time.time() - t0:.2f}s.")

print("\n3. Matching items against Column D and fetching Shopify images from Column F...")
downloader = ImageDownloader(timeout=15.0)
image_data_map = {}
matched_items = []

for item in items:
    sku = item.detected_sku
    if not sku:
        print(f"   Item #{item.item_number:2d}: (Delivery terms - skipped)")
        continue

    # Match in catalog
    matched = []
    pattern = r"(?:\b|_)" + re.escape(sku) + r"(?:\b|_)"
    for entry in catalog:
        if re.search(pattern, entry["good_bill_name"], re.IGNORECASE):
            matched.append(entry)

    if not matched:
        print(f"   Item #{item.item_number:2d}: SKU='{sku}' NOT FOUND")
        continue

    # Pick match with image if possible
    with_img = [e for e in matched if e["image_url"]]
    chosen = with_img[0] if with_img else matched[0]
    img_url = chosen["image_url"]

    if img_url:
        print(f"   Item #{item.item_number:2d}: SKU='{sku:12s}' -> Downloading image: {img_url[:60]}...")
        img_bytes = downloader.get_image(img_url)
        if img_bytes:
            image_data_map[item.item_number] = img_bytes
            item.selected_image_url = img_url
            print(f"           [OK] Image downloaded ({len(img_bytes)} bytes)")
        else:
            print(f"           [WARN] Image failed to download")
    else:
        print(f"   Item #{item.item_number:2d}: SKU='{sku:12s}' -> Matched in Column D but no image in Column F")

print(f"\n4. Rendering PDF with inserted images...")
renderer = QuotationPDFRenderer(template=SEVEN_FIVE_TEMPLATE)
output_pdf_path = Path("QT_test_with_images.pdf")
renderer.render(
    pdf_source="QT_test.pdf",
    items=items,
    image_data_map=image_data_map,
    output_path=output_pdf_path,
)

print(f"   PDF successfully generated: '{output_pdf_path}' ({output_pdf_path.stat().st_size} bytes).")

print(f"\n5. Generating page preview images (PNG)...")
import fitz
doc = fitz.open(str(output_pdf_path))
for page_num in range(min(3, len(doc))):
    p = doc[page_num]
    pix = p.get_pixmap(dpi=150)
    out_img = f"QT_test_output_page{page_num + 1}.png"
    pix.save(out_img)
    print(f"   Saved preview: {out_img}")
doc.close()

print("\n--- Processing Finished Successfully ---")
