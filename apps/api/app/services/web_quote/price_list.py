"""Read VAT-exclusive list prices from the product-finder Supabase project.

The price list is the sales team's source of truth, so its price wins over the
Shopify price. Products it does not price keep their Shopify price.
"""

import logging
import os
from decimal import Decimal, InvalidOperation

import httpx

logger = logging.getLogger(__name__)

MAX_SKUS = 100


def in_filter(values: list[str]) -> str:
    # PostgREST list syntax; quoting keeps commas and parentheses inside a SKU literal.
    quoted = ('"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"' for value in values)
    return f'in.({",".join(quoted)})'


def parse_prices(rows: list[dict]) -> dict[str, Decimal]:
    prices = {}
    for row in rows:
        sku = row.get('good_code')
        try:
            price = Decimal(str(row.get('price')))
        except (InvalidOperation, ValueError):
            continue
        # Zero or missing prices mean "not priced", so the Shopify price still applies.
        if sku and price.is_finite() and price > 0 and sku not in prices:
            prices[sku] = price
    return prices


class SupabasePriceSource:
    """Looks up `products.price` by `good_code`, which matches the Shopify SKU."""

    def __init__(self, url: str, key: str, timeout: float = 10.0):
        self.url = url.rstrip('/')
        self.key = key
        self.timeout = timeout

    @classmethod
    def from_env(cls):
        # Product Finder's project already signs in Studio users, so its URL and publishable key are reused.
        url = os.environ.get('PRICE_LIST_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
        key = os.environ.get('PRICE_LIST_SUPABASE_KEY') or os.environ.get('SUPABASE_PUBLISHABLE_KEY')
        return cls(url, key) if url and key else None

    def fetch(self, skus: list[str]) -> dict[str, Decimal]:
        skus = sorted({sku for sku in skus if sku})[:MAX_SKUS]
        if not skus:
            return {}
        try:
            response = httpx.get(
                f'{self.url}/rest/v1/products',
                params={'select': 'good_code,price', 'good_code': in_filter(skus)},
                headers={'apikey': self.key, 'Authorization': f'Bearer {self.key}'},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return parse_prices(response.json())
        except (httpx.HTTPError, ValueError):
            # The quote still works with Shopify prices when the price list is unavailable.
            logger.exception('Unable to read the price list')
            return {}
