"""
Check available Groq models
"""
import requests
from dotenv import load_dotenv
import os

# Load from .env file
load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("ERROR: GROQ_API_KEY not found in .env file")
    exit(1)

print(f"Using API key: {api_key[:10]}...{api_key[-4:]}")

url = "https://api.groq.com/openai/v1/models"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    print("\n=== Available Groq Models ===\n")
    for model in data.get('data', []):
        print(f"  - {model.get('id')}")
else:
    print(f"Error {response.status_code}: {response.json()}")