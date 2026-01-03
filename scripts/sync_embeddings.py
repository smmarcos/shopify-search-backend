#!/usr/bin/env python3
"""
Sync products from Shopify - generates embeddings for products without them
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_client
from database.embeddings import EmbeddingGenerator


async def sync_missing_embeddings():
    """Generate embeddings for products that don't have them"""
    
    embedding_gen = EmbeddingGenerator()
    pool = await db_client.connect()
    
    # Get products without embeddings
    query = """
        SELECT product_id, title, description, price, vendor, category, tags, metadata
        FROM product_embeddings
        WHERE embedding IS NULL
    """
    
    async with pool.acquire() as conn:
        products = await conn.fetch(query)
    
    synced = 0
    for product in products:
        try:
            searchable_text = f"{product['title']}. {product['description'] or ''}"
            embedding = await embedding_gen.generate_embedding(searchable_text)
            
            await db_client.upsert_product(
                product_id=product['product_id'],
                title=product['title'],
                description=product['description'],
                price=float(product['price']) if product['price'] else 0.0,
                vendor=product['vendor'],
                category=product['category'],
                tags=product['tags'],
                embedding=embedding,
                metadata=product['metadata'] if isinstance(product['metadata'], dict) else {}
            )
            synced += 1
            print(f"✅ {product['product_id']}")
        except Exception as e:
            print(f"❌ {product['product_id']}: {e}")
    
    return synced, len(products)


if __name__ == '__main__':
    synced, total = asyncio.run(sync_missing_embeddings())
    print(f"\nSynced {synced}/{total} products")
