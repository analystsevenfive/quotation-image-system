"""Generator for synthetic, selectable-text quotation PDFs and sample test images."""

import io
from pathlib import Path
import sys
from typing import List, Optional

api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate


def create_test_image(
    width: int = 150,
    height: int = 150,
    color: str = "red",
    fmt: str = "PNG",
    transparent: bool = False,
) -> bytes:
    """Creates a valid test image in bytes with specified dimensions and format."""
    mode = "RGBA" if transparent else "RGB"
    bg = (0, 0, 0, 0) if transparent else color
    img = Image.new(mode, (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Draw simple shapes inside
    draw.rectangle([5, 5, width - 5, height - 5], outline="blue" if not transparent else "white", width=2)
    draw.text((15, height // 2 - 5), f"{width}x{height}", fill="black" if not transparent else "white")

    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def generate_quotation_pdf(
    items_data: Optional[List[dict]] = None,
    template: QuotationTemplate = DEFAULT_TEMPLATE,
    num_pages: int = 1,
) -> bytes:
    """
    Generates a selectable-text quotation PDF matching realistic commercial quotations.
    """
    doc = fitz.open()

    default_items = [
        {
            "num": 1,
            "sku": "BER1-BMCFP4",
            "desc": "BER1-BMCFP4 Countertop Deep Fryer\nStainless steel construction, 4L capacity\n220V 50Hz 2.5kW",
            "qty": "2 UNIT",
            "price": "15,000.00",
            "net": "30,000.00",
            "height": 55.0,
        },
        {
            "num": 2,
            "sku": "CSHL550",
            "desc": "CSHL550 Under-counter Dishwasher",
            "qty": "1 SET",
            "price": "68,000.00",
            "net": "68,000.00",
            "height": 35.0,
        },
        {
            "num": 3,
            "sku": "DB-CW76-DRG",
            "desc": "DB-CW76-DRG Glass Door Display Refrigerator\nDigital thermostat control, LED illumination\nAutomatic defrost, 4 adjustable shelves\nEnergy saving compressor R290",
            "qty": "1 UNIT",
            "price": "42,500.00",
            "net": "42,500.00",
            "height": 70.0,
        },
        {
            "num": 4,
            "sku": "DB-PP120-GY",
            "desc": "DB-PP120-GY Pizza Prep Table\nIncludes GN 1/3 pan holders",
            "qty": "1 UNIT",
            "price": "55,000.00",
            "net": "55,000.00",
            "height": 45.0,
        },
        {
            "num": 5,
            "sku": "UNKNOWN-999",
            "desc": "UNKNOWN-999 Custom Fabrication Stainless Sink 2-Bowl",
            "qty": "1 LOT",
            "price": "12,000.00",
            "net": "12,000.00",
            "height": 40.0,
        },
    ]

    items_to_render = items_data if items_data is not None else default_items

    for page_idx in range(num_pages):
        page = doc.new_page(width=595.28, height=841.89)  # A4 standard

        # 1. Company Header & Title
        page.insert_text(fitz.Point(40, 50), "SEVEN FIVE DISTRIBUTOR CO., LTD.", fontsize=14, fontname="helv")
        page.insert_text(fitz.Point(40, 68), "88/8 Vibhavadi Rangsit Rd., Bangkok 10900", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(420, 50), "QUOTATION", fontsize=18, fontname="helv")
        page.insert_text(fitz.Point(420, 70), f"No: QT0926-00287-{page_idx+1}", fontsize=10, fontname="helv")
        page.insert_text(fitz.Point(420, 85), "Date: 09/09/2026", fontsize=10, fontname="helv")

        # 2. Customer Info
        page.insert_text(fitz.Point(40, 110), "Customer: ABC Restaurant Group Co., Ltd.", fontsize=10, fontname="helv")
        page.insert_text(fitz.Point(40, 125), "Address: Sukhumvit Soi 24, Bangkok", fontsize=9, fontname="helv")

        # 3. Table Column Header Row
        header_y = 170.0
        # Draw header background bar
        page.draw_rect(fitz.Rect(35, header_y - 15, 560, header_y + 8), color=fitz.utils.getColor("black"), width=0.5)

        page.insert_text(fitz.Point(template.item_col_x0 + 5, header_y), "ITEM", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(template.desc_col_x0 + 5, header_y), "DESCRIPTION", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(template.qty_col_x0 + 5, header_y), "QTY", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(template.price_col_x0 + 5, header_y), "PRICE", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(template.net_price_col_x0 + 5, header_y), "NET PRICE", fontsize=9, fontname="helv")

        # 4. Table Items
        current_y = header_y + 25.0
        for itm in items_to_render:
            h = itm.get("height", 45.0)
            item_num_str = str(itm["num"])

            # Item number
            page.insert_text(fitz.Point(template.item_col_x0 + 10, current_y + 12), item_num_str, fontsize=9, fontname="helv")

            # Description (can be multi-line)
            desc_lines = itm["desc"].split("\n")
            line_y = current_y + 12
            for line in desc_lines:
                page.insert_text(fitz.Point(template.desc_col_x0 + 5, line_y), line, fontsize=8, fontname="helv")
                line_y += 11.0

            # QTY, Price, Net
            page.insert_text(fitz.Point(template.qty_col_x0 + 5, current_y + 12), itm.get("qty", "1"), fontsize=9, fontname="helv")
            page.insert_text(fitz.Point(template.price_col_x0 + 5, current_y + 12), itm.get("price", "0.00"), fontsize=9, fontname="helv")
            page.insert_text(fitz.Point(template.net_price_col_x0 + 5, current_y + 12), itm.get("net", "0.00"), fontsize=9, fontname="helv")

            current_y += h

        # 5. Table Footer
        footer_y = 680.0
        page.draw_line(fitz.Point(35, footer_y - 10), fitz.Point(560, footer_y - 10), color=fitz.utils.getColor("black"), width=0.5)
        page.insert_text(fitz.Point(380, footer_y + 5), "SUBTOTAL: 207,500.00", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(380, footer_y + 20), "VAT 7%: 14,525.00", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(380, footer_y + 35), "GRAND TOTAL: 222,025.00", fontsize=10, fontname="helv")
        page.insert_text(fitz.Point(40, footer_y + 5), "REMARKS:", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(40, footer_y + 18), "1. Price validity: 30 days.", fontsize=8, fontname="helv")
        page.insert_text(fitz.Point(40, footer_y + 30), "2. Delivery within 14 days after PO.", fontsize=8, fontname="helv")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
