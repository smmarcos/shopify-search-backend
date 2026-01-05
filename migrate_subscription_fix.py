#!/usr/bin/env python3
"""
Migración: Actualizar función check_plan_limits para incluir billing_cycle_end
"""

import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/shopify_search")

SQL = """
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
"""

# También arreglar registros existentes que tengan NULL
FIX_NULLS = """
UPDATE user_subscriptions 
SET billing_cycle_end = CURRENT_DATE + INTERVAL '30 days',
    updated_at = CURRENT_TIMESTAMP
WHERE billing_cycle_end IS NULL;
"""

async def migrate():
    print("🔧 Aplicando migración de billing_cycle_end...")
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # 1. Actualizar función
        print("📝 Actualizando función check_plan_limits...")
        await conn.execute(SQL)
        print("✅ Función actualizada")
        
        # 2. Arreglar registros existentes con NULL
        print("\n📝 Arreglando registros con billing_cycle_end NULL...")
        result = await conn.execute(FIX_NULLS)
        rows_updated = int(result.split()[-1]) if result else 0
        print(f"✅ {rows_updated} registros actualizados")
        
        print("\n✅ Migración completada exitosamente!")
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
