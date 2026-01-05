#!/bin/bash

# Script de prueba de búsqueda usando curl
# Ejecuta búsquedas directamente contra el backend

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
SHOP="test.myshopify.com"

echo "======================================"
echo "🔍 TEST DE BÚSQUEDA CON CURL"
echo "======================================"
echo ""

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para hacer búsqueda
search() {
    local query="$1"
    local description="$2"
    
    echo -e "${BLUE}🔍 Búsqueda: ${NC}${query}"
    echo -e "   ${description}"
    echo ""
    
    # Ejecutar búsqueda
    response=$(curl -s -X POST "${BACKEND_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"${query}\",
            \"shop\": \"${SHOP}\",
            \"max_results\": 5
        }")
    
    # Parsear y mostrar resultados
    echo "$response" | jq -r '
        if .results then
            "   📊 Resultados encontrados: \(.results | length)\n" +
            (.results | to_entries | map(
                "   \(.key + 1). \(.value.title)\n" +
                "      Relevancia: \(.value.score | tonumber | . * 100 | floor)% | €\(.value.price)"
            ) | join("\n"))
        else
            "   ❌ Error: \(.detail // "Sin resultados")"
        end
    '
    
    echo ""
    echo "---"
    echo ""
}

# Ejecutar casos de prueba

search "camiseta blanca" \
    "Búsqueda directa de producto básico"

search "ropa casual" \
    "Búsqueda genérica de ropa"

search "portátil para juegos" \
    "Búsqueda con sinónimo (juegos = gaming)"

search "cascos inalambricos" \
    "Búsqueda con sinónimo (cascos = auriculares)"

search "café espresso" \
    "Búsqueda de electrodoméstico específico"

search "correr deportes" \
    "Búsqueda conceptual de productos deportivos"

search "regalo tecnología" \
    "Búsqueda por intención de compra"

search "teletrabajo oficina casa" \
    "Búsqueda por contexto de uso"

search "agua termica" \
    "Búsqueda con error tipográfico"

search "ordenador rapido nvidia" \
    "Búsqueda por especificaciones técnicas"

echo "======================================"
echo "✅ PRUEBAS COMPLETADAS"
echo "======================================"
