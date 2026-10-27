"""VAT and amount-in-words rules for quotations built from VAT-inclusive cart prices."""

from decimal import ROUND_HALF_UP, Decimal

from app.services.web_quote.models import Cart, QuoteTotals

VAT_RATE = Decimal('0.07')
CENT = Decimal('0.01')


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def exclude_vat(value: Decimal) -> Decimal:
    return money(value / (1 + VAT_RATE))


def quote_totals(cart: Cart) -> QuoteTotals:
    """Split the cart total into WinSpeed-style rows.

    GRAND TOTAL always equals the cart total the customer saw. VAT absorbs the
    satang rounding from removing VAT per unit, so every row still adds up.
    """
    total = sum((exclude_vat(line.unit_price) * line.quantity for line in cart.lines), Decimal('0'))
    gross = sum((line.unit_price * line.quantity for line in cart.lines), Decimal('0'))
    discount = exclude_vat(gross - cart.total) if gross > cart.total else Decimal('0.00')
    subtotal = money(total - discount)
    grand_total = money(cart.total)
    return QuoteTotals(
        total=money(total),
        discount=discount,
        subtotal=subtotal,
        vat=money(grand_total - subtotal),
        grand_total=grand_total,
    )


ONES = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'TEN',
        'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN', 'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
TENS = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']
SCALES = [(1_000_000_000, 'BILLION'), (1_000_000, 'MILLION'), (1_000, 'THOUSAND'), (100, 'HUNDRED')]


def number_words(number: int) -> str:
    if number < 20:
        return ONES[number]
    if number < 100:
        return ' '.join(filter(None, [TENS[number // 10], ONES[number % 10]]))
    for size, name in SCALES:
        if number >= size:
            return ' '.join(filter(None, [number_words(number // size), name, number_words(number % size)]))
    return ''


def baht_words(amount: Decimal) -> str:
    """Write an amount the way the WinSpeed quotation does, e.g. 'TEN BAHT AND FIVE SATANG'."""
    baht, satang = divmod(int(money(amount) * 100), 100)
    words = f'{number_words(baht) or "ZERO"} BAHT'
    return f'{words} AND {number_words(satang)} SATANG' if satang else f'{words} ONLY'
