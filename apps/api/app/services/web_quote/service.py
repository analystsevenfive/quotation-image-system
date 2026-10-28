"""Turn a signed-in customer's storefront cart into a numbered quotation PDF."""

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.services.images.downloader import ImageDownloader
from app.services.matching.normalizer import normalize_image_url
from app.services.web_quote.models import Cart, Quote, QuoteLine, QuoteTerms
from app.services.web_quote.renderer import render_quote
from app.services.web_quote.store import MemoryQuoteStore, PostgresQuoteStore, quote_number
from app.services.web_quote.totals import exclude_vat, quote_totals

BANGKOK = timezone(timedelta(hours=7))
QUOTES_PER_HOUR = int(os.environ.get('WEB_QUOTES_PER_HOUR', 20))
MAX_TERM_LENGTH = 80
MAX_REMARK_LENGTH = 300
IMAGE_WIDTH = 400


class QuoteRateLimited(Exception):
    """Raised when a customer requests more quotations than the hourly limit."""


class HourlyRateLimiter:
    """In-memory per-customer limit; resets when the API restarts."""

    def __init__(self, per_hour: int):
        self.per_hour = per_hour
        self.requests: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            recent = self.requests[key]
            while recent and now - recent[0] > 3600:
                recent.popleft()
            if len(recent) >= self.per_hour:
                raise QuoteRateLimited
            recent.append(now)


def clean_terms(payment_term: str, remark: str, validity_days: int) -> QuoteTerms:
    return QuoteTerms(
        payment_term=' '.join(payment_term.split())[:MAX_TERM_LENGTH],
        remark=' '.join(remark.split())[:MAX_REMARK_LENGTH],
        validity_days=max(1, min(int(validity_days), 365)),
    )


def shopify_image_url(url: str | None) -> str | None:
    # Only fetch Shopify CDN images; the downloader also accepts local paths.
    if not url or urlparse(url).scheme != 'https' or urlparse(url).hostname != 'cdn.shopify.com':
        return None
    return normalize_image_url(url, IMAGE_WIDTH)


class WebQuoteService:
    def __init__(self, cart_source, customer_source, store, downloader=None, clock=None, quotes_per_hour=QUOTES_PER_HOUR, spec_source=None):
        self.cart_source = cart_source
        self.spec_source = spec_source
        self.customer_source = customer_source
        self.store = store
        self.downloader = downloader or ImageDownloader()
        self.clock = clock or (lambda: datetime.now(BANGKOK))
        self.limiter = HourlyRateLimiter(quotes_per_hour)

    @classmethod
    def from_env(cls):
        from app.services.shopify_sync import DEFAULT_SHOP
        from app.services.web_quote.shopify_sources import AdminCustomerSource, AdminProductSpecSource, StorefrontCartSource
        url = os.environ.get('DATABASE_URL')
        store = PostgresQuoteStore(url) if url else MemoryQuoteStore()
        return cls(
            StorefrontCartSource(os.environ.get('SHOPIFY_SHOP', DEFAULT_SHOP)),
            AdminCustomerSource(),
            store,
            spec_source=AdminProductSpecSource(),
        )

    def check_rate(self, customer_id: str) -> None:
        self.limiter.check(customer_id)

    def quote_lines(self, cart: Cart) -> list[QuoteLine]:
        urls = {index: shopify_image_url(line.image_url) for index, line in enumerate(cart.lines)}
        images = self.downloader.get_images_batch([url for url in urls.values() if url])
        specs = self.spec_source.fetch([line.product_id for line in cart.lines]) if self.spec_source else {}
        lines = []
        for index, line in enumerate(cart.lines):
            unit_price = exclude_vat(line.unit_price)
            details = [detail for detail in [line.variant_title, f'SKU: {line.sku}' if line.sku else ''] if detail]
            details += specs.get(line.product_id, [])
            lines.append(QuoteLine(
                number=index + 1,
                title=line.title,
                details=details,
                quantity=line.quantity,
                unit_price=unit_price,
                net_price=unit_price * line.quantity,
                image=images.get(urls[index]) if urls[index] else None,
            ))
        return lines

    def create(self, customer_id: str, cart_token: str, terms: QuoteTerms) -> tuple[Quote, bytes]:
        self.check_rate(customer_id)
        cart = self.cart_source.fetch(cart_token)
        customer = self.customer_source.fetch(customer_id)
        issued_at = self.clock()
        number = quote_number(issued_at, self.store.next_sequence(f'{issued_at:%Y%m}'))
        quote = Quote(
            number=number,
            issued_at=issued_at,
            customer=customer,
            terms=terms,
            lines=self.quote_lines(cart),
            totals=quote_totals(cart),
            currency=cart.currency,
        )
        pdf = render_quote(quote)
        self.store.save(quote)
        return quote, pdf
