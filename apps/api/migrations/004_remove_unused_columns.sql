-- Migration 004: Remove unused columns from products table
-- Keep only: good_id, sku, winspeed, model, title, image_url, product_url, good_bill_name, last_sync_at

ALTER TABLE products DROP COLUMN IF EXISTS product_type;
ALTER TABLE products DROP COLUMN IF EXISTS tags;
ALTER TABLE products DROP COLUMN IF EXISTS part_type;
ALTER TABLE products DROP COLUMN IF EXISTS power_type;
ALTER TABLE products DROP COLUMN IF EXISTS spapart_or_product;
ALTER TABLE products DROP COLUMN IF EXISTS inventory_quantity;
ALTER TABLE products DROP COLUMN IF EXISTS price;
ALTER TABLE products DROP COLUMN IF EXISTS compare_at_price;
ALTER TABLE products DROP COLUMN IF EXISTS vendor;
ALTER TABLE products DROP COLUMN IF EXISTS status;
