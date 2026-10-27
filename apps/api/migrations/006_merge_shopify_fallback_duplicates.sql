BEGIN;

CREATE TEMP TABLE shopify_duplicate_pairs ON COMMIT DROP AS
WITH sku_groups AS (
    SELECT
        sku,
        max(good_id) FILTER (WHERE good_id !~ '^V[0-9]+$') AS canonical_good_id,
        max(good_id) FILTER (WHERE good_id ~ '^V[0-9]+$') AS fallback_good_id
    FROM products
    WHERE sku IS NOT NULL AND btrim(sku) <> ''
    GROUP BY sku
    HAVING count(*) FILTER (WHERE good_id ~ '^V[0-9]+$') = 1
       AND count(*) FILTER (WHERE good_id !~ '^V[0-9]+$') = 1
)
SELECT groups.sku, groups.canonical_good_id, groups.fallback_good_id
FROM sku_groups AS groups
JOIN products AS canonical ON canonical.good_id = groups.canonical_good_id
JOIN products AS fallback ON fallback.good_id = groups.fallback_good_id
WHERE (canonical.title IS NULL OR fallback.title IS NULL OR canonical.title = fallback.title)
    AND (canonical.product_url IS NULL OR fallback.product_url IS NULL OR canonical.product_url = fallback.product_url)
    AND (canonical.model IS NULL OR fallback.model IS NULL OR canonical.model = fallback.model);

UPDATE products AS canonical
SET
    winspeed = COALESCE(canonical.winspeed, fallback.winspeed),
    model = COALESCE(canonical.model, fallback.model),
    title = COALESCE(canonical.title, fallback.title),
    product_url = COALESCE(canonical.product_url, fallback.product_url),
    image_url = COALESCE(canonical.image_url, fallback.image_url),
    image_status = CASE
        WHEN COALESCE(canonical.image_url, fallback.image_url) IS NOT NULL THEN 'available'
        WHEN canonical.image_status = 'broken' OR fallback.image_status = 'broken' THEN 'broken'
        ELSE 'missing'
    END,
    good_bill_name = COALESCE(canonical.good_bill_name, fallback.good_bill_name),
    last_sync_at = COALESCE(canonical.last_sync_at, fallback.last_sync_at),
    updated_at = now()
FROM shopify_duplicate_pairs AS pair
JOIN products AS fallback ON fallback.good_id = pair.fallback_good_id
WHERE canonical.good_id = pair.canonical_good_id;

DELETE FROM products AS fallback
USING shopify_duplicate_pairs AS pair
WHERE fallback.good_id = pair.fallback_good_id;

COMMIT;