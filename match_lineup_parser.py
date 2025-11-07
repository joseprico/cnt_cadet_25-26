"""
Parser ROBUST per obtenir la convocatòria d'un partit d'ACTAWP
Usa requests-html per executar JavaScript de forma lleugera

Instal·lació:
    pip install requests-html --break-system-packages

Ús:
    python match_lineup_parser.py https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results
"""

import json
import sys
import re

try:
    from requests_html import HTMLSession
    HAS_REQUESTS_HTML = True
except ImportError:
    HAS_REQUESTS_HTML = False
    import requests
    from bs4 import BeautifulSoup

def get_match_lineup(match_url):
    """
    Obté els jugadors convocats per CN Terrassa d'un partit específic
    """
    try:
        match_id_search = re.search(r'/match/(\d+)', match_url)
        if not match_id_search:
            return {"error": "No s'ha pogut trobar l'ID del partit a la URL"}
        
        match_id = match_id_search.group(1)
        
        result = {
            "match_url": match_url,
            "match_id": match_id,
            "cn_terrassa_players": [],
            "rival_team": "",
            "rival_players": []
        }
        
        if HAS_REQUESTS_HTML:
            print("🔧 Usant requests-html (pot executar JavaScript)...")
            result = get_lineup_with_js(match_url, result)
        else:
            print("⚠️  requests-html no disponible, usant mètode bàsic...")
            print("💡 Instal·la: pip install requests-html --break-system-packages")
            result = get_lineup_basic(match_url, result)
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

def get_lineup_with_js(match_url, result):
    """
    Obté la convocatòria executant JavaScript (més fiable)
    """
    session = HTMLSession()
    
    try:
        print(f"🌐 Accedint a: {match_url}")
        response = session.get(match_url)
        
        # Executar JavaScript per carregar contingut dinàmic
        print("⚙️  Executant JavaScript...")
        response.html.render(sleep=2, timeout=20)
        
        # Buscar jugadors en el HTML renderitzat
        print("🔍 Buscant jugadors...")
        
        # Estratègia 1: Buscar taules
        tables = response.html.find('table')
        print(f"📊 Trobades {len(tables)} taules")
        
        for table in tables:
            table_html = table.html
            
            # Comprovar si conté "TERRASSA"
            if 'TERRASSA' in table_html.upper():
                print("✅ Taula de CN Terrassa trobada!")
                result["cn_terrassa_players"] = extract_players_from_table_html(table.html)
                
                # Buscar nom rival
                try:
                    headers = response.html.find('h2, h3, h4')
                    for header in headers:
                        header_text = header.text.strip()
                        if header_text and 'TERRASSA' not in header_text.upper() and len(header_text) > 3:
                            result["rival_team"] = header_text
                            break
                except:
                    pass
                
                break
        
        # Estratègia 2: Si no hem trobat res, buscar amb selectors CSS
        if not result["cn_terrassa_players"]:
            print("🔍 Provant selectors CSS...")
            selectors = [
                '.lineup-player',
                '.player-row',
                '[data-player-id]',
                'tr[data-player]',
                'tbody tr'
            ]
            
            for selector in selectors:
                elements = response.html.find(selector)
                if elements:
                    for elem in elements:
                        text = elem.text
                        # Buscar patró: número + nom
                        match = re.search(r'(\d{1,2})\s+([A-ZÀÈÉÍÒÓÚÇ\s]+)', text)
                        if match:
                            num = int(match.group(1))
                            name = match.group(2).strip()
                            if 1 <= num <= 99 and len(name) > 3:
                                result["cn_terrassa_players"].append({
                                    "num": num,
                                    "name": name.upper()
                                })
                    
                    if result["cn_terrassa_players"]:
                        print(f"✅ Trobats jugadors amb selector: {selector}")
                        break
        
        # Eliminar duplicats
        seen = set()
        unique_players = []
        for player in result["cn_terrassa_players"]:
            key = (player["num"], player["name"])
            if key not in seen:
                seen.add(key)
                unique_players.append(player)
        
        result["cn_terrassa_players"] = sorted(unique_players, key=lambda x: x["num"])
        
    finally:
        session.close()
    
    return result

def get_lineup_basic(match_url, result):
    """
    Mètode bàsic sense JavaScript (menys fiable per ACTAWP)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(match_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Buscar taules
    tables = soup.find_all('table')
    
    for table in tables:
        if 'TERRASSA' in str(table).upper():
            result["cn_terrassa_players"] = extract_players_from_table_html(str(table))
            break
    
    return result

def extract_players_from_table_html(table_html):
    """
    Extreu jugadors del HTML d'una taula
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(table_html, 'html.parser')
    
    players = []
    rows = soup.find_all('tr')
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 2:
            num_text = cells[0].get_text(strip=True)
            name_text = cells[1].get_text(strip=True)
            
            num_match = re.search(r'\d+', num_text)
            if num_match and name_text and len(name_text) > 2:
                player = {
                    "num": int(num_match.group()),
                    "name": name_text.upper()
                }
                players.append(player)
    
    return players

def format_for_app(lineup_data):
    """
    Formata les dades per a l'app d'entrada de dades
    """
    if "error" in lineup_data:
        return lineup_data
    
    players = sorted(lineup_data["cn_terrassa_players"], key=lambda x: x["num"])
    
    js_format = "let players = " + json.dumps(players, ensure_ascii=False, indent=2) + ";"
    
    return {
        "players": players,
        "rival_team": lineup_data.get("rival_team", ""),
        "rival_players": lineup_data.get("rival_players", []),
        "js_code": js_format,
        "count": len(players)
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ús: python match_lineup_parser.py <URL_PARTIT>")
        print("\nExemple:")
        print("  python match_lineup_parser.py https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results")
        print("\n📦 Recomanat instal·lar:")
        print("  pip install requests-html --break-system-packages")
        sys.exit(1)
    
    match_url = sys.argv[1]
    
    print(f"\n{'='*60}")
    print(f"🏊 CN TERRASSA - Parser de Convocatòries")
    print(f"{'='*60}\n")
    
    lineup_data = get_match_lineup(match_url)
    formatted = format_for_app(lineup_data)
    
    if "error" in formatted:
        print(f"\n❌ ERROR: {formatted['error']}\n")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"✅ RESULTAT")
    print(f"{'='*60}\n")
    print(f"👥 Jugadors CN Terrassa: {formatted['count']}")
    
    if formatted['count'] > 0:
        print("\n📋 Llista de jugadors:")
        for player in formatted['players']:
            print(f"   {player['num']:2d}. {player['name']}")
    else:
        print("\n⚠️  No s'han pogut extreure jugadors.")
        print("💡 Potser ACTAWP ha canviat el format o cal JavaScript.")
        print("   Prova instal·lar: pip install requests-html")
    
    if formatted['rival_team']:
        print(f"\n🆚 Equip rival: {formatted['rival_team']}")
    
    # Guardar a fitxer JSON
    match_id = lineup_data.get('match_id', 'unknown')
    output_file = f"match_{match_id}_lineup.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Fitxer generat: {output_file}")
    print(f"\n{'='*60}\n")
