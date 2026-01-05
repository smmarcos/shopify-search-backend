#!/usr/bin/env python3
"""
Script de testing para evaluar la calidad de búsqueda con productos de prueba en español
Crea productos realistas, los sincroniza y ejecuta búsquedas de prueba
"""

import asyncio
import asyncpg
import os
import json
from datetime import datetime
from openai import AsyncOpenAI

# Configuración
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/shopify_search")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Productos de prueba realistas en español
PRODUCTOS_PRUEBA = [
    {
        "product_id": "test_001",
        "title": "Camiseta Básica de Algodón - Blanca",
        "description": "Camiseta de manga corta confeccionada en algodón 100% orgánico. Cuello redondo y corte regular. Perfecta para el día a día. Disponible en tallas S a XXL. Lavable a máquina.",
        "price": 19.99,
        "vendor": "BasicWear",
        "category": "Ropa > Camisetas",
        "tags": ["camiseta", "básicos", "algodón", "blanco", "manga corta", "unisex"]
    },
    {
        "product_id": "test_002",
        "title": "Vaqueros Slim Fit Azul Oscuro",
        "description": "Pantalones vaqueros de corte slim con elastano para mayor comodidad. Cinco bolsillos clásicos. Tela denim de alta calidad con acabado stonewashed. Cierre de botón y cremallera.",
        "price": 49.99,
        "vendor": "DenimCo",
        "category": "Ropa > Pantalones",
        "tags": ["vaqueros", "jeans", "slim fit", "denim", "azul", "pantalones"]
    },
    {
        "product_id": "test_003",
        "title": "Zapatillas Deportivas Running - Negro/Rojo",
        "description": "Zapatillas de running con suela de goma EVA para máxima amortiguación. Upper transpirable en mesh. Perfectas para corredores de cualquier nivel. Diseño ergonómico y ligero.",
        "price": 79.99,
        "vendor": "SportMax",
        "category": "Calzado > Deportivo",
        "tags": ["zapatillas", "running", "deporte", "calzado", "negro", "rojo"]
    },
    {
        "product_id": "test_004",
        "title": "Portátil Gaming 15.6\" - Intel i7 16GB RAM",
        "description": "Ordenador portátil gaming con procesador Intel Core i7 de 11ª generación, 16GB RAM DDR4, SSD 512GB, tarjeta gráfica NVIDIA RTX 3060. Pantalla Full HD 144Hz. Teclado retroiluminado RGB.",
        "price": 1299.99,
        "vendor": "TechPro",
        "category": "Electrónica > Ordenadores",
        "tags": ["portátil", "gaming", "ordenador", "laptop", "intel", "nvidia"]
    },
    {
        "product_id": "test_005",
        "title": "Auriculares Bluetooth Inalámbricos con Cancelación de Ruido",
        "description": "Auriculares over-ear con cancelación activa de ruido (ANC). Batería de 30 horas. Bluetooth 5.0 con aptX HD. Controles táctiles. Estuche de transporte incluido. Sonido Hi-Fi.",
        "price": 149.99,
        "vendor": "AudioTech",
        "category": "Electrónica > Audio",
        "tags": ["auriculares", "bluetooth", "inalámbricos", "ANC", "audio", "música"]
    },
    {
        "product_id": "test_006",
        "title": "Mochila Urbana Antirrobo con Puerto USB",
        "description": "Mochila con compartimento acolchado para portátil de hasta 15.6\". Puerto USB externo para cargar dispositivos. Bolsillo oculto antirrobo en la espalda. Material impermeable. 25L de capacidad.",
        "price": 39.99,
        "vendor": "BagStyle",
        "category": "Accesorios > Mochilas",
        "tags": ["mochila", "portátil", "USB", "antirrobo", "impermeable", "urbana"]
    },
    {
        "product_id": "test_007",
        "title": "Reloj Inteligente Smartwatch - Monitor Salud y Deporte",
        "description": "Smartwatch con pantalla AMOLED de 1.4\". Monitor de frecuencia cardíaca, SpO2 y sueño. GPS integrado. Resistente al agua IP68. Más de 100 modos deportivos. Batería 7 días.",
        "price": 199.99,
        "vendor": "FitTech",
        "category": "Electrónica > Wearables",
        "tags": ["smartwatch", "reloj", "deporte", "salud", "fitness", "GPS"]
    },
    {
        "product_id": "test_008",
        "title": "Cafetera Express Profesional - 15 Bares",
        "description": "Máquina de café espresso con bomba de presión de 15 bares. Vaporizador para espumar leche. Bandeja calienta tazas. Depósito de agua extraíble 1.5L. Cappuccino, latte, espresso perfecto.",
        "price": 89.99,
        "vendor": "HomeBar",
        "category": "Hogar > Electrodomésticos",
        "tags": ["cafetera", "café", "espresso", "cappuccino", "electrodoméstico"]
    },
    {
        "product_id": "test_009",
        "title": "Sartén Antiadherente 28cm - Inducción",
        "description": "Sartén profesional con revestimiento antiadherente de titanio. Compatible con todo tipo de cocinas incluyendo inducción. Mango ergonómico termorresistente. Fácil limpieza. Libre de PFOA.",
        "price": 34.99,
        "vendor": "ChefMaster",
        "category": "Hogar > Cocina",
        "tags": ["sartén", "cocina", "antiadherente", "inducción", "utensilios"]
    },
    {
        "product_id": "test_010",
        "title": "Libro: Cien Años de Soledad - Gabriel García Márquez",
        "description": "Edición especial conmemorativa de la obra maestra de García Márquez. Tapa dura con sobrecubierta ilustrada. Incluye prólogo del autor y notas del editor. 432 páginas. Literatura latinoamericana.",
        "price": 24.99,
        "vendor": "LibrosPlus",
        "category": "Libros > Ficción",
        "tags": ["libro", "literatura", "novela", "García Márquez", "español", "ficción"]
    },
    {
        "product_id": "test_011",
        "title": "Sudadera Con Capucha - Gris Jaspeado",
        "description": "Hoodie unisex con capucha ajustable y bolsillo canguro. Mezcla de algodón y poliéster 80/20. Interior con felpa suave. Puños y dobladillo elásticos. Perfecta para entretiempo.",
        "price": 34.99,
        "vendor": "BasicWear",
        "category": "Ropa > Sudaderas",
        "tags": ["sudadera", "hoodie", "capucha", "gris", "algodón", "unisex"]
    },
    {
        "product_id": "test_012",
        "title": "Botella Térmica Acero Inoxidable 750ml",
        "description": "Botella térmica de doble pared que mantiene bebidas frías 24h y calientes 12h. Acero inoxidable 18/8. Libre de BPA. Boca ancha para hielos. A prueba de fugas. Incluye asa de transporte.",
        "price": 24.99,
        "vendor": "EcoLife",
        "category": "Hogar > Botellas",
        "tags": ["botella", "térmica", "acero", "agua", "deporte", "eco"]
    },
    {
        "product_id": "test_013",
        "title": "Ratón Inalámbrico Ergonómico Vertical",
        "description": "Mouse inalámbrico con diseño vertical ergonómico que reduce la tensión en muñeca y brazo. 6 botones programables. DPI ajustable hasta 2400. Batería recargable. Conexión USB 2.4GHz.",
        "price": 29.99,
        "vendor": "TechPro",
        "category": "Electrónica > Accesorios PC",
        "tags": ["ratón", "mouse", "inalámbrico", "ergonómico", "vertical", "PC"]
    },
    {
        "product_id": "test_014",
        "title": "Funda de Sofá Elástica 3 Plazas - Beige",
        "description": "Funda protectora para sofá de 3 plazas. Tejido elástico que se adapta perfectamente. Fácil instalación. Lavable a máquina. Protege contra manchas, mascotas y desgaste. Material suave y duradero.",
        "price": 44.99,
        "vendor": "HomeDeco",
        "category": "Hogar > Textil",
        "tags": ["funda", "sofá", "protector", "elástica", "beige", "textil"]
    },
    {
        "product_id": "test_015",
        "title": "Set de Sushi para Principiantes - 11 Piezas",
        "description": "Kit completo para hacer sushi en casa. Incluye esterilla de bambú, espátula de arroz, palillos, moldes para onigiri y libro de recetas. Ideal para aprender a preparar sushi casero.",
        "price": 19.99,
        "vendor": "ChefMaster",
        "category": "Hogar > Cocina",
        "tags": ["sushi", "cocina", "japonés", "kit", "regalo", "principiantes"]
    }
]

# Casos de prueba para búsquedas
CASOS_BUSQUEDA = [
    {
        "query": "camiseta blanca",
        "expected": ["test_001"],  # Debe encontrar la camiseta blanca
        "description": "Búsqueda directa de producto básico"
    },
    {
        "query": "ropa casual hombre",
        "expected": ["test_001", "test_011"],  # Camiseta y sudadera
        "description": "Búsqueda genérica de ropa"
    },
    {
        "query": "portátil para juegos",
        "expected": ["test_004"],  # Portátil gaming
        "description": "Búsqueda con sinónimo (juegos = gaming)"
    },
    {
        "query": "cascos inalambricos",
        "expected": ["test_005"],  # Auriculares bluetooth
        "description": "Búsqueda con sinónimo (cascos = auriculares) y error tipográfico"
    },
    {
        "query": "café espresso",
        "expected": ["test_008"],  # Cafetera express
        "description": "Búsqueda de electrodoméstico específico"
    },
    {
        "query": "correr deportes",
        "expected": ["test_003", "test_007"],  # Zapatillas running y smartwatch
        "description": "Búsqueda conceptual de productos deportivos"
    },
    {
        "query": "regalo cumpleaños tecnología",
        "expected": ["test_005", "test_007"],  # Auriculares o smartwatch
        "description": "Búsqueda por intención de compra"
    },
    {
        "query": "teletrabajo oficina casa",
        "expected": ["test_004", "test_013"],  # Portátil y ratón ergonómico
        "description": "Búsqueda por contexto de uso"
    },
    {
        "query": "agua termica deporte",
        "expected": ["test_012"],  # Botella térmica
        "description": "Búsqueda con error tipográfico (termica sin tilde)"
    },
    {
        "query": "ordenador rapido nvidia",
        "expected": ["test_004"],  # Portátil gaming
        "description": "Búsqueda por especificaciones técnicas"
    }
]


async def create_products_in_db(pool):
    """Inserta productos de prueba en la base de datos"""
    print("🔨 Creando productos de prueba en la base de datos...")
    
    async with pool.acquire() as conn:
        for producto in PRODUCTOS_PRUEBA:
            try:
                await conn.execute("""
                    INSERT INTO product_embeddings 
                    (product_id, title, description, price, vendor, category, tags, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (product_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        price = EXCLUDED.price,
                        vendor = EXCLUDED.vendor,
                        category = EXCLUDED.category,
                        tags = EXCLUDED.tags,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, 
                    producto["product_id"],
                    producto["title"],
                    producto["description"],
                    producto["price"],
                    producto["vendor"],
                    producto["category"],
                    producto["tags"],
                    json.dumps({"shop": "test.myshopify.com", "test": True})
                )
                print(f"  ✓ {producto['product_id']}: {producto['title']}")
            except Exception as e:
                print(f"  ✗ Error con {producto['product_id']}: {e}")
    
    print(f"\n✅ {len(PRODUCTOS_PRUEBA)} productos insertados\n")


async def generate_embeddings(pool):
    """Genera embeddings para todos los productos sin embedding"""
    print("🧠 Generando embeddings con OpenAI...")
    
    if not OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY no configurada")
        return
    
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async with pool.acquire() as conn:
        # Obtener productos sin embedding
        products = await conn.fetch("""
            SELECT product_id, title, description, category, tags
            FROM product_embeddings
            WHERE embedding IS NULL
        """)
        
        if not products:
            print("✅ Todos los productos ya tienen embeddings\n")
            return
        
        print(f"📝 Procesando {len(products)} productos...\n")
        
        for product in products:
            # Crear texto para embedding
            text_parts = [product['title']]
            if product['description']:
                text_parts.append(product['description'])
            if product['category']:
                text_parts.append(f"Categoría: {product['category']}")
            if product['tags']:
                text_parts.append(f"Etiquetas: {', '.join(product['tags'])}")
            
            text = " ".join(text_parts)
            
            try:
                # Generar embedding
                response = await client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                
                embedding = response.data[0].embedding
                
                # Guardar en BD
                await conn.execute("""
                    UPDATE product_embeddings
                    SET embedding = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE product_id = $2
                """, embedding, product['product_id'])
                
                print(f"  ✓ {product['product_id']}: embedding generado")
                
            except Exception as e:
                print(f"  ✗ Error con {product['product_id']}: {e}")
        
        print(f"\n✅ Embeddings generados para {len(products)} productos\n")


async def test_search(pool, query, expected_ids, description):
    """Ejecuta una búsqueda y evalúa los resultados"""
    print(f"\n🔍 Búsqueda: '{query}'")
    print(f"   {description}")
    
    if not OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY no configurada")
        return
    
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    try:
        # Generar embedding de la búsqueda
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        search_embedding = response.data[0].embedding
        
        # Buscar productos similares
        async with pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT 
                    product_id,
                    title,
                    price,
                    1 - (embedding <=> $1::vector) AS similarity
                FROM product_embeddings
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 5
            """, search_embedding)
        
        print(f"\n   📊 Resultados (Top 5):")
        found_expected = []
        
        for i, result in enumerate(results, 1):
            is_expected = result['product_id'] in expected_ids
            mark = "✅" if is_expected else "  "
            
            if is_expected:
                found_expected.append(result['product_id'])
            
            print(f"   {mark} {i}. {result['title']}")
            print(f"      Similitud: {result['similarity']:.3f} | ID: {result['product_id']} | €{result['price']}")
        
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
        print(f"   ❌ Error en búsqueda: {e}")


async def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 80)
    print("🧪 TEST DE CALIDAD DE BÚSQUEDA - Productos en Español")
    print("=" * 80)
    print()
    
    # Conectar a la BD
    print("📡 Conectando a la base de datos...")
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("✅ Conectado\n")
    
    try:
        # 1. Crear productos
        await create_products_in_db(pool)
        
        # 2. Generar embeddings
        await generate_embeddings(pool)
        
        # 3. Ejecutar búsquedas de prueba
        print("=" * 80)
        print("🎯 EJECUTANDO CASOS DE PRUEBA")
        print("=" * 80)
        
        for caso in CASOS_BUSQUEDA:
            await test_search(
                pool,
                caso["query"],
                caso["expected"],
                caso["description"]
            )
            await asyncio.sleep(0.5)  # Pequeña pausa entre búsquedas
        
        print("\n" + "=" * 80)
        print("✅ TESTS COMPLETADOS")
        print("=" * 80)
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
