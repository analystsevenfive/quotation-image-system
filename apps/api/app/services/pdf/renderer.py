"""PyMuPDF renderer for inserting product images into quotation PDFs."""
from app.services.pdf.visible_text import visible_words

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import fitz  # PyMuPDF

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.quotation import BoundingBox, QuotationItem
from app.services.pdf.fitter import calculate_safe_placement, get_image_dimensions
from app.services.pdf.placement import validate_placement

logger = logging.getLogger(__name__)


class PDFRenderingError(Exception):
    """Raised when PDF rendering or export fails."""


class QuotationPDFRenderer:
    """
    Inserts product images into native PDF document without rasterization,
    preserving vector text, font rendering, and crisp layout quality.
    """

    def __init__(self, template: QuotationTemplate = DEFAULT_TEMPLATE):
        self.template = template

    def render(
        self,
        pdf_source: Union[str, Path, bytes],
        items: List[QuotationItem],
        image_data_map: Dict[int, bytes],  # item_number -> image_bytes
        output_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Inserts images for matched items into the PDF and saves or returns bytes.
        """
        if isinstance(pdf_source, (str, Path)):
            doc = fitz.open(str(pdf_source))
        elif isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            raise PDFRenderingError("Invalid pdf_source type")

        try:
            page_words = {}
            for item in items:
                item.image_inserted = False
                item.image_bbox = None
                img_bytes = image_data_map.get((item.page_number, item.item_number), image_data_map.get(item.item_number))
                if not img_bytes:
                    continue

                page_idx = item.page_number - 1
                if page_idx < 0 or page_idx >= len(doc):
                    logger.warning("Item %d page %d out of document range", item.item_number, item.page_number)
                    continue

                page = doc[page_idx]
                if page_idx not in page_words:
                    page_words[page_idx] = visible_words(page)
                words = page_words[page_idx]

                try:
                    img_w, img_h = get_image_dimensions(img_bytes)
                    img_bbox = item.manual_image_bbox or calculate_safe_placement(
                        item_bbox=item.bbox,
                        image_width=img_w,
                        image_height=img_h,
                        words=words,
                        template=self.template,
                    )

                    if not img_bbox:
                        item.error_message = "Insufficient row height or space for image"
                        continue

                    if item.manual_image_bbox:
                        validate_placement(img_bbox, item, page, (img_w, img_h), self.template, words=words)

                    # Target rectangle in PDF points
                    rect = fitz.Rect(img_bbox.x0, img_bbox.y0, img_bbox.x1, img_bbox.y1)

                    if any(rect.intersects(fitz.Rect(word[:4])) for word in words):
                        item.error_message = "Image area overlaps document text; image skipped"
                        continue

                    # Insert image natively into PDF stream
                    # keep_proportion=True ensures no stretching
                    page.insert_image(rect, stream=img_bytes, keep_proportion=True)

                    item.image_bbox = img_bbox
                    item.image_inserted = True
                except Exception as e:
                    logger.warning("Failed inserting image for item %d: %s", item.item_number, str(e))
                    item.error_message = f"Rendering error: {str(e)}"

            # Save to output path or return bytes with garbage collection and compression
            if output_path:
                out_path_obj = Path(output_path)
                out_path_obj.parent.mkdir(parents=True, exist_ok=True)
                doc.save(str(out_path_obj), garbage=3, deflate=True)
                return out_path_obj.read_bytes()
            else:
                return doc.tobytes(garbage=3, deflate=True)
        except Exception as e:
            raise PDFRenderingError(f"Failed to render quotation PDF: {str(e)}") from e
        finally:
            doc.close()
