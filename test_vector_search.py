"""
Quick test of vector search
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_client
from database.embeddings import EmbeddingGenerator

async def test():
    await db_client.connect()
    
    # Generate test embedding
    gen = EmbeddingGenerator()
    embedding = await gen.generate_embedding("comfortable running shoes")
    
    print(f"✅ Generated embedding: {len(embedding)} dimensions")
    print(f"First 5 values: {embedding[:5]}")
    
    # Search
    results = await db_client.vector_search(
        query_embedding=embedding,
        limit=3
    )
    
    print(f"\n✅ Found {len(results)} products:")
    for r in results:
        print(f"  - {r['title']}: ${r['price']} (score: {r.get('similarity_score', 'N/A')})")
    
    await db_client.disconnect()

if __name__ == "__main__":
    # Set OPENAI_API_KEY environment variable before running
    asyncio.run(test())
