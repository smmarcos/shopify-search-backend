-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create products table with vector embeddings
CREATE TABLE IF NOT EXISTS product_embeddings (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price DECIMAL(10, 2),
    vendor VARCHAR(255),
    category VARCHAR(255),
    tags TEXT[],
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast vector similarity search
CREATE INDEX IF NOT EXISTS product_embeddings_vector_idx 
ON product_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for product_id lookups
CREATE INDEX IF NOT EXISTS product_embeddings_product_id_idx 
ON product_embeddings (product_id);

-- Create index for metadata queries (price filters, etc)
CREATE INDEX IF NOT EXISTS product_embeddings_metadata_idx 
ON product_embeddings USING GIN (metadata);

-- Create search analytics table
CREATE TABLE IF NOT EXISTS search_analytics (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    results_count INT,
    clicked_product_id VARCHAR(255),
    session_id VARCHAR(255),
    shop_domain VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for analytics queries
CREATE INDEX IF NOT EXISTS search_analytics_created_at_idx 
ON search_analytics (created_at DESC);

-- Create index for shop_domain queries
CREATE INDEX IF NOT EXISTS search_analytics_shop_domain_idx 
ON search_analytics (shop_domain);

-- Create settings table for app configuration
CREATE TABLE IF NOT EXISTS app_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for settings key lookups
CREATE INDEX IF NOT EXISTS app_settings_key_idx 
ON app_settings (key);

-- Insert default configuration
INSERT INTO app_settings (key, value, description) VALUES
('ai_search', '{"enabled": true, "autocorrect": true, "results_limit": "10", "similarity_threshold": 70, "exclude_out_of_stock": false, "exclude_archived": false, "language": "es"}'::jsonb, 'AI search configuration settings')
ON CONFLICT (key) DO NOTHING;

-- Insert sample data
INSERT INTO product_embeddings (product_id, title, description, price, vendor, category, tags, metadata) VALUES
('prod_001', 'Nike Air Zoom Pegasus 40', 'Comfortable running shoes with responsive cushioning perfect for daily training runs', 89.99, 'Nike', 'Running Shoes', ARRAY['running', 'sports', 'training'], '{"in_stock": true, "stock_quantity": 47, "sizes": ["7", "8", "9", "10", "11", "12"]}'::jsonb),
('prod_002', 'Adidas Ultraboost 22', 'Premium running shoes designed for long-distance comfort with boost technology', 94.99, 'Adidas', 'Running Shoes', ARRAY['running', 'premium', 'long-distance'], '{"in_stock": true, "stock_quantity": 32, "sizes": ["8", "9", "10", "11"]}'::jsonb),
('prod_003', 'New Balance Fresh Foam 1080', 'Maximum cushioning running shoes for comfortable daily runs and recovery', 79.99, 'New Balance', 'Running Shoes', ARRAY['running', 'comfort', 'cushioning'], '{"in_stock": true, "stock_quantity": 56, "sizes": ["7", "8", "9", "10", "11", "12", "13"]}'::jsonb),
('prod_004', 'Brooks Ghost 15', 'Balanced running shoes with soft cushioning for neutral runners', 129.99, 'Brooks', 'Running Shoes', ARRAY['running', 'neutral', 'cushioning'], '{"in_stock": true, "stock_quantity": 23, "sizes": ["8", "9", "10", "11", "12"]}'::jsonb),
('prod_005', 'Hoka Clifton 9', 'Lightweight cushioned shoes perfect for everyday running and walking', 144.99, 'Hoka', 'Running Shoes', ARRAY['running', 'lightweight', 'walking'], '{"in_stock": false, "stock_quantity": 0, "sizes": []}'::jsonb);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
CREATE TRIGGER update_product_embeddings_updated_at
    BEFORE UPDATE ON product_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO shopify_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO shopify_admin;
