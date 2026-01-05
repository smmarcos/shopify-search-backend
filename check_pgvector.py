#!/usr/bin/env python3
"""Check if pgvector extension is installed"""
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect("postgresql://postgres:fMmLRDdaoCKxRiMPVUWOsyZlWGSnjPkM@autorack.proxy.rlwy.net:55632/railway")
    
    try:
        # Check extension
        result = await conn.fetch("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
        if result:
            print(f"✅ pgvector extension installed: version {result[0]['extversion']}")
        else:
            print("❌ pgvector extension NOT installed")
            
        # Check if embedding column has vector type
        result2 = await conn.fetch("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'product_embeddings' AND column_name = 'embedding'
        """)
        if result2:
            print(f"✅ embedding column type: {result2[0]['data_type']} (udt: {result2[0]['udt_name']})")
        
        # Try a simple vector operation
        try:
            test = await conn.fetchval("SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector")
            print(f"✅ Vector operation works: {test}")
        except Exception as e:
            print(f"❌ Vector operation failed: {e}")
            
    finally:
        await conn.close()

asyncio.run(check())
