"""Unit tests for MappingStore and Priority 0 manual matching."""
import shutil
import tempfile
import unittest
from pathlib import Path
from app.models.quotation import MatchMethod, MatchStatus
from app.services.matching.mappings import MappingStore
from app.services.matching.matcher import ProductMatcher
from tests.fixtures.sample_products import get_sample_products


class TestMappingStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_path = str(Path(self.temp_dir) / "test_mappings.json")
        self.store = MappingStore(self.file_path)
        self.products = get_sample_products()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_mapping(self):
        self.assertIsNone(self.store.get("UNKNOWN-SKU-123"))
        self.store.set("UNKNOWN-SKU-123", 1, note="User manual choice")
        self.assertEqual(self.store.get("UNKNOWN-SKU-123"), 1)
        # Should also match case-insensitively and normalized
        self.assertEqual(self.store.get("unknown-sku-123"), 1)

    def test_list_all_and_delete(self):
        self.store.set("SKU-A", 1)
        self.store.set("SKU-B", 2)
        mappings = self.store.list_all()
        self.assertEqual(len(mappings), 2)
        # Delete
        self.assertTrue(self.store.delete("SKU-A"))
        self.assertIsNone(self.store.get("SKU-A"))
        self.assertEqual(len(self.store.list_all()), 1)

    def test_priority_0_matching_with_mapping_store(self):
        # Without mapping, UNKNOWN-SKU is MISSING
        matcher = ProductMatcher(self.products, mapping_store=self.store)
        res1 = matcher.match("UNKNOWN-CUSTOM-SKU")
        self.assertEqual(res1.status, MatchStatus.MISSING)

        # Now map UNKNOWN-CUSTOM-SKU to product id 1 (BER1-BMCFP4)
        target_product = self.products[0]
        self.store.set("UNKNOWN-CUSTOM-SKU", target_product.id)

        # Match again
        res2 = matcher.match("UNKNOWN-CUSTOM-SKU")
        self.assertEqual(res2.status, MatchStatus.MATCHED)
        self.assertEqual(res2.method, MatchMethod.MANUAL)
        self.assertEqual(res2.confidence, 1.0)
        self.assertEqual(res2.product.id, target_product.id)
