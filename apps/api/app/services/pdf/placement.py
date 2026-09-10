"""Shared constraints for direct manipulation and native PDF export."""
import math
from app.models.quotation import BoundingBox


def editing_bounds(item, page, template):
    return BoundingBox(
        x0=max(0, item.bbox.x0, template.desc_col_x0) + template.image_top_margin,
        y0=max(0, item.bbox.y0) + template.image_top_margin,
        x1=min(page.rect.width, item.bbox.x1, template.desc_col_x1, template.qty_col_x0) - template.image_right_margin,
        y1=min(page.rect.height, item.bbox.y1) - template.image_bottom_margin,
    )


def normalized_box(box, page):
    if box is None:
        return None
    return {'x': box.x0/page.rect.width, 'y': box.y0/page.rect.height,
            'width': box.width/page.rect.width, 'height': box.height/page.rect.height}


def from_normalized(rect, page):
    return BoundingBox(x0=rect.x*page.rect.width, y0=rect.y*page.rect.height,
                       x1=(rect.x+rect.width)*page.rect.width,
                       y1=(rect.y+rect.height)*page.rect.height)


def validate_placement(box, item, page, dimensions, template):
    if not all(math.isfinite(v) for v in (box.x0, box.y0, box.x1, box.y1)):
        raise ValueError('ตำแหน่งรูปไม่ถูกต้อง')
    bounds = editing_bounds(item, page, template)
    epsilon = 0.01
    if (box.x0 < bounds.x0-epsilon or box.y0 < bounds.y0-epsilon
            or box.x1 > bounds.x1+epsilon or box.y1 > bounds.y1+epsilon):
        raise ValueError('กรุณาวางรูปภายในกรอบ DESCRIPTION ของรายการนี้')
    if min(box.width, box.height) < 5:
        raise ValueError('รูปเล็กเกินไป กรุณาขยายรูปเล็กน้อย')
    aspect = dimensions[0]/dimensions[1]
    if abs(box.width/box.height/aspect-1) > 0.005:
        raise ValueError('กรุณาปรับขนาดโดยรักษาสัดส่วนเดิมของรูป')
    if any(box.x0 < w[2] and box.x1 > w[0] and box.y0 < w[3] and box.y1 > w[1]
           for w in page.get_text('words')):
        raise ValueError('รูปทับข้อความ กรุณาเลื่อนหรือย่อรูปให้อยู่ในช่องว่าง')
