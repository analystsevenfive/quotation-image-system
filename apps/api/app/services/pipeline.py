"""End-to-end quotation processing pipeline orchestrator."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.product import ImageStatus, Product
from app.models.quotation import MatchStatus, ProcessingReport, QuotationItem
from app.services.images.downloader import ImageDownloader
from app.services.matching.matcher import ProductMatcher
from app.services.pdf.parser import QuotationPDFParser
from app.services.pdf.renderer import QuotationPDFRenderer

logger = logging.getLogger(__name__)


class QuotationPipeline:
    """
    Orchestrates the complete Phase 1 flow:
    PDF Upload -> Extraction -> Matching -> Image Fetching -> Rendering -> Export
    """

    def __init__(
        self,
        products: List[Product],
        template: QuotationTemplate = DEFAULT_TEMPLATE,
        downloader: Optional[ImageDownloader] = None,
    ):
        self.template = template
        self.matcher = ProductMatcher(products)
        self.downloader = downloader or ImageDownloader()
        self.parser = QuotationPDFParser(template)
        self.renderer = QuotationPDFRenderer(template)

    def process(
        self,
        pdf_source: Union[str, Path, bytes],
        output_path: Optional[Union[str, Path]] = None,
    ) -> ProcessingReport:
        """
        Processes a quotation PDF and produces the output PDF with product images.
        """
        source_name = str(pdf_source) if isinstance(pdf_source, (str, Path)) else "in-memory.pdf"
        report = ProcessingReport(
            source_file=source_name,
            output_file=str(output_path) if output_path else None,
        )

        # 1. Parse PDF
        items: List[QuotationItem] = self.parser.parse(pdf_source)
        report.total_items = len(items)

        # 2. Match each item against Product Master
        image_data_map: Dict[int, bytes] = {}
        for item in items:
            match_res = self.matcher.match(
                detected_value=item.detected_sku,
                detected_model=item.detected_model,
            )
            item.match_status = match_res.status
            item.match_method = match_res.method
            item.match_confidence = match_res.confidence
            item.matched_product = match_res.product
            item.candidate_products = match_res.candidates

            if match_res.status == MatchStatus.MATCHED:
                report.matched_count += 1
                if match_res.product and match_res.product.image_url:
                    item.selected_image_url = match_res.product.image_url

                    # 3. Retrieve image
                    img_bytes = self.downloader.get_image(match_res.product.image_url)
                    if img_bytes:
                        image_data_map[(item.page_number, item.item_number)] = img_bytes
                    else:
                        item.error_message = "Failed to download or validate image from URL"
                else:
                    item.error_message = "Product matched but has no image_url"
            elif match_res.status == MatchStatus.NEEDS_REVIEW:
                report.needs_review_count += 1
            else:
                report.missing_count += 1

        # 4. Render PDF with images
        if output_path or image_data_map:
            self.renderer.render(
                pdf_source=pdf_source,
                items=items,
                image_data_map=image_data_map,
                output_path=output_path,
            )

        report.images_inserted_count = sum(1 for i in items if i.image_inserted)
        report.items = items

        logger.info(
            "Processing complete: %d items, %d matched, %d images inserted",
            report.total_items,
            report.matched_count,
            report.images_inserted_count,
        )
        return report
