"""
SmartSearch AI - Agent with Function Tools (FIXED)
Uses @function_tool decorator - the correct way!
"""

import asyncio
import os
from agents import Agent, Runner, function_tool


# ====================
# TOOL DEFINITIONS
# ====================

@function_tool
async def vector_search(query: str, max_results: int = 5) -> str:
    """
    Perform semantic search on product catalog.
    
    Args:
        query: The search query from the user
        max_results: Maximum number of results to return
    
    Returns:
        JSON string with matching products and their relevance scores
    """
    print(f"🔍 Tool called: vector_search('{query}', max_results={max_results})")
    
    # Mock data simulating vector search results
    return f"""
    {{
        "query": "{query}",
        "results": [
            {{
                "id": "prod_001",
                "name": "Nike Air Zoom Pegasus 40",
                "description": "Comfortable running shoes with responsive cushioning",
                "price": 89.99,
                "rating": 4.7,
                "similarity_score": 0.95
            }},
            {{
                "id": "prod_002",
                "name": "Adidas Ultraboost 22",
                "description": "Premium running shoes for long-distance comfort",
                "price": 94.99,
                "rating": 4.8,
                "similarity_score": 0.92
            }},
            {{
                "id": "prod_003",
                "name": "New Balance Fresh Foam 1080",
                "description": "Maximum cushioning for comfortable daily runs",
                "price": 79.99,
                "rating": 4.6,
                "similarity_score": 0.88
            }}
        ],
        "total_found": 3,
        "search_time_ms": 45
    }}
    """


@function_tool
async def apply_price_filter(products_json: str, min_price: float = 0, max_price: float = 1000) -> str:
    """
    Filter products by price range.
    
    Args:
        products_json: JSON string of products from vector_search
        min_price: Minimum price (default: 0)
        max_price: Maximum price (default: 1000)
    
    Returns:
        Filtered products as JSON string
    """
    print(f"💰 Tool called: apply_price_filter(min=${min_price}, max=${max_price})")
    
    return f"""
    {{
        "filters_applied": {{
            "min_price": {min_price},
            "max_price": {max_price}
        }},
        "results": [
            {{
                "id": "prod_003",
                "name": "New Balance Fresh Foam 1080",
                "price": 79.99,
                "passes_filter": true
            }}
        ],
        "filtered_count": 1,
        "original_count": 3
    }}
    """


@function_tool
async def get_product_details(product_id: str) -> str:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: The unique product identifier
    
    Returns:
        Detailed product information as JSON
    """
    print(f"📦 Tool called: get_product_details('{product_id}')")
    
    return f"""
    {{
        "id": "{product_id}",
        "name": "Nike Air Zoom Pegasus 40",
        "full_description": "The Nike Air Zoom Pegasus 40 delivers responsive cushioning with every step. Perfect for daily training runs with enhanced breathability.",
        "price": 89.99,
        "in_stock": true,
        "stock_quantity": 47,
        "sizes_available": ["7", "8", "9", "10", "11", "12"],
        "colors": ["Black", "White", "Blue"],
        "rating": 4.7,
        "reviews_count": 1243,
        "shipping": "Free shipping on orders over $50"
    }}
    """


# ====================
# AGENT CONFIGURATION
# ====================

search_agent = Agent(
    name="SmartSearch AI Assistant",
    instructions="""
    You are an intelligent shopping assistant for an e-commerce store.
    
    Your capabilities:
    1. Search products using semantic understanding (vector_search)
    2. Filter results by price (apply_price_filter)
    3. Get detailed product information (get_product_details)
    
    Your goal is to help users find exactly what they need by:
    - Understanding their search intent
    - Calling the right tools in the right order
    - Presenting results in a helpful, conversational way
    
    When a user searches:
    1. Use vector_search to find relevant products
    2. If they mention a budget, use apply_price_filter
    3. If they want details about a specific product, use get_product_details
    
    Always be helpful, conversational, and explain your reasoning.
    """,
    tools=[vector_search, apply_price_filter, get_product_details],
    model="gpt-4o-mini"
)


# ====================
# TEST SCENARIOS
# ====================

async def test_agent():
    """Test the agent with different queries"""
    
    print("\n" + "="*70)
    print("🚀 OPENAI AGENTS SDK - FUNCTION CALLING TEST")
    print("="*70 + "\n")
    
    # Test 1: Simple search
    print("\n📋 TEST 1: Simple product search")
    print("-" * 70)
    result = await Runner.run(
        search_agent,
        input="I need comfortable running shoes"
    )
    print(f"\n✅ Agent Response:\n{result.final_output}\n")
    
    # Test 2: Search with budget constraint
    print("\n📋 TEST 2: Search with price filter")
    print("-" * 70)
    result = await Runner.run(
        search_agent,
        input="Show me running shoes under $90"
    )
    print(f"\n✅ Agent Response:\n{result.final_output}\n")
    
    # Test 3: Get specific product details
    print("\n📋 TEST 3: Product details lookup")
    print("-" * 70)
    result = await Runner.run(
        search_agent,
        input="Tell me more about product prod_001, especially stock and sizes"
    )
    print(f"\n✅ Agent Response:\n{result.final_output}\n")
    
    print("="*70)
    print("✅ ALL TESTS COMPLETED!")
    print("="*70)


if __name__ == "__main__":
    # Verify API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment")
        print("Please run: export OPENAI_API_KEY='your-key-here'")
        exit(1)
    
    print(f"✅ OpenAI API Key found: {api_key[:15]}...")
    
    # Run tests
    asyncio.run(test_agent())
