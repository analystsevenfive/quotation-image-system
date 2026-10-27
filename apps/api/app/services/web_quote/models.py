"""Data passed between the storefront cart, totals, store, and PDF renderer."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class CartLine:
    title: str
    variant_title: str
    sku: str
    quantity: int
    unit_price: Decimal  # VAT-inclusive storefront price per unit
    image_url: str | None = None


@dataclass
class Cart:
    currency: str
    lines: list[CartLine]
    total: Decimal  # VAT-inclusive amount the customer pays, after discounts


@dataclass
class Customer:
    id: str
    name: str = ''
    email: str = ''
    phone: str = ''
    company: str = ''
    address_lines: list[str] = field(default_factory=list)


@dataclass
class QuoteTerms:
    payment_term: str
    remark: str
    validity_days: int


@dataclass
class QuoteLine:
    number: int
    title: str
    details: list[str]
    quantity: int
    unit_price: Decimal  # excluding VAT
    net_price: Decimal
    image: bytes | None = None


@dataclass
class QuoteTotals:
    total: Decimal
    discount: Decimal
    subtotal: Decimal
    vat: Decimal
    grand_total: Decimal


@dataclass
class Quote:
    number: str
    issued_at: datetime
    customer: Customer
    terms: QuoteTerms
    lines: list[QuoteLine]
    totals: QuoteTotals
    currency: str
