# Test de Calidad de Búsqueda

Scripts para probar la calidad de búsqueda del backend con productos realistas en español.

## 📁 Archivos

- **test_search_quality.py**: Script Python completo que crea productos, genera embeddings y ejecuta tests
- **test_search_curl.sh**: Script bash simple con curl para pruebas rápidas

## 🚀 Uso

### Opción 1: Script Python Completo (Recomendado)

```bash
# Configurar variables de entorno
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
export OPENAI_API_KEY="sk-..."

# Ejecutar
python3 test_search_quality.py
```

Este script:
1. ✅ Inserta 15 productos de prueba en español
2. 🧠 Genera embeddings con OpenAI
3. 🔍 Ejecuta 10 búsquedas de prueba
4. 📊 Muestra métricas de calidad (precision, recall)

### Opción 2: Script Bash con curl

```bash
# Backend debe estar corriendo
export BACKEND_URL="http://localhost:8000"

# Ejecutar
./test_search_curl.sh
```

Este script ejecuta búsquedas directas contra el backend y muestra resultados formateados.

## 📦 Productos de Prueba

Los productos incluyen:
- 👕 Ropa (camisetas, vaqueros, sudaderas)
- 👟 Calzado deportivo
- 💻 Electrónica (portátiles, auriculares, smartwatch)
- 🎒 Accesorios
- 🏠 Hogar (electrodomésticos, cocina, textil)
- 📚 Libros

## 🎯 Casos de Prueba

1. **Búsqueda directa**: "camiseta blanca"
2. **Búsqueda genérica**: "ropa casual"
3. **Con sinónimos**: "portátil para juegos" → gaming
4. **Con errores**: "cascos inalambricos" → auriculares inalámbricos
5. **Conceptual**: "correr deportes" → zapatillas + smartwatch
6. **Por intención**: "regalo tecnología"
7. **Por contexto**: "teletrabajo oficina casa"
8. **Con typos**: "agua termica" (sin tilde)
9. **Técnica**: "ordenador rapido nvidia"

## 📈 Métricas

Cada búsqueda evalúa:
- **Precision**: % de resultados relevantes
- **Recall**: % de productos esperados encontrados
- **Similarity Score**: Similitud coseno con el embedding de búsqueda

### Evaluación
- ✅ **EXCELENTE**: Recall ≥ 80%
- ⚠️ **ACEPTABLE**: Recall ≥ 50%
- ❌ **MEJORABLE**: Recall < 50%

## 🔧 Requisitos

### Python Script
```bash
pip install asyncpg openai
```

### Bash Script
```bash
# Necesita jq para parsear JSON
brew install jq  # macOS
# o
sudo apt-get install jq  # Linux
```

## 📊 Ejemplo de Salida

```
🔍 Búsqueda: 'camiseta blanca'
   Búsqueda directa de producto básico

   📊 Resultados (Top 5):
   ✅ 1. Camiseta Básica de Algodón - Blanca
      Similitud: 0.892 | ID: test_001 | €19.99
      2. Sudadera Con Capucha - Gris Jaspeado
      Similitud: 0.654 | ID: test_011 | €34.99

   📈 Métricas:
      Esperados encontrados: 1/1
      Precision: 20.00%
      Recall: 100.00%
      Evaluación: ✅ EXCELENTE
```

## 🗄️ Limpieza

Para eliminar productos de prueba:

```sql
DELETE FROM product_embeddings WHERE metadata->>'test' = 'true';
```
