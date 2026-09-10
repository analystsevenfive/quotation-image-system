import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import fitz
sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.catalog import Catalog
from app.services.quotations import QuotationService
from app.models.product import Product
from app.core.template import DEFAULT_TEMPLATE, SEVEN_FIVE_TEMPLATE
from app.models.quotation import BoundingBox, MatchStatus
from app.services.pdf.fitter import calculate_image_placement
from app.services.matching.matcher import ProductMatcher
from tests.fixtures.generate_sample_pdf import generate_quotation_pdf
from tests.fixtures.sample_products import get_sample_products
from tests.test_pipeline import MockImageDownloader


class WebTests(unittest.TestCase):
    def setUp(self):
        products = get_sample_products()
        for i, product in enumerate(products, 1):
            product.id = i
        self.service = QuotationService(Catalog(products), DEFAULT_TEMPLATE, MockImageDownloader())
        self.client = TestClient(create_app(self.service))

    def upload(self):
        response = self.client.post('/api/quotations', files={'file': ('../../quote.pdf', generate_quotation_pdf(num_pages=1), 'application/pdf')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_full_flow_manual_selection_invalidates_output_and_preserves_text(self):
        q = self.upload()
        url = '/api/quotations/' + q['id']
        self.assertEqual(q['filename'], 'quote.pdf')
        self.assertNotIn('bbox', q['items'][0])
        self.assertEqual(self.client.get(url+'/download').status_code, 409)
        result = self.client.post(url+'/generate').json()
        self.assertTrue(result['generated'])
        self.assertEqual(result['images_inserted'], 3)
        response = self.client.get(url+'/download')
        self.assertEqual(response.status_code, 200)
        with fitz.open(stream=response.content, filetype='pdf') as document:
            self.assertIn('BER1-BMCFP4', document[0].get_text())
        selection = self.client.post(url+'/items/4/select-product', json={'product_id':1})
        self.assertEqual(selection.json()['items'][4]['status'], 'manual')
        self.assertFalse(selection.json()['generated'])
        self.assertEqual(self.client.get(url+'/download').status_code, 409)
        self.assertEqual(self.client.post(url+'/generate').status_code, 200)

    def test_session_isolation(self):
        q = self.upload()
        other = TestClient(create_app(self.service))
        for suffix in ['', '/preview', '/download']:
            self.assertEqual(other.get('/api/quotations/'+q['id']+suffix).status_code, 404)
        self.assertEqual(other.post('/api/quotations/'+q['id']+'/generate').status_code, 404)

    def test_invalid_scanned_and_oversize_pdf(self):
        response = self.client.post('/api/quotations', files={'file': ('fake.pdf', b'not a pdf', 'application/pdf')})
        self.assertEqual(response.status_code, 422)
        with fitz.open() as document:
            document.new_page()
            response = self.client.post('/api/quotations', files={'file': ('scan.pdf', document.tobytes(), 'application/pdf')})
        self.assertEqual(response.status_code, 422)
        with patch('app.main.MAX_UPLOAD', 10):
            response = self.client.post('/api/quotations', files={'file': ('large.pdf', b'%PDF-'+b'x'*20, 'application/pdf')})
        self.assertEqual(response.status_code, 413)

    def test_cross_site_and_invalid_selection(self):
        self.assertEqual(self.client.get('/api/health', headers={'Origin':'https://evil.example'}).status_code, 403)
        q = self.upload()
        url = '/api/quotations/'+q['id']
        self.assertEqual(self.client.post(url+'/items/-1/select-product', json={'product_id':1}).status_code, 404)
        self.assertEqual(self.client.post(url+'/items/0/select-product', json={'product_id':99999}).status_code, 404)

    def test_web_images_reject_local_and_untrusted_urls(self):
        for url in ['file:///etc/passwd', 'http://127.0.0.1/image', 'https://evil.example/image', 'https://cdn.shopify.com:444/image']:
            self.assertIsNone(self.service.image(Product(id=50, sku='X', image_url=url)))

    def test_template_expansion_never_exceeds_real_row(self):
        row = BoundingBox(x0=25, y0=350, x1=580, y1=380)
        template = SEVEN_FIVE_TEMPLATE.model_copy(update={'image_min_slot_height':95})
        box = calculate_image_placement(row, 100, 100, template)
        self.assertGreaterEqual(box.y0, row.y0)
        self.assertLessEqual(box.y1, row.y1)
        narrow = template.model_copy(update={'desc_col_x1':200})
        self.assertIsNone(calculate_image_placement(row, 100, 100, narrow))

    def test_duplicate_exact_sku_requires_review(self):
        matcher = ProductMatcher([Product(id=1,sku='A1'), Product(id=2,sku='A1')])
        result = matcher.match('A1')
        self.assertEqual(result.status, MatchStatus.NEEDS_REVIEW)
        self.assertIsNone(result.product)


if __name__ == '__main__':
    unittest.main()

