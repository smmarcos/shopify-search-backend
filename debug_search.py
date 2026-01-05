"""
Debug script to test vector search locally
"""
import asyncio
import asyncpg
import os
from openai import AsyncOpenAI

async def test_search():
    # Connect to database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found")
        return
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Generate embedding for query
    openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    query = "camiseta blanca"
    print(f"🔍 Query: {query}")
    
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    
    embedding = response.data[0].embedding
    embedding_str = f"[{','.join(map(str, embedding))}]"
    
    print(f"✅ Generated embedding ({len(embedding)} dimensions)")
    
    # Test 1: Search WITHOUT shop filter
    print("\n" + "="*60)
    print("TEST 1: Search WITHOUT shop filter")
    print("="*60)
    
    results = await conn.fetch("""
        SELECT 
            product_id,
            title,
            1 - (embedding <=> CAST($1 AS vector)) as similarity_score,
            metadata->>'shop' as shop_value
        FROM product_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST($1 AS vector)
        LIMIT 5
    """, embedding_str)
    
    if not results:
        print("❌ NO RESULTS")
    else:
        for r in results:
            print(f"  {r['product_id']}: {r['title']}")
            print(f"    Score: {float(r['similarity_score']):.4f}")
            print(f"    Shop: {r['shop_value']}")
            print()
    
    # Test 2: Search WITH shop filter
    print("\n" + "="*60)
    print("TEST 2: Search WITH shop filter (test.myshopify.com)")
    print("="*60)
    
    results = await conn.fetch("""
        SELECT 
            product_id,
            title,
            1 - (embedding <=> CAST($1 AS vector)) as similarity_score,
            metadata->>'shop' as shop_value
        FROM product_embeddings
        WHERE embedding IS NOT NULL
        AND metadata->>'shop' = $2
        ORDER BY embedding <=> CAST($1 AS vector)
        LIMIT 5
    """, embedding_str, "test.myshopify.com")
    
    if not results:
        print("❌ NO RESULTS")
    else:
        for r in results:
            print(f"  {r['product_id']}: {r['title']}")
            print(f"    Score: {float(r['similarity_score']):.4f}")
            print(f"    Shop: {r['shop_value']}")
            print()
    
    # Test 3: Check threshold filtering
    print("\n" + "="*60)
    print("TEST 3: Check if scores pass 0.7 threshold")
    print("="*60)
    
    results = await conn.fetch("""
        SELECT 
            product_id,
            title,
            1 - (embedding <=> CAST($1 AS vector)) as similarity_score,
            metadata->>'shop' as shop_value
        FROM product_embeddings
        WHERE embedding IS NOT NULL
        AND metadata->>'shop' = $2
        AND (1 - (embedding <=> CAST($1 AS vector))) >= 0.7
        ORDER BY embedding <=> CAST($1 AS vector)
        LIMIT 5
    """, embedding_str, "test.myshopify.com")
    
    if not results:
        print("❌ NO RESULTS pass 0.7 threshold")
        print("💡 Similarity threshold might be too high!")
    else:
        print(f"✅ {len(results)} results pass 0.7 threshold:")
        for r in results:
            print(f"  {r['product_id']}: {r['title']}")
            print(f"    Score: {float(r['similarity_score']):.4f}")
            print()
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_search())
