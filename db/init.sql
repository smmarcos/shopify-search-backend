-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================
-- STORES TABLE
-- Multi-tenant: cada tienda Shopify
-- ==========================================
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    shop_domain VARCHAR(255) UNIQUE NOT NULL, -- example.myshopify.com
    access_token TEXT NOT NULL,
    scope TEXT,
    
    -- Shopify shop info
    shop_name VARCHAR(255),
    email VARCHAR(255),
    currency VARCHAR(3),
    timezone VARCHAR(50),
    
    -- Billing
    plan_name VARCHAR(50) DEFAULT 'free',
    billing_status VARCHAR(50) DEFAULT 'active',
    charge_id BIGINT,
    trial_ends_at TIMESTAMP,
    
    -- Settings
    settings JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_sync_at TIMESTAMP,
    uninstalled_at TIMESTAMP
);

CREATE INDEX idx_stores_domain ON stores(shop_domain);
CREATE INDEX idx_stores_plan ON stores(plan_name);
CREATE INDEX idx_stores_status ON stores(billing_status);

-- ==========================================
-- PRODUCTS TABLE
-- Productos de cada tienda con embeddings
-- ==========================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    shopify_product_id BIGINT NOT NULL,
    
    -- Product data
    title VARCHAR(500) NOT NULL,
    description TEXT,
    handle VARCHAR(255),
    vendor VARCHAR(255),
    product_type VARCHAR(255),
    tags TEXT[],
    
    -- Variants aggregated
    price_min DECIMAL(10, 2),
    price_max DECIMAL(10, 2),
    available BOOLEAN DEFAULT true,
    inventory_quantity INTEGER DEFAULT 0,
    
    -- Images
    image_url TEXT,
    images_urls TEXT[],
    
    -- Vector embedding (1536 dimensions for text-embedding-3-small)
    embedding vector(1536),
    
    -- SEO
    seo_title VARCHAR(255),
    seo_description TEXT,
    
    -- Metadata
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    synced_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(store_id, shopify_product_id)
);

CREATE INDEX idx_products_store ON products(store_id);
CREATE INDEX idx_products_shopify_id ON products(shopify_product_id);
CREATE INDEX idx_products_available ON products(available);
CREATE INDEX idx_products_handle ON products(handle);

-- Vector similarity search index (HNSW algorithm for fast approximate search)
CREATE INDEX idx_products_embedding ON products 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ==========================================
-- SEARCHES TABLE
-- Analytics: cada búsqueda realizada
-- ==========================================
CREATE TABLE IF NOT EXISTS searches (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    
    -- Query info
    query TEXT NOT NULL,
    query_embedding vector(1536),
    
    -- Filters applied
    filters JSONB,
    
    -- Results
    results_count INTEGER,
    top_result_id INTEGER REFERENCES products(id),
    
    -- User interaction
    clicked_product_id INTEGER REFERENCES products(id),
    clicked_position INTEGER,
    time_to_click_ms INTEGER,
    
    -- Metadata
    user_ip VARCHAR(45),
    user_agent TEXT,
    session_id VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_searches_store ON searches(store_id);
CREATE INDEX idx_searches_created ON searches(created_at);
CREATE INDEX idx_searches_query ON searches USING gin(to_tsvector('english', query));

-- ==========================================
-- ANALYTICS TABLE
-- Métricas agregadas por día
-- ==========================================
CREATE TABLE IF NOT EXISTS analytics_daily (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Search metrics
    total_searches INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    avg_results_per_search DECIMAL(10, 2),
    zero_results_rate DECIMAL(5, 2),
    
    -- Engagement metrics
    click_through_rate DECIMAL(5, 2),
    avg_time_to_click_ms INTEGER,
    avg_clicked_position DECIMAL(5, 2),
    
    -- Popular queries
    top_queries JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(store_id, date)
);

CREATE INDEX idx_analytics_store_date ON analytics_daily(store_id, date);

-- ==========================================
-- WEBHOOKS LOG
-- Registro de webhooks recibidos
-- ==========================================
CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    
    topic VARCHAR(100) NOT NULL,
    shopify_webhook_id VARCHAR(255),
    
    payload JSONB,
    processed BOOLEAN DEFAULT false,
    error TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

CREATE INDEX idx_webhooks_store ON webhook_logs(store_id);
CREATE INDEX idx_webhooks_processed ON webhook_logs(processed);
CREATE INDEX idx_webhooks_created ON webhook_logs(created_at);

-- ==========================================
-- JOBS QUEUE
-- Trabajos asíncronos (embeddings, sync, etc)
-- ==========================================
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    
    payload JSONB,
    result JSONB,
    error TEXT,
    
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_jobs_store ON jobs(store_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_type ON jobs(job_type);

-- ==========================================
-- FUNCTIONS
-- ==========================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_stores_updated_at BEFORE UPDATE ON stores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- VECTOR SEARCH FUNCTIONS
-- ==========================================

-- Function to find similar products
CREATE OR REPLACE FUNCTION search_products(
    p_store_id INTEGER,
    p_embedding vector(1536),
    p_limit INTEGER DEFAULT 20,
    p_similarity_threshold DECIMAL DEFAULT 0.7
)
RETURNS TABLE (
    product_id INTEGER,
    title VARCHAR,
    description TEXT,
    price_min DECIMAL,
    image_url TEXT,
    similarity DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.title,
        p.description,
        p.price_min,
        p.image_url,
        (1 - (p.embedding <=> p_embedding))::DECIMAL as similarity
    FROM products p
    WHERE 
        p.store_id = p_store_id
        AND p.available = true
        AND (1 - (p.embedding <=> p_embedding)) >= p_similarity_threshold
    ORDER BY p.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- SEED DATA (development only)
-- ==========================================

-- Insert demo store (for testing)
-- UNCOMMENT FOR LOCAL DEVELOPMENT
/*
INSERT INTO stores (shop_domain, access_token, shop_name, email, plan_name)
VALUES ('demo-store.myshopify.com', 'demo_token', 'Demo Store', 'demo@example.com', 'free')
ON CONFLICT (shop_domain) DO NOTHING;
*/
