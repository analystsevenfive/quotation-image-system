-- Keep the most complete product per SKU; placeholders do not count as data.
-- Ties prefer an available image, then the latest update, then the lowest id.
-- Run in one transaction. Back up affected rows before applying.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.products IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE ranked_sku_products ON COMMIT DROP AS
SELECT p.*, upper(btrim(sku)) AS sku_key,
    row_number() OVER (PARTITION BY upper(btrim(sku)) ORDER BY
        (CASE WHEN p.winspeed IS NOT NULL AND upper(btrim(p.winspeed)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END + CASE WHEN p.model IS NOT NULL AND upper(btrim(p.model)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END + CASE WHEN p.title IS NOT NULL AND upper(btrim(p.title)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END + CASE WHEN p.product_url IS NOT NULL AND upper(btrim(p.product_url)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END + CASE WHEN p.image_url IS NOT NULL AND upper(btrim(p.image_url)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END + CASE WHEN p.good_bill_name IS NOT NULL AND upper(btrim(p.good_bill_name)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') THEN 1 ELSE 0 END) DESC,
        (image_status = 'available' AND image_url IS NOT NULL) DESC,
        updated_at DESC NULLS LAST, id) AS preference
FROM public.products p
WHERE upper(btrim(sku)) IN (
    SELECT upper(btrim(sku)) FROM public.products
    GROUP BY upper(btrim(sku)) HAVING count(*) > 1
);
UPDATE public.products p SET
    winspeed = COALESCE((SELECT d.winspeed FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.winspeed IS NOT NULL AND upper(btrim(d.winspeed)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.winspeed),
    model = COALESCE((SELECT d.model FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.model IS NOT NULL AND upper(btrim(d.model)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.model),
    title = COALESCE((SELECT d.title FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.title IS NOT NULL AND upper(btrim(d.title)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.title),
    product_url = COALESCE((SELECT d.product_url FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.product_url IS NOT NULL AND upper(btrim(d.product_url)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.product_url),
    image_url = COALESCE((SELECT d.image_url FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.image_url IS NOT NULL AND upper(btrim(d.image_url)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.image_url),
    good_bill_name = COALESCE((SELECT d.good_bill_name FROM ranked_sku_products d WHERE d.sku_key = r.sku_key AND d.good_bill_name IS NOT NULL AND upper(btrim(d.good_bill_name)) NOT IN ('', 'N/A', '#N/A', 'NULL', 'NONE') ORDER BY d.preference LIMIT 1), p.good_bill_name)
FROM ranked_sku_products r WHERE r.preference = 1 AND p.id = r.id;
DELETE FROM public.products p USING ranked_sku_products r
WHERE p.id = r.id AND r.preference > 1;
CREATE UNIQUE INDEX products_sku_normalized_unique ON public.products (upper(btrim(sku)));
