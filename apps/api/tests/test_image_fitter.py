"""Unit tests for image fitting calculations and boundary constraints."""

import unittest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.template import DEFAULT_TEMPLATE, QuotationTemplate
from app.models.quotation import BoundingBox
from app.services.pdf.fitter import calculate_image_placement, get_image_dimensions
from tests.fixtures.generate_sample_pdf import create_test_image


class TestImageFitter(unittest.TestCase):
    """Test aspect ratio preservation, column clearance, and scale adaptation."""

    def setUp(self):
        self.template = DEFAULT_TEMPLATE
        # Standard row bounding box: height = 60pt
        self.standard_row = BoundingBox(x0=30.0, y0=200.0, x1=580.0, y1=260.0)

    def test_landscape_image_aspect_ratio(self):
        # 600 x 300 (2:1 aspect ratio)
        orig_w, orig_h = 600, 300
        bbox = calculate_image_placement(self.standard_row, orig_w, orig_h, self.template)

        self.assertIsNotNone(bbox)
        # Aspect ratio should equal 2:1 within floating-point rounding
        fitted_aspect = bbox.width / bbox.height
        self.assertAlmostEqual(fitted_aspect, 2.0, places=1)

        # Must never exceed max allowed width or height
        self.assertLessEqual(bbox.width, self.template.image_max_width)
        self.assertLessEqual(bbox.height, self.standard_row.height)

        # Must strictly stay before QTY column
        self.assertLess(bbox.x1, self.template.qty_col_x0)

    def test_portrait_image_aspect_ratio(self):
        # 300 x 600 (1:2 aspect ratio)
        orig_w, orig_h = 300, 600
        bbox = calculate_image_placement(self.standard_row, orig_w, orig_h, self.template)

        self.assertIsNotNone(bbox)
        fitted_aspect = bbox.width / bbox.height
        self.assertAlmostEqual(fitted_aspect, 0.5, places=1)

        # Must strictly stay inside vertical row boundaries with margins
        self.assertGreaterEqual(bbox.y0, self.standard_row.y0 + self.template.image_top_margin - 0.5)
        self.assertLessEqual(bbox.y1, self.standard_row.y1 - self.template.image_bottom_margin + 0.5)
        self.assertLess(bbox.x1, self.template.qty_col_x0)

    def test_square_image(self):
        # 400 x 400 (1:1 aspect ratio)
        orig_w, orig_h = 400, 400
        bbox = calculate_image_placement(self.standard_row, orig_w, orig_h, self.template)

        self.assertIsNotNone(bbox)
        self.assertAlmostEqual(bbox.width, bbox.height, delta=1.0)
        self.assertLess(bbox.x1, self.template.qty_col_x0)

    def test_very_small_item_area(self):
        # Very cramped row: height = 12pt (below min_row_height_for_image = 20.0)
        cramped_row = BoundingBox(x0=30.0, y0=200.0, x1=580.0, y1=212.0)
        bbox = calculate_image_placement(cramped_row, 200, 200, self.template)

        # Fitter should return None to avoid overflowing into other rows
        self.assertIsNone(bbox)

    def test_transparent_png_image_dimensions(self):
        png_bytes = create_test_image(width=180, height=120, transparent=True, fmt="PNG")
        w, h = get_image_dimensions(png_bytes)
        self.assertEqual(w, 180)
        self.assertEqual(h, 120)


if __name__ == "__main__":
    unittest.main()
