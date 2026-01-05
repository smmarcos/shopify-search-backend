-- Tabla de planes de suscripción
CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    max_products INTEGER NOT NULL,
    max_searches_per_month INTEGER NOT NULL,
    features JSONB,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar planes definidos
INSERT INTO subscription_plans (name, price, max_products, max_searches_per_month, features) VALUES
('starter', 0.00, 50, 300, '{"ai_search": true, "semantic_search": true, "typo_correction": true, "basic_analytics": true, "email_support": true}'),
('launch', 9.00, 1000, 3000, '{"ai_search": true, "semantic_search": true, "typo_correction": true, "analytics": true, "user_intent": true, "email_support": true}'),
('growth', 19.00, 5000, 12000, '{"ai_search": true, "semantic_search": true, "typo_correction": true, "advanced_analytics": true, "user_intent": true, "merchandising": true, "email_support": true}'),
('scale', 49.00, 25000, 60000, '{"ai_search": true, "semantic_search": true, "typo_correction": true, "advanced_analytics": true, "user_intent": true, "merchandising": true, "api_access": true, "priority_support": true}'),
('enterprise', 149.00, -1, -1, '{"ai_search": true, "semantic_search": true, "typo_correction": true, "unlimited": true, "user_intent": true, "merchandising": true, "dedicated_support": true, "custom_integrations": true, "api_access": true, "priority_support": true}');

-- Tabla de suscripciones de usuarios
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    shop_domain VARCHAR(255) NOT NULL UNIQUE,
    plan_id INTEGER REFERENCES subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active', -- active, canceled, expired
    current_products INTEGER DEFAULT 0,
    searches_this_month INTEGER DEFAULT 0,
    search_reset_date DATE DEFAULT CURRENT_DATE,
    billing_cycle_start DATE DEFAULT CURRENT_DATE,
    billing_cycle_end DATE DEFAULT CURRENT_DATE + INTERVAL '30 days',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para tracking de uso
CREATE TABLE IF NOT EXISTS usage_tracking (
    id SERIAL PRIMARY KEY,
    shop_domain VARCHAR(255) NOT NULL,
    usage_type VARCHAR(20) NOT NULL, -- 'search', 'product_sync'
    usage_date DATE DEFAULT CURRENT_DATE,
    usage_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(shop_domain, usage_type, usage_date)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_shop ON user_subscriptions(shop_domain);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_shop_date ON usage_tracking(shop_domain, usage_date);
CREATE INDEX IF NOT EXISTS idx_subscription_plans_active ON subscription_plans(active);

-- Función para resetear búsquedas mensuales
CREATE OR REPLACE FUNCTION reset_monthly_searches()
RETURNS void AS $$
BEGIN
    UPDATE user_subscriptions 
    SET searches_this_month = 0,
        search_reset_date = CURRENT_DATE
    WHERE search_reset_date <= CURRENT_DATE - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Función para verificar límites
CREATE OR REPLACE FUNCTION check_plan_limits(p_shop_domain VARCHAR, p_usage_type VARCHAR)
RETURNS JSONB AS $$
DECLARE
    v_subscription RECORD;
    v_plan RECORD;
    v_current_products INTEGER;
    v_current_searches INTEGER;
    v_result JSONB;
BEGIN
    -- Obtener suscripción actual
    SELECT * INTO v_subscription 
    FROM user_subscriptions 
    WHERE shop_domain = p_shop_domain;
    
    -- Si no existe suscripción, crear una gratuita
    IF NOT FOUND THEN
        INSERT INTO user_subscriptions (shop_domain, plan_id, billing_cycle_start, billing_cycle_end)
        SELECT p_shop_domain, id, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days' 
        FROM subscription_plans WHERE name = 'free'
        RETURNING * INTO v_subscription;
    END IF;
    
    -- Obtener detalles del plan
    SELECT * INTO v_plan 
    FROM subscription_plans 
    WHERE id = v_subscription.plan_id;
    
    -- Obtener uso actual
    SELECT COUNT(*) INTO v_current_products 
    FROM product_embeddings 
    WHERE metadata->>'shop' = p_shop_domain;
    
    SELECT COALESCE(SUM(usage_count), 0) INTO v_current_searches
    FROM usage_tracking 
    WHERE shop_domain = p_shop_domain 
    AND usage_type = 'search' 
    AND usage_date >= v_subscription.search_reset_date;
    
    -- Verificar límites
    v_result = jsonb_build_object(
        'shop', p_shop_domain,
        'plan', v_plan.name,
        'current_products', v_current_products,
        'max_products', v_plan.max_products,
        'current_searches', v_current_searches,
        'max_searches', v_plan.max_searches_per_month,
        'products_exceeded', CASE 
            WHEN v_plan.max_products = -1 THEN false
            ELSE v_current_products > v_plan.max_products
        END,
        'searches_exceeded', CASE 
            WHEN v_plan.max_searches_per_month = -1 THEN false
            ELSE v_current_searches >= v_plan.max_searches_per_month
        END,
        'upgrade_required', CASE 
            WHEN v_plan.max_products != -1 AND v_current_products > v_plan.max_products THEN true
            WHEN v_plan.max_searches_per_month != -1 AND v_current_searches >= v_plan.max_searches_per_month THEN true
            ELSE false
        END
    );
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;