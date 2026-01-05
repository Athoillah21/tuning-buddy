"""
Test DeepSeek API connection and list available models
"""
import os
from dotenv import load_dotenv

# Load from .env file
load_dotenv()

api_key = os.environ.get("DEEPSEEK_API_KEY")

if not api_key:
    print("ERROR: DEEPSEEK_API_KEY not found in .env file")
    print("\nTo get a DeepSeek API key:")
    print("  1. Go to https://platform.deepseek.com/")
    print("  2. Sign up / Log in")
    print("  3. Go to API Keys section")
    print("  4. Add DEEPSEEK_API_KEY=your_key to your .env file")
    exit(1)

print(f"Using API key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")

# Test with OpenAI SDK (DeepSeek uses OpenAI-compatible API)
try:
    from openai import OpenAI
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    # List models
    print("\n=== Testing DeepSeek API ===\n")
    
    # Try a simple completion
    print("Testing chat completion...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello, DeepSeek is working!' in one line."}
        ],
        max_tokens=50,
    )
    
    print(f"Response: {response.choices[0].message.content}")
    print(f"\nModel used: {response.model}")
    print("\n✅ DeepSeek API is working correctly!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nPossible issues:")
    print("  - Invalid API key")
    print("  - No credits/balance on DeepSeek account")
    print("  - Network connectivity issue")
