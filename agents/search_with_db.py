"""
SmartSearch AI Agent - Connected to Real pgvector Database
"""

import asyncio
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import Agent, Runner, function_tool
from openai import AsyncOpenAI
from database.connection import db_client
from database.embeddings import EmbeddingGenerator


# Initialize clients
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
embedding_gen = EmbeddingGenerator()


# ====================
# TOOLS WITH REAL DATABASE
# ====================

@function_tool
async def vector_search(query: str, max_results: int = 5, max_price: float = None) -> str:
    """
    Search products using semantic vector search.
    
    Args:
        query: Natural language search query from user
        max_results: Maximum number of products to return
        max_price: Optional maximum price filter
    
    Returns:
        JSON string with matching products
    """
    print(f"🔍 vector_search: '{query}' (max_results={max_results}, max_price={max_price})")
    
    try:
        # Generate embedding for the search query
        query_embedding = await embedding_gen.generate_embedding(query)
        
        # Search in database
        results = await db_client.vector_search(
            query_embedding=query_embedding,
            limit=max_results,
            max_price=max_price,
            in_stock_only=True
        )
        
        # Track analytics
        await db_client.track_search(
            query=query,
            results_count=len(results)
        )
        
        # Format results
        products = []
        for row in results:
            # Safely handle similarity_score which might be None
            similarity = row.get('similarity_score') or row.get('similarity')
            similarity_score = round(float(similarity), 3) if similarity is not None else 0.0
            
            product = {
                "id": row['product_id'],
                "title": row['title'],
                "description": row['description'],
                "price": float(row['price']) if row['price'] is not None else 0.0,
                "vendor": row['vendor'],
                "category": row['category'],
                "similarity_score": similarity_score,
                "in_stock": row['metadata'].get('in_stock', False) if isinstance(row['metadata'], dict) else False,
                "stock_quantity": row['metadata'].get('stock_quantity', 0) if isinstance(row['metadata'], dict) else 0
            }
            products.append(product)
        
        print(f"   → Found {len(products)} products from database")
        
        return json.dumps({
            "query": query,
            "results": products,
            "total": len(products)
        }, indent=2)
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return json.dumps({
            "error": str(e),
            "results": []
        })


@function_tool
async def get_product_details(product_id: str) -> str:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: The unique product identifier
    
    Returns:
        Detailed product information as JSON
    """
    print(f"📦 get_product_details: '{product_id}'")
    
    try:
        product = await db_client.get_product_by_id(product_id)
        
        if not product:
            return json.dumps({"error": "Product not found"})
        
        details = {
            "id": product['product_id'],
            "title": product['title'],
            "description": product['description'],
            "price": float(product['price']) if product['price'] is not None else 0.0,
            "vendor": product['vendor'],
            "category": product['category'],
            "tags": product['tags'],
            "in_stock": product['metadata'].get('in_stock', False),
            "stock_quantity": product['metadata'].get('stock_quantity', 0),
            "sizes": product['metadata'].get('sizes', [])
        }
        
        return json.dumps(details, indent=2)
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return json.dumps({"error": str(e)})


@function_tool
async def get_search_analytics() -> str:
    """
    Get search analytics and trending queries.
    
    Returns:
        Analytics data as JSON
    """
    print(f"📊 get_search_analytics")
    
    try:
        stats = await db_client.get_search_stats(days=7)
        return json.dumps(stats, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ====================
# AGENT CONFIGURATION
# ====================

search_agent = Agent(
    name="SmartSearch AI with Database",
    instructions="""
    You are an intelligent e-commerce search assistant connected to a real product database.
    
    Your capabilities:
    1. Semantic search using vector embeddings (vector_search)
    2. Get detailed product information (get_product_details)
    3. Access search analytics (get_search_analytics)
    
    When users search:
    - Use vector_search to find semantically similar products
    - Consider their budget constraints (use max_price parameter)
    - Present results conversationally
    - If they ask for details, use get_product_details
    
    Always be helpful and explain what you found in natural language.
    """,
    tools=[vector_search, get_product_details, get_search_analytics],
    model="gpt-4o-mini"
)


# ====================
# TEST SCENARIOS
# ====================

async def test_database_agent():
    """Test agent with real database"""
    
    print("\n" + "="*70)
    print("🚀 SMARTSEARCH AI - CONNECTED TO PGVECTOR DATABASE")
    print("="*70 + "\n")
    
    try:
        # Connect to database
        await db_client.connect()
        print("✅ Connected to database\n")
        
        # Test 1: Semantic search
        print("\n📋 TEST 1: Semantic search for running shoes")
        print("-" * 70)
        result = await Runner.run(
            search_agent,
            input="I need comfortable shoes for jogging in the morning"
        )
        print(f"\n✅ Agent Response:\n{result.final_output}\n")
        
        # Test 2: Search with budget
        print("\n📋 TEST 2: Search with price constraint")
        print("-" * 70)
        result = await Runner.run(
            search_agent,
            input="Show me running shoes under $100"
        )
        print(f"\n✅ Agent Response:\n{result.final_output}\n")
        
        # Test 3: Product details
        print("\n📋 TEST 3: Get specific product details")
        print("-" * 70)
        result = await Runner.run(
            search_agent,
            input="Tell me more about prod_001"
        )
        print(f"\n✅ Agent Response:\n{result.final_output}\n")
        
        print("="*70)
        print("✅ ALL TESTS COMPLETED!")
        print("="*70)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        await db_client.disconnect()
        print("\n✅ Database connection closed")


if __name__ == "__main__":
    # Verify environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found")
        exit(1)
    
    print(f"✅ OpenAI API Key: {os.environ.get('OPENAI_API_KEY')[:15]}...")
    
    # Run tests
    asyncio.run(test_database_agent())
