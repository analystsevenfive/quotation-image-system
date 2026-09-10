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
from app.services.catalog import Catalog, read_excel
from app.models.quotation import MatchStatus
from app.services.pdf.parser import QuotationPDFParser
from app.services.pdf.renderer import QuotationPDFRenderer

print("1. Parsing 'QT_test.pdf'...")
parser = QuotationPDFParser(template=SEVEN_FIVE_TEMPLATE)
items = parser.parse("QT_test.pdf")
print(f"   Found {len(items)} items across pages.")

print("\n2. Loading 'web sevenfive 75.xlsx'...")
t0 = time.time()
catalog = Catalog(read_excel("web sevenfive 75.xlsx"))
print(f"   Loaded {len(catalog.products)} products in {time.time() - t0:.2f}s.")

print("\n3. Matching items against Column D and fetching Shopify images from Column F...")
downloader = ImageDownloader(timeout=15.0)
image_data_map = {}
matched_items = []

for item in items:
    sku = item.detected_sku
    if not sku:
        print(f"   Item #{item.item_number:2d}: (Delivery terms - skipped)")
        continue

    result = catalog.matcher.match(item.detected_sku, item.detected_model)
    item.match_status = result.status
    item.match_method = result.method
    item.matched_product = result.product
    item.candidate_products = result.candidates
    if result.status != MatchStatus.MATCHED:
        print(f"   Item #{item.item_number}: {result.status.value} ({len(result.candidates)} candidates)")
        continue
    img_url = result.product.image_url

    if img_url:
        print(f"   Item #{item.item_number:2d}: SKU='{sku:12s}' -> Downloading image: {img_url[:60]}...")
        img_bytes = downloader.get_image(img_url)
        if img_bytes:
            image_data_map[(item.page_number, item.item_number)] = img_bytes
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
