"""
Generate embeddings for products using OpenAI
"""

import asyncio
import os
from typing import List, Dict
from openai import AsyncOpenAI
from database.connection import db_client


class EmbeddingGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = "text-embedding-3-small"  # 1536 dimensions
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    async def generate_product_embedding(self, product: Dict) -> List[float]:
        """
        Generate embedding for product combining title, description, tags
        
        Args:
            product: Dict with 'title', 'description', 'tags', etc.
        
        Returns:
            Embedding vector
        """
        # Combine relevant text fields
        text_parts = [product.get('title', '')]
        
        if product.get('description'):
            text_parts.append(product['description'])
        
        if product.get('vendor'):
            text_parts.append(f"Brand: {product['vendor']}")
        
        if product.get('category'):
            text_parts.append(f"Category: {product['category']}")
        
        if product.get('tags'):
            tags = product['tags'] if isinstance(product['tags'], list) else []
            text_parts.append(f"Tags: {', '.join(tags)}")
        
        combined_text = " ".join(text_parts)
        return await self.generate_embedding(combined_text)
    
    async def sync_product_to_db(self, product: Dict) -> bool:
        """
        Generate embedding and sync product to database
        
        Args:
            product: Product dict with at minimum 'product_id' and 'title'
        
        Returns:
            Success boolean
        """
        try:
            # Generate embedding
            embedding = await self.generate_product_embedding(product)
            
            # Upsert to database
            success = await db_client.upsert_product(
                product_id=product['product_id'],
                title=product['title'],
                embedding=embedding,
                description=product.get('description'),
                price=product.get('price'),
                vendor=product.get('vendor'),
                category=product.get('category'),
                tags=product.get('tags'),
                metadata=product.get('metadata')
            )
            
            if success:
                print(f"✅ Synced product: {product['product_id']} - {product['title']}")
            else:
                print(f"❌ Failed to sync: {product['product_id']}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error syncing {product.get('product_id')}: {str(e)}")
            return False
    
    async def sync_products_batch(self, products: List[Dict]) -> Dict:
        """
        Sync multiple products in batch
        
        Returns:
            Stats dict with success/failure counts
        """
        print(f"\n🔄 Syncing {len(products)} products to database...")
        
        tasks = [self.sync_product_to_db(product) for product in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        failure_count = len(results) - success_count
        
        print(f"\n📊 Sync complete: {success_count} success, {failure_count} failures")
        
        return {
            "total": len(products),
            "success": success_count,
            "failures": failure_count
        }


# Test/Demo function
async def generate_embeddings_for_existing_products():
    """Generate embeddings for products already in database"""
    
    print("🚀 Generating embeddings for existing products...\n")
    
    # Sample products (in real app, fetch from Shopify)
    products = [
        {
            "product_id": "prod_001",
            "title": "Nike Air Zoom Pegasus 40",
            "description": "Comfortable running shoes with responsive cushioning perfect for daily training runs",
            "price": 89.99,
            "vendor": "Nike",
            "category": "Running Shoes",
            "tags": ["running", "sports", "training"],
            "metadata": {
                "in_stock": True,
                "stock_quantity": 47,
                "sizes": ["7", "8", "9", "10", "11", "12"]
            }
        },
        {
            "product_id": "prod_002",
            "title": "Adidas Ultraboost 22",
            "description": "Premium running shoes designed for long-distance comfort with boost technology",
            "price": 94.99,
            "vendor": "Adidas",
            "category": "Running Shoes",
            "tags": ["running", "premium", "long-distance"],
            "metadata": {
                "in_stock": True,
                "stock_quantity": 32,
                "sizes": ["8", "9", "10", "11"]
            }
        }
    ]
    
    generator = EmbeddingGenerator()
    stats = await generator.sync_products_batch(products)
    
    return stats


if __name__ == "__main__":
    asyncio.run(generate_embeddings_for_existing_products())
