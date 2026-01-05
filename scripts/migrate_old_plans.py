#!/usr/bin/env python3
"""
Migrar usuarios de planes antiguos (free/basic/pro/business) a nuevos (starter/launch/growth/scale)
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate_plans():
    # Database connection
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "autorack.proxy.rlwy.net"),
        port=int(os.getenv("DB_PORT", 55632)),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "railway")
    )
    
    try:
        print("🔄 Starting plan migration...\n")
        
        # Plan mapping
        plan_mapping = {
            'free': 'launch',      # Free users upgraded to Launch (better value)
            'basic': 'launch',     # Basic = Launch (same tier)
            'pro': 'growth',       # Pro = Growth (same tier)
            'business': 'scale'    # Business = Scale (same tier)
        }
        
        for old_plan, new_plan in plan_mapping.items():
            # Get old plan ID
            old_plan_row = await conn.fetchrow(
                "SELECT id FROM subscription_plans WHERE name = $1", 
                old_plan
            )
            
            if not old_plan_row:
                print(f"⚠️  Old plan '{old_plan}' not found, skipping...")
                continue
            
            # Get new plan ID
            new_plan_row = await conn.fetchrow(
                "SELECT id, price, max_products, max_searches_per_month FROM subscription_plans WHERE name = $1", 
                new_plan
            )
            
            if not new_plan_row:
                print(f"❌ New plan '{new_plan}' not found!")
                continue
            
            # Count users on old plan
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_subscriptions WHERE plan_id = $1",
                old_plan_row['id']
            )
            
            if count == 0:
                print(f"ℹ️  No users on '{old_plan}' plan")
                continue
            
            # Update users to new plan
            await conn.execute("""
                UPDATE user_subscriptions 
                SET plan_id = $1, updated_at = NOW()
                WHERE plan_id = $2
            """, new_plan_row['id'], old_plan_row['id'])
            
            print(f"✅ Migrated {count} users from '{old_plan}' to '{new_plan}'")
            print(f"   → Price: ${new_plan_row['price']}/month")
            print(f"   → Products: {new_plan_row['max_products']}")
            print(f"   → Searches: {new_plan_row['max_searches_per_month']}/month\n")
        
        # Summary
        print("\n📊 Migration Summary:")
        result = await conn.fetch("""
            SELECT sp.name, COUNT(us.id) as user_count
            FROM subscription_plans sp
            LEFT JOIN user_subscriptions us ON sp.id = us.plan_id
            WHERE sp.active = true
            GROUP BY sp.name, sp.price
            ORDER BY sp.price ASC
        """)
        
        print("\nCurrent plan distribution:")
        for row in result:
            print(f"  {row['name'].upper()}: {row['user_count']} users")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_plans())
