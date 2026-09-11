import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import fitz
from app.services.pdf.visible_text import visible_words
from app.services.pdf.parser import QuotationPDFParser
from app.services.matching.normalizer import normalize_sku
from app.services.matching.matcher import ProductMatcher
from app.models.product import Product
from app.models.quotation import MatchStatus


class VisibleTextTests(unittest.TestCase):
    def test_only_text_before_opaque_cover_is_excluded(self):
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((70, 320), 'MODEL OLD-123')
            page.draw_rect(fitz.Rect(60, 300, 300, 340), fill=(1, 1, 1))
            page.insert_text((70, 320), 'MODEL NEW-456')
            original = page.get_text()
            text = ' '.join(w[4] for w in visible_words(page))
            self.assertNotIn('OLD-123', text)
            self.assertIn('NEW-456', text)
            self.assertEqual(page.get_text(), original)

    def test_transparency_outline_and_partial_cover_keep_text(self):
        for kind in ('transparent', 'outline', 'partial', 'triangle'):
            with self.subTest(kind=kind), fitz.open() as doc:
                page = doc.new_page()
                page.insert_text((70, 320), 'KEEP-123')
                if kind == 'triangle':
                    page.draw_polyline([(60, 300), (300, 300), (300, 340)],
                                       fill=(1, 1, 1), closePath=True)
                else:
                    page.draw_rect(fitz.Rect(60, 300, 80 if kind == 'partial' else 300, 340),
                                   fill=None if kind == 'outline' else (1, 1, 1),
                                   fill_opacity=0.5 if kind == 'transparent' else 1)
                self.assertIn('KEEP-123', [w[4] for w in visible_words(page)])

    def test_labeled_sku_precedes_model_and_unicode_hyphens(self):
        parser = QuotationPDFParser()
        for dash in ('\u00ad', '\u2011', '\u2013'):
            text = f'MODEL: PCCM{dash}P3D{dash}07 MODEL / SKU: NTS1{dash}PCCM{dash}P3D{dash}07'
            self.assertEqual(parser._detect_sku_candidate(text), ('NTS1-PCCM-P3D-07', None))
            self.assertEqual(normalize_sku(f'NTS1{dash}PCCM'), 'NTS1-PCCM')

    def test_covered_item_markers_do_not_create_extra_rows(self):
        with fitz.open() as doc:
            page = doc.new_page()
            for y, number in [(300, 1), (350, 2), (400, 3)]:
                page.insert_text((35, y), str(number))
                page.insert_text((70, y), 'MODEL OLD-123')
            page.draw_rect(fitz.Rect(25, 280, 410, 430), fill=(1, 1, 1))
            for y, number in [(310, 1), (410, 2)]:
                page.insert_text((35, y), str(number))
                page.insert_text((70, y), f'MODEL NEW-{number}')
            page.insert_text((450, 580), 'TOTAL')
            items = QuotationPDFParser().parse(doc.tobytes())
            self.assertEqual([i.detected_sku for i in items], ['NEW-1', 'NEW-2'])

    def test_decimal_models_match_full_catalog_suffix_without_guessing(self):
        parser = QuotationPDFParser()
        matcher = ProductMatcher([
            Product(id=1, sku='PUJ1-331.044', model='331'),
            Product(id=2, sku='PUJ1-331.050', model='331'),
        ])
        code, model = parser._detect_sku_candidate('SCOOP # 331.044 MODEL: 331.044')
        self.assertEqual(code, '331.044')
        self.assertEqual(matcher.match(code, model).product.id, 1)
        self.assertEqual(matcher.match('331').status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(parser._detect_sku_candidate('MODEL / SKU: PUJ1-723.024'),
                         ('PUJ1-723.024', None))

    def test_full_model_alias_keeps_duplicate_products_ambiguous(self):
        matcher = ProductMatcher([
            Product(id=1, sku='CAM1-331.044', model='331'),
            Product(id=2, sku='CAM2-331.044', model='331'),
        ])
        self.assertEqual(matcher.match('331.044').status, MatchStatus.NEEDS_REVIEW)
