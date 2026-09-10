"""Fit images strictly inside the detected row and description column."""
import io
from typing import Optional, Tuple
from PIL import Image
from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.quotation import BoundingBox


def get_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return img.width, img.height


def calculate_image_placement(item_bbox: BoundingBox, image_width: int,
                              image_height: int,
                              template: QuotationTemplate = DEFAULT_TEMPLATE) -> Optional[BoundingBox]:
    if min(image_width, image_height) <= 0 or item_bbox.height < template.min_row_height_for_image:
        return None
    left = max(item_bbox.x0, template.desc_col_x0) + template.image_text_reserve_width
    right = min(item_bbox.x1, template.desc_col_x1, template.qty_col_x0) - template.image_right_margin
    top = item_bbox.y0 + template.image_top_margin
    bottom = item_bbox.y1 - template.image_bottom_margin
    width = min(template.image_max_width, right - left)
    height = min(template.image_max_height, bottom - top)
    if min(width, height) <= 10:
        return None
    scale = min(width / image_width, height / image_height)
    w, h = image_width * scale, image_height * scale
    x = min(max(template.image_slot_center_x - w / 2, left), right - w)
    y = top + (bottom - top - h) / 2
    return BoundingBox(x0=x, y0=y, x1=x+w, y1=y+h)


def calculate_safe_placement(item_bbox, image_width, image_height, words, template=DEFAULT_TEMPLATE):
    """Choose the largest text-free vertical gap in the configured image slot."""
    initial = calculate_image_placement(item_bbox, image_width, image_height, template)
    if initial is None:
        return None
    overlaps = lambda a, b: a.x0 < b[2] and a.x1 > b[0] and a.y0 < b[3] and a.y1 > b[1]
    if not any(overlaps(initial, w) for w in words):
        return initial
    left = max(item_bbox.x0, template.desc_col_x0) + template.image_text_reserve_width
    right = min(item_bbox.x1, template.desc_col_x1, template.qty_col_x0) - template.image_right_margin
    blocked = sorted((max(item_bbox.y0, w[1]-1), min(item_bbox.y1, w[3]+1))
                     for w in words if w[0] < right and w[2] > left
                     and w[1] < item_bbox.y1 and w[3] > item_bbox.y0)
    gaps, cursor = [], item_bbox.y0
    for top, bottom in blocked:
        if top > cursor:
            gaps.append((cursor, top))
        cursor = max(cursor, bottom)
    if cursor < item_bbox.y1:
        gaps.append((cursor, item_bbox.y1))
    candidates = []
    for top, bottom in gaps:
        area = item_bbox.model_copy(update={'y0': top, 'y1': bottom})
        box = calculate_image_placement(area, image_width, image_height, template)
        if box and not any(overlaps(box, w) for w in words):
            candidates.append(box)
    return max(candidates, key=lambda b: b.width*b.height, default=None)
