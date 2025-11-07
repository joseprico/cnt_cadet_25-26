#!/bin/bash
# ============================================
# Script automatitzat: Generar convocatòria
# ============================================
#
# Ús: ./generar_convocatoria.sh "URL_PARTIT"
#
# Exemple:
# ./generar_convocatoria.sh "https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results"
#

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🏊  CN TERRASSA - CONVOCATÒRIA       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Comprovar si s'ha passat la URL
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: Cal proporcionar la URL del partit${NC}"
    echo ""
    echo "Ús: $0 \"URL_PARTIT\""
    echo ""
    echo "Exemple:"
    echo "  $0 \"https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results\""
    echo ""
    exit 1
fi

URL=$1

# Extreure match_id de la URL
MATCH_ID=$(echo "$URL" | grep -oP '/match/\K\d+')

if [ -z "$MATCH_ID" ]; then
    echo -e "${RED}❌ Error: No s'ha pogut extreure l'ID del partit de la URL${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Partit ID: ${MATCH_ID}${NC}"
echo ""

# Executar el parser Python
echo -e "${YELLOW}⚙️  Executant parser...${NC}"
python3 match_lineup_parser.py "$URL"

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Error: El parser ha fallat${NC}"
    exit 1
fi

echo ""

# Comprovar que s'ha generat el fitxer
JSON_FILE="match_${MATCH_ID}_lineup.json"

if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}❌ Error: No s'ha generat el fitxer ${JSON_FILE}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Fitxer generat: ${JSON_FILE}${NC}"
echo ""

# Preguntar si vol pujar a GitHub
echo -e "${YELLOW}📤 Vols pujar a GitHub? (s/n)${NC}"
read -r response

if [[ "$response" =~ ^([sS][iI]?|[yY][eE][sS]?)$ ]]; then
    echo ""
    echo -e "${YELLOW}🔼 Pujant a GitHub...${NC}"
    
    git add "$JSON_FILE"
    git commit -m "📋 Convocatòria partit ${MATCH_ID} - $(date +%Y-%m-%d)"
    git push
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Pujat a GitHub correctament!${NC}"
        echo ""
        echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║  ✨ LLEST! Ara pots importar a l'app ║${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}📱 A l'app:${NC}"
        echo "   1. Config → 🔗 Importar"
        echo "   2. Enganxa la URL"
        echo "   3. ✅ Jugadors importats!"
        echo ""
    else
        echo ""
        echo -e "${RED}❌ Error en pujar a GitHub${NC}"
        exit 1
    fi
else
    echo ""
    echo -e "${YELLOW}⏭️  Saltant pujada a GitHub${NC}"
    echo ""
    echo -e "${BLUE}Per pujar-lo manualment:${NC}"
    echo "  git add $JSON_FILE"
    echo "  git commit -m \"Convocatòria partit $MATCH_ID\""
    echo "  git push"
    echo ""
fi
