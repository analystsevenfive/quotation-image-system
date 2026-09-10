"""Import the company workbook to PostgreSQL, or a local development snapshot."""
import argparse
import json
import os
from pathlib import Path
from app.services.catalog import read_excel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('excel')
    parser.add_argument('--json', help='Write a development snapshot instead of PostgreSQL')
    args = parser.parse_args()
    products = read_excel(args.excel)
    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([p.model_dump(mode='json') for p in products], ensure_ascii=False), encoding='utf-8')
    else:
        import psycopg
        url = os.environ.get('DATABASE_URL')
        if not url:
            parser.error('Set DATABASE_URL or pass --json for local development')
        keys = ['good_id', 'sku', 'winspeed', 'model', 'product_url', 'image_url', 'image_status']
        if any(not p.good_id for p in products) or len({p.good_id for p in products}) != len(products):
            parser.error('PostgreSQL import requires unique, nonempty good_id values')
        with psycopg.connect(url) as conn:
            with conn.cursor() as cursor:
                cursor.executemany('''INSERT INTO products (good_id, sku, winspeed, model, product_url, image_url, image_status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (good_id) DO UPDATE SET
                    sku=EXCLUDED.sku, winspeed=EXCLUDED.winspeed, model=EXCLUDED.model,
                    product_url=EXCLUDED.product_url, image_url=EXCLUDED.image_url,
                    image_status=EXCLUDED.image_status, updated_at=now()''',
                    [tuple(p.model_dump(mode='json')[k] for k in keys) for p in products])
    print(f'Imported {len(products)} products')


if __name__ == '__main__':
    main()
