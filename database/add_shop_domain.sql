-- MIGRATION: Add shop_domain to multi-tenant support
-- Run this on existing database to add shop isolation

-- 1. Add shop_domain column to product_embeddings
ALTER TABLE product_embeddings 
ADD COLUMN IF NOT EXISTS shop_domain VARCHAR(255);

-- 2. Add shop_domain column to search_analytics
ALTER TABLE search_analytics 
ADD COLUMN IF NOT EXISTS shop_domain VARCHAR(255);

-- 3. Create indexes for shop_domain filtering
CREATE INDEX IF NOT EXISTS product_embeddings_shop_idx 
ON product_embeddings (shop_domain);

CREATE INDEX IF NOT EXISTS search_analytics_shop_idx 
ON search_analytics (shop_domain);

-- 4. Make product_id + shop_domain unique (drop old unique constraint)
ALTER TABLE product_embeddings 
DROP CONSTRAINT IF EXISTS product_embeddings_product_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS product_embeddings_product_shop_idx 
ON product_embeddings (product_id, shop_domain);

-- 5. Update init.sql for new installs (reference only, doesn't execute)
COMMENT ON COLUMN product_embeddings.shop_domain IS 'Shopify store domain for multi-tenant isolation';
COMMENT ON COLUMN search_analytics.shop_domain IS 'Shopify store domain for analytics isolation';

-- 6. Set default shop for existing data (if any)
-- UPDATE product_embeddings SET shop_domain = 'legacy-shop.myshopify.com' WHERE shop_domain IS NULL;
-- UPDATE search_analytics SET shop_domain = 'legacy-shop.myshopify.com' WHERE shop_domain IS NULL;
