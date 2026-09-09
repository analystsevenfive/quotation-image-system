"""Unit tests for SKU and model normalization."""

import unittest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.matching.normalizer import extract_model_from_sku, normalize_sku


class TestSKUNormalizer(unittest.TestCase):
    """Test SKU normalization rules specified in the specification."""

    def test_uppercase_and_whitespace(self):
        self.assertEqual(normalize_sku("  ber1-bmcfp4  "), "BER1-BMCFP4")
        self.assertEqual(normalize_sku("BER1-BMCFP4\n"), "BER1-BMCFP4")
        self.assertEqual(normalize_sku("\tBER1-BMCFP4\r\n"), "BER1-BMCFP4")

    def test_unicode_dashes(self):
        # En-dash (\u2013)
        self.assertEqual(normalize_sku("BER1\u2013BMCFP4"), "BER1-BMCFP4")
        # Em-dash (\u2014)
        self.assertEqual(normalize_sku("BER1\u2014BMCFP4"), "BER1-BMCFP4")
        # Minus sign (\u2212)
        self.assertEqual(normalize_sku("BER1\u2212BMCFP4"), "BER1-BMCFP4")
        # Fullwidth hyphen (\uFF0D)
        self.assertEqual(normalize_sku("BER1\uFF0DBMCFP4"), "BER1-BMCFP4")

    def test_internal_spaces_and_brackets(self):
        self.assertEqual(normalize_sku("BER1 - BMCFP4"), "BER1 - BMCFP4")
        self.assertEqual(normalize_sku("  (BER1-BMCFP4)  "), "BER1-BMCFP4")
        self.assertEqual(normalize_sku("'BER1-BMCFP4'"), "BER1-BMCFP4")

    def test_empty_and_none(self):
        self.assertEqual(normalize_sku(None), "")
        self.assertEqual(normalize_sku(""), "")
        self.assertEqual(normalize_sku("   \n"), "")

    def test_extract_model(self):
        self.assertEqual(extract_model_from_sku("BER1-BMCFP4"), "BMCFP4")
        self.assertEqual(extract_model_from_sku("CW-76"), "76")
        self.assertEqual(extract_model_from_sku("BRAND/CSHL550"), "CSHL550")
        self.assertIsNone(extract_model_from_sku("CSHL550"))
        self.assertIsNone(extract_model_from_sku(""))


if __name__ == "__main__":
    unittest.main()
