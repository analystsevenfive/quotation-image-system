import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import fitz
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.template import DEFAULT_TEMPLATE
from app.services.catalog import Catalog
from app.services.quotations import QuotationService
from app.services.images.uploads import normalize_uploaded_image
from tests.fixtures.generate_sample_pdf import generate_quotation_pdf, create_test_image
from tests.fixtures.sample_products import get_sample_products
from tests.test_pipeline import MockImageDownloader


class ImageEditorTests(unittest.TestCase):
    def setUp(self):
        products = get_sample_products()
        for index, product in enumerate(products, 1):
            product.id = index
        self.service = QuotationService(Catalog(products), DEFAULT_TEMPLATE, MockImageDownloader())
        self.app = create_app(self.service)
        self.client = TestClient(self.app)
        self.source = generate_quotation_pdf(num_pages=1)
        response = self.client.post('/api/quotations', files={'file': ('test.pdf', self.source, 'application/pdf')})
        self.assertEqual(response.status_code, 201, response.text)
        self.q = response.json()
        self.url = '/api/quotations/' + self.q['id']

    def upload_image(self, index=4, image=None):
        image = image or create_test_image(180, 120, 'red', 'PNG', transparent=True)
        return self.client.post(f'{self.url}/items/{index}/image', files={'file': ('paste.png', image, 'image/png')})

    def test_upload_paste_image_on_missing_product_and_export_exact_placement(self):
        response = self.upload_image()
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][4]
        self.assertTrue(item['uploaded_image'])
        self.assertEqual(item['status'], 'manual')
        self.assertIsNone(item['product'])
        self.assertTrue(item['placement'])
        original = item['placement']
        # Shrink from the same top-left; this stays inside the already-safe box.
        moved = {**original, 'width': original['width']*.75, 'height': original['height']*.75}
        result = self.client.put(f'{self.url}/items/4/placement', json=moved)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['items'][4]['manual_placement'])
        generated = self.client.post(self.url+'/generate')
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()['images_inserted'], 4)
        output = self.client.get(self.url+'/download').content
        with fitz.open(stream=output, filetype='pdf') as doc, fitz.open(stream=self.source, filetype='pdf') as source:
            self.assertEqual(doc[0].get_text(), source[0].get_text())
            expected = (moved['x']*doc[0].rect.width, moved['y']*doc[0].rect.height,
                        (moved['x']+moved['width'])*doc[0].rect.width,
                        (moved['y']+moved['height'])*doc[0].rect.height)
            self.assertTrue(any(all(abs(a-b)<.02 for a,b in zip(info['bbox'],expected)) for info in doc[0].get_image_info()))
            self.assertTrue(any(image[1] for image in doc[0].get_images()))  # Transparency mask survives.
        self.assertEqual(self.client.get(self.url+'/original').content, self.source)

    def test_rejects_cross_row_price_column_distortion_and_text_collision(self):
        item = self.q['items'][0]
        rect = item['placement']
        for invalid in [{**rect,'x':.8}, {**rect,'y':.9}, {**rect,'width':rect['width']/2}, {**rect,'x':.1,'y':item['bounds']['y']}]:
            response = self.client.put(f'{self.url}/items/0/placement', json=invalid)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get(self.url).json()['items'][0]['placement'], rect)

    def test_invalid_upload_and_placement_do_not_destroy_generated_output(self):
        self.client.post(self.url+'/generate')
        old = self.client.get(self.url+'/download').content
        response = self.upload_image(image=b'<svg>not a bitmap</svg>')
        self.assertEqual(response.status_code, 422)
        response = self.client.put(f'{self.url}/items/0/placement', json={'x':0, 'y':0,'width':.1,'height':.1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(self.url+'/download').content, old)

    def test_replacement_reset_and_catalog_selection(self):
        self.upload_image(index=0)
        item = self.client.get(self.url).json()['items'][0]
        small = {**item['placement'], 'width':item['placement']['width']*.8,'height':item['placement']['height']*.8}
        self.client.put(f'{self.url}/items/0/placement', json=small)
        self.client.post(self.url+'/generate')
        response = self.client.delete(f'{self.url}/items/0/placement')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['items'][0]['manual_placement'])
        self.assertTrue(response.json()['items'][0]['uploaded_image'])
        self.assertEqual(self.client.get(self.url+'/download').status_code, 409)
        response = self.client.post(f'{self.url}/items/0/select-product', json={'product_id':1})
        self.assertFalse(response.json()['items'][0]['uploaded_image'])

    def test_owner_only_for_uploaded_images_and_edits(self):
        self.upload_image()
        other = TestClient(self.app)
        self.assertEqual(other.get(self.url+'/original').status_code, 404)
        self.assertEqual(other.get(f'{self.url}/items/4/image').status_code, 404)
        self.assertEqual(other.post(f'{self.url}/items/4/image', files={'file':('x.png',b'bad','image/png')}).status_code, 404)
        self.assertEqual(other.put(f'{self.url}/items/4/placement', json=self.q['items'][0]['placement']).status_code, 404)
        self.assertEqual(other.delete(f'{self.url}/items/4/placement').status_code, 404)

    def test_size_limits_and_nonfinite_placement(self):
        with patch('app.main.MAX_IMAGE_UPLOAD', 10):
            self.assertEqual(self.upload_image().status_code, 413)
        rect = {**self.q['items'][0]['placement'], 'x':'NaN'}
        self.assertEqual(self.client.put(f'{self.url}/items/0/placement', json=rect).status_code, 422)
        self.assertEqual(self.upload_image(index=-1).status_code, 404)

    def test_exif_orientation_and_pixel_limit(self):
        image = Image.new('RGB', (40,80), 'red')
        exif = Image.Exif()
        exif[274] = 6
        stream = io.BytesIO()
        image.save(stream,format='JPEG',exif=exif)
        normalized = normalize_uploaded_image(stream.getvalue())
        with Image.open(io.BytesIO(normalized)) as result:
            self.assertEqual(result.size, (80,40))
            self.assertFalse(result.getexif())
        with patch('app.services.images.uploads.MAX_IMAGE_PIXELS', 100):
            with self.assertRaises(ValueError):
                normalize_uploaded_image(stream.getvalue())

    def test_webp_upload_and_true_file_validation(self):
        with Image.open(io.BytesIO(create_test_image(40,60))) as image:
            stream = io.BytesIO()
            image.save(stream,format='WEBP')
        response = self.upload_image(image=stream.getvalue())
        self.assertEqual(response.status_code, 200)
        preview = self.client.get(f'{self.url}/items/4/image')
        self.assertEqual(preview.headers['content-type'], 'image/png')
        self.assertTrue(preview.content.startswith(b'\x89PNG'))
