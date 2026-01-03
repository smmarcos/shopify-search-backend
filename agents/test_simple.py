"""
SmartSearch AI - Search Agent (Working Version)
Simple test to verify OpenAI Agents SDK is working.
"""

from agents import Agent, Runner
import asyncio
import os

# Simple agent without custom tools first
simple_agent = Agent(
    name="SearchAgent",
    model="gpt-4o-mini",
    instructions="""
    You are a helpful ecommerce search assistant.
    
    When a user searches for products, provide intelligent recommendations
    based on their query. Be conversational and helpful.
    
    For now, suggest product ideas based on the query.
    Later, we'll add real product search capabilities.
    """
)

async def test_agent():
    print("\n" + "="*60)
    print("🤖 SmartSearch AI - Agent Test")
    print("="*60 + "\n")
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        return
    
    print("✅ OpenAI API key configured")
    print("🔄 Running agent...\n")
    
    # Test query
    query = "I need comfortable running shoes under $100"
    print(f"Query: {query}\n")
    
    try:
        result = await Runner.run(
            simple_agent,
            query
        )
        
        print("="*60)
        print("📋 Agent Response:")
        print("="*60)
        print(result.final_output)
        print("\n" + "="*60)
        print("✅ Agent executed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
