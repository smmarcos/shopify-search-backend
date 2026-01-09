"""
FastAPI server for SmartSearch AI
Connects Remix frontend with Python AI backend
"""

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
from typing import Optional, List
from rapidfuzz import fuzz, process
import hmac
import hashlib
import base64
import logging

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import Agent, Runner
from agents import function_tool
from openai import AsyncOpenAI
from database.connection import db_client
from database.embeddings import EmbeddingGenerator

# Initialize
app = FastAPI(title="SmartSearch AI API", version="1.0.0")

# CORS for Remix frontend AND Shopify storefronts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas las tiendas Shopify
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI client
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
embedding_gen = EmbeddingGenerator()

# ==================
# HEALTH CHECK
# ==================

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring"""
    return {
        "status": "healthy",
        "service": "shopify-search-backend",
        "version": "1.0.1"  # Updated with auto-reset
    }

@app.post("/api/admin/update-check-limits-function")
async def update_check_limits_function(secret: str = ""):
    """Admin endpoint to update check_plan_limits function with auto-reset"""
    expected_secret = os.getenv("ADMIN_SECRET", "update-function-2026")
    if secret != expected_secret:
        raise HTTPException(403, "Forbidden")
    
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE OR REPLACE FUNCTION check_plan_limits(p_shop_domain VARCHAR, p_usage_type VARCHAR)
                RETURNS JSONB AS $$
                DECLARE
                    v_subscription RECORD; v_plan RECORD; v_current_products INTEGER; v_current_searches INTEGER; v_result JSONB;
                BEGIN
                    SELECT * INTO v_subscription FROM user_subscriptions WHERE shop_domain = p_shop_domain;
                    IF NOT FOUND THEN
                        INSERT INTO user_subscriptions (
                            shop_domain, 
                            plan_id, 
                            search_reset_date, 
                            billing_cycle_start, 
                            billing_cycle_end
                        )
                        SELECT 
                            p_shop_domain, 
                            id, 
                            CURRENT_DATE, 
                            CURRENT_DATE, 
                            CURRENT_DATE + INTERVAL '30 days'
                        FROM subscription_plans 
                        WHERE name = 'starter' 
                        RETURNING * INTO v_subscription;
                    END IF;
                    IF v_subscription.search_reset_date <= CURRENT_DATE - INTERVAL '30 days' THEN
                        UPDATE user_subscriptions SET searches_this_month = 0, search_reset_date = CURRENT_DATE,
                            billing_cycle_start = CURRENT_DATE, billing_cycle_end = CURRENT_DATE + INTERVAL '30 days'
                        WHERE shop_domain = p_shop_domain;
                        v_subscription.search_reset_date := CURRENT_DATE; v_subscription.searches_this_month := 0;
                        DELETE FROM usage_tracking WHERE shop_domain = p_shop_domain AND usage_date < CURRENT_DATE - INTERVAL '90 days';
                    END IF;
                    SELECT * INTO v_plan FROM subscription_plans WHERE id = v_subscription.plan_id;
                    SELECT COUNT(*) INTO v_current_products FROM product_embeddings WHERE metadata->>'shop' = p_shop_domain;
                    SELECT COALESCE(SUM(usage_count), 0) INTO v_current_searches
                    FROM usage_tracking WHERE shop_domain = p_shop_domain AND usage_type = 'search' AND usage_date >= v_subscription.search_reset_date;
                    v_result = jsonb_build_object('shop', p_shop_domain, 'plan', v_plan.name, 'current_products', v_current_products,
                        'max_products', v_plan.max_products, 'current_searches', v_current_searches, 'max_searches', v_plan.max_searches_per_month,
                        'products_exceeded', CASE WHEN v_plan.max_products = -1 THEN false ELSE v_current_products > v_plan.max_products END,
                        'searches_exceeded', CASE WHEN v_plan.max_searches_per_month = -1 THEN false ELSE v_current_searches >= v_plan.max_searches_per_month END,
                        'upgrade_required', CASE WHEN v_plan.max_products != -1 AND v_current_products > v_plan.max_products THEN true
                                                 WHEN v_plan.max_searches_per_month != -1 AND v_current_searches >= v_plan.max_searches_per_month THEN true ELSE false END);
                    RETURN v_result;
                END;
                $$ LANGUAGE plpgsql;
            """)
            return {"success": True, "message": "Function updated with auto-reset logic"}
    except Exception as e:
        raise HTTPException(500, f"Error updating function: {str(e)}")

@app.post("/api/admin/migrate-shop-domain")
async def migrate_shop_domain(secret: str = ""):
    """Add shop_domain columns to tables for multi-tenant support"""
    expected_secret = os.getenv("ADMIN_SECRET", "update-function-2026")
    if secret != expected_secret:
        raise HTTPException(403, "Forbidden")
    
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # CRITICAL: Drop old unique constraint FIRST
            try:
                # Try multiple possible constraint names
                await conn.execute("ALTER TABLE product_embeddings DROP CONSTRAINT IF EXISTS product_embeddings_product_id_key CASCADE")
                await conn.execute("ALTER TABLE product_embeddings DROP CONSTRAINT IF EXISTS product_embeddings_pkey CASCADE")
                print("✅ Dropped old unique constraints")
            except Exception as e:
                print(f"⚠️ Constraint drop error: {str(e)}")
            
            # Add shop_domain to product_embeddings
            try:
                await conn.execute("""
                    ALTER TABLE product_embeddings 
                    ADD COLUMN shop_domain VARCHAR(255)
                """)
                print("✅ Added shop_domain to product_embeddings")
            except Exception as e:
                print(f"⚠️ product_embeddings column exists or error: {str(e)}")
            
            # Add shop_domain to search_analytics
            try:
                await conn.execute("""
                    ALTER TABLE search_analytics 
                    ADD COLUMN shop_domain VARCHAR(255)
                """)
                print("✅ Added shop_domain to search_analytics")
            except Exception as e:
                print(f"⚠️ search_analytics column exists or error: {str(e)}")
            
            # Create indexes
            try:
                await conn.execute("""
                    CREATE INDEX product_embeddings_shop_idx 
                    ON product_embeddings (shop_domain)
                """)
                print("✅ Created index on product_embeddings.shop_domain")
            except Exception as e:
                print(f"⚠️ Index exists or error: {str(e)}")
            
            try:
                await conn.execute("""
                    CREATE INDEX search_analytics_shop_idx 
                    ON search_analytics (shop_domain)
                """)
                print("✅ Created index on search_analytics.shop_domain")
            except Exception as e:
                print(f"⚠️ Index exists or error: {str(e)}")
            
            # Create composite unique index
            try:
                await conn.execute("""
                    DROP INDEX IF EXISTS product_embeddings_product_shop_idx
                """)
                await conn.execute("""
                    CREATE UNIQUE INDEX product_embeddings_product_shop_idx 
                    ON product_embeddings (product_id, shop_domain)
                """)
                print("✅ Created composite unique index")
            except Exception as e:
                print(f"⚠️ Composite index error: {str(e)}")
            
            # Delete products without shop_domain (orphaned data)
            try:
                result = await conn.execute("DELETE FROM product_embeddings WHERE shop_domain IS NULL")
                print(f"✅ Cleaned orphaned products: {result}")
            except Exception as e:
                print(f"⚠️ Cleanup error: {str(e)}")
            
            return {"success": True, "message": "Migration completed: shop_domain columns added"}
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        raise HTTPException(500, f"Migration error: {str(e)}")

# ==================
# GDPR COMPLIANCE WEBHOOKS
# ==================

def verify_shopify_webhook(body: bytes, hmac_header: str) -> bool:
    """
    Verify Shopify webhook HMAC signature
    Returns True if signature is valid
    """
    try:
        # Get API secret from environment (same as SHOPIFY_API_SECRET)
        api_secret = os.getenv("SHOPIFY_API_SECRET", "")
        if not api_secret:
            logging.warning("SHOPIFY_API_SECRET not set, cannot verify webhook")
            return False
        
        # Calculate HMAC
        computed_hmac = base64.b64encode(
            hmac.new(
                api_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
        ).decode()
        
        # Compare with header
        return hmac.compare_digest(computed_hmac, hmac_header)
    except Exception as e:
        logging.error(f"HMAC verification failed: {str(e)}")
        return False

@app.post("/webhooks")
async def webhooks_test_endpoint(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Generic webhook endpoint for Shopify to test webhook delivery.
    Validates HMAC and returns 401 if invalid, 200 if valid.
    """
    # Read raw body
    body = await request.body()
    
    # Verify HMAC
    if not x_shopify_hmac_sha256:
        logging.warning("Webhook received without HMAC header")
        raise HTTPException(status_code=401, detail="Missing HMAC signature")
    
    if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
        logging.warning("Webhook HMAC verification failed")
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    
    # HMAC is valid - webhook accepted
    logging.info("Webhook test endpoint called - HMAC valid")
    return {"status": "ok", "message": "Webhook received and validated"}

@app.post("/webhooks/customers/data_request")
async def customer_data_request(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    GDPR: Customer requests their data
    Store owner must provide customer data within 30 days
    """
    try:
        body = await request.body()
        
        # Verify HMAC signature
        if not x_shopify_hmac_sha256:
            raise HTTPException(401, "Missing HMAC header")
        
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            raise HTTPException(401, "Invalid HMAC signature")
        
        # Parse payload
        import json
        payload = json.loads(body)
        shop_domain = payload.get("shop_domain")
        customer = payload.get("customer", {})
        
        logging.info(f"[GDPR] Customer data request for shop={shop_domain}, customer={customer.get('id')}")
        
        # TODO: Implement logic to gather customer data
        # For now, we only store:
        # - Shop domain and owner email in user_subscriptions
        # - No individual customer PII
        # - Product embeddings (no customer data)
        # - Usage tracking (anonymous shop-level data)
        
        return {
            "status": "acknowledged",
            "message": "Customer data request received. No customer PII stored.",
            "shop_domain": shop_domain
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing customer data request: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/webhooks/customers/redact")
async def customer_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    GDPR: Customer requests deletion of their data
    Must delete customer data within 30 days (unless legally required to retain)
    """
    try:
        body = await request.body()
        
        # Verify HMAC signature
        if not x_shopify_hmac_sha256:
            raise HTTPException(401, "Missing HMAC header")
        
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            raise HTTPException(401, "Invalid HMAC signature")
        
        # Parse payload
        import json
        payload = json.loads(body)
        shop_domain = payload.get("shop_domain")
        customer = payload.get("customer", {})
        
        logging.info(f"[GDPR] Customer redaction for shop={shop_domain}, customer={customer.get('id')}")
        
        # TODO: Implement logic to delete customer data
        # Current data model:
        # - We don't store individual customer data
        # - Only shop-level aggregated analytics
        # - No action needed unless we add customer tracking
        
        return {
            "status": "acknowledged",
            "message": "Customer redaction request received. No customer PII to delete.",
            "shop_domain": shop_domain
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing customer redaction: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/webhooks/shop/redact")
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    GDPR: Shop uninstalled app, delete all shop data
    Triggered 48 hours after app uninstallation
    """
    try:
        body = await request.body()
        
        # Verify HMAC signature
        if not x_shopify_hmac_sha256:
            raise HTTPException(401, "Missing HMAC header")
        
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            raise HTTPException(401, "Invalid HMAC signature")
        
        # Parse payload
        import json
        payload = json.loads(body)
        shop_domain = payload.get("shop_domain")
        shop_id = payload.get("shop_id")
        
        logging.info(f"[GDPR] Shop redaction for shop={shop_domain}, id={shop_id}")
        
        # Delete ALL shop data from database
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Delete in correct order (respecting foreign keys)
            await conn.execute("DELETE FROM usage_tracking WHERE shop_domain = $1", shop_domain)
            await conn.execute("DELETE FROM product_embeddings WHERE shop_domain = $1", shop_domain)
            await conn.execute("DELETE FROM user_subscriptions WHERE shop_domain = $1", shop_domain)
            
            logging.info(f"[GDPR] All data deleted for shop {shop_domain}")
        
        return {
            "status": "completed",
            "message": "All shop data deleted successfully",
            "shop_domain": shop_domain
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing shop redaction: {str(e)}")
        raise HTTPException(500, str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "SmartSearch AI API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/api/admin/fix-subscriptions")
async def fix_subscriptions():
    """Temporary endpoint to fix billing_cycle_end NULL values"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Update function
            await conn.execute("""
                CREATE OR REPLACE FUNCTION check_plan_limits(p_shop_domain VARCHAR, p_usage_type VARCHAR)
                RETURNS JSONB AS $$
                DECLARE
                    v_subscription RECORD;
                    v_plan RECORD;
                    v_current_products INTEGER;
                    v_current_searches INTEGER;
                    v_result JSONB;
                BEGIN
                    SELECT * INTO v_subscription 
                    FROM user_subscriptions 
                    WHERE shop_domain = p_shop_domain;
                    
                    IF NOT FOUND THEN
                        INSERT INTO user_subscriptions (shop_domain, plan_id, billing_cycle_start, billing_cycle_end)
                        SELECT p_shop_domain, id, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days' 
                        FROM subscription_plans WHERE name = 'starter'
                        RETURNING * INTO v_subscription;
                    END IF;
                    
                    SELECT * INTO v_plan 
                    FROM subscription_plans 
                    WHERE id = v_subscription.plan_id;
                    
                    SELECT COUNT(*) INTO v_current_products 
                    FROM product_embeddings 
                    WHERE metadata->>'shop' = p_shop_domain;
                    
                    SELECT COALESCE(SUM(usage_count), 0) INTO v_current_searches
                    FROM usage_tracking 
                    WHERE shop_domain = p_shop_domain 
                    AND usage_type = 'search' 
                    AND usage_date >= v_subscription.search_reset_date;
                    
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
            """)
            
            # Fix NULL values
            result = await conn.execute("""
                UPDATE user_subscriptions 
                SET billing_cycle_end = CURRENT_DATE + INTERVAL '30 days',
                    updated_at = CURRENT_TIMESTAMP
                WHERE billing_cycle_end IS NULL
            """)
            
            rows_updated = int(result.split()[-1]) if result else 0
            
            return {
                "status": "success",
                "message": "Subscriptions fixed",
                "rows_updated": rows_updated
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/check-schema")
async def check_schema():
    """Check embedding column type and fix if needed"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Check current column type
            column_info = await conn.fetchrow("""
                SELECT 
                    column_name, 
                    data_type, 
                    udt_name
                FROM information_schema.columns 
                WHERE table_name = 'product_embeddings' 
                AND column_name = 'embedding'
            """)
            
            result = {
                "column": column_info['column_name'] if column_info else None,
                "data_type": column_info['data_type'] if column_info else None,
                "udt_name": column_info['udt_name'] if column_info else None,
                "is_vector": column_info['udt_name'] == 'vector' if column_info else False
            }
            
            # If it's not vector type, fix it
            if column_info and column_info['udt_name'] != 'vector':
                # Drop and recreate with correct type
                await conn.execute("""
                    ALTER TABLE product_embeddings 
                    DROP COLUMN IF EXISTS embedding
                """)
                
                await conn.execute("""
                    ALTER TABLE product_embeddings 
                    ADD COLUMN embedding vector(1536)
                """)
                
                # Recreate index
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS product_embeddings_vector_idx 
                    ON product_embeddings 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                result["fixed"] = True
                result["message"] = "Column type fixed from text to vector"
            else:
                result["fixed"] = False
                result["message"] = "Column type is already correct (vector)"
            
            return result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/generate-missing-embeddings")
async def generate_missing_embeddings(request: dict):
    """Force generate embeddings for all products without them"""
    try:
        shop = request.get('shop', 'test.myshopify.com')
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Get products without embeddings
            products = await conn.fetch("""
                SELECT product_id, title, description, vendor, category, tags
                FROM product_embeddings
                WHERE embedding IS NULL
                AND (metadata->>'shop' = $1 OR $1 = '')
            """, shop)
            
            if not products:
                return {
                    "status": "success",
                    "message": "No products without embeddings",
                    "generated": 0
                }
            
            print(f"🧠 Generating embeddings for {len(products)} products...")
            embedding_gen = EmbeddingGenerator()
            generated = 0
            
            for prod in products:
                try:
                    # Create text for embedding
                    text_parts = [prod['title']]
                    if prod['description']:
                        text_parts.append(prod['description'])
                    if prod['category']:
                        text_parts.append(f"Category: {prod['category']}")
                    if prod['tags']:
                        text_parts.append(f"Tags: {', '.join(prod['tags'])}")
                    
                    text = " ".join(text_parts)
                    
                    # Generate embedding
                    embedding = await embedding_gen.generate_embedding(text)
                    
                    # Save embedding
                    embedding_str = f"[{','.join(map(str, embedding))}]"
                    await conn.execute("""
                        UPDATE product_embeddings
                        SET embedding = $1::vector, updated_at = CURRENT_TIMESTAMP
                        WHERE product_id = $2
                    """, embedding_str, prod['product_id'])
                    
                    generated += 1
                    print(f"   ✓ {generated}/{len(products)} - {prod['product_id']}")
                    
                except Exception as e:
                    print(f"   ✗ Error with {prod['product_id']}: {e}")
            
            return {
                "status": "success",
                "message": f"Generated {generated} embeddings",
                "total_processed": len(products),
                "generated": generated,
                "failed": len(products) - generated
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/migrate-old-plans")
async def migrate_old_plans():
    """Migrate users from old plan names to new ones"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            print("🔄 Starting plan migration...")
            
            # Plan mapping: old -> new
            plan_mapping = {
                'free': 'launch',      # Free users upgraded to Launch
                'basic': 'launch',     # Basic = Launch
                'pro': 'growth',       # Pro = Growth
                'business': 'scale'    # Business = Scale
            }
            
            results = []
            
            for old_plan, new_plan in plan_mapping.items():
                # Get old plan ID
                old_plan_row = await conn.fetchrow(
                    "SELECT id FROM subscription_plans WHERE name = $1", 
                    old_plan
                )
                
                if not old_plan_row:
                    results.append(f"⚠️ Old plan '{old_plan}' not found")
                    continue
                
                # Get new plan ID
                new_plan_row = await conn.fetchrow(
                    "SELECT id, price, max_products, max_searches_per_month FROM subscription_plans WHERE name = $1", 
                    new_plan
                )
                
                if not new_plan_row:
                    results.append(f"❌ New plan '{new_plan}' not found")
                    continue
                
                # Count users on old plan
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_subscriptions WHERE plan_id = $1",
                    old_plan_row['id']
                )
                
                if count == 0:
                    results.append(f"ℹ️ No users on '{old_plan}' plan")
                    continue
                
                # Update users to new plan
                await conn.execute("""
                    UPDATE user_subscriptions 
                    SET plan_id = $1, updated_at = NOW()
                    WHERE plan_id = $2
                """, new_plan_row['id'], old_plan_row['id'])
                
                results.append(f"✅ Migrated {count} users: {old_plan} → {new_plan}")
            
            # Get final distribution
            distribution = await conn.fetch("""
                SELECT sp.name, COUNT(us.id) as user_count
                FROM subscription_plans sp
                LEFT JOIN user_subscriptions us ON sp.id = us.plan_id
                WHERE sp.active = true
                GROUP BY sp.name, sp.price
                ORDER BY sp.price ASC
            """)
            
            return {
                "status": "success",
                "migrations": results,
                "current_distribution": {row['name']: row['user_count'] for row in distribution}
            }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}\n{traceback.format_exc()}")

@app.post("/api/admin/update-subscription-plans")
async def update_subscription_plans():
    """Update subscription plans with new pricing and limits"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            print("🔄 Updating subscription plans...")
            
            # New plan definitions
            new_plans = [
                {'name': 'starter', 'price': 0.00, 'max_products': 50, 'max_searches': 300},
                {'name': 'launch', 'price': 9.00, 'max_products': 250, 'max_searches': 1000},
                {'name': 'growth', 'price': 19.00, 'max_products': 2500, 'max_searches': 7500},
                {'name': 'scale', 'price': 49.00, 'max_products': 5000, 'max_searches': 20000},
                {'name': 'enterprise', 'price': 149.00, 'max_products': -1, 'max_searches': -1}
            ]
            
            results = []
            
            for plan in new_plans:
                # Check if plan exists
                existing = await conn.fetchrow(
                    "SELECT id, name, price, max_products, max_searches_per_month FROM subscription_plans WHERE name = $1",
                    plan['name']
                )
                
                if existing:
                    # Update existing plan
                    await conn.execute("""
                        UPDATE subscription_plans 
                        SET price = $1, 
                            max_products = $2, 
                            max_searches_per_month = $3,
                            updated_at = NOW()
                        WHERE name = $4
                    """, plan['price'], plan['max_products'], plan['max_searches'], plan['name'])
                    
                    results.append(f"✅ Updated {plan['name']}: ${plan['price']}/mo, {plan['max_products']} products, {plan['max_searches']} searches")
                else:
                    # Insert new plan
                    await conn.execute("""
                        INSERT INTO subscription_plans (name, price, max_products, max_searches_per_month, features, active)
                        VALUES ($1, $2, $3, $4, $5, true)
                    """, plan['name'], plan['price'], plan['max_products'], plan['max_searches'],
                    '{"ai_search": true, "semantic_search": true, "typo_correction": true, "analytics": true}')
                    
                    results.append(f"✅ Created {plan['name']}: ${plan['price']}/mo, {plan['max_products']} products, {plan['max_searches']} searches")
            
            # Get all current plans
            all_plans = await conn.fetch("""
                SELECT name, price, max_products, max_searches_per_month, active
                FROM subscription_plans
                ORDER BY price ASC
            """)
            
            return {
                "status": "success",
                "updates": results,
                "current_plans": [dict(p) for p in all_plans]
            }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}\n{traceback.format_exc()}")

@app.post("/api/admin/deactivate-old-plans")
async def deactivate_old_plans():
    """Deactivate old plan names (free, basic, pro, business) so only new ones show"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            old_plans = ['free', 'basic', 'pro', 'business']
            
            for plan_name in old_plans:
                await conn.execute("""
                    UPDATE subscription_plans 
                    SET active = false 
                    WHERE name = $1
                """, plan_name)
            
            # Get active plans
            active_plans = await conn.fetch("""
                SELECT name, price, max_products, max_searches_per_month
                FROM subscription_plans
                WHERE active = true
                ORDER BY price ASC
            """)
            
            return {
                "status": "success",
                "deactivated": old_plans,
                "active_plans": [dict(p) for p in active_plans]
            }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}\n{traceback.format_exc()}")

@app.get("/api/admin/debug-products")
async def debug_products(shop: str = "test.myshopify.com"):
    """Debug endpoint to see product status"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Get all products for this shop
            products = await conn.fetch("""
                SELECT 
                    product_id,
                    title,
                    embedding IS NULL as missing_embedding,
                    metadata->>'shop' as shop_value,
                    updated_at
                FROM product_embeddings
                WHERE metadata->>'shop' = $1 OR $1 = ''
                ORDER BY updated_at DESC
                LIMIT 20
            """, shop)
            
            # Get counts
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM product_embeddings
                WHERE metadata->>'shop' = $1 OR $1 = ''
            """, shop)
            
            without_embeddings = await conn.fetchval("""
                SELECT COUNT(*) FROM product_embeddings
                WHERE embedding IS NULL
                AND (metadata->>'shop' = $1 OR $1 = '')
            """, shop)
            
            return {
                "shop": shop,
                "total_products": total,
                "without_embeddings": without_embeddings,
                "with_embeddings": total - without_embeddings,
                "sample_products": [
                    {
                        "product_id": p['product_id'],
                        "title": p['title'],
                        "missing_embedding": p['missing_embedding'],
                        "shop_value": p['shop_value'],
                        "updated_at": p['updated_at'].isoformat() if p['updated_at'] else None
                    }
                    for p in products
                ]
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/test-search")
async def test_search(query: str = "camiseta blanca", shop: str = "test.myshopify.com"):
    """Test vector search with raw similarity scores"""
    try:
        # Generate embedding for query
        query_embedding = await embedding_gen.generate_embedding(query)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Raw search without filters to see all scores
            results = await conn.fetch("""
                SELECT 
                    product_id,
                    title,
                    1 - (embedding <=> CAST($1 AS vector)) as similarity_score,
                    metadata->>'shop' as shop_value
                FROM product_embeddings
                WHERE embedding IS NOT NULL
                AND (metadata->>'shop' = $2 OR $2 = '')
                ORDER BY embedding <=> CAST($1 AS vector)
                LIMIT 10
            """, embedding_str, shop)
            
            return {
                "query": query,
                "shop": shop,
                "results": [
                    {
                        "product_id": r['product_id'],
                        "title": r['title'],
                        "similarity_score": float(r['similarity_score']),
                        "shop_value": r['shop_value']
                    }
                    for r in results
                ]
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/get-config")
async def get_current_config(shop: str):
    """Get current config from database (per-shop)"""
    try:
        config = await db_client.get_app_config(shop=shop)
        return {
            "config": config,
            "source": "database" if config else "default",
            "shop": shop
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/reset-config")
async def reset_config():
    """Reset config to defaults with better values"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM app_settings WHERE key = 'ai_search'
            """)
        
        return {
            "status": "success",
            "message": "Config reset to defaults",
            "new_defaults": {
                "similarity_threshold": 50,
                "results_limit": "unlimited",
                "ai_search_enabled": True
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/reinstall-pgvector")
async def reinstall_pgvector():
    """Reinstall pgvector extension and recreate table"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Drop everything first
            await conn.execute("DROP TABLE IF EXISTS product_embeddings CASCADE")
            await conn.execute("DROP EXTENSION IF EXISTS vector CASCADE")
            
            # Create extension
            await conn.execute("CREATE EXTENSION vector")
            
            # Recreate the product_embeddings table
            await conn.execute("""
                CREATE TABLE product_embeddings (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(255) UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2),
                    vendor VARCHAR(255),
                    category VARCHAR(255),
                    tags TEXT[],
                    embedding vector(1536),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Recreate indexes
            await conn.execute("""
                CREATE INDEX product_embeddings_vector_idx 
                ON product_embeddings 
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            
            await conn.execute("""
                CREATE INDEX product_embeddings_product_id_idx 
                ON product_embeddings (product_id)
            """)
            
            await conn.execute("""
                CREATE INDEX product_embeddings_metadata_idx 
                ON product_embeddings USING GIN (metadata)
            """)
            
            # Verify it works
            test = await conn.fetchval("SELECT '[1,2,3]'::vector(3) <=> '[1,2,3]'::vector(3)")
            
            return {
                "status": "success",
                "message": "pgvector extension and table recreated successfully",
                "test_query": float(test),
                "note": "Table is empty. Re-sync products from Shopify to regenerate embeddings."
            }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}\n{traceback.format_exc()}")

# ==================
# TYPO CORRECTION
# ==================

# Dictionary of common search terms (built from product catalog)
COMMON_TERMS = {
    # English
    "snowboard", "snowboards", "running", "shoes", "boots", "jacket", "pants",
    "accessories", "sport", "winter", "summer", "premium", "quality",
    # Spanish
    "tabla", "tablas", "snowboard", "zapatillas", "zapatos", "deportivo", "deporte",
    "calzado", "running", "correr", "invierno", "verano", "premium", "calidad",
    "comprar", "tienda", "online",
    # Brands (will be populated from DB)
    "nike", "adidas", "hoka", "brooks", "new balance", "salomon"
}

def correct_typos(query: str, threshold: int = 75) -> tuple[str, bool]:
    """
    Correct typos in search query using fuzzy matching
    
    Args:
        query: User's search query
        threshold: Minimum similarity score (0-100) to consider a match
    
    Returns:
        (corrected_query, was_corrected)
    """
    words = query.lower().split()
    corrected_words = []
    was_corrected = False
    
    for word in words:
        # Skip very short words
        if len(word) <= 2:
            corrected_words.append(word)
            continue
        
        # Find best match in dictionary
        match = process.extractOne(
            word,
            COMMON_TERMS,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )
        
        if match and match[1] >= threshold:
            # Found a good match
            corrected_word = match[0]
            if corrected_word != word:
                print(f"🔧 Typo corrected: '{word}' → '{corrected_word}' (score: {match[1]})")
                was_corrected = True
            corrected_words.append(corrected_word)
        else:
            # No good match, keep original
            corrected_words.append(word)
    
    corrected_query = " ".join(corrected_words)
    return corrected_query, was_corrected

# Initialize AI client
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
embedding_gen = EmbeddingGenerator()

# ==================
# MODELS
# ==================

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    max_price: Optional[float] = None
    shop: Optional[str] = None  # Optional for development, required in production

class SearchResponse(BaseModel):
    results: List[dict]
    total: int
    query: str

class SyncRequest(BaseModel):
    shop: str
    product_ids: Optional[List[str]] = None  # If None, sync all

# ==================
# TOOLS FOR AGENT
# ==================

@function_tool
async def vector_search(query: str, max_results: int = 5, max_price: float = None) -> str:
    """Search products using semantic vector search"""
    import json
    
    try:
        # Generate embedding
        query_embedding = await embedding_gen.generate_embedding(query)
        
        # Search in database
        results = await db_client.vector_search(
            query_embedding=query_embedding,
            limit=max_results,
            max_price=max_price,
            in_stock_only=True,
            shop="test.myshopify.com"  # TODO: Get from request context
        )
        
        # Track analytics
        await db_client.track_search(query=query, results_count=len(results))
        
        # Format results
        products = []
        for row in results:
            # Extract handle from title (convert to slug format)
            handle = row['title'].lower().replace(' ', '-').replace(':', '').replace('|', '').strip()
            # Remove multiple dashes and special characters
            import re
            handle = re.sub(r'-+', '-', handle)
            handle = re.sub(r'[^a-z0-9-]', '', handle)
            
            product = {
                "id": row['product_id'],
                "handle": handle,  # Add handle for DOM matching
                "title": row['title'],
                "description": row['description'],
                "price": float(row['price']) if row['price'] is not None else 0.0,
                "vendor": row['vendor'],
                "category": row['category'],
                "similarity_score": round(float(row['similarity_score']), 3) if row.get('similarity_score') else 0.0,
                "in_stock": row['metadata'].get('in_stock', False),
                "stock_quantity": row['metadata'].get('stock_quantity', 0)
            }
            products.append(product)
        
        return json.dumps({
            "query": query,
            "results": products,
            "total": len(products)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})

# Create agent
search_agent = Agent(
    name="SmartSearch AI",
    instructions="""
    You are an intelligent e-commerce search assistant.
    
    When users search:
    - Use vector_search to find semantically similar products
    - Consider budget constraints (max_price parameter)
    - Present results naturally and conversationally
    
    Always be helpful and explain what you found.
    """,
    tools=[vector_search],
    model="gpt-4o-mini"
)

# ==================
# API ENDPOINTS
# ==================

@app.on_event("startup")
async def startup():
    """Connect to database on startup"""
    await db_client.connect()
    print("✅ Connected to database")

@app.on_event("shutdown")
async def shutdown():
    """Disconnect from database on shutdown"""
    await db_client.disconnect()
    print("✅ Disconnected from database")

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "SmartSearch AI API",
        "version": "1.0.0"
    }

@app.post("/api/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """
    Semantic search endpoint with subscription limits
    """
    try:
        shop = request.shop or "demo"
        
        # 1. CHECK SUBSCRIPTION LIMITS FIRST
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            limits_json = await conn.fetchval("""
                SELECT check_plan_limits($1, 'search')
            """, shop)
            
            # Parse the JSON response
            import json
            limits = json.loads(limits_json) if isinstance(limits_json, str) else limits_json
            
            # Check if searches are exceeded
            if limits.get('searches_exceeded', False):
                raise HTTPException(
                    status_code=402, 
                    detail={
                        "error": "Search limit exceeded",
                        "plan": limits.get('plan'),
                        "current_searches": limits.get('current_searches'),
                        "max_searches": limits.get('max_searches'),
                        "upgrade_required": True
                    }
                )
            
            # 2. TRACK USAGE (increment search count) - inside the same connection block
            await conn.execute("""
                INSERT INTO usage_tracking (shop_domain, usage_type, usage_count)
                VALUES ($1, 'search', 1)
                ON CONFLICT (shop_domain, usage_type, usage_date) DO UPDATE SET
                    usage_count = usage_tracking.usage_count + 1
            """, shop)
            
            await conn.execute("""
                UPDATE user_subscriptions 
                SET searches_this_month = searches_this_month + 1
                WHERE shop_domain = $1
            """, shop)
            
            print(f"🔍 Search started for shop: {shop}, query: '{request.query}'")
        
        # 3. PROCEED WITH SEARCH (existing logic)
        # Get current configuration from database (per-shop)
        config = await db_client.get_app_config(shop=shop)
        
        # Check if AI search is enabled
        if not config.get("ai_search_enabled", True):
            # Fallback to simple search without AI
            return SearchResponse(results=[], total=0, query=request.query)
        
        # 1. TYPO CORRECTION - Apply if enabled in config
        original_query = request.query
        corrected_query = original_query
        was_corrected = False
        
        if config.get("autocorrect", True):
            corrected_query, was_corrected = correct_typos(original_query)
            if was_corrected:
                print(f"✏️ Query corrected: '{original_query}' → '{corrected_query}'")
        
        # 2. Get results limit from config
        results_limit = config.get("results_limit", "10")
        max_results = 1000 if results_limit == "unlimited" else int(results_limit)
        if request.max_results:
            max_results = min(request.max_results, max_results) if results_limit != "unlimited" else max_results
        
        # 3. Get similarity threshold from config (default 10% for better recall)
        # Lower threshold = more results (good for semantic search with embeddings)
        similarity_threshold = config.get("similarity_threshold", 10) / 100.0
        
        # 4. Direct vector search (más rápido y permite pasar shop correctamente)
        query_embedding = await embedding_gen.generate_embedding(corrected_query)
        results = await db_client.vector_search(
            query_embedding=query_embedding,
            limit=max_results,
            max_price=request.max_price,
            in_stock_only=config.get("exclude_out_of_stock", False),
            shop=shop  # ✅ Shop del request, no hardcoded
        )
        
        print(f"🔍 vector_search returned {len(results)} results")
        if results:
            print(f"📊 First result: {results[0].get('title', 'N/A')} - similarity: {results[0].get('similarity_score', 0):.4f}")
        
        # 5. Filter by similarity threshold
        filtered_results = [
            r for r in results 
            if r.get('similarity_score', 0) >= similarity_threshold
        ]
        
        print(f"🎯 After threshold filter ({similarity_threshold:.2f}): {len(filtered_results)} results")
        
        # 6. Apply config filters
        if config.get("exclude_archived", True):
            filtered_results = [
                r for r in filtered_results 
                if not r.get('metadata', {}).get('archived', False)
            ]
        
        # 7. Format results
        products = [
            {
                "id": r['product_id'],
                "title": r['title'],
                "description": r['description'],
                "price": float(r['price']) if r['price'] else 0.0,
                "vendor": r['vendor'],
                "category": r.get('category', ''),
                "handle": r.get('metadata', {}).get('handle', '') if isinstance(r.get('metadata'), dict) else '',
                "similarity_score": float(r.get('similarity_score', 0))
            }
            for r in filtered_results
        ]
        
        # 8. SAVE TO ANALYTICS with actual results count (moved from beginning)
        final_results_count = len(products)
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO search_analytics (query, results_count, shop_domain)
                VALUES ($1, $2, $3)
            """, corrected_query, final_results_count, shop)
            print(f"📊 Analytics tracked: '{corrected_query}' → {final_results_count} results for shop: {shop}")
        
        print(f"🎁 Returning {final_results_count} final results to frontend")
        
        return SearchResponse(
            results=products,
            total=len(products),
            query=corrected_query
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync")
async def sync_products(request: dict):
    """Sync products - receives products from Shopify and generates embeddings"""
    try:
        pool = await db_client.connect()
        
        # Get products from request (sent from Shopify GraphQL)
        products = request.get('products', [])
        
        if not products:
            # Fallback: sync products already in DB without embeddings
            query = """
                SELECT product_id, title, description, price, vendor, category, tags, metadata, shop_domain
                FROM product_embeddings
                WHERE embedding IS NULL
            """
            
            async with pool.acquire() as conn:
                db_products = await conn.fetch(query)
            
            if not db_products:
                return {
                    "status": "success",
                    "synced": 0,
                    "total": 0,
                    "message": "No products to sync"
                }
            
            products = [dict(p) for p in db_products]
        
        # Generate embeddings for all products
        synced = 0
        errors = []
        
        print(f"🔄 Processing {len(products)} products...")
        
        for product in products:
            try:
                print(f"📦 Processing: {product['title']}")
                
                # BUILD RICH SEARCHABLE TEXT - Include all relevant fields
                text_parts = []
                
                # 1. TITLE (most important - weight 2x by repeating)
                title = product.get('title', '')
                text_parts.append(title)
                text_parts.append(title)  # Repeat for higher weight
                
                # 2. DESCRIPTION
                description = product.get('description', '') or ''
                if description:
                    text_parts.append(description)
                
                # 3. VENDOR/BRAND
                vendor = product.get('vendor', '')
                if vendor:
                    text_parts.append(f"Brand: {vendor}")
                    text_parts.append(f"Marca: {vendor}")  # Spanish
                
                # 4. CATEGORY
                category = product.get('category', '')
                if category:
                    text_parts.append(f"Category: {category}")
                    text_parts.append(f"Categoría: {category}")  # Spanish
                
                # 5. PRODUCT TYPE
                product_type = product.get('product_type', '') or product.get('type', '')
                if product_type:
                    text_parts.append(f"Type: {product_type}")
                    text_parts.append(f"Tipo: {product_type}")  # Spanish
                
                # 6. TAGS (important for semantic matching)
                tags = product.get('tags', '')
                if isinstance(tags, str):
                    tags_list = [t.strip() for t in tags.split(',')] if tags else []
                else:
                    tags_list = tags if tags else []
                
                if tags_list:
                    text_parts.append(f"Tags: {', '.join(tags_list)}")
                    text_parts.append(f"Etiquetas: {', '.join(tags_list)}")  # Spanish
                
                # 7. PRICE RANGE (for semantic "cheap", "expensive", "barato", "caro")
                price = float(product.get('price', 0.0))
                if price > 0:
                    if price < 50:
                        text_parts.append("affordable budget-friendly económico barato")
                    elif price < 150:
                        text_parts.append("mid-range precio medio")
                    else:
                        text_parts.append("premium high-end caro premium")
                
                # 8. METADATA - Extract useful context
                metadata = product.get('metadata', {})
                if isinstance(metadata, dict):
                    # Add any useful metadata fields
                    if metadata.get('colors'):
                        text_parts.append(f"Colors: {metadata['colors']}")
                    if metadata.get('sizes'):
                        text_parts.append(f"Sizes: {metadata['sizes']}")
                    if metadata.get('material'):
                        text_parts.append(f"Material: {metadata['material']}")
                
                # Combine all parts into rich searchable text
                searchable_text = " ".join(filter(None, text_parts))
                
                print(f"📝 Searchable text length: {len(searchable_text)} chars")
                
                embedding = await embedding_gen.generate_embedding(searchable_text)
                
                # Keep tags_list for database storage
                tags_list = tags_list if tags_list else []
                
                # Extract shop_domain from product (either from request or from database)
                shop_domain = product.get('shop_domain') or product.get('metadata', {}).get('shop_domain') if isinstance(product.get('metadata'), dict) else None
                
                await db_client.upsert_product(
                    product_id=product['product_id'],
                    title=product['title'],
                    description=product.get('description', ''),
                    price=float(product.get('price', 0.0)),
                    vendor=product.get('vendor', ''),
                    category=product.get('category', ''),
                    tags=tags_list,
                    embedding=embedding,
                    metadata=product.get('metadata', {}) if isinstance(product.get('metadata'), dict) else {},
                    shop_domain=shop_domain
                )
                synced += 1
                print(f"✅ Synced: {product['title']} for shop: {shop_domain}")
            except Exception as e:
                error_msg = f"{product['product_id']}: {str(e)}"
                print(f"❌ Error: {error_msg}")
                errors.append(error_msg)
        
        print(f"🎉 Sync complete: {synced}/{len(products)} products")
        
        return {
            "status": "success",
            "synced": synced,
            "total": len(products),
            "errors": errors if errors else None,
            "message": f"Synced {synced}/{len(products)} products"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-incremental")
async def sync_incremental(request: dict):
    """Sync only new/modified products (faster)"""
    try:
        pool = await db_client.connect()
        
        # Get products without embeddings (new/modified)
        async with pool.acquire() as conn:
            products_to_sync = await conn.fetch("""
                SELECT product_id, title, description, price, vendor, category, tags, metadata
                FROM product_embeddings
                WHERE embedding IS NULL
                LIMIT 50
            """)
        
        if not products_to_sync:
            return {
                "status": "success",
                "synced": 0,
                "message": "✅ All products are up to date!"
            }
        
        # Generate embeddings for missing products only
        synced = 0
        for product in products_to_sync:
            try:
                # Use existing embedding generation logic
                title = product['title']
                description = product['description'] or ''
                
                # Build searchable text (simplified version)
                text_parts = [title, title]  # Title weight 2x
                if description:
                    text_parts.append(description)
                if product['vendor']:
                    text_parts.append(f"Brand: {product['vendor']}")
                
                searchable_text = " ".join(filter(None, text_parts))
                embedding = await embedding_gen.generate_embedding(searchable_text)
                
                # Update product with embedding
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE product_embeddings 
                        SET embedding = $1, updated_at = NOW()
                        WHERE product_id = $2
                    """, embedding, product['product_id'])
                
                synced += 1
                print(f"✅ Synced: {title}")
                
            except Exception as e:
                print(f"❌ Failed to sync {product['title']}: {e}")
                continue
        
        return {
            "status": "success",
            "synced": synced,
            "message": f"✅ {synced} products synced successfully"
        }
        
    except Exception as e:
        print(f"❌ Incremental sync error: {e}")
        return {"status": "error", "error": str(e), "synced": 0}

@app.get("/api/stats")
async def get_stats():
    """Get database statistics"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM product_embeddings")
            with_embeddings = await conn.fetchval(
                "SELECT COUNT(*) FROM product_embeddings WHERE embedding IS NOT NULL"
            )
        
        return {
            "total_products": total,
            "indexed_products": with_embeddings,
            "missing_embeddings": total - with_embeddings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/subscription/status")
async def get_subscription_status(shop: str):
    """Get current subscription status and limits for a shop"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Check if subscription exists first
            existing = await conn.fetchrow("""
                SELECT id FROM user_subscriptions WHERE shop_domain = $1
            """, shop)
            
            # If no subscription exists, create starter plan
            if not existing:
                print(f"🔄 No subscription found for {shop}, initializing starter plan...")
                
                # Get starter plan ID
                starter_plan = await conn.fetchrow("""
                    SELECT id FROM subscription_plans WHERE name = 'starter' AND active = true
                """)
                
                if starter_plan:
                    # Insert new subscription with starter plan
                    await conn.execute("""
                        INSERT INTO user_subscriptions (
                            shop_domain, 
                            plan_id, 
                            billing_cycle_start, 
                            billing_cycle_end,
                            created_at
                        )
                        VALUES ($1, $2, NOW(), NOW() + INTERVAL '1 month', NOW())
                    """, shop, starter_plan['id'])
                    
                    print(f"✅ Auto-initialized starter subscription for {shop}")
            
            # Now check plan limits using database function
            result = await conn.fetchval("""
                SELECT check_plan_limits($1, 'general')
            """, shop)
            
            return result
    except Exception as e:
        print(f"❌ Subscription status error: {e}")
        # Return default starter plan if error
        return {
            "shop": shop,
            "plan": "starter",
            "current_products": 0,
            "max_products": 50,
            "current_searches": 0,
            "max_searches": 300,
            "products_exceeded": False,
            "searches_exceeded": False,
            "upgrade_required": False
        }

@app.get("/api/subscription/plans")
async def get_subscription_plans():
    """Get all available subscription plans"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            plans = await conn.fetch("""
                SELECT id, name, price, max_products, max_searches_per_month, features
                FROM subscription_plans 
                WHERE active = true 
                ORDER BY price ASC
            """)
            
            return {
                "plans": [dict(plan) for plan in plans]
            }
    except Exception as e:
        print(f"❌ Plans fetch error: {e}")
        return {"plans": []}

@app.post("/api/subscription/upgrade")
async def upgrade_subscription(request: dict):
    """Upgrade user subscription"""
    try:
        shop = request.get("shop")
        plan_name = request.get("plan")
        
        if not shop or not plan_name:
            raise HTTPException(status_code=400, detail="Shop and plan are required")
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Get plan ID
            plan = await conn.fetchrow("""
                SELECT id, name, price FROM subscription_plans 
                WHERE name = $1 AND active = true
            """, plan_name)
            
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found")
            
            # Update or insert subscription
            await conn.execute("""
                INSERT INTO user_subscriptions (shop_domain, plan_id, billing_cycle_start, billing_cycle_end)
                VALUES ($1, $2, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days')
                ON CONFLICT (shop_domain) DO UPDATE SET
                    plan_id = $2,
                    status = 'active',
                    billing_cycle_start = CURRENT_DATE,
                    billing_cycle_end = CURRENT_DATE + INTERVAL '30 days',
                    updated_at = CURRENT_TIMESTAMP
            """, shop, plan['id'])
            
            return {
                "success": True,
                "message": f"Successfully upgraded to {plan['name']} plan",
                "plan": plan['name'],
                "price": float(plan['price'])
            }
    except Exception as e:
        print(f"❌ Subscription upgrade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/usage/track")
async def track_usage(request: dict):
    """Track usage (searches, product syncs)"""
    try:
        shop = request.get("shop")
        usage_type = request.get("type", "search")  # search, product_sync
        count = request.get("count", 1)
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Track usage
            await conn.execute("""
                INSERT INTO usage_tracking (shop_domain, usage_type, usage_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (shop_domain, usage_type, usage_date) DO UPDATE SET
                    usage_count = usage_tracking.usage_count + $3
            """, shop, usage_type, count)
            
            # Update user subscription counters
            if usage_type == "search":
                await conn.execute("""
                    UPDATE user_subscriptions 
                    SET searches_this_month = searches_this_month + $2
                    WHERE shop_domain = $1
                """, shop, count)
            
            return {"success": True, "tracked": count}
    except Exception as e:
        print(f"❌ Usage tracking error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/subscription/initialize")
async def initialize_subscription(request: dict):
    """Initialize starter plan for new shop installation"""
    try:
        shop = request.get("shop")
        
        if not shop:
            raise HTTPException(status_code=400, detail="Shop domain is required")
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Check if subscription already exists
            existing = await conn.fetchrow("""
                SELECT id FROM user_subscriptions WHERE shop_domain = $1
            """, shop)
            
            if existing:
                return {"status": "already_exists", "message": "Subscription already initialized"}
            
            # Get starter plan ID
            starter_plan = await conn.fetchrow("""
                SELECT id FROM subscription_plans WHERE name = 'starter' AND active = true
            """)
            
            if not starter_plan:
                raise HTTPException(status_code=500, detail="Starter plan not found in database")
            
            # Insert new subscription with starter plan
            await conn.execute("""
                INSERT INTO user_subscriptions (
                    shop_domain, 
                    plan_id, 
                    billing_cycle_start, 
                    billing_cycle_end,
                    created_at
                )
                VALUES ($1, $2, NOW(), NOW() + INTERVAL '1 month', NOW())
            """, shop, starter_plan['id'])
            
            print(f"✅ Initialized starter subscription for {shop}")
            return {
                "status": "success", 
                "message": "Starter subscription initialized",
                "shop": shop,
                "plan": "starter"
            }
            
    except Exception as e:
        print(f"❌ Subscription initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/subscription/uninstall")
async def uninstall_cleanup(request: dict):
    """Clean up all shop data on app uninstall (GDPR compliant)"""
    try:
        shop = request.get("shop")
        
        if not shop:
            raise HTTPException(status_code=400, detail="Shop domain is required")
        
        pool = await db_client.connect()
        deleted_counts = {}
        
        async with pool.acquire() as conn:
            # 1. Delete usage tracking
            result = await conn.execute("""
                DELETE FROM usage_tracking WHERE shop_domain = $1
            """, shop)
            deleted_counts['usage_tracking'] = result.split()[1] if result else '0'
            
            # 2. Delete user subscription
            result = await conn.execute("""
                DELETE FROM user_subscriptions WHERE shop_domain = $1
            """, shop)
            deleted_counts['subscriptions'] = result.split()[1] if result else '0'
            
            # 3. Delete product embeddings (contains shop in metadata)
            result = await conn.execute("""
                DELETE FROM product_embeddings 
                WHERE metadata->>'shop' = $1
            """, shop)
            deleted_counts['products'] = result.split()[1] if result else '0'
            
            # 4. Delete search analytics (if shop-specific)
            # Note: Current schema doesn't have shop_domain in search_analytics
            # Consider adding it for better data isolation
            
            # 5. Delete app settings/config
            result = await conn.execute("""
                DELETE FROM app_settings 
                WHERE key = $1 OR key LIKE $2
            """, shop, f"{shop}_%")
            deleted_counts['settings'] = result.split()[1] if result else '0'
        
        print(f"🧹 Uninstall cleanup completed for {shop}: {deleted_counts}")
        
        return {
            "status": "success",
            "message": f"All data deleted for {shop}",
            "shop": shop,
            "deleted": deleted_counts
        }
        
    except Exception as e:
        print(f"❌ Uninstall cleanup error for {shop}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gdpr/customer-redact")
async def gdpr_customer_redact(request: dict):
    """GDPR: Redact customer-specific data"""
    try:
        shop = request.get("shop")
        customer_id = request.get("customer_id")
        customer_email = request.get("customer_email")
        
        if not shop:
            raise HTTPException(status_code=400, detail="Shop domain required")
        
        print(f"📋 GDPR Customer Redaction: shop={shop}, customer_id={customer_id}")
        
        # SearchAI doesn't store customer PII - only anonymous search queries
        # If you add customer tracking in the future, delete it here
        
        return {
            "status": "success",
            "message": "No customer PII stored by SearchAI",
            "shop": shop,
            "customer_id": customer_id
        }
        
    except Exception as e:
        print(f"❌ Customer redaction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gdpr/shop-redact")
async def gdpr_shop_redact(request: dict):
    """GDPR: Complete shop data redaction (same as uninstall but for GDPR)"""
    try:
        shop = request.get("shop")
        
        if not shop:
            raise HTTPException(status_code=400, detail="Shop domain required")
        
        print(f"🗑️ GDPR Shop Redaction for: {shop}")
        
        pool = await db_client.connect()
        deleted_counts = {}
        
        async with pool.acquire() as conn:
            # Delete ALL shop data
            result = await conn.execute("DELETE FROM usage_tracking WHERE shop_domain = $1", shop)
            deleted_counts['usage_tracking'] = result.split()[1] if result else '0'
            
            result = await conn.execute("DELETE FROM user_subscriptions WHERE shop_domain = $1", shop)
            deleted_counts['subscriptions'] = result.split()[1] if result else '0'
            
            result = await conn.execute("DELETE FROM product_embeddings WHERE metadata->>'shop' = $1", shop)
            deleted_counts['products'] = result.split()[1] if result else '0'
            
            result = await conn.execute("DELETE FROM app_settings WHERE key = $1 OR key LIKE $2", shop, f"{shop}_%")
            deleted_counts['settings'] = result.split()[1] if result else '0'
        
        print(f"✅ GDPR Shop Redaction completed for {shop}: {deleted_counts}")
        
        return {
            "status": "success",
            "message": f"All data permanently deleted for {shop}",
            "shop": shop,
            "deleted": deleted_counts,
            "gdpr_compliant": True
        }
        
    except Exception as e:
        print(f"❌ Shop redaction error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/extension-status")
async def get_extension_status():
    """Check if theme extension is active by looking for recent searches"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Check if there are any searches in the last 24 hours
            recent_searches = await conn.fetchval("""
                SELECT COUNT(*) FROM search_analytics 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            # If there are recent searches, extension is likely active
            # If no searches, extension might not be activated
            extension_active = recent_searches > 0
            
            return {
                "active": extension_active,
                "recent_searches": recent_searches,
                "status": "active" if extension_active else "inactive",
                "message": "Extension receiving searches" if extension_active else "No recent searches detected - extension may not be activated"
            }
    except Exception as e:
        print(f"❌ Extension status error: {e}")
        return {
            "active": False,
            "recent_searches": 0,
            "status": "unknown",
            "message": "Could not determine extension status"
        }

@app.post("/api/extension/ping")
async def extension_ping(request: dict):
    """Receive ping from theme extension to track when it's active"""
    try:
        shop = request.get('shop', '').replace('https://', '').replace('http://', '').split('/')[0]
        
        if not shop:
            return {"status": "error", "message": "Shop domain required"}
        
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Update or insert extension_last_active timestamp in app_settings
            await conn.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) 
                DO UPDATE SET value = $2, updated_at = NOW()
            """, f"{shop}:extension_last_active", request.get('timestamp', ''))
            
        return {
            "status": "success",
            "message": "Extension ping registered"
        }
    except Exception as e:
        print(f"❌ Extension ping error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/extension/status")
async def get_extension_status_new(shop: str):
    """Check if theme extension is active based on recent pings"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Get last ping timestamp
            last_ping = await conn.fetchval("""
                SELECT updated_at FROM app_settings 
                WHERE key = $1
            """, f"{shop}:extension_last_active")
            
            if not last_ping:
                return {
                    "active": False,
                    "status": "never_activated",
                    "message": "Extension has never been activated"
                }
            
            # Check if ping was within last 48 hours
            from datetime import datetime, timedelta
            is_active = (datetime.now() - last_ping) < timedelta(hours=48)
            
            return {
                "active": is_active,
                "last_seen": last_ping.isoformat(),
                "status": "active" if is_active else "inactive",
                "message": "Extension is active" if is_active else "Extension was active but not seen recently"
            }
    except Exception as e:
        print(f"❌ Extension status check error: {e}")
        return {
            "active": False,
            "status": "error",
            "message": str(e)
        }

@app.get("/api/sync-status")
async def get_sync_status():
    """Get sync status for smart sync UI"""
    try:
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM product_embeddings")
            with_embeddings = await conn.fetchval(
                "SELECT COUNT(*) FROM product_embeddings WHERE embedding IS NOT NULL"
            )
            needs_sync = total - with_embeddings
            
            # Show alert if there are products without embeddings
            show_alert = needs_sync > 0
            
            # Get some example products that need sync
            if needs_sync > 0:
                sample_products = await conn.fetch("""
                    SELECT title FROM product_embeddings 
                    WHERE embedding IS NULL 
                    LIMIT 3
                """)
                sample_titles = [p['title'] for p in sample_products]
            else:
                sample_titles = []
        
        return {
            "total_products": total,
            "with_embeddings": with_embeddings, 
            "needs_sync": needs_sync,
            "show_alert": show_alert,
            "status": "ready" if needs_sync == 0 else "needs_sync",
            "sample_products": sample_titles,
            "alert_message": f"🔄 {needs_sync} productos necesitan sincronización de embeddings" if show_alert else None
        }
    except Exception as e:
        print(f"❌ Sync status error: {e}")
        return {
            "total_products": 0,
            "with_embeddings": 0,
            "needs_sync": 0,
            "show_alert": False,
            "status": "error",
            "sample_products": [],
            "alert_message": None
        }

@app.post("/api/simulate-unsync")
async def simulate_unsync(request: dict):
    """Simulate products without embeddings for testing alerts"""
    try:
        count = request.get("count", 3)
        
        # Set some embeddings to NULL to simulate unsync'd products
        query = """
            UPDATE product_embeddings 
            SET embedding = NULL 
            WHERE id IN (
                SELECT id FROM product_embeddings 
                WHERE embedding IS NOT NULL 
                LIMIT $1
            )
        """
        
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.execute(query, count)
        
        # Get updated counts
        total = await conn.fetchval("SELECT COUNT(*) FROM product_embeddings")
        with_embeddings = await conn.fetchval("SELECT COUNT(*) FROM product_embeddings WHERE embedding IS NOT NULL")
        unsync_count = total - with_embeddings
        
        await conn.close()
        
        return {
            "message": f"Simulation completed: {unsync_count} products now need sync",
            "total_products": total,
            "with_embeddings": with_embeddings,
            "needs_sync": unsync_count,
            "success": True
        }
    
    except Exception as e:
        print(f"❌ Simulation error: {e}")
        return {
            "message": f"Simulation failed: {str(e)}",
            "success": False
        }

@app.get("/api/analytics")
async def get_analytics(days: int = 7, shop: str = None):
    """Get search analytics filtered by shop"""
    try:
        if not shop:
            raise HTTPException(400, "Missing shop parameter")
        stats = await db_client.get_search_stats(days=days, shop_domain=shop)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-product")
async def sync_single_product(product_id: str):
    """Sync a single product by ID to the search index"""
    try:
        print(f"🔍 Syncing product: {product_id}")
        
        # Get product from database
        product = await db_client.get_product_by_id(product_id)
        print(f"📄 Product data type: {type(product)}")
        print(f"📄 Product data: {product}")
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        
        # Handle both dict and row-like objects
        title = product.get('title', '') if hasattr(product, 'get') else getattr(product, 'title', '')
        description = product.get('description', '') if hasattr(product, 'get') else getattr(product, 'description', '')
        
        # Generate embeddings for this product
        product_text = f"{title} {description}"
        print(f"📝 Product text for embeddings: {product_text[:100]}...")
        
        # Get embeddings
        embedding = await embedding_gen.generate_embedding(product_text)
        if embedding:
            # Update the product with embeddings (REESCRIBE, no duplica)
            await db_client.update_product_embedding(product_id, embedding)
            
            return {
                "success": True,
                "message": f"Product '{title}' synchronized successfully",
                "product_id": product_id,
                "indexed": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate embeddings")
            
    except Exception as e:
        print(f"❌ Single product sync error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
async def get_products():
    """Get list of product IDs for testing"""
    try:
        products = await db_client.get_all_product_ids()
        return {"products": products}
    except Exception as e:
        print(f"❌ Get products error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class ProductsList(BaseModel):
    products: List[dict]

@app.post("/api/compare-shopify-products")
async def compare_shopify_products(request: dict):
    """Compare Shopify products with database and update"""
    try:
        shopify_products = request.get('products', [])
        shop = request.get('shop', '')
        
        # Get current products in DB with embedding status (FILTERED BY SHOP)
        db_products = await db_client.get_all_products_with_status(shop_domain=shop)
        db_products_dict = {p['product_id']: p for p in db_products}
        
        updated_products = []
        
        # Upsert all Shopify products into database
        for product in shopify_products:
            # Check if product already has embedding
            existing_product = db_products_dict.get(product['product_id'])
            
            # Detect if product data changed
            needs_update = False
            if existing_product:
                # Compare key fields safely
                title_changed = existing_product.get('title') != product['title']
                desc_changed = existing_product.get('description') != product.get('description', '')
                
                # Safe price comparison handling None values
                old_price = existing_product.get('price') or 0
                new_price = product.get('price') or 0
                price_changed = float(old_price) != float(new_price)
                
                needs_update = title_changed or desc_changed or price_changed
                
                if needs_update:
                    updated_products.append({
                        'product_id': product['product_id'],
                        'title': product['title'],
                        'changes': {
                            'title': title_changed,
                            'description': desc_changed,
                            'price': price_changed
                        }
                    })
            
            # Preserve existing embedding if product already exists
            # Only set to None for NEW products
            preserve_embedding = existing_product and existing_product.get('has_embedding')
            
            # Convert tags string to list if needed
            tags_list = product.get('tags', '').split(', ') if product.get('tags') else []
            
            # Only upsert basic info, don't touch embeddings if they exist
            # We need a different method that doesn't overwrite embeddings
            
            # Merge metadata: preserve incoming metadata (like handle) + add needs_resync flag
            product_metadata = product.get('metadata', {})
            if isinstance(product_metadata, dict):
                product_metadata['needs_resync'] = needs_update
            else:
                product_metadata = {'needs_resync': needs_update}
            
            await db_client.upsert_product_info(
                product_id=product['product_id'],
                shop_domain=shop,  # ✅ CRITICAL: Add shop isolation
                title=product['title'],
                description=product.get('description', ''),
                price=product.get('price', 0),
                vendor=product.get('vendor', ''),
                category=product.get('category', ''),
                tags=tags_list,
                metadata=product_metadata
            )
        
        # IMPORTANT: Generate embeddings for products that don't have them
        print(f"🧠 Generating embeddings for new products...")
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            # Get products without embeddings (FILTERED BY SHOP)
            products_without_embeddings = await conn.fetch("""
                SELECT product_id, title, description, vendor, category, tags
                FROM product_embeddings
                WHERE embedding IS NULL
                AND shop_domain = $1
            """, shop)
            
            if products_without_embeddings:
                print(f"   Found {len(products_without_embeddings)} products without embeddings")
                embedding_gen = EmbeddingGenerator()
                
                for prod in products_without_embeddings:
                    try:
                        # Create text for embedding
                        text_parts = [prod['title']]
                        if prod['description']:
                            text_parts.append(prod['description'])
                        if prod['category']:
                            text_parts.append(f"Category: {prod['category']}")
                        if prod['tags']:
                            text_parts.append(f"Tags: {', '.join(prod['tags'])}")
                        
                        text = " ".join(text_parts)
                        
                        # Generate embedding
                        embedding = await embedding_gen.generate_embedding(text)
                        
                        # Save embedding
                        embedding_str = f"[{','.join(map(str, embedding))}]"
                        await conn.execute("""
                            UPDATE product_embeddings
                            SET embedding = $1::vector, updated_at = CURRENT_TIMESTAMP
                            WHERE product_id = $2
                        """, embedding_str, prod['product_id'])
                        
                        print(f"   ✓ Generated embedding for {prod['product_id']}")
                    except Exception as e:
                        print(f"   ✗ Error generating embedding for {prod['product_id']}: {e}")
        
        return {
            "success": True,
            "total_shopify": len(shopify_products),
            "updated_products": len(updated_products),
            "embeddings_generated": len(products_without_embeddings) if products_without_embeddings else 0,
            "changes_detected": updated_products,
            "message": f"Productos sincronizados: {len(shopify_products)} productos. {len(updated_products)} con cambios detectados."
        }
    except Exception as e:
        print(f"❌ Compare Shopify products error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/regenerate-embeddings")
async def regenerate_embeddings():
    """Regenerate embeddings for products with needs_resync flag"""
    try:
        # Get products that need resync
        pool = await db_client.connect()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT product_id, title, description, vendor, category, tags
                FROM product_embeddings
                WHERE metadata->>'needs_resync' = 'true'
            """)
        
        if not rows:
            return {
                "success": True,
                "message": "No hay productos que necesiten regeneración",
                "regenerated_count": 0
            }
        
        regenerated_count = 0
        
        for row in rows:
            try:
                # Generate new embedding
                combined_text = f"{row['title']} {row['description']} {row['vendor']} {row['category']}"
                if row['tags']:
                    tags_str = ' '.join(row['tags']) if isinstance(row['tags'], list) else row['tags']
                    combined_text += f" {tags_str}"
                
                embedding = await embedding_gen.generate_embedding(combined_text)
                
                # Update product with new embedding and remove needs_resync flag
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE product_embeddings
                        SET embedding = $1,
                            metadata = metadata - 'needs_resync'
                        WHERE product_id = $2
                    """, embedding, row['product_id'])
                
                regenerated_count += 1
                print(f"✅ Regenerated embedding for: {row['title']}")
                
            except Exception as product_error:
                print(f"⚠️ Failed to regenerate embedding for {row['product_id']}: {product_error}")
                continue
        
        return {
            "success": True,
            "message": f"Embeddings regenerados exitosamente",
            "regenerated_count": regenerated_count,
            "total_found": len(rows)
        }
        
    except Exception as e:
        print(f"❌ Regenerate embeddings error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-shopify-products")
async def sync_shopify_products():
    """Fetch products from Shopify and update database"""
    try:
        # This would normally call Shopify GraphQL API
        # For now, we'll just trigger a database refresh
        # In production, you'd integrate with Shopify Admin API
        
        # Get products that need sync
        synced_products = await db_client.get_all_products_with_status()
        
        return {
            "success": True,
            "message": f"Productos actualizados desde Shopify",
            "total_products": len(synced_products),
            "note": "Endpoint listo para integración con Shopify Admin API"
        }
    except Exception as e:
        print(f"❌ Sync Shopify products error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products-comparison")
async def get_products_comparison(shop: str = None):
    """Compare Shopify products with synced products in database, filtered by shop"""
    try:
        if not shop:
            raise HTTPException(400, "Missing shop parameter")
        
        # Get all products from database with their sync status (FILTERED BY SHOP)
        synced_products = await db_client.get_all_products_with_status(shop_domain=shop)
        
        # Count stats from products
        total_products = len(synced_products)
        indexed_products = len([p for p in synced_products if p.get("has_embedding")])
        missing_embeddings = total_products - indexed_products
        
        return {
            "total_in_shopify": total_products,
            "total_synced": indexed_products,
            "missing_sync": missing_embeddings,
            "products": synced_products,
            "summary": {
                "ready": indexed_products,
                "needs_sync": missing_embeddings
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Products comparison error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================
# CONFIGURATION
# ==================

class ConfigModel(BaseModel):
    config: dict

@app.post("/api/config/initialize")
async def initialize_config(request: dict):
    """Initialize default configuration for new shop installation"""
    try:
        shop = request.get("shop")
        
        if not shop:
            raise HTTPException(status_code=400, detail="Shop domain is required")
        
        # Check if config already exists
        existing_config = await db_client.get_app_config(shop=shop)
        
        # Check if it's using defaults (empty config means defaults)
        if existing_config.get("ai_search_enabled") is not None:
            return {"status": "already_exists", "message": "Configuration already initialized"}
        
        # Default configuration (5% threshold for better recall)
        default_config = {
            "ai_search_enabled": True,
            "autocorrect": True,
            "results_limit": "unlimited",
            "similarity_threshold": 5,
            "exclude_out_of_stock": False,
            "exclude_archived": False,
            "language": "es"
        }
        
        # Save default configuration
        await db_client.save_app_config(default_config, shop=shop)
        
        return {
            "status": "success",
            "message": "Default configuration initialized",
            "config": default_config
        }
        
    except Exception as e:
        print(f"❌ Error initializing config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config(shop: str):
    """Get current search configuration from database (per-shop)"""
    try:
        config = await db_client.get_app_config(shop=shop)
        return {"config": config, "shop": shop}
    except Exception as e:
        print(f"❌ Error getting config for {shop}: {e}")
        # Return defaults on error
        return {
            "config": {
                "ai_search_enabled": True,
                "autocorrect": True,
                "results_limit": "unlimited",
                "similarity_threshold": 5,
                "exclude_out_of_stock": False,
                "exclude_archived": False,
                "language": "es"
            },
            "shop": shop
        }

@app.post("/api/config")
async def save_config(data: ConfigModel, shop: str):
    """Save search configuration to database (per-shop)"""
    try:
        await db_client.save_app_config(data.config, shop=shop)
        return {"success": True, "config": data.config, "shop": shop}
    except Exception as e:
        print(f"❌ Error saving config for {shop}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
