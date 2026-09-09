"""Image fitting logic preserving aspect ratio and preventing column overlap."""

import io
from typing import Optional, Tuple
from PIL import Image

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.quotation import BoundingBox


def get_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """Extracts (width, height) in pixels from raw image bytes."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        return img.width, img.height


def calculate_image_placement(
    item_bbox: BoundingBox,
    image_width: int,
    image_height: int,
    template: QuotationTemplate = DEFAULT_TEMPLATE,
) -> Optional[BoundingBox]:
    """
    Computes a BoundingBox for inserting a product image within the item row.
    
    Guarantees:
    - Never extends past template.desc_col_x1 into template.qty_col_x0.
    - Preserves aspect ratio perfectly (no stretching).
    - Centers horizontally within the right-side image slot (~350 pt).
    - Allows images to reach realistic size (up to 100-110 pt) matching quotation designs.
    - Returns None if the available space is insufficient.
    """
    if image_width <= 0 or image_height <= 0:
        return None

    row_height = item_bbox.height
    if row_height < template.min_row_height_for_image:
        return None

    # Available vertical space: allows row to use template.image_min_slot_height
    # when text has fewer lines, matching standard quotation right-column layout
    min_slot_h = getattr(template, "image_min_slot_height", 0.0)
    if min_slot_h > 0.0:
        avail_h = max(row_height, min_slot_h) - (template.image_top_margin + template.image_bottom_margin)
    else:
        avail_h = row_height - (template.image_top_margin + template.image_bottom_margin)

    # Determine horizontal boundaries inside DESCRIPTION column (strictly before QTY column)
    slot_right = min(template.desc_col_x1, template.qty_col_x0) - template.image_right_margin
    max_w = min(template.image_max_width, slot_right - template.desc_col_x0)
    max_h = min(template.image_max_height, avail_h)

    if max_w <= 10.0 or max_h <= 10.0:
        return None

    # Preserve aspect ratio
    scale = min(max_w / float(image_width), max_h / float(image_height))
    final_w = float(image_width) * scale
    final_h = float(image_height) * scale

    # Position: Horizontally centered around image_slot_center_x (approx 350 pt)
    center_x = getattr(template, "image_slot_center_x", 350.0)
    x0 = center_x - (final_w / 2.0)
    x1 = x0 + final_w

    # Ensure horizontal coordinates stay within bounds
    if x1 > slot_right:
        x1 = slot_right
        x0 = x1 - final_w
    min_x0 = template.desc_col_x0 + 200.0  # leave at least 200pt on left for text
    if x0 < min_x0:
        x0 = min_x0
        x1 = x0 + final_w

    # Vertical position: Centered within item's vertical range
    center_y = (item_bbox.y0 + item_bbox.y1) / 2.0
    y0 = center_y - (final_h / 2.0)
    y1 = y0 + final_h

    # Ensure vertical coordinates stay inside bounds
    if min_slot_h == 0.0:
        if y0 < item_bbox.y0 + template.image_top_margin:
            y0 = item_bbox.y0 + template.image_top_margin
            y1 = y0 + final_h
        if y1 > item_bbox.y1 - template.image_bottom_margin:
            y1 = item_bbox.y1 - template.image_bottom_margin
            y0 = y1 - final_h
    else:
        header_bound = getattr(template, "default_header_bottom_y", 277.0)
        footer_bound = getattr(template, "default_footer_top_y", 600.0)
        if y0 < header_bound + template.image_top_margin:
            y0 = header_bound + template.image_top_margin
            y1 = y0 + final_h
        if y1 > footer_bound - template.image_bottom_margin:
            y1 = footer_bound - template.image_bottom_margin
            y0 = y1 - final_h

    # Final safety check: must be strictly to the left of QTY column
    if x1 >= template.qty_col_x0:
        x1 = template.qty_col_x0 - 2.0
        x0 = x1 - final_w

    return BoundingBox(x0=round(x0, 2), y0=round(y0, 2), x1=round(x1, 2), y1=round(y1, 2))
