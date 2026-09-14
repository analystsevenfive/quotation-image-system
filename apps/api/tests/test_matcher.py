"""Unit tests for 5-tier product matching engine."""

import unittest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.quotation import MatchMethod, MatchStatus
from app.services.matching.matcher import ProductMatcher
from tests.fixtures.sample_products import get_sample_products


class TestProductMatcher(unittest.TestCase):
    """Test 5-tier matching priority and ambiguity handling."""

    def setUp(self):
        self.products = get_sample_products()
        self.matcher = ProductMatcher(self.products)

    def test_priority_1_exact_sku(self):
        result = self.matcher.match("BER1-BMCFP4")
        self.assertEqual(result.status, MatchStatus.MATCHED)
        self.assertEqual(result.method, MatchMethod.EXACT_SKU)
        self.assertEqual(result.confidence, 1.0)
        self.assertIsNotNone(result.product)
        self.assertEqual(result.product.sku, "BER1-BMCFP4")

    def test_priority_2_exact_winspeed(self):
        result = self.matcher.match("CSHL550")
        self.assertEqual(result.status, MatchStatus.MATCHED)
        # In sample products CSHL550 is both exact sku and winspeed; exact sku takes precedence
        self.assertEqual(result.method, MatchMethod.EXACT_SKU)

        # Test winspeed when SKU differs
        # Create a product where sku != winspeed
        products_with_ws = get_sample_products()
        products_with_ws[0].sku = "OTHER-SKU-999"
        matcher_ws = ProductMatcher(products_with_ws)
        result_ws = matcher_ws.match("BER1-BMCFP4")
        self.assertEqual(result_ws.status, MatchStatus.MATCHED)
        self.assertEqual(result_ws.method, MatchMethod.WINSPEED)
        self.assertEqual(result_ws.confidence, 0.95)

    def test_priority_3_normalized_sku(self):
        # Lowercase and Unicode dash
        result = self.matcher.match("ber1\u2013bmcfp4")
        self.assertEqual(result.status, MatchStatus.MATCHED)
        self.assertEqual(result.method, MatchMethod.NORMALIZED_SKU)
        self.assertEqual(result.confidence, 0.90)
        self.assertEqual(result.product.sku, "BER1-BMCFP4")

    def test_priority_4_good_bill_name(self):
        # 1. Exact billing name in description
        result = self.matcher.match(
            detected_value=None,
            description='"NTS" CONDIMENT 6 COMPARTMENT MODEL : CD-06',
        )
        self.assertEqual(result.status, MatchStatus.MATCHED)
        self.assertEqual(result.method, MatchMethod.GOOD_BILL_NAME)
        self.assertEqual(result.confidence, 0.88)
        self.assertIsNotNone(result.product)
        self.assertEqual(result.product.sku, "NTS1-CD-06")

        # 2. Normalized billing name (different whitespace/quotes) in description
        result_norm = self.matcher.match(
            detected_value=None,
            description='NTS CONDIMENT 6 COMPARTMENT MODEL: CD-06',
        )
        self.assertEqual(result_norm.status, MatchStatus.MATCHED)
        self.assertEqual(result_norm.method, MatchMethod.GOOD_BILL_NAME)
        self.assertEqual(result_norm.product.sku, "NTS1-CD-06")

        # 3. First-line match in multi-line quotation description
        multiline = '"NTS" CONDIMENT 6 COMPARTMENT MODEL : CD-06\nDIMENSION : 45.5 x 15 x 9 CM.\nSTAINLESS STEEL'
        result_multi = self.matcher.match(
            detected_value=None,
            description=multiline,
        )
        self.assertEqual(result_multi.status, MatchStatus.MATCHED)
        self.assertEqual(result_multi.method, MatchMethod.GOOD_BILL_NAME)
        self.assertEqual(result_multi.product.sku, "NTS1-CD-06")

        # 4. In detected_value when parser captured the full bill name
        result_val = self.matcher.match(detected_value='"NTS" CONDIMENT 6 COMPARTMENT MODEL : CD-06')
        self.assertEqual(result_val.status, MatchStatus.MATCHED)
        self.assertEqual(result_val.method, MatchMethod.GOOD_BILL_NAME)
        self.assertEqual(result_val.product.sku, "NTS1-CD-06")

    def test_priority_5_model_match(self):
        # Only model provided
        result = self.matcher.match("BMCFP4")
        self.assertEqual(result.status, MatchStatus.MATCHED)
        self.assertEqual(result.method, MatchMethod.MODEL)
        self.assertEqual(result.confidence, 0.80)
        self.assertEqual(result.product.sku, "BER1-BMCFP4")

    def test_ambiguous_model_never_auto_accepted(self):
        # MOD100 exists under both BRAND-A-MOD100 and BRAND-B-MOD100
        result = self.matcher.match("MOD100")
        self.assertEqual(result.status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.method, MatchMethod.MODEL)
        self.assertEqual(len(result.candidates), 2)
        self.assertIsNone(result.product)  # Never auto-assign ambiguous candidate!

    def test_missing_product(self):
        result = self.matcher.match("NON-EXISTENT-SKU-404")
        self.assertEqual(result.status, MatchStatus.MISSING)
        self.assertIsNone(result.method)
        self.assertEqual(result.confidence, 0.0)
        self.assertIsNone(result.product)


if __name__ == "__main__":
    unittest.main()
