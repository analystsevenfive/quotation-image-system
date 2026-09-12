"""Catalog adapters. Excel is imported once; requests never read spreadsheets."""
import json
import re
from pathlib import Path
from app.models.product import Product
from app.services.matching.matcher import ProductMatcher
from app.services.matching.normalizer import extract_model_from_sku


def normalize_image_url(url: str | None, width: int = 200) -> str | None:
    """Ensure Shopify CDN image URLs include width optimization parameter."""
    if not url or 'cdn.shopify.com' not in url:
        return url
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs['width'] = [str(width)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class Catalog:
    def __init__(self, products, mapping_store=None):
        self.products = products
        self.mapping_store = mapping_store
        self.matcher = ProductMatcher(products, mapping_store=mapping_store)
        self.by_id = {p.id: p for p in products}

    def set_mapping_store(self, mapping_store):
        self.mapping_store = mapping_store
        self.matcher.mapping_store = mapping_store

    def search(self, query):
        q = query.strip().casefold()
        return [p for p in self.products if q in ' '.join(filter(None, [p.sku, p.winspeed, p.model])).casefold()][:30]

    @classmethod
    def from_json(cls, path):
        products = [Product.model_validate(p) for p in json.loads(Path(path).read_text(encoding='utf-8'))]
        for index, product in enumerate(products, 1):
            product.id = index
            if product.image_url and 'cdn.shopify.com' in product.image_url and 'width=' not in product.image_url:
                product.image_url = normalize_image_url(product.image_url)
        return cls(products)

    @classmethod
    def from_postgres(cls, url):
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            rows = conn.execute('SELECT id, good_id, sku, winspeed, model, product_url, image_url, image_status FROM products ORDER BY id').fetchall()
        products = []
        for row in rows:
            p = Product.model_validate(row)
            if p.image_url and 'cdn.shopify.com' in p.image_url and 'width=' not in p.image_url:
                p.image_url = normalize_image_url(p.image_url)
            products.append(p)
        return cls(products)


def read_excel(path):
    import openpyxl
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        rows = iter(workbook.active.values)
        headers = [str(h or '').strip().lower().replace(' ', '_') for h in next(rows)]
        if not {'good_id', 'sku', 'winspeed'}.issubset(headers):
            raise ValueError('Excel must contain good_id, sku and winspeed columns')
        products = []
        for values in rows:
            row = dict(zip(headers, values))
            value = lambda key: str(row.get(key) or '').strip() or None
            sku = value('sku') or value('winspeed')
            if not sku:
                continue
            description = value('goodbillname') or ''
            models = re.findall(r'(?:MODEL\s*:?|#)\s*([A-Z0-9]+(?:[-_/][A-Z0-9]+)*)', description, re.I)
            model = value('model') or (models[0] if len(set(models)) == 1 else extract_model_from_sku(sku))
            image = normalize_image_url(value('link_image') or value('image_url'))
            products.append(Product(id=len(products)+1, good_id=value('good_id'), sku=sku,
                                    winspeed=value('winspeed'), model=model,
                                    product_url=value('product_url') or value('url'),
                                    image_url=image, image_status='available' if image else 'missing'))
        return products
    finally:
        workbook.close()
