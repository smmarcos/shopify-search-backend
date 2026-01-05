#!/usr/bin/env python3
"""
Script de testing usando los endpoints HTTP del backend
No requiere acceso directo a la base de datos
"""

import requests
import json
import time
from typing import List, Dict

# Configuración
BACKEND_URL = "https://shopify-search-backend-production.up.railway.app"
SHOP = "test.myshopify.com"

# Productos de prueba realistas en español
PRODUCTOS_PRUEBA = [
    {
        "product_id": "test_001",
        "title": "Camiseta Básica de Algodón - Blanca",
        "description": "Camiseta de manga corta confeccionada en algodón 100% orgánico. Cuello redondo y corte regular. Perfecta para el día a día. Disponible en tallas S a XXL. Lavable a máquina.",
        "price": 19.99,
        "vendor": "BasicWear",
        "product_type": "Ropa",
        "tags": "camiseta, básicos, algodón, blanco, manga corta, unisex",
        "variants": [{"id": "var_001", "title": "M / Blanco", "price": "19.99"}],
        "images": []
    },
    {
        "product_id": "test_002",
        "title": "Vaqueros Slim Fit Azul Oscuro",
        "description": "Pantalones vaqueros de corte slim con elastano para mayor comodidad. Cinco bolsillos clásicos. Tela denim de alta calidad con acabado stonewashed. Cierre de botón y cremallera.",
        "price": 49.99,
        "vendor": "DenimCo",
        "product_type": "Ropa",
        "tags": "vaqueros, jeans, slim fit, denim, azul, pantalones",
        "variants": [{"id": "var_002", "title": "32 / Azul", "price": "49.99"}],
        "images": []
    },
    {
        "product_id": "test_003",
        "title": "Zapatillas Deportivas Running - Negro/Rojo",
        "description": "Zapatillas de running con suela de goma EVA para máxima amortiguación. Upper transpirable en mesh. Perfectas para corredores de cualquier nivel. Diseño ergonómico y ligero.",
        "price": 79.99,
        "vendor": "SportMax",
        "product_type": "Calzado",
        "tags": "zapatillas, running, deporte, calzado, negro, rojo",
        "variants": [{"id": "var_003", "title": "42 / Negro", "price": "79.99"}],
        "images": []
    },
    {
        "product_id": "test_004",
        "title": "Portátil Gaming 15.6\" - Intel i7 16GB RAM",
        "description": "Ordenador portátil gaming con procesador Intel Core i7 de 11ª generación, 16GB RAM DDR4, SSD 512GB, tarjeta gráfica NVIDIA RTX 3060. Pantalla Full HD 144Hz. Teclado retroiluminado RGB.",
        "price": 1299.99,
        "vendor": "TechPro",
        "product_type": "Electrónica",
        "tags": "portátil, gaming, ordenador, laptop, intel, nvidia",
        "variants": [{"id": "var_004", "title": "i7/16GB/512GB", "price": "1299.99"}],
        "images": []
    },
    {
        "product_id": "test_005",
        "title": "Auriculares Bluetooth Inalámbricos con Cancelación de Ruido",
        "description": "Auriculares over-ear con cancelación activa de ruido (ANC). Batería de 30 horas. Bluetooth 5.0 con aptX HD. Controles táctiles. Estuche de transporte incluido. Sonido Hi-Fi.",
        "price": 149.99,
        "vendor": "AudioTech",
        "product_type": "Electrónica",
        "tags": "auriculares, bluetooth, inalámbricos, ANC, audio, música",
        "variants": [{"id": "var_005", "title": "Negro", "price": "149.99"}],
        "images": []
    },
    {
        "product_id": "test_006",
        "title": "Mochila Urbana Antirrobo con Puerto USB",
        "description": "Mochila con compartimento acolchado para portátil de hasta 15.6\". Puerto USB externo para cargar dispositivos. Bolsillo oculto antirrobo en la espalda. Material impermeable. 25L de capacidad.",
        "price": 39.99,
        "vendor": "BagStyle",
        "product_type": "Accesorios",
        "tags": "mochila, portátil, USB, antirrobo, impermeable, urbana",
        "variants": [{"id": "var_006", "title": "Negro", "price": "39.99"}],
        "images": []
    },
    {
        "product_id": "test_007",
        "title": "Reloj Inteligente Smartwatch - Monitor Salud y Deporte",
        "description": "Smartwatch con pantalla AMOLED de 1.4\". Monitor de frecuencia cardíaca, SpO2 y sueño. GPS integrado. Resistente al agua IP68. Más de 100 modos deportivos. Batería 7 días.",
        "price": 199.99,
        "vendor": "FitTech",
        "product_type": "Electrónica",
        "tags": "smartwatch, reloj, deporte, salud, fitness, GPS",
        "variants": [{"id": "var_007", "title": "Negro", "price": "199.99"}],
        "images": []
    },
    {
        "product_id": "test_008",
        "title": "Cafetera Express Profesional - 15 Bares",
        "description": "Máquina de café espresso con bomba de presión de 15 bares. Vaporizador para espumar leche. Bandeja calienta tazas. Depósito de agua extraíble 1.5L. Cappuccino, latte, espresso perfecto.",
        "price": 89.99,
        "vendor": "HomeBar",
        "product_type": "Hogar",
        "tags": "cafetera, café, espresso, cappuccino, electrodoméstico",
        "variants": [{"id": "var_008", "title": "Acero", "price": "89.99"}],
        "images": []
    },
    {
        "product_id": "test_009",
        "title": "Sartén Antiadherente 28cm - Inducción",
        "description": "Sartén profesional con revestimiento antiadherente de titanio. Compatible con todo tipo de cocinas incluyendo inducción. Mango ergonómico termorresistente. Fácil limpieza. Libre de PFOA.",
        "price": 34.99,
        "vendor": "ChefMaster",
        "product_type": "Hogar",
        "tags": "sartén, cocina, antiadherente, inducción, utensilios",
        "variants": [{"id": "var_009", "title": "28cm", "price": "34.99"}],
        "images": []
    },
    {
        "product_id": "test_010",
        "title": "Libro: Cien Años de Soledad - Gabriel García Márquez",
        "description": "Edición especial conmemorativa de la obra maestra de García Márquez. Tapa dura con sobrecubierta ilustrada. Incluye prólogo del autor y notas del editor. 432 páginas. Literatura latinoamericana.",
        "price": 24.99,
        "vendor": "LibrosPlus",
        "product_type": "Libros",
        "tags": "libro, literatura, novela, García Márquez, español, ficción",
        "variants": [{"id": "var_010", "title": "Tapa Dura", "price": "24.99"}],
        "images": []
    }
]

# Casos de prueba para búsquedas
CASOS_BUSQUEDA = [
    {
        "query": "camiseta blanca",
        "expected": ["test_001"],
        "description": "Búsqueda directa de producto básico"
    },
    {
        "query": "ropa casual",
        "expected": ["test_001", "test_002"],
        "description": "Búsqueda genérica de ropa"
    },
    {
        "query": "portátil para juegos",
        "expected": ["test_004"],
        "description": "Búsqueda con sinónimo (juegos = gaming)"
    },
    {
        "query": "cascos inalambricos",
        "expected": ["test_005"],
        "description": "Búsqueda con sinónimo (cascos = auriculares)"
    },
    {
        "query": "café espresso",
        "expected": ["test_008"],
        "description": "Búsqueda de electrodoméstico específico"
    },
    {
        "query": "correr deportes",
        "expected": ["test_003", "test_007"],
        "description": "Búsqueda conceptual de productos deportivos"
    },
    {
        "query": "regalo tecnología",
        "expected": ["test_005", "test_007"],
        "description": "Búsqueda por intención de compra"
    },
    {
        "query": "teletrabajo oficina casa",
        "expected": ["test_004", "test_006"],
        "description": "Búsqueda por contexto de uso"
    }
]


def sync_products():
    """Sincroniza productos de prueba con el backend"""
    print("🔨 Sincronizando productos de prueba...")
    print()
    
    payload = {
        "products": PRODUCTOS_PRUEBA,
        "shop": SHOP
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/compare-shopify-products",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Sincronización completada:")
            print(f"   Nuevos: {data.get('new', 0)}")
            print(f"   Actualizados: {data.get('updated', 0)}")
            print(f"   Sin cambios: {data.get('unchanged', 0)}")
            print()
            return True
        else:
            print(f"❌ Error en sincronización: {response.status_code}")
            print(f"   {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_search(query: str, expected_ids: List[str], description: str):
    """Ejecuta una búsqueda y evalúa los resultados"""
    print(f"\n🔍 Búsqueda: '{query}'")
    print(f"   {description}")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/search",
            json={
                "query": query,
                "shop": SHOP,
                "max_results": 5
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"   ❌ Error: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        results = data.get("results", [])
        
        print(f"\n   📊 Resultados (Top {len(results)}):")
        
        found_expected = []
        
        for i, result in enumerate(results, 1):
            is_expected = result['product_id'] in expected_ids
            mark = "✅" if is_expected else "  "
            
            if is_expected:
                found_expected.append(result['product_id'])
            
            print(f"   {mark} {i}. {result['title']}")
            print(f"      Relevancia: {result['score']:.1%} | ID: {result['product_id']} | €{result['price']}")
        
        # Evaluación
        precision = len(found_expected) / len(results) if results else 0
        recall = len(found_expected) / len(expected_ids) if expected_ids else 0
        
        print(f"\n   📈 Métricas:")
        print(f"      Esperados encontrados: {len(found_expected)}/{len(expected_ids)}")
        print(f"      Precision: {precision:.2%}")
        print(f"      Recall: {recall:.2%}")
        
        if recall >= 0.8:
            print(f"      Evaluación: ✅ EXCELENTE")
        elif recall >= 0.5:
            print(f"      Evaluación: ⚠️  ACEPTABLE")
        else:
            print(f"      Evaluación: ❌ MEJORABLE")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")


def main():
    """Ejecuta todos los tests"""
    print("=" * 80)
    print("🧪 TEST DE CALIDAD DE BÚSQUEDA - Productos en Español")
    print("=" * 80)
    print(f"Backend: {BACKEND_URL}")
    print(f"Shop: {SHOP}")
    print("=" * 80)
    print()
    
    # 1. Sincronizar productos
    if not sync_products():
        print("❌ Error en sincronización. Abortando tests.")
        return
    
    # 2. Forzar generación de embeddings para productos sin embeddings
    print("🧠 Generando embeddings para productos sin embeddings...")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/admin/generate-missing-embeddings",
            json={"shop": SHOP},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Embeddings generados: {data.get('generated', 0)}/{data.get('total_processed', 0)}")
        else:
            print(f"⚠️  Warning: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️  Warning en generación de embeddings: {e}")
    
    # Esperar a que se procesen los embeddings
    print("⏳ Esperando 5 segundos para asegurar que todo está listo...")
    time.sleep(5)
    print()
    
    # 2. Ejecutar búsquedas de prueba
    print("=" * 80)
    print("🎯 EJECUTANDO CASOS DE PRUEBA")
    print("=" * 80)
    
    for caso in CASOS_BUSQUEDA:
        test_search(
            caso["query"],
            caso["expected"],
            caso["description"]
        )
        time.sleep(1)  # Pequeña pausa entre búsquedas
    
    print("\n" + "=" * 80)
    print("✅ TESTS COMPLETADOS")
    print("=" * 80)


if __name__ == "__main__":
    main()
