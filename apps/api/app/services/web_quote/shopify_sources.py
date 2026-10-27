"""Read the customer's cart and profile from Shopify instead of trusting browser data."""

import logging
import re
from decimal import Decimal

import httpx

from app.services.shopify_sync import ShopifyClient
from app.services.web_quote.models import Cart, CartLine, Customer

logger = logging.getLogger(__name__)

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
          product { title featuredImage { url } }
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
        self.client = client or ShopifyClient()

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
    return Customer(
        id=customer_id,
        name=data.get('displayName') or '',
        email=data.get('email') or '',
        phone=data.get('phone') or address.get('phone') or '',
        company=address.get('company') or '',
        address_lines=[line for line in [address.get('address1'), address.get('address2'), region] if line],
    )
