"""Allocate web quotation numbers and keep each issued quote as a sales lead."""

import json
import threading
from datetime import datetime

from app.services.web_quote.models import Quote

NUMBER_PREFIX = 'WQ'


def quote_number(issued_at: datetime, sequence: int) -> str:
    # Mirrors WinSpeed's QT0926-00083 (MMYY-sequence) under its own prefix.
    return f'{NUMBER_PREFIX}{issued_at:%m%y}-{sequence:05d}'


def quote_record(quote: Quote) -> dict:
    return {
        'quote_number': quote.number,
        'shopify_customer_id': quote.customer.id,
        'customer_name': quote.customer.name,
        'customer_email': quote.customer.email,
        'company': quote.customer.company,
        'phone': quote.customer.phone,
        'currency': quote.currency,
        'subtotal': str(quote.totals.subtotal),
        'vat': str(quote.totals.vat),
        'grand_total': str(quote.totals.grand_total),
        'lines': [
            {'title': line.title, 'details': line.details, 'quantity': line.quantity,
             'unit_price': str(line.unit_price), 'net_price': str(line.net_price)}
            for line in quote.lines
        ],
        'payment_term': quote.terms.payment_term,
        'remark': quote.terms.remark,
        'validity_days': quote.terms.validity_days,
    }


class PostgresQuoteStore:
    def __init__(self, url: str):
        self.url = url

    def next_sequence(self, period: str) -> int:
        import psycopg
        with psycopg.connect(self.url) as conn:
            row = conn.execute(
                """INSERT INTO web_quote_counters (period, last_value) VALUES (%s, 1)
                   ON CONFLICT (period) DO UPDATE SET last_value = web_quote_counters.last_value + 1
                   RETURNING last_value""",
                (period,),
            ).fetchone()
        return row[0]

    def save(self, quote: Quote) -> None:
        import psycopg
        record = quote_record(quote)
        record['lines'] = json.dumps(record['lines'], ensure_ascii=False)
        columns = ', '.join(record)
        placeholders = ', '.join(f'%({key})s' for key in record)
        with psycopg.connect(self.url) as conn:
            conn.execute(f'INSERT INTO web_quotes ({columns}) VALUES ({placeholders})', record)


class MemoryQuoteStore:
    """Used for local development and tests when DATABASE_URL is not configured."""

    def __init__(self):
        self.lock = threading.Lock()
        self.counters: dict[str, int] = {}
        self.records: list[dict] = []

    def next_sequence(self, period: str) -> int:
        with self.lock:
            self.counters[period] = self.counters.get(period, 0) + 1
            return self.counters[period]

    def save(self, quote: Quote) -> None:
        with self.lock:
            self.records.append(quote_record(quote))
