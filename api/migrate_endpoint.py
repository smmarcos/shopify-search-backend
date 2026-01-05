"""
Endpoint API para migrar planes antiguos a nuevos
"""
from fastapi import HTTPException

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
