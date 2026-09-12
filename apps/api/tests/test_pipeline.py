"""Integration tests for end-to-end quotation processing pipeline."""

import tempfile
import unittest
import sys
from pathlib import Path
import fitz

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.product import ImageStatus, Product
from app.models.quotation import MatchStatus
from app.services.images.downloader import ImageDownloader
from app.services.pipeline import QuotationPipeline
from tests.fixtures.generate_sample_pdf import create_test_image, generate_quotation_pdf
from tests.fixtures.sample_products import get_sample_products


class MockImageDownloader(ImageDownloader):
    """Mock downloader providing in-memory image bytes for test URLs."""

    def __init__(self):
        super().__init__()
        # Pre-generate valid image payloads
        self.mock_images = {
            "https://cdn.shopify.com/s/files/1/0000/products/BER1-BMCFP4.jpg": create_test_image(200, 150, "orange", "JPEG"),
            "https://cdn.shopify.com/s/files/1/0000/products/CSHL550.jpg": create_test_image(160, 160, "blue", "JPEG"),
            "https://cdn.shopify.com/s/files/1/0000/products/DB-CW76-DRG.png": create_test_image(120, 240, "green", "PNG", transparent=True),
        }

    def get_image(self, url_or_path: str):
        if not url_or_path:
            return None
        if url_or_path in self.mock_images:
            return self.mock_images[url_or_path]
        base_url = url_or_path.split("?")[0]
        for k, v in self.mock_images.items():
            if k == url_or_path or k.split("?")[0] == base_url:
                return v
        return None


class TestQuotationPipeline(unittest.TestCase):
    """End-to-end pipeline integration test."""

    def setUp(self):
        self.products = get_sample_products()
        self.mock_downloader = MockImageDownloader()
        self.pipeline = QuotationPipeline(
            products=self.products,
            downloader=self.mock_downloader,
        )

    def test_full_pipeline_processing(self):
        # 1. Generate synthetic input quotation PDF
        input_pdf_bytes = generate_quotation_pdf(num_pages=1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample_quotation.pdf"
            output_path = Path(tmp_dir) / "sample_quotation_with_images.pdf"
            input_path.write_bytes(input_pdf_bytes)

            # 2. Process through pipeline
            report = self.pipeline.process(input_path, output_path=output_path)

            # 3. Verify report statistics
            self.assertEqual(report.total_items, 5)
            self.assertEqual(report.matched_count, 4)  # Items 1, 2, 3, 4
            self.assertEqual(report.missing_count, 1)  # Item 5 (UNKNOWN-999)
            self.assertEqual(report.images_inserted_count, 3)  # Items 1, 2, 3

            # Check individual item statuses
            item1 = report.items[0]
            self.assertEqual(item1.detected_sku, "BER1-BMCFP4")
            self.assertEqual(item1.match_status, MatchStatus.MATCHED)
            self.assertTrue(item1.image_inserted)
            self.assertIsNotNone(item1.image_bbox)

            item4 = report.items[3]
            self.assertEqual(item4.detected_sku, "DB-PP120-GY")
            self.assertEqual(item4.match_status, MatchStatus.MATCHED)
            self.assertFalse(item4.image_inserted)  # Missing image_url in catalog
            self.assertEqual(item4.error_message, "Product matched but has no image_url")

            item5 = report.items[4]
            self.assertEqual(item5.detected_sku, "UNKNOWN-999")
            self.assertEqual(item5.match_status, MatchStatus.MISSING)
            self.assertFalse(item5.image_inserted)

            # 4. Verify output PDF file
            self.assertTrue(output_path.is_file())
            self.assertGreater(output_path.stat().st_size, 1000)

            # 5. Open output PDF and verify images and text preservation
            out_doc = fitz.open(str(output_path))
            self.assertEqual(len(out_doc), 1)
            page = out_doc[0]

            # Verify image list contains the 3 inserted images
            images_on_page = page.get_images()
            self.assertEqual(len(images_on_page), 3)

            # Verify text remains crisp vector/searchable
            page_text = page.get_text()
            self.assertIn("BER1-BMCFP4", page_text)
            self.assertIn("CSHL550", page_text)
            self.assertIn("SEVEN FIVE DISTRIBUTOR", page_text)
            self.assertIn("GRAND TOTAL", page_text)

            out_doc.close()


if __name__ == "__main__":
    unittest.main()
