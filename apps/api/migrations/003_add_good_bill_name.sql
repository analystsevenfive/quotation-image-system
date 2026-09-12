-- Migration 003: Add GoodBillName column to products table
-- Preserves legacy quotation billing name during automated Shopify synchronizations

ALTER TABLE products ADD COLUMN IF NOT EXISTS good_bill_name text;
CREATE INDEX IF NOT EXISTS products_good_bill_name_idx ON products(good_bill_name);
