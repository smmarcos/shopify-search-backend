#!/usr/bin/env python3
"""Test direct SQL query to verify syntax works"""
import asyncio
import asyncpg
import os
from database.embeddings import EmbeddingGenerator

async def test_query():
    # Connect to database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return
    
    conn = await asyncpg.connect(db_url)
    
    try:
        # Generate embedding
        embedding_gen = EmbeddingGenerator()
        query_embedding = await embedding_gen.generate_embedding("camiseta blanca")
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        print(f"✅ Embedding generated, length: {len(query_embedding)}")
        print(f"📝 Embedding string first 50 chars: {embedding_str[:50]}")
        
        # Test 1: Static query (like test-search)
        print("\n🧪 Test 1: Static query with CAST($1 AS vector)")
        results1 = await conn.fetch("""
            SELECT 
                product_id,
                title,
                1 - (embedding <=> CAST($1 AS vector)) as similarity_score
            FROM product_embeddings
            WHERE embedding IS NOT NULL
            AND metadata->>'shop' = $2
            ORDER BY embedding <=> CAST($1 AS vector)
            LIMIT 10
        """, embedding_str, "test.myshopify.com")
        
        print(f"✅ Test 1 passed! Got {len(results1)} results")
        if results1:
            print(f"   Best: {results1[0]['title']} (score: {results1[0]['similarity_score']:.4f})")
        
        # Test 2: Dynamic WHERE clause
        print("\n🧪 Test 2: Dynamic WHERE clause")
        shop = "test.myshopify.com"
        where_clause = f"WHERE metadata->>'shop' = $2 AND embedding IS NOT NULL"
        
        query = f"""
            SELECT 
                product_id,
                title,
                1 - (embedding <=> CAST($1 AS vector)) as similarity_score
            FROM product_embeddings
            {where_clause}
            ORDER BY embedding <=> CAST($1 AS vector)
            LIMIT 10
        """
        
        print(f"📄 Query: {query[:200]}...")
        results2 = await conn.fetch(query, embedding_str, shop)
        
        print(f"✅ Test 2 passed! Got {len(results2)} results")
        if results2:
            print(f"   Best: {results2[0]['title']} (score: {results2[0]['similarity_score']:.4f})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_query())
