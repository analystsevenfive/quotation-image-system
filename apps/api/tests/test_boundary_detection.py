"""Unit tests for PDF table and item boundary detection."""

import unittest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.template import DEFAULT_TEMPLATE
from app.services.pdf.parser import QuotationPDFParser
from tests.fixtures.generate_sample_pdf import generate_quotation_pdf


class TestItemBoundaryDetection(unittest.TestCase):
    """Test dynamic Y-coordinate detection and variable row heights."""

    def setUp(self):
        self.parser = QuotationPDFParser(template=DEFAULT_TEMPLATE)

    def test_variable_item_heights_and_boundaries(self):
        # Generate single page quotation with 5 items of varying heights
        pdf_bytes = generate_quotation_pdf(num_pages=1)
        items = self.parser.parse(pdf_bytes)

        self.assertEqual(len(items), 5)

        # 1. Verify item numbers are sequential
        for idx, item in enumerate(items, start=1):
            self.assertEqual(item.item_number, idx)
            self.assertEqual(item.page_number, 1)

        # 2. Verify dynamic boundaries (y0 < y1)
        for item in items:
            self.assertGreater(item.bbox.y1, item.bbox.y0)
            self.assertGreater(item.bbox.height, 20.0)

        # 3. Verify contiguous boundary relationship: item[i].end_y == item[i+1].start_y
        for i in range(len(items) - 1):
            curr_y1 = items[i].bbox.y1
            next_y0 = items[i + 1].bbox.y0
            # Difference between row end and next row start should be very small (within padding tolerance)
            self.assertAlmostEqual(curr_y1, next_y0, delta=5.0)

        # 4. Verify last item boundary is constrained by footer
        last_item = items[-1]
        self.assertLessEqual(last_item.bbox.y1, 680.0)

        # 5. Verify SKUs were correctly extracted
        expected_skus = ["BER1-BMCFP4", "CSHL550", "DB-CW76-DRG", "DB-PP120-GY", "UNKNOWN-999"]
        extracted_skus = [item.detected_sku for item in items]
        self.assertEqual(extracted_skus, expected_skus)

    def test_multi_page_quotation(self):
        # Generate 2-page quotation
        pdf_bytes = generate_quotation_pdf(num_pages=2)
        items = self.parser.parse(pdf_bytes)

        self.assertEqual(len(items), 10)  # 5 items per page * 2 pages

        # Items on page 1
        page_1_items = [i for i in items if i.page_number == 1]
        self.assertEqual(len(page_1_items), 5)

        # Items on page 2
        page_2_items = [i for i in items if i.page_number == 2]
        self.assertEqual(len(page_2_items), 5)

        # Sequential numbering across the entire quotation
        for idx, item in enumerate(items, start=1):
            self.assertEqual(item.item_number, idx)

    def test_real_quotation_qt0926_detection(self):
        sample_path = Path(__file__).parent / "fixtures" / "QT0926-00287.pdf"
        if not sample_path.is_file():
            self.skipTest("Real QT0926 sample PDF not found")

        items = self.parser.parse(sample_path)
        self.assertEqual(len(items), 19)

        # Verify specific detected models matching the actual Seven Five document
        detected_models = {item.item_number: item.detected_sku for item in items}
        self.assertEqual(detected_models[1], "CSHL550")
        self.assertEqual(detected_models[2], "DB-CW76-DRG")
        self.assertEqual(detected_models[3], "DB-PP120-GY")
        self.assertEqual(detected_models[4], "MFC3535-BL")
        self.assertEqual(detected_models[5], "MFC3535-GR")
        self.assertEqual(detected_models[6], "MFC3535-RD")
        self.assertEqual(detected_models[7], "SSG-22L")
        self.assertEqual(detected_models[8], "LFB-60")
        self.assertEqual(detected_models[9], "RS-PT")
        self.assertEqual(detected_models[10], "MOP-MO")
        self.assertEqual(detected_models[11], "SB-WF")
        self.assertEqual(detected_models[12], "1120CBR-110")
        self.assertEqual(detected_models[13], "1520CBR-110")
        self.assertEqual(detected_models[14], "S-RESER")
        self.assertEqual(detected_models[15], "BELL-C")
        self.assertEqual(detected_models[16], "PT1400-167")
        self.assertEqual(detected_models[17], "PT1600-167")
        self.assertEqual(detected_models[18], "KK-BSP924")
        self.assertIsNone(detected_models[19])  # Delivery conditions row


if __name__ == "__main__":
    unittest.main()
