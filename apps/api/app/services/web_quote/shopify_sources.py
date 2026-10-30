"""Read the customer's cart and profile from Shopify instead of trusting browser data."""

import logging
import re
from decimal import Decimal
from html import unescape

import httpx

from app.services.shopify_sync import ShopifyClient
from app.services.web_quote.models import Cart, CartLine, Customer

logger = logging.getLogger(__name__)

_shared_client: ShopifyClient | None = None


def shared_client() -> ShopifyClient:
    # One client per process, so the customer and specification reads reuse one access token.
    global _shared_client
    if _shared_client is None:
        _shared_client = ShopifyClient()
    return _shared_client

STOREFRONT_API_VERSION = '2025-01'
MAX_CART_LINES = 100
CART_TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9_-]{8,128}(\?key=[A-Za-z0-9]{8,128})?$')

CART_QUERY = """
query CartQuote($id: ID!) {
  cart(id: $id) {
    cost { totalAmount { amount currencyCode } }
    lines(first: %d) {
      pageInfo { hasNextPage }
      edges { node {
        quantity
        cost { amountPerQuantity { amount } }
        merchandise { ... on ProductVariant {
          sku
          title
          image { url }
          product { id title featuredImage { url } }
        } }
      } }
    }
  }
}
""" % MAX_CART_LINES

CUSTOMER_QUERY = """
query QuoteCustomer($id: ID!) {
  customer(id: $id) {
    displayName
    email
    phone
    defaultAddress { company address1 address2 city province zip phone }
  }
}
"""


SPEC_QUERY = """
query QuoteSpecs($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Product {
      id
      descriptionHtml
      metafields(first: 100, namespace: "specs") { nodes { key value type definition { name } } }
    }
  }
}
"""
MAX_SPEC_LINES = 8
# Shown in this order; dimensions and electrical values are combined into one line each.
DIMENSION_KEYS = (('width_mm',), ('depth_mm', 'length_mm'), ('height_mm',))
ELECTRICAL_KEYS = (('voltage', 'V'), ('hz', 'Hz'), ('phrase', ''))
SPEC_KEYS = (
    'weight_kg', 'net_weight_kg', 'wattage', 'max_electric_power_w', 'refrigerant',
    'chiller_capacity_liter', 'chiller_temperature', 'chiller_door_amount', 'freezer_capacity_volume',
    'freezer_temperature', 'freezer_door_amount', 'material', 'rack_size_mm', 'tank_volume_l',
    'max_theoretical_productivity_rph', 'cutting_size', 'type_of_cut', 'energy_type', 'cooking_surface_mm',
    'made_in', 'certificates', 'service_warranty', 'spareparts_warranty', 'compressor_warranty',
)
LIST_ITEM_PATTERN = re.compile(r'<li[^>]*>(.*?)</li>', re.I | re.S)
TAG_PATTERN = re.compile(r'<[^>]+>')


class CartUnavailable(Exception):
    """Raised when the cart cannot be read or cannot be quoted."""


def valid_cart_token(token: str) -> bool:
    return bool(CART_TOKEN_PATTERN.match(token or ''))


class StorefrontCartSource:
    """Reads carts through Shopify's tokenless Storefront API."""

    def __init__(self, shop: str, timeout: float = 15.0):
        self.shop = shop
        self.timeout = timeout

    def fetch(self, cart_token: str) -> Cart:
        response = httpx.post(
            f'https://{self.shop}/api/{STOREFRONT_API_VERSION}/graphql.json',
            json={'query': CART_QUERY, 'variables': {'id': f'gid://shopify/Cart/{cart_token}'}},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise CartUnavailable(f'Storefront API HTTP {response.status_code}')
        body = response.json()
        if body.get('errors'):
            raise CartUnavailable(f'Storefront API error: {body["errors"]}')
        return parse_cart(body.get('data', {}).get('cart'))


def parse_cart(data: dict | None) -> Cart:
    if not data:
        raise CartUnavailable('Cart not found')
    if data['lines']['pageInfo']['hasNextPage']:
        raise CartUnavailable(f'Cart has more than {MAX_CART_LINES} lines')
    lines = []
    for edge in data['lines']['edges']:
        node = edge['node']
        variant = node.get('merchandise') or {}
        product = variant.get('product') or {}
        if not product:
            continue
        image = variant.get('image') or product.get('featuredImage') or {}
        lines.append(CartLine(
            title=product.get('title') or '',
            product_id=product.get('id') or '',
            variant_title='' if variant.get('title') == 'Default Title' else (variant.get('title') or ''),
            sku=variant.get('sku') or '',
            quantity=int(node['quantity']),
            unit_price=Decimal(node['cost']['amountPerQuantity']['amount']),
            image_url=image.get('url'),
        ))
    if not lines:
        raise CartUnavailable('Cart is empty')
    total = data['cost']['totalAmount']
    return Cart(currency=total['currencyCode'], lines=lines, total=Decimal(total['amount']))


class AdminCustomerSource:
    """Reads the signed-in customer's profile with the Admin API (needs read_customers)."""

    def __init__(self, client: ShopifyClient | None = None):
        self.client = client or shared_client()

    def fetch(self, customer_id: str) -> Customer:
        try:
            data = self.client.graphql(CUSTOMER_QUERY, {'id': f'gid://shopify/Customer/{customer_id}'})
        except (RuntimeError, httpx.HTTPError):
            # A missing scope must not block the quote; sales still gets the customer ID.
            logger.exception('Unable to read Shopify customer %s', customer_id)
            return Customer(id=customer_id)
        return parse_customer(customer_id, data.get('data', {}).get('customer'))


def parse_customer(customer_id: str, data: dict | None) -> Customer:
    if not data:
        return Customer(id=customer_id)
    address = data.get('defaultAddress') or {}
    region = ' '.join(filter(None, [address.get('city'), address.get('province'), address.get('zip')]))
    email = data.get('email') or ''
    # Shopify falls back to the email address when the customer has no name.
    name = data.get('displayName') or ''
    return Customer(
        id=customer_id,
        name='' if name == email else name,
        email=email,
        phone=data.get('phone') or address.get('phone') or '',
        company=address.get('company') or '',
        address_lines=[line for line in [address.get('address1'), address.get('address2'), region] if line],
    )


class AdminProductSpecSource:
    """Reads product specifications from `specs` metafields, or the description's spec list."""

    def __init__(self, client: ShopifyClient | None = None):
        self.client = client or shared_client()

    def fetch(self, product_ids: list[str]) -> dict[str, list[str]]:
        ids = sorted({product_id for product_id in product_ids if product_id})
        if not ids:
            return {}
        try:
            data = self.client.graphql(SPEC_QUERY, {'ids': ids})
        except (RuntimeError, httpx.HTTPError):
            # Specifications are optional; the quotation still lists the products.
            logger.exception('Unable to read product specifications')
            return {}
        specs = {}
        for node in data.get('data', {}).get('nodes') or []:
            if node and node.get('id'):
                metafields = {
                    field['key']: field for field in node['metafields']['nodes']
                    if field.get('value') and field.get('type') != 'boolean'
                }
                specs[node['id']] = spec_lines(metafields, node.get('descriptionHtml') or '')
        return specs


def spec_value(field: dict) -> str:
    return ' '.join(str(field['value']).split())


def spec_lines(metafields: dict[str, dict], description_html: str = '') -> list[str]:
    lines = []
    dimensions = [next((spec_value(metafields[key]) for key in keys if key in metafields), '') for keys in DIMENSION_KEYS]
    if all(dimensions):
        lines.append(f'Dimensions (W x D x H): {" x ".join(dimensions)} mm')
    electrical = [f'{spec_value(metafields[key])} {unit}'.strip() for key, unit in ELECTRICAL_KEYS if key in metafields]
    if electrical:
        lines.append(f'Electrical: {" / ".join(electrical)}')
    for key in SPEC_KEYS:
        if key in metafields:
            field = metafields[key]
            label = (field.get('definition') or {}).get('name') or key.replace('_', ' ').capitalize()
            lines.append(f'{label}: {spec_value(field)}')
    if not lines:
        lines = description_specs(description_html)
    return lines[:MAX_SPEC_LINES]


def description_specs(description_html: str) -> list[str]:
    start = description_html.lower().find('technical specification')
    if start < 0:
        return []
    section = description_html[start:]
    end = section.lower().find('</ul>')
    items = LIST_ITEM_PATTERN.findall(section[:end] if end >= 0 else section)
    lines = [' '.join(unescape(TAG_PATTERN.sub(' ', item)).split()) for item in items]
    # The SKU is already printed on its own line.
    return [line for line in lines if line and not line.lower().startswith('product code')]
