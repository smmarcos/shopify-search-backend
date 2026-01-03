"""
SmartSearch AI - Search Agent with Function Calling
Complete working example with tools.
"""

from agents import Agent, Runner
from agents.tool import FunctionTool
from typing import List, Dict
import asyncio
import os
import json

# ==========================================
# TOOL FUNCTIONS
# ==========================================

async def vector_search(query: str, store_id: str, limit: int = 20) -> List[Dict]:
    """
    Semantic search for products using vector embeddings.
    
    Args:
        query: Natural language search query
        store_id: Shopify store identifier
        limit: Maximum results
    
    Returns:
        List of matching products
    """
    print(f"🔍 vector_search called: '{query}' (store: {store_id})")
    
    # Mock data for demo
    products = [
        {
            "id": "prod_001",
            "title": "Nike Air Zoom Pegasus 40",
            "description": "Comfortable cushioning for daily running",
            "price": 89.99,
            "vendor": "Nike",
            "tags": ["running", "sports"],
            "similarity": 0.92
        },
        {
            "id": "prod_002",
            "title": "Adidas Ultraboost 22",
            "description": "Premium running shoes for long distances",
            "price": 95.00,
            "vendor": "Adidas",
            "tags": ["running", "premium"],
            "similarity": 0.89
        },
        {
            "id": "prod_003",
            "title": "New Balance Fresh Foam 1080",
            "description": "Maximum cushioning for comfort",
            "price": 99.99,
            "vendor": "New Balance",
            "tags": ["running", "comfort"],
            "similarity": 0.87
        }
    ]
    
    return products[:limit]


async def apply_filters(
    products: List[Dict],
    max_price: float = None,
    min_price: float = None,
    in_stock: bool = True
) -> List[Dict]:
    """
    Apply business filters to products.
    
    Args:
        products: List of products
        max_price: Maximum price filter
        min_price: Minimum price filter
        in_stock: Only show in-stock items
    
    Returns:
        Filtered products
    """
    print(f"💰 apply_filters called: max_price=${max_price}, min_price=${min_price}")
    
    filtered = products.copy()
    
    if max_price:
        filtered = [p for p in filtered if p['price'] <= max_price]
    
    if min_price:
        filtered = [p for p in filtered if p['price'] >= min_price]
    
    print(f"   → Filtered to {len(filtered)} products")
    return filtered


async def track_analytics(query: str, results_count: int) -> Dict:
    """
    Track search analytics.
    
    Args:
        query: Search query
        results_count: Number of results
    
    Returns:
        Confirmation
    """
    print(f"📊 track_analytics called: '{query}' → {results_count} results")
    return {"tracked": True, "query": query, "count": results_count}


# ==========================================
# CREATE AGENT WITH TOOLS
# ==========================================

# Convert functions to tools
tools = [
    FunctionTool(vector_search),
    FunctionTool(apply_filters),
    FunctionTool(track_analytics),
]

search_agent = Agent(
    name="SearchAgent",
    model="gpt-4o-mini",
    instructions="""
    You are an intelligent ecommerce search assistant.
    
    When a user searches for products:
    1. Use vector_search to find relevant products
    2. If they mention price constraints, use apply_filters
    3. Always call track_analytics to log the search
    4. Explain why you chose these products
    
    Be conversational and helpful. Focus on understanding user intent.
    """,
    tools=tools
)

# ==========================================
# TEST EXAMPLES
# ==========================================

async def example_1():
    """Simple search"""
    print("\n" + "="*60)
    print("Example 1: Simple Search")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "Show me comfortable running shoes"
    )
    
    print("\n📋 Agent Response:")
    print(result.final_output)


async def example_2():
    """Search with price filter"""
    print("\n" + "="*60)
    print("Example 2: Search with Price Filter")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "I need running shoes under $95"
    )
    
    print("\n📋 Agent Response:")
    print(result.final_output)


async def example_3():
    """Complex query"""
    print("\n" + "="*60)
    print("Example 3: Complex Query")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "What are the best running shoes for marathons that won't break the bank?"
    )
    
    print("\n📋 Agent Response:")
    print(result.final_output)


async def main():
    print("\n🤖 SmartSearch AI - Agent with Function Calling")
    print("Using OpenAI Agents SDK\n")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        return
    
    print("✅ OpenAI API key configured")
    print("✅ Tools registered: vector_search, apply_filters, track_analytics\n")
    
    # Run examples
    await example_1()
    await example_2()
    await example_3()
    
    print("\n" + "="*60)
    print("✅ All examples completed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Connect to real pgvector database")
    print("2. Add more tools (recommendations, product details)")
    print("3. Implement MCP server for Shopify")
    print("4. Add handoffs to specialized agents\n")


if __name__ == "__main__":
    asyncio.run(main())
