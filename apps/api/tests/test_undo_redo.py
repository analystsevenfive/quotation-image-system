import io
import sys
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.catalog import Catalog
from app.services.quotations import QuotationService
from app.core.template import DEFAULT_TEMPLATE
from tests.fixtures.generate_sample_pdf import generate_quotation_pdf
from tests.fixtures.sample_products import get_sample_products
from tests.test_pipeline import MockImageDownloader


class UndoRedoTests(unittest.TestCase):
    def setUp(self):
        products = get_sample_products()
        for i, product in enumerate(products, 1):
            product.id = i
        self.service = QuotationService(Catalog(products), DEFAULT_TEMPLATE, MockImageDownloader())
        self.client = TestClient(create_app(self.service))

    def upload(self):
        res = self.client.post('/api/quotations', files={'file': ('quote.pdf', generate_quotation_pdf(num_pages=1), 'application/pdf')})
        self.assertEqual(res.status_code, 201)
        return res.json()

    def make_png(self, color=(255, 0, 0)):
        buf = io.BytesIO()
        Image.new('RGB', (100, 100), color=color).save(buf, format='PNG')
        return buf.getvalue()

    def test_undo_and_redo_placement_change(self):
        q = self.upload()
        qid = q['id']
        self.assertFalse(q['can_undo'])
        self.assertFalse(q['can_redo'])

        original_placement = q['items'][0]['placement']
        self.assertIsNotNone(original_placement)

        # Shrink item 0 to new placement within safe bounds
        new_rect = {**original_placement, 'width': original_placement['width'] * 0.8, 'height': original_placement['height'] * 0.8}
        put_res = self.client.put(f'/api/quotations/{qid}/items/0/placement', json=new_rect)
        self.assertEqual(put_res.status_code, 200)
        updated = put_res.json()
        self.assertTrue(updated['can_undo'])
        self.assertFalse(updated['can_redo'])
        self.assertAlmostEqual(updated['items'][0]['placement']['y'], new_rect['y'], places=3)

        # Undo placement change
        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 200)
        undone = undo_res.json()
        self.assertFalse(undone['can_undo'])
        self.assertTrue(undone['can_redo'])
        self.assertAlmostEqual(undone['items'][0]['placement']['y'], original_placement['y'], places=3)

        # Redo placement change
        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 200)
        redone = redo_res.json()
        self.assertTrue(redone['can_undo'])
        self.assertFalse(redone['can_redo'])
        self.assertAlmostEqual(redone['items'][0]['placement']['y'], new_rect['y'], places=3)

    def test_undo_and_redo_image_replacement(self):
        q = self.upload()
        qid = q['id']

        self.assertFalse(q['items'][0]['uploaded_image'])
        png_data = self.make_png(color=(0, 255, 0))

        # Upload replacement image
        up_res = self.client.post(f'/api/quotations/{qid}/items/0/image', files={'file': ('custom.png', png_data, 'image/png')})
        self.assertEqual(up_res.status_code, 200)
        with_image = up_res.json()
        self.assertTrue(with_image['items'][0]['uploaded_image'])
        self.assertTrue(with_image['can_undo'])

        # Undo image upload
        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 200)
        undone = undo_res.json()
        self.assertFalse(undone['items'][0]['uploaded_image'])
        self.assertTrue(undone['can_redo'])

        # Redo image upload
        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 200)
        redone = redo_res.json()
        self.assertTrue(redone['items'][0]['uploaded_image'])
        self.assertFalse(redone['can_redo'])

    def test_undo_and_redo_product_selection(self):
        q = self.upload()
        qid = q['id']

        original_product_sku = q['items'][4]['product']['sku'] if q['items'][4]['product'] else None

        # Select product 1
        sel_res = self.client.post(f'/api/quotations/{qid}/items/4/select-product', json={'product_id': 1})
        self.assertEqual(sel_res.status_code, 200)
        selected = sel_res.json()
        self.assertEqual(selected['items'][4]['status'], 'manual')
        self.assertTrue(selected['can_undo'])

        # Undo selection
        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 200)
        undone = undo_res.json()
        if original_product_sku is None:
            self.assertIsNone(undone['items'][4]['product'])
        else:
            self.assertEqual(undone['items'][4]['product']['sku'], original_product_sku)
        self.assertTrue(undone['can_redo'])

        # Redo selection
        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 200)
        redone = redo_res.json()
        self.assertEqual(redone['items'][4]['status'], 'manual')
        self.assertEqual(redone['items'][4]['product']['id'], 1)

    def test_empty_undo_and_redo_returns_400(self):
        q = self.upload()
        qid = q['id']

        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 400)
        self.assertEqual(undo_res.json()['detail'], 'ไม่มีประวัติให้ย้อนกลับ')

        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 400)
    def test_delete_image_and_undo_redo(self):
        q = self.upload()
        qid = q['id']

        self.assertTrue(q['items'][0]['has_image'])
        self.assertIsNotNone(q['items'][0]['product'])

        # Delete image for item 0
        del_res = self.client.delete(f'/api/quotations/{qid}/items/0/image')
        self.assertEqual(del_res.status_code, 200)
        deleted = del_res.json()
        self.assertFalse(deleted['items'][0]['has_image'])
        self.assertIsNone(deleted['items'][0]['product'])
        self.assertEqual(deleted['items'][0]['status'], 'missing')
        self.assertTrue(deleted['can_undo'])

        # Undo delete
        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 200)
        undone = undo_res.json()
        self.assertTrue(undone['items'][0]['has_image'])
        self.assertIsNotNone(undone['items'][0]['product'])
        self.assertTrue(undone['can_redo'])

        # Redo delete
        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 200)
        redone = redo_res.json()
        self.assertFalse(redone['items'][0]['has_image'])
        self.assertIsNone(redone['items'][0]['product'])

    def test_batch_delete_images_and_undo_redo(self):
        q = self.upload()
        qid = q['id']

        # Ensure items 0 and 1 have images initially
        self.assertTrue(q['items'][0]['has_image'])
        self.assertTrue(q['items'][1]['has_image'])

        # Batch delete items 0 and 1
        res = self.client.post(f'/api/quotations/{qid}/items/batch-delete-images', json={'item_ids': [0, 1]})
        self.assertEqual(res.status_code, 200)
        batch_deleted = res.json()
        self.assertFalse(batch_deleted['items'][0]['has_image'])
        self.assertFalse(batch_deleted['items'][1]['has_image'])
        self.assertTrue(batch_deleted['can_undo'])

        # Undo restores both items in a single step!
        undo_res = self.client.post(f'/api/quotations/{qid}/undo')
        self.assertEqual(undo_res.status_code, 200)
        undone = undo_res.json()
        self.assertTrue(undone['items'][0]['has_image'])
        self.assertTrue(undone['items'][1]['has_image'])
        self.assertTrue(undone['can_redo'])

        # Redo deletes both items in a single step!
        redo_res = self.client.post(f'/api/quotations/{qid}/redo')
        self.assertEqual(redo_res.status_code, 200)
        redone = redo_res.json()
        self.assertFalse(redone['items'][0]['has_image'])
        self.assertFalse(redone['items'][1]['has_image'])


if __name__ == '__main__':
    unittest.main()
