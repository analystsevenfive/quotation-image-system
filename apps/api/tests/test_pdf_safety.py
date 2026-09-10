import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import fitz
from app.models.quotation import BoundingBox, QuotationItem
from app.services.pdf.fitter import calculate_safe_placement
from app.services.pdf.renderer import QuotationPDFRenderer
from tests.fixtures.generate_sample_pdf import create_test_image


class PdfSafetyTests(unittest.TestCase):
    def test_moves_below_text_within_same_row(self):
        row = BoundingBox(x0=25,y0=200,x1=580,y1=300)
        words = [(260,225,405,240,'long description')]
        box = calculate_safe_placement(row,100,100,words)
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box.y0,240)
        self.assertLessEqual(box.y1,row.y1)
        self.assertAlmostEqual(box.width,box.height)

    def test_skips_when_text_fills_slot(self):
        row = BoundingBox(x0=25,y0=200,x1=580,y1=300)
        self.assertIsNone(calculate_safe_placement(row,100,100,[(260,200,405,300,'text')]))

    def test_repeated_item_numbers_on_different_pages_keep_their_own_images(self):
        with fitz.open() as document:
            document.new_page()
            document.new_page()
            source = document.tobytes()
        items = [QuotationItem(item_number=1,page_number=page,description='',bbox=BoundingBox(x0=25,y0=200,x1=580,y1=300)) for page in (1,2)]
        red = create_test_image(100,100,'red','PNG')
        blue = create_test_image(100,100,'blue','PNG')
        data = QuotationPDFRenderer().render(source,items,{(1,1):red,(2,1):blue})
        with fitz.open(stream=data,filetype='pdf') as document:
            self.assertNotEqual(document[0].get_image_info(hashes=True)[0]['digest'], document[1].get_image_info(hashes=True)[0]['digest'])
        self.assertTrue(all(i.image_inserted for i in items))
