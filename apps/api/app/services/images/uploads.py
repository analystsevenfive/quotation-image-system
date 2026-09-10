"""Decode user-supplied images and retain pixels only, scoped to a quotation."""
import io
from PIL import Image, ImageOps

MAX_IMAGE_UPLOAD = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


def normalize_uploaded_image(data: bytes) -> bytes:
    if not data or len(data) > MAX_IMAGE_UPLOAD:
        raise ValueError('รูปต้องมีขนาดไม่เกิน 10 MB')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('รองรับรูป JPG, PNG และ WEBP เท่านั้น')
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError('รูปมีความละเอียดสูงเกินไป กรุณาใช้รูปไม่เกิน 20 ล้านพิกเซล')
            image.load()
            oriented = ImageOps.exif_transpose(image)
            pixels = oriented.convert('RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB')
            # Create a clean image: no filename, EXIF, comments or other metadata.
            clean = Image.frombytes(pixels.mode, pixels.size, pixels.tobytes())
            output = io.BytesIO()
            clean.save(output, format='PNG')
            result = output.getvalue()
            if len(result) > MAX_IMAGE_UPLOAD:
                raise ValueError('รูปหลังแปลงมีขนาดเกิน 10 MB กรุณาย่อรูปก่อนอัปโหลด')
            return result
    except ValueError:
        raise
    except Exception:
        raise ValueError('อ่านรูปนี้ไม่ได้ กรุณาใช้ไฟล์ JPG, PNG หรือ WEBP ที่สมบูรณ์') from None
