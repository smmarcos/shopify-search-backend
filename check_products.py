#!/usr/bin/env python3
"""
Check products and their embeddings status
"""

import requests

BACKEND_URL = "https://shopify-search-backend-production.up.railway.app"

print("🔍 Verificando productos de prueba...")

# Intentar obtener config primero
response = requests.post(
    f"{BACKEND_URL}/api/compare-shopify-products",
    json={
        "products": [],
        "shop": "test.myshopify.com"
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Verificar si hay productos
print("\n🔍 Intentando búsqueda simple...")
search = requests.post(
    f"{BACKEND_URL}/api/search",
    json={
        "query": "test",
        "shop": "test.myshopify.com",
        "max_results": 1
    }
)

print(f"Status: {search.status_code}")
if search.status_code != 200:
    print(f"Error: {search.text}")
else:
    print(f"Results: {search.json()}")
