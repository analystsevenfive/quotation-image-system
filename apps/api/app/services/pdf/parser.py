"""PyMuPDF parser for quotation PDF structure, item boundaries, and SKU detection."""

from collections import defaultdict
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union
import fitz  # PyMuPDF

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.quotation import BoundingBox, QuotationItem
from app.services.pdf.visible_text import visible_words
from app.services.matching.normalizer import UNICODE_DASHES_PATTERN

logger = logging.getLogger(__name__)

# Regular expressions for identifying candidate SKU/model strings in description text
# Real SKUs and product models contain digits or structured prefixes
SKU_WITH_DIGITS_PATTERN = re.compile(r"\b(?=.*\d)[A-Z0-9]+(?:[-_/.][A-Z0-9]+)+\b", re.IGNORECASE)
ALPHANUM_CODE_PATTERN = re.compile(r"\b(?=.*\d)[A-Z0-9]{3,}\b", re.IGNORECASE)


class NoSelectableTextError(Exception):
    """Raised when the PDF has no extractable text layer (scanned or image-only)."""


class QuotationPDFParser:
    """
    Extracts quotation items, dynamic vertical boundaries, and SKU candidates
    using PyMuPDF without OCR or fixed Y coordinates.
    """

    def __init__(self, template: QuotationTemplate = DEFAULT_TEMPLATE):
        self.template = template

    def parse(
        self,
        pdf_source: Union[str, Path, bytes, fitz.Document],
        page_words_cache: Optional[dict] = None,
    ) -> List[QuotationItem]:
        """
        Parses a PDF file path or bytes and returns detected QuotationItems.
        Optionally populates page_words_cache with {page_number: words} to avoid re-parsing.
        """
        if isinstance(pdf_source, (str, Path, bytes)):
            if isinstance(pdf_source, bytes):
                doc = fitz.open(stream=pdf_source, filetype="pdf")
            else:
                doc = fitz.open(str(pdf_source))
        else:
            doc = pdf_source

        all_items: List[QuotationItem] = []
        total_words_count = 0

        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                words = visible_words(page)  # list of (x0, y0, x1, y1, word, block_no, line_no, word_no)
                total_words_count += len(words)
                if page_words_cache is not None:
                    page_words_cache[page_index + 1] = words

                page_items = self._parse_page(page, page_index + 1, words)
                all_items.extend(page_items)

            if total_words_count == 0:
                raise NoSelectableTextError(
                    "No selectable text found in the PDF. Scanned or image-only PDFs are not supported."
                )

            # Re-index items sequentially across pages if needed
            for idx, itm in enumerate(all_items, start=1):
                itm.item_number = idx

            return all_items
        finally:
            if isinstance(pdf_source, (str, Path, bytes)):
                doc.close()

    def _parse_page(
        self, page: fitz.Page, page_number: int, words: List[Tuple]
    ) -> List[QuotationItem]:
        """Parses a single PDF page for quotation table items."""
        if not words:
            return []

        # 1. Detect table header bottom and footer top Y coordinates
        header_bottom_y = self._detect_header_y(words, page.rect.height)
        footer_top_y = self._detect_footer_y(words, page.rect.height)

        # 2. Find item numbers in the ITEM column between header and footer
        raw_item_markers = self._find_item_markers(words, header_bottom_y, footer_top_y)
        if not raw_item_markers:
            return []

        # 3. Calculate dynamic vertical range for each item
        # start_y of item[i] = its marker y0 (with small top margin)
        # end_y of item[i] = start_y of item[i+1], or footer_top_y for the last item
        items: List[QuotationItem] = []
        for i, marker in enumerate(raw_item_markers):
            item_num, marker_bbox = marker

            y0 = marker_bbox.y0 - 2.0  # slight padding above the marker line
            if i + 1 < len(raw_item_markers):
                next_marker_bbox = raw_item_markers[i + 1][1]
                y1 = next_marker_bbox.y0 - 2.0
            else:
                y1 = footer_top_y

            # Item row bounding box covering the table columns
            item_bbox = BoundingBox(
                x0=self.template.item_col_x0,
                y0=round(y0, 2),
                x1=self.template.net_price_col_x1,
                y1=round(y1, 2),
            )

            # 4. Extract words in the DESCRIPTION column for this row
            desc_text = self._extract_description_text(words, y0, y1)

            # 5. Detect candidate SKU and model
            detected_sku, detected_model = self._detect_sku_candidate(desc_text)

            items.append(
                QuotationItem(
                    item_number=item_num,
                    page_number=page_number,
                    description=desc_text,
                    detected_sku=detected_sku,
                    detected_model=detected_model,
                    bbox=item_bbox,
                )
            )

        return items

    def _detect_header_y(self, words: List[Tuple], page_height: float) -> float:
        """Finds the bottom Y coordinate of the quotation table header by grouping keywords on the same line."""
        lines = defaultdict(list)
        for w in words:
            x0, y0, x1, y1, word = w[:5]
            # Table headers appear in upper half of quotation
            if y0 < page_height * 0.45:
                word_clean = word.strip().upper()
                if any(k in word_clean for k in self.template.header_keywords):
                    line_key = round(y0 / 6.0) * 6.0
                    lines[line_key].append(w)

        if lines:
            # Pick the line with the most header keyword hits (e.g. ITEM + DESCRIPTION + QTY + PRICE)
            best_line = max(lines.values(), key=len)
            return max(w[3] for w in best_line)

        return self.template.default_header_bottom_y

    def _detect_footer_y(self, words: List[Tuple], page_height: float) -> float:
        """Finds the top Y coordinate where table items end (e.g. Total, Remarks)."""
        footer_y_candidates = []
        for w in words:
            x0, y0, x1, y1, word = w[:5]
            word_clean = word.strip().upper()
            # Only consider footer keywords in lower half of the page
            if y0 > page_height * 0.4:
                if any(k in word_clean for k in self.template.footer_keywords):
                    footer_y_candidates.append(y0)

        if footer_y_candidates:
            return min(footer_y_candidates) - 6.0

        return min(self.template.default_footer_top_y, page_height - 50.0)

    def _find_item_markers(
        self, words: List[Tuple], header_y: float, footer_y: float
    ) -> List[Tuple[int, BoundingBox]]:
        """
        Locates item row numbers (1, 2, 3...) in the ITEM column.
        Returns sorted list of (item_number, BoundingBox).
        """
        candidates: List[Tuple[int, BoundingBox]] = []

        for w in words:
            x0, y0, x1, y1, word = w[:5]
            clean_word = word.strip()

            # Must be inside ITEM column bounds and between header and footer
            if (
                self.template.item_col_x0 - 5.0 <= x0 <= self.template.item_col_x1 + 5.0
                and header_y <= y0 <= footer_y
            ):
                # Check if it represents an integer item number
                # Strip trailing dots or dashes (e.g. "1." or "1-")
                num_str = clean_word.rstrip(".-")
                if num_str.isdigit():
                    num = int(num_str)
                    candidates.append(
                        (num, BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1))
                    )

        # Sort candidates by Y coordinate (top to bottom)
        candidates.sort(key=lambda item: item[1].y0)

        # Filter duplicates on approximately the same Y position
        unique_markers: List[Tuple[int, BoundingBox]] = []
        for c in candidates:
            if not unique_markers:
                unique_markers.append(c)
            else:
                last = unique_markers[-1]
                # If Y difference is greater than 8 points, it's a new row
                if abs(c[1].y0 - last[1].y0) > 8.0:
                    unique_markers.append(c)

        return unique_markers

    def _extract_description_text(
        self, words: List[Tuple], y0: float, y1: float
    ) -> str:
        """Extracts and formats text within the DESCRIPTION column for an item row."""
        desc_words = []
        for w in words:
            wx0, wy0, wx1, wy1, text, block_no, line_no, word_no = w
            # Check if word falls in row vertical range and description horizontal range
            y_center = (wy0 + wy1) / 2.0
            if (
                y0 <= y_center <= y1
                and self.template.desc_col_x0 - 5.0 <= wx0 <= self.template.qty_col_x0 - 5.0
            ):
                desc_words.append((wy0, wx0, text))

        # Sort by vertical line, then horizontal reading order
        desc_words.sort(key=lambda x: (round(x[0] / 4.0) * 4.0, x[1]))
        return " ".join(t[2] for t in desc_words).strip()

    def _detect_sku_candidate(
        self, desc_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts SKU and model candidates from description text.
        Returns (detected_sku, detected_model).
        """
        if not desc_text:
            return None, None

        # Normalize before token extraction, otherwise a Unicode hyphen truncates codes.
        desc_text = UNICODE_DASHES_PATTERN.sub("-", desc_text)
        # A labeled SKU is more specific than a model mentioned earlier in the row.
        sku_match = re.search(r"\b(?:MODEL\s*/\s*)?SKU\s*:\s*([A-Z0-9]+(?:[-_/.][A-Z0-9]+)*)", desc_text, re.I)
        if sku_match:
            return sku_match.group(1), None

        # 1. Check for explicit MODEL or # designation in description:
        # e.g. "MODEL CSHL550", "MODEL: 1120CBR-110", "# MFC3535-BL", "# SSG-22L"
        explicit_match = re.search(
            r"(?:MODEL:?|#)\s*([A-Z0-9]+(?:[-_/.][A-Z0-9]+)*)", desc_text, re.IGNORECASE
        )
        if explicit_match:
            candidate = explicit_match.group(1).strip()
            if len(candidate) >= 2:
                return candidate, candidate

        tokens = desc_text.split()
        if not tokens:
            return None, None

        # 2. First token in quotation descriptions is very commonly the exact SKU or model
        first_token = tokens[0].strip(",;:()'\"")
        if (
            SKU_WITH_DIGITS_PATTERN.fullmatch(first_token)
            or ALPHANUM_CODE_PATTERN.fullmatch(first_token)
        ):
            return first_token, None

        # 3. Check tokens for hyphenated SKU containing digits (e.g., 'BER1-BMCFP4', 'DB-CW76-DRG')
        for token in tokens:
            cleaned = token.strip(",;:()'\"")
            if SKU_WITH_DIGITS_PATTERN.fullmatch(cleaned):
                return cleaned, None

        # 4. Check for alphanumeric model codes with digits (e.g., 'CSHL550', 'BMCFP4')
        for token in tokens:
            cleaned = token.strip(",;:()'\"")
            if ALPHANUM_CODE_PATTERN.fullmatch(cleaned) and len(cleaned) >= 4:
                return cleaned, None

        # 5. Fallback: check first token if alphanumeric (e.g. BMCFP4)
        if first_token.isalnum() and len(first_token) >= 3 and not first_token.isdigit():
            return first_token, None

        return None, None
