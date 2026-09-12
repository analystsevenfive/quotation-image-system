import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.matching.normalizer import normalize_image_url, extract_model_from_sku
from app.services.shopify_sync import is_sync_running


class TestShopifySync(unittest.TestCase):
    def setUp(self):
        self.app = create_app(service=MagicMock())
        self.client = TestClient(self.app, base_url="http://localhost:8000")

    def test_image_url_normalization(self):
        # Adds &width=200 to cdn.shopify.com URLs
        url = "https://cdn.shopify.com/s/files/1/0123/products/sample.jpg?v=123"
        normalized = normalize_image_url(url)
        self.assertIn("width=200", normalized)

        # Existing width is replaced or set
        url2 = "https://cdn.shopify.com/s/files/1/0123/products/sample.jpg?width=500"
        normalized2 = normalize_image_url(url2, width=200)
        self.assertIn("width=200", normalized2)

        # Non-Shopify URLs remain untouched
        ext_url = "https://example.com/image.png"
        self.assertEqual(normalize_image_url(ext_url), ext_url)

    def test_extract_model_from_sku(self):
        self.assertEqual(extract_model_from_sku("BER1-BMCFP4"), "BMCFP4")
        self.assertEqual(extract_model_from_sku("CW-76"), "76")
        self.assertIsNone(extract_model_from_sku(""))

    def test_get_sync_status(self):
        resp = self.client.get("/api/sync/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("is_running", data)
        self.assertIn("last_sync", data)

    @patch("app.main.run_sync_background")
    def test_trigger_shopify_sync(self, mock_run_sync):
        resp = self.client.post("/api/sync/shopify")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "started")

    @patch("app.services.good_bill_name_sync.update_good_bill_names_in_db")
    def test_sync_good_bill_names(self, mock_update):
        mock_update.return_value = 2
        payload = [
            {"good_id": "123", "good_bill_name": "Product 123"},
            {"good_id": "456", "good_bill_name": "Product 456"},
        ]
        resp = self.client.post("/api/sync/good-bill-names", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("updated"), 2)


if __name__ == "__main__":
    unittest.main()

