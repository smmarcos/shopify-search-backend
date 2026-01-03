"""
SmartSearch AI - Search Agent
Modern implementation using OpenAI Agents SDK with function calling.
"""

from agents import Agent, Runner
from agents.tool import Tool
from typing import List, Dict, Optional
import asyncio
import json
import os
from datetime import datetime

# ==========================================
# AGENT TOOLS (Function Calling)
# ==========================================

@Tool
async def vector_search(
    query: str,
    store_id: str,
    limit: int = 20,
    similarity_threshold: float = 0.7
) -> List[Dict]:
    """
    Semantic search for products using vector embeddings.
    
    This tool searches products based on semantic similarity, understanding
    the intent behind natural language queries like "comfortable running shoes"
    or "gift for mom under $50".
    
    Args:
        query: Natural language search query from user
        store_id: Shopify store identifier
        limit: Maximum number of results to return (default 20)
        similarity_threshold: Minimum similarity score 0-1 (default 0.7)
    
    Returns:
        List of products with similarity scores
    """
    # TODO: Connect to pgvector database
    # For now, return mock data
    
    print(f"🔍 Searching for: '{query}' in store {store_id}")
    
    # Simulate vector search results
    mock_products = [
        {
            "id": "prod_001",
            "title": "Nike Air Zoom Pegasus 40",
            "description": "Comfortable running shoes with responsive cushioning",
            "price": 129.99,
            "currency": "USD",
            "image_url": "https://example.com/nike-pegasus.jpg",
            "tags": ["running", "sports", "footwear"],
            "vendor": "Nike",
            "available": True,
            "inventory": 45,
            "similarity": 0.92
        },
        {
            "id": "prod_002", 
            "title": "Adidas Ultraboost 22",
            "description": "Premium running sneakers for long distances",
            "price": 189.99,
            "currency": "USD",
            "image_url": "https://example.com/adidas-ultraboost.jpg",
            "tags": ["running", "premium", "marathon"],
            "vendor": "Adidas",
            "available": True,
            "inventory": 23,
            "similarity": 0.89
        },
        {
            "id": "prod_003",
            "title": "New Balance Fresh Foam 1080",
            "description": "Cushioned running shoes for comfort",
            "price": 149.99,
            "currency": "USD",
            "image_url": "https://example.com/nb-1080.jpg",
            "tags": ["running", "comfort"],
            "vendor": "New Balance",
            "available": True,
            "inventory": 67,
            "similarity": 0.87
        }
    ]
    
    # Filter by threshold
    results = [p for p in mock_products if p['similarity'] >= similarity_threshold]
    
    return results[:limit]


@Tool
async def apply_business_filters(
    products: List[Dict],
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    tags: Optional[List[str]] = None,
    vendors: Optional[List[str]] = None,
    in_stock_only: bool = True
) -> List[Dict]:
    """
    Apply business rules and filters to search results.
    
    Filters products based on price range, tags, vendors, and stock availability.
    This ensures results match the user's constraints.
    
    Args:
        products: List of products from vector search
        max_price: Maximum price filter
        min_price: Minimum price filter
        tags: Required tags (any match)
        vendors: Allowed vendors
        in_stock_only: Only show products with inventory > 0
    
    Returns:
        Filtered list of products
    """
    filtered = products.copy()
    
    if max_price is not None:
        filtered = [p for p in filtered if p['price'] <= max_price]
        print(f"💰 Filtered by max price ${max_price}: {len(filtered)} products")
    
    if min_price is not None:
        filtered = [p for p in filtered if p['price'] >= min_price]
        print(f"💰 Filtered by min price ${min_price}: {len(filtered)} products")
    
    if tags:
        filtered = [
            p for p in filtered 
            if any(tag in p.get('tags', []) for tag in tags)
        ]
        print(f"🏷️  Filtered by tags {tags}: {len(filtered)} products")
    
    if vendors:
        filtered = [p for p in filtered if p['vendor'] in vendors]
        print(f"🏢 Filtered by vendors {vendors}: {len(filtered)} products")
    
    if in_stock_only:
        filtered = [p for p in filtered if p.get('inventory', 0) > 0]
        print(f"📦 Filtered in-stock only: {len(filtered)} products")
    
    return filtered


@Tool
async def re_rank_by_business_rules(
    products: List[Dict],
    boost_in_stock: float = 1.2,
    boost_price_range: Optional[tuple] = None,
    boost_vendors: Optional[List[str]] = None
) -> List[Dict]:
    """
    Re-rank search results based on business priorities.
    
    Adjusts product ranking to prioritize:
    - Products in stock
    - Preferred price ranges
    - Strategic vendors
    - High margins (if available)
    
    Args:
        products: Filtered products from previous steps
        boost_in_stock: Multiplier for in-stock products (default 1.2)
        boost_price_range: Tuple of (min, max) to boost
        boost_vendors: List of vendors to prioritize
    
    Returns:
        Re-ranked products with updated scores
    """
    for product in products:
        score = product['similarity']
        
        # Boost in-stock items
        if product.get('inventory', 0) > 0:
            score *= boost_in_stock
        
        # Boost preferred price range
        if boost_price_range:
            min_p, max_p = boost_price_range
            if min_p <= product['price'] <= max_p:
                score *= 1.1
                print(f"📈 Boosted {product['title']} (price in sweet spot)")
        
        # Boost strategic vendors
        if boost_vendors and product['vendor'] in boost_vendors:
            score *= 1.15
            print(f"📈 Boosted {product['title']} (preferred vendor)")
        
        product['final_score'] = score
    
    # Sort by final score
    products.sort(key=lambda p: p['final_score'], reverse=True)
    
    return products


@Tool
async def track_search_analytics(
    query: str,
    results_count: int,
    store_id: str,
    user_id: Optional[str] = None,
    filters_applied: Optional[Dict] = None
) -> Dict:
    """
    Track search event for analytics and improvement.
    
    Logs search queries, results, and user context for:
    - Analytics dashboard
    - Search quality monitoring
    - ML model improvement
    
    Args:
        query: User's search query
        results_count: Number of results returned
        store_id: Store identifier
        user_id: Optional user identifier
        filters_applied: Filters used in search
    
    Returns:
        Confirmation with event ID
    """
    event = {
        "event_type": "search",
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "results_count": results_count,
        "store_id": store_id,
        "user_id": user_id,
        "filters": filters_applied or {}
    }
    
    # TODO: Save to database for analytics
    print(f"📊 Analytics tracked: {query} → {results_count} results")
    
    return {
        "tracked": True,
        "event_id": f"evt_{datetime.now().timestamp()}",
        "message": "Search analytics recorded"
    }


@Tool
async def get_product_details(product_id: str, store_id: str) -> Dict:
    """
    Get detailed product information from Shopify.
    
    Fetches real-time product data including:
    - Variants and options
    - Current inventory
    - Reviews and ratings (if available)
    - Related products
    
    This would connect to MCP server in production.
    
    Args:
        product_id: Product identifier
        store_id: Store identifier
    
    Returns:
        Detailed product information
    """
    # TODO: Connect to MCP server for real Shopify data
    print(f"🔍 Fetching details for product {product_id}")
    
    return {
        "id": product_id,
        "fetched_at": datetime.now().isoformat(),
        "source": "mock_data",
        "note": "In production, this connects to Shopify via MCP"
    }


# ==========================================
# SEARCH AGENT DEFINITION
# ==========================================

search_agent = Agent(
    name="SearchAgent",
    model="gpt-4o-mini",  # Cost-effective, fast, intelligent
    instructions="""
    You are an expert ecommerce search assistant for SmartSearch AI.
    
    Your mission is to help customers find exactly what they're looking for,
    even when they use natural language or vague descriptions.
    
    ## Your Process:
    
    1. **Understand Intent**
       - Parse the user's query for intent and constraints
       - Identify price ranges, features, use cases mentioned
       - Detect implicit preferences (e.g., "marathon" implies long-distance running)
    
    2. **Search Products**
       - Use vector_search to find semantically similar products
       - Consider the query holistically, not just keywords
    
    3. **Apply Filters**
       - Use apply_business_filters for hard constraints (price, stock, tags)
       - Only filter if explicitly or implicitly requested
    
    4. **Re-rank Results**
       - Use re_rank_by_business_rules to prioritize:
         * In-stock items (always prefer)
         * Products in reasonable price ranges
         * High-quality vendors
    
    5. **Explain Results**
       - Provide clear explanations for why products match
       - Highlight key features relevant to the query
       - Be concise but helpful
    
    6. **Track Analytics**
       - Always call track_search_analytics to log the search
       - This helps improve search quality over time
    
    ## Guidelines:
    
    - Be conversational and helpful
    - If no results meet criteria, explain why and suggest alternatives
    - Prioritize user experience over perfect matches
    - Use all available tools to provide the best results
    - Return structured data that the frontend can easily display
    
    ## Output Format:
    
    Return a structured response with:
    - products: List of top products (3-10)
    - explanation: Brief reasoning for recommendations
    - filters_applied: What filters were used
    - suggestions: Alternative searches if needed
    """,
    tools=[
        vector_search,
        apply_business_filters,
        re_rank_by_business_rules,
        track_search_analytics,
        get_product_details,
    ]
)


# ==========================================
# USAGE EXAMPLES
# ==========================================

async def example_search_1():
    """Example: Simple product search"""
    print("\n" + "="*60)
    print("Example 1: Simple Search")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "I need comfortable running shoes",
        context={
            "store_id": "shop_demo_001",
            "user_id": "user_123"
        }
    )
    
    print("\n📋 Agent Response:")
    print(json.dumps(result.final_output, indent=2))


async def example_search_2():
    """Example: Complex search with constraints"""
    print("\n" + "="*60)
    print("Example 2: Complex Search with Filters")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "Show me running shoes under $150 that are good for marathons",
        context={
            "store_id": "shop_demo_001",
            "user_id": "user_456"
        }
    )
    
    print("\n📋 Agent Response:")
    print(json.dumps(result.final_output, indent=2))


async def example_search_3():
    """Example: Vague query requiring interpretation"""
    print("\n" + "="*60)
    print("Example 3: Vague Query (Agent must interpret)")
    print("="*60 + "\n")
    
    result = await Runner.run(
        search_agent,
        "something comfortable for long runs, not too expensive",
        context={
            "store_id": "shop_demo_001"
        }
    )
    
    print("\n📋 Agent Response:")
    print(json.dumps(result.final_output, indent=2))


async def main():
    """Run all examples"""
    print("\n🤖 SmartSearch AI - Search Agent Demo")
    print("Using OpenAI Agents SDK with Function Calling\n")
    
    # Set OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY=sk-...")
        return
    
    # Run examples
    await example_search_1()
    await example_search_2()
    await example_search_3()
    
    print("\n" + "="*60)
    print("✅ Demo Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Connect to real pgvector database")
    print("2. Implement MCP server for Shopify")
    print("3. Add recommendation agent with handoffs")
    print("4. Deploy with FastAPI")


if __name__ == "__main__":
    asyncio.run(main())
