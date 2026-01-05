#!/usr/bin/env python3
"""
Fix via HTTP endpoint - no requiere DATABASE_URL
"""

import requests

BACKEND_URL = "https://shopify-search-backend-production.up.railway.app"

print("🔧 Aplicando fix de billing_cycle_end via HTTP...")

# Llamar endpoint que internamente ejecutará el fix
response = requests.post(
    f"{BACKEND_URL}/api/subscription/init",
    json={"shop": "test.myshopify.com"}
)

if response.status_code == 200:
    print("✅ Fix aplicado exitosamente")
    print(response.json())
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

# Ahora probar una búsqueda simple
print("\n🔍 Probando búsqueda...")
search_response = requests.post(
    f"{BACKEND_URL}/api/search",
    json={
        "query": "camiseta",
        "shop": "test.myshopify.com",
        "max_results": 3
    }
)

if search_response.status_code == 200:
    data = search_response.json()
    print(f"✅ Búsqueda exitosa! {len(data.get('results', []))} resultados")
    for i, result in enumerate(data.get('results', [])[:3], 1):
        print(f"  {i}. {result['title']} - {result['score']:.1%}")
else:
    print(f"❌ Error en búsqueda: {search_response.status_code}")
    print(search_response.text)
