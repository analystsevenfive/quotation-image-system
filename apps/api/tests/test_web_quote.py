import io
import os
import sys
import time
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient

from app.core.app_proxy import proxy_signature, verified_proxy_params
from app.main import create_app
from app.services.web_quote.models import Cart, CartLine, Customer
from app.services.web_quote.service import BANGKOK, WebQuoteService, clean_terms, shopify_image_url
from app.services.web_quote.shopify_sources import CartUnavailable, parse_cart, parse_customer, spec_lines, valid_cart_token
from app.services.web_quote.store import MemoryQuoteStore
from app.services.web_quote.renderer import amount
from app.services.web_quote.totals import baht_words, quote_totals

SECRET = 'proxy-secret'
SHOP = 'example.myshopify.com'
TOKEN = 'Z2NwLWFzaWEtc291dGhlYXN0MTowMUpBQkM?key=abcdef123456'


def png():
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buffer, 'PNG')
    return buffer.getvalue()


def signed_query(**params):
    params = {'shop': SHOP, 'path_prefix': '/apps/quotation', 'timestamp': str(int(time.time())), **params}
    params['signature'] = proxy_signature(params.items(), SECRET)
    return urlencode(params)


def page_text(document, index):
    return document[index].get_text().replace('​', '')


class FakeCartSource:
    def __init__(self, cart):
        self.cart = cart

    def fetch(self, token):
        if self.cart is None:
            raise CartUnavailable('Cart not found')
        return self.cart


class FakeCustomerSource:
    def fetch(self, customer_id):
        return Customer(
            id=customer_id,
            name='คุณนก ทดสอบ',
            email='nok@example.com',
            phone='085 1088 777',
            company='บริษัท ซีเลค เซอร์วิส พาร์ทเนอร์ จำกัด',
            address_lines=['อาคารเดอะปาร์ค ชั้นที่ 11 เลขที่ 88 ถนนรัชดาภิเษก', 'คลองเตย กรุงเทพมหานคร 10110'],
        )


class FakeDownloader:
    def get_images_batch(self, urls):
        return {url: png() for url in urls}


def cart(lines=1, total=None):
    items = [
        CartLine(title=f'"CAMBRO" PC COVER W/HANDLE GN1/2 #{index}', variant_title='Clear', sku=f'20CWCH-{index}',
                 quantity=2, unit_price=Decimal('149.80'), image_url=f'https://cdn.shopify.com/s/files/{index}.png')
        for index in range(lines)
    ]
    gross = sum(line.unit_price * line.quantity for line in items)
    return Cart(currency='THB', lines=items, total=gross if total is None else total)


class ProxySignatureTests(unittest.TestCase):
    def test_accepts_shopify_signature(self):
        query = signed_query(logged_in_customer_id='42')
        params = verified_proxy_params(urllib_items(query), SECRET, SHOP)
        self.assertEqual(params['logged_in_customer_id'], '42')

    def test_rejects_tampered_customer(self):
        query = signed_query(logged_in_customer_id='42').replace('logged_in_customer_id=42', 'logged_in_customer_id=43')
        self.assertIsNone(verified_proxy_params(urllib_items(query), SECRET, SHOP))

    def test_rejects_other_shop_and_stale_timestamp(self):
        other = signed_query(shop='other.myshopify.com')
        stale = signed_query(timestamp=str(int(time.time()) - 3600))
        self.assertIsNone(verified_proxy_params(urllib_items(other), SECRET, SHOP))
        self.assertIsNone(verified_proxy_params(urllib_items(stale), SECRET, SHOP))

    def test_rejects_missing_secret(self):
        self.assertIsNone(verified_proxy_params(urllib_items(signed_query()), '', SHOP))


def urllib_items(query):
    from urllib.parse import parse_qsl
    return parse_qsl(query, keep_blank_values=True)


class TotalsTests(unittest.TestCase):
    def test_vat_inclusive_cart_without_discount(self):
        totals = quote_totals(cart(lines=2))
        self.assertEqual(totals.total, Decimal('560.00'))
        self.assertEqual(totals.discount, Decimal('0.00'))
        self.assertEqual(totals.subtotal, Decimal('560.00'))
        self.assertEqual(totals.vat, Decimal('39.20'))
        self.assertEqual(totals.grand_total, Decimal('599.20'))

    def test_cart_discount_keeps_grand_total_equal_to_cart(self):
        totals = quote_totals(cart(lines=2, total=Decimal('500.00')))
        self.assertEqual(totals.grand_total, Decimal('500.00'))
        self.assertEqual(totals.discount, Decimal('92.71'))
        self.assertEqual(totals.subtotal + totals.vat, Decimal('500.00'))
        self.assertEqual(totals.total - totals.discount, totals.subtotal)

    def test_unpriced_amounts_stay_blank(self):
        self.assertEqual(amount(Decimal('0')), '')
        self.assertEqual(amount(Decimal('1234.5')), '1,234.50')

    def test_baht_words(self):
        self.assertEqual(baht_words(Decimal('39065.70')), 'THIRTY NINE THOUSAND SIXTY FIVE BAHT AND SEVENTY SATANG')
        self.assertEqual(baht_words(Decimal('1200000')), 'ONE MILLION TWO HUNDRED THOUSAND BAHT ONLY')
        self.assertEqual(baht_words(Decimal('0.05')), 'ZERO BAHT AND FIVE SATANG')


class ShopifyParsingTests(unittest.TestCase):
    def test_parse_cart(self):
        data = {
            'cost': {'totalAmount': {'amount': '320.0', 'currencyCode': 'THB'}},
            'lines': {'pageInfo': {'hasNextPage': False}, 'edges': [{'node': {
                'quantity': 2,
                'cost': {'amountPerQuantity': {'amount': '160.5'}},
                'merchandise': {'sku': 'A-1', 'title': 'Default Title', 'image': None,
                                'product': {'title': 'Pan', 'featuredImage': {'url': 'https://cdn.shopify.com/a.png'}}},
            }}]},
        }
        parsed = parse_cart(data)
        self.assertEqual(parsed.total, Decimal('320.0'))
        self.assertEqual(parsed.lines[0].variant_title, '')
        self.assertEqual(parsed.lines[0].image_url, 'https://cdn.shopify.com/a.png')

    def test_empty_or_missing_cart(self):
        with self.assertRaises(CartUnavailable):
            parse_cart(None)
        with self.assertRaises(CartUnavailable):
            parse_cart({'cost': {}, 'lines': {'pageInfo': {'hasNextPage': False}, 'edges': []}})

    def test_parse_customer(self):
        customer = parse_customer('7', {'displayName': 'Nok', 'email': 'n@example.com', 'phone': None,
                                        'defaultAddress': {'company': 'ACME', 'address1': '1 Road', 'address2': None,
                                                           'city': 'Bangkok', 'province': None, 'zip': '10110', 'phone': '02'}})
        self.assertEqual(customer.phone, '02')
        self.assertEqual(customer.address_lines, ['1 Road', 'Bangkok 10110'])

    def test_customer_without_name_is_not_named_by_email(self):
        customer = parse_customer('7', {'displayName': 'n@example.com', 'email': 'n@example.com'})
        self.assertEqual((customer.name, customer.email), ('', 'n@example.com'))

    def test_spec_lines_from_metafields(self):
        def field(value, name=''):
            return {'value': value, 'definition': {'name': name}}
        lines = spec_lines({
            'width_mm': field('575'), 'length_mm': field('605'), 'height_mm': field('820'),
            'voltage': field('400'), 'hz': field('50'), 'phrase': field('3N'),
            'made_in': field('Italy', 'Made in'), 'packing_width': field('690', 'Packing Width'),
        })
        self.assertEqual(lines, ['Dimensions (W x D x H): 575 x 605 x 820 mm', 'Electrical: 400 V / 50 Hz / 3N', 'Made in: Italy'])

    def test_spec_lines_fall_back_to_description_list(self):
        html = ('<p>Intro</p><ul><li>Not a spec</li></ul><p>Technical Specifications:</p><ul>'
                '<li>Product Code: X-1</li><li>Tank Capacity: 24L</li><li>Size: 5 &amp; 6</li></ul><ul><li>Later</li></ul>')
        self.assertEqual(spec_lines({}, html), ['Tank Capacity: 24L', 'Size: 5 & 6'])
        self.assertEqual(spec_lines({}, '<p>No specs</p>'), [])

    def test_cart_token_format(self):
        self.assertTrue(valid_cart_token(TOKEN))
        self.assertTrue(valid_cart_token('c1-0123456789abcdef'))
        self.assertFalse(valid_cart_token('gid://shopify/Cart/x'))
        self.assertFalse(valid_cart_token('abc'))

    def test_only_shopify_cdn_images_are_fetched(self):
        self.assertIn('width=400', shopify_image_url('https://cdn.shopify.com/s/files/a.png?v=1'))
        self.assertIsNone(shopify_image_url('file:///etc/passwd'))
        self.assertIsNone(shopify_image_url('http://cdn.shopify.com/a.png'))
        self.assertIsNone(shopify_image_url('https://example.com/a.png'))

    def test_terms_are_trimmed_and_bounded(self):
        terms = clean_terms('  CASH \n ', 'x' * 900, 999)
        self.assertEqual(terms.payment_term, 'CASH')
        self.assertEqual(len(terms.remark), 300)
        self.assertEqual(terms.validity_days, 365)


class CartQuoteEndpointTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'SHOPIFY_CLIENT_SECRET': SECRET, 'SHOPIFY_SHOP': SHOP, 'AUTH_ENABLED': 'true', 'ALLOWED_ORIGINS': ''})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = MemoryQuoteStore()
        self.quotes = WebQuoteService(FakeCartSource(cart(lines=7)), FakeCustomerSource(), self.store, FakeDownloader(),
                                      clock=lambda: datetime(2026, 10, 26, 10, 0, tzinfo=BANGKOK), quotes_per_hour=2)
        self.client = TestClient(create_app(service=MagicMock(), web_quote_service=self.quotes))
        self.body = {'cart_token': TOKEN, 'payment_term': 'CASH / TRANSFER', 'remark': 'กรุณาตอบกลับใบยืนยันการสั่งซื้อ', 'validity_days': 30}

    def post(self, query, body=None):
        return self.client.post(f'/api/proxy/cart-quote?{query}', json=body or self.body,
                                headers={'Origin': 'https://www.sevenfive.co.th'})

    def test_unsigned_request_is_forbidden(self):
        response = self.post(urlencode({'shop': SHOP, 'logged_in_customer_id': '42', 'signature': 'bad', 'timestamp': str(int(time.time()))}))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.store.records, [])

    def test_guest_must_log_in(self):
        response = self.post(signed_query(logged_in_customer_id=''))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'code': 'login_required'})

    def test_signed_in_customer_gets_numbered_pdf(self):
        response = self.post(signed_query(logged_in_customer_id='42'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['content-type'], 'application/pdf')
        self.assertEqual(response.headers['x-quote-number'], 'WQ1026-00001')
        with fitz.open(stream=response.content, filetype='pdf') as document:
            self.assertGreater(len(document), 1)
            first, last = page_text(document, 0), page_text(document, len(document) - 1)
            self.assertIn('WQ1026-00001', first)
            self.assertIn('ซีเลค', first)
            self.assertIn('SKU: 20CWCH-0', first)
            self.assertIn('CASH / TRANSFER', first)
            self.assertIn('26/10/2569', first)
            self.assertNotIn('1,960.00', first)
            self.assertIn('1,960.00', last)  # 7 lines x 2 x 140.00 excluding VAT
            self.assertIn('2,097.20', last)
            self.assertIn(f'หน้า {len(document)} / {len(document)}', last)
            self.assertTrue(document[0].get_images())
        self.assertEqual(self.store.records[0]['shopify_customer_id'], '42')
        self.assertEqual(self.store.records[0]['grand_total'], '2097.20')

    def test_numbers_increase_and_rate_limit_applies(self):
        query = signed_query(logged_in_customer_id='42')
        self.assertEqual(self.post(query).headers['x-quote-number'], 'WQ1026-00001')
        self.assertEqual(self.post(query).headers['x-quote-number'], 'WQ1026-00002')
        response = self.post(query)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {'code': 'rate_limited'})

    def test_empty_cart_and_bad_token(self):
        self.quotes.cart_source = FakeCartSource(None)
        self.assertEqual(self.post(signed_query(logged_in_customer_id='42')).json(), {'code': 'cart_unavailable'})
        bad = self.post(signed_query(logged_in_customer_id='42'), {**self.body, 'cart_token': '../../x'})
        self.assertEqual(bad.status_code, 422)


if __name__ == '__main__':
    unittest.main()
