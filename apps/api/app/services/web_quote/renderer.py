"""Draw web quotations on the Seven Five WinSpeed quotation layout.

Geometry is measured from a WinSpeed quotation (Letter, points) so web and
sales-issued quotations look the same. Text goes through insert_htmlbox because
it shapes Thai marks correctly; long single-line fields shrink to fit.
"""

import html
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import fitz

from app.services.web_quote.models import Quote, QuoteLine
from app.services.web_quote.totals import baht_words

ASSETS = Path(__file__).resolve().parents[2] / 'assets'
ARCHIVE = fitz.Archive(str(ASSETS / 'fonts'))
LOGO = (ASSETS / 'letterhead-logo.jpeg').read_bytes()
CSS = """
@font-face { font-family: sarabun; src: url(Sarabun-Regular.ttf); }
@font-face { font-family: sarabun; src: url(Sarabun-Bold.ttf); font-weight: bold; }
* { font-family: sarabun; margin: 0; padding: 0; line-height: 1.6; color: #000; }
p { margin: 0; }
"""
# insert_htmlbox clips to its rect; below 1.6 line-height, stacked Thai tone marks are cut off.

COMPANY_NAME = 'SEVEN FIVE DISTRIBUTOR CO., LTD.'
COMPANY_LINES = [
    '75 MOO 7 NAKORN-IN RD, BANG KHU WIANG, BANG KRUAI, NONTHABURI 11130',
    'Tel: 02 423 7575' + ' ' * 8 + 'Fax: 02 423 7500-1',
    'E-Mail: sales@sevenfive.co.th' + ' ' * 4 + 'Web Site: http://www.sevenfive.co.th',
]
SALES_CONTACT = ['ONLINE SALES', '02 423 7575', 'sales@sevenfive.co.th']

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
LEFT, RIGHT = 22.44, 576.48
DESC_X, QTY_X, PRICE_X, NET_X = 58.44, 405.0, 440.16, 507.72
HEADER_ROW = fitz.Rect(LEFT, 257.16, RIGHT, 281.76)
BODY_TOP, BODY_BOTTOM = 281.76, 594.84
FOOTER_BOX = fitz.Rect(LEFT, BODY_BOTTOM, RIGHT, 662.16)
WORDS_BOX = fitz.Rect(LEFT, 661.56, RIGHT, 683.16)
SIGNATURE_BOXES = [fitz.Rect(LEFT, 684.84, 203.76, 770.16), fitz.Rect(204.0, 684.84, 385.32, 770.16), fitz.Rect(395.16, 684.84, RIGHT, 770.16)]
BLUE = (0, 0, 1)
STROKE = 0.72

ROW_PADDING = 4
IMAGE_BOX = (300.0, 400.0, 92.0)  # x0, x1, max height inside the description column
TEXT_X0, TEXT_X1, TEXT_X1_WITH_IMAGE = 61.0, 400.0, 294.0

THAI_LEADING_VOWELS = 'เแโใไ'
THAI_MARKS = 'ัิีึืฺุู็่้๊๋์ํ๎'


def breakable(text: str) -> str:
    """Add zero-width break opportunities between Thai syllable clusters.

    MuPDF only wraps at spaces, and Thai has none between words. Without a
    dictionary, break before a leading vowel, or before a consonant that follows
    a consonant or trailing vowel (a mark usually means the syllable continues).
    """
    out = []
    for index, char in enumerate(text):
        previous = text[index - 1] if index else ''
        if '฀' <= previous <= '๿' and previous not in THAI_LEADING_VOWELS:
            if char in THAI_LEADING_VOWELS or ('ก' <= char <= 'ฮ' and previous not in THAI_MARKS):
                out.append('​')
        out.append(char)
    return ''.join(out)


def paragraph(text: str, size: float, bold: bool = False, align: str = 'left', indent: float = 0, wrap: bool = True) -> str:
    style = f'font-size:{size}pt;text-align:{align};margin-left:{indent}pt'
    if bold:
        style += ';font-weight:bold'
    # Break opportunities show up as spaces in copied text, so single-line fields skip them.
    return f'<p style="{style}">{html.escape(breakable(text) if wrap else text)}</p>'


def put(page, rect, text, size=9.0, bold=False, align='left', wrap=False):
    if text:
        page.insert_htmlbox(fitz.Rect(rect), paragraph(text, size, bold, align, wrap=wrap), css=CSS, archive=ARCHIVE)


def rounded(page, rect, radius=6.0):
    page.draw_rect(rect, color=(0, 0, 0), fill=(1, 1, 1), width=STROKE, radius=(radius / rect.width, radius / rect.height))


def amount(value: Decimal) -> str:
    return f'{value:,.2f}'


def description_html(line: QuoteLine) -> str:
    return paragraph(line.title, 10) + ''.join(paragraph(detail, 9, indent=12) for detail in line.details)


def text_height(markup: str, width: float) -> float:
    story = fitz.Story(markup, user_css=CSS, archive=ARCHIVE)
    _, filled = story.place(fitz.Rect(0, 0, width, 10_000))
    return filled[3]


def row_height(line: QuoteLine) -> float:
    width = (TEXT_X1_WITH_IMAGE if line.image else TEXT_X1) - TEXT_X0
    height = text_height(description_html(line), width)
    if line.image:
        height = max(height, IMAGE_BOX[2])
    return height + ROW_PADDING * 2


def paginate(lines: list[QuoteLine]) -> list[list[tuple[QuoteLine, float]]]:
    pages, current, used = [], [], 0.0
    available = BODY_BOTTOM - BODY_TOP
    for line in lines:
        height = min(row_height(line), available)
        if current and used + height > available:
            pages.append(current)
            current, used = [], 0.0
        current.append((line, height))
        used += height
    pages.append(current)
    return pages


def draw_letterhead(page, quote: Quote, index: int, count: int):
    put(page, (480, 22, 572, 38), f'หน้า {index} / {count}', 9, align='right')
    page.insert_image(fitz.Rect(26.16, 40.44, 83.88, 104.16), stream=LOGO)
    put(page, (97.4, 26, 560, 60), COMPANY_NAME, 20, bold=True)
    for offset, text in zip((58.5, 72.5, 86.5), COMPANY_LINES):
        put(page, (97.4, offset, 560, offset + 15), text, 9)
    put(page, (420, 94, 572, 128), 'QUOTATION', 20, bold=True, align='center')

    customer = quote.customer
    left_box = fitz.Rect(23.16, 128.16, 350.04, 251.76)
    rounded(page, left_box)
    put(page, (25.4, 133.5, 76, 150), 'COMPANY', 9, bold=True)
    put(page, (78, 133.5, 345, 150), customer.company or customer.name, 9.5)
    if customer.company and customer.name:
        put(page, (78, 153.5, 345, 170), customer.name, 9.5)
    put(page, (25.4, 174.4, 76, 191), 'ADDRESS', 9, bold=True)
    address = customer.address_lines
    put(page, (78, 174.4, 345, 191), address[0] if address else '', 9.5)
    put(page, (78, 194, 345, 211), ' '.join(address[1:]), 9.5)
    put(page, (78, 213.4, 115, 230), 'PHONE :', 9, bold=True)
    put(page, (116, 213.4, 345, 230), customer.phone, 9.5)
    put(page, (25.4, 232.8, 80, 249), 'ATTENTION', 9, bold=True)
    attention = ' / '.join(filter(None, [customer.name, customer.email, customer.phone]))
    put(page, (82, 232.8, 345, 249), attention, 9.5)

    issued = quote.issued_at
    rounded(page, fitz.Rect(353.16, 128.16, RIGHT, 176.76))
    put(page, (360, 133.1, 418, 150), 'NO.', 9, bold=True, align='center')
    put(page, (422, 133.1, 572, 150), quote.number, 9.5)
    put(page, (360, 153.4, 418, 170), 'DATE', 9, bold=True, align='center')
    put(page, (422, 153.4, 572, 170), f'{issued:%d/%m/%Y}', 9.5)

    rounded(page, fitz.Rect(353.16, 180.0, RIGHT, 251.88))
    put(page, (356.2, 183.7, 455, 200), 'PRICE VALIDITY (DAY)', 9, bold=True)
    put(page, (457.4, 183.7, 572, 200), str(quote.terms.validity_days), 9.5)
    put(page, (356.2, 205.8, 455, 222), 'VALID UNTIL', 9, bold=True)
    put(page, (457.4, 205.8, 572, 222), f'{issued + timedelta(days=quote.terms.validity_days):%d/%m/%Y}', 9.5)
    put(page, (356.2, 227.5, 455, 244), 'TERM OF PAYMENT', 9, bold=True)
    put(page, (457.4, 227.5, 572, 244), quote.terms.payment_term, 9.5)


def draw_table(page, rows: list[tuple[QuoteLine, float]]):
    rounded(page, HEADER_ROW)
    for (x0, x1), label in zip(
        [(LEFT, DESC_X), (DESC_X, QTY_X), (QTY_X, PRICE_X), (PRICE_X, NET_X), (NET_X, RIGHT)],
        ['ITEM', 'DESCRIPTION', 'QTY', 'PRICE', 'NET PRICE'],
    ):
        put(page, (x0, 262, x1, 279), label, 9, bold=True, align='center')
    for x in (LEFT, DESC_X, QTY_X, PRICE_X, NET_X, RIGHT):
        page.draw_line((x, HEADER_ROW.y1 - 2.5), (x, BODY_BOTTOM), color=BLUE, width=STROKE)
    page.draw_line((LEFT, 279.0), (RIGHT, 279.0), color=BLUE, width=STROKE)

    y = BODY_TOP
    for line, height in rows:
        top = y + ROW_PADDING
        put(page, (LEFT, top, DESC_X, top + 16), str(line.number), 10, align='center')
        text_right = TEXT_X1_WITH_IMAGE if line.image else TEXT_X1
        page.insert_htmlbox(fitz.Rect(TEXT_X0, top, text_right, y + height), description_html(line), css=CSS, archive=ARCHIVE)
        if line.image:
            x0, x1, max_height = IMAGE_BOX
            page.insert_image(fitz.Rect(x0, top, x1, top + max_height), stream=line.image, keep_proportion=True)
        put(page, (QTY_X, top, PRICE_X, top + 16), str(line.quantity), 9.5, align='center')
        put(page, (PRICE_X, top, NET_X - 2, top + 16), amount(line.unit_price), 9.5, align='right')
        put(page, (NET_X, top, RIGHT - 2, top + 16), amount(line.net_price), 9.5, align='right')
        y += height


def draw_footer(page, quote: Quote, last: bool):
    page.draw_rect(FOOTER_BOX, color=(0, 0, 0), fill=(1, 1, 1), width=STROKE)
    put(page, (26.2, 596, 72, 612), 'REMARK', 9, bold=True)
    page.draw_line((26.2, 609.5), (61.5, 609.5), color=(0, 0, 0), width=0.5)
    put(page, (75, 596, 436, 660), quote.terms.remark, 9, wrap=True)
    rounded(page, WORDS_BOX)
    for x in (PRICE_X, NET_X):
        page.draw_line((x, BODY_BOTTOM), (x, WORDS_BOX.y1 - 0.6), color=BLUE, width=STROKE)

    totals = quote.totals
    rows = [('TOTAL', totals.total), ('DISCOUNT', totals.discount if totals.discount else None),
            ('SUB TOTAL', totals.subtotal), ('VAT', totals.vat)]
    for (label, value), y in zip(rows, (596.0, 611.5, 627.0, 642.5)):
        put(page, (443, y, NET_X - 2, y + 16), label, 9, bold=True)
        if last and value is not None:
            put(page, (NET_X, y, RIGHT - 2, y + 16), amount(value), 9.5, align='right')
    if last:
        put(page, (480, 642.5, NET_X - 3, 658.5), '7%', 9.5, align='right')
        put(page, (35, 664.5, 432, 680), baht_words(totals.grand_total), 8.5, align='center')
    put(page, (443, 664, NET_X - 2, 680), 'GRAND TOTAL', 9, bold=True)
    if last:
        put(page, (NET_X, 664, RIGHT - 2, 680), amount(totals.grand_total), 9.5, align='right')

    customer_box, sales_box, date_box = SIGNATURE_BOXES
    for box in SIGNATURE_BOXES:
        rounded(page, box)
        page.draw_line((box.x0 + 21, 735), (box.x1 - 21, 735), color=BLUE, width=STROKE)
    put(page, (customer_box.x0, 737, customer_box.x1, 752), 'CUSTOMER SIGNATURE', 8.5, bold=True, align='center')
    put(page, (customer_box.x0, 752.5, customer_box.x1, 768), 'DATE ____/____/________', 8.5, bold=True, align='center')
    for text, y in zip(SALES_CONTACT, (690, 703.5, 717)):
        put(page, (sales_box.x0, y, sales_box.x1, y + 15), text, 9, align='center')
    put(page, (sales_box.x0, 752.5, sales_box.x1, 768), 'SALES REPRESENTATIVE', 8.5, bold=True, align='center')
    buddhist_year = quote.issued_at.year + 543
    put(page, (date_box.x0, 752.5, date_box.x1, 768), f'DATE    {quote.issued_at:%d/%m/}{buddhist_year}', 8.5, bold=True, align='center')


def render_quote(quote: Quote) -> bytes:
    pages = paginate(quote.lines)
    document = fitz.open()
    try:
        for index, rows in enumerate(pages, 1):
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            draw_letterhead(page, quote, index, len(pages))
            draw_table(page, rows)
            draw_footer(page, quote, last=index == len(pages))
        document.set_metadata({'title': f'Quotation {quote.number}', 'author': COMPANY_NAME, 'creator': 'Seven Five web quotation'})
        # Every text box embeds its own font copy; garbage=4 merges the duplicates.
        # subset_fonts() is avoided because it drops the shaped Thai tone-mark glyphs.
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
