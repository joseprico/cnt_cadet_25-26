"""
Parser DEFINITIU per obtenir la convocatòria d'un partit d'ACTAWP
Usa Playwright - la solució més fiable per GitHub Actions

Instal·lació:
    pip install playwright
    playwright install chromium

Ús:
    python match_lineup_parser.py URL_PARTIT
"""

import json
import sys
import re

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

def get_match_lineup(match_url):
    """Obté jugadors convocats per CN Terrassa"""
    
    match_id_search = re.search(r'/match/(\d+)', match_url)
    if not match_id_search:
        return {"error": "No s'ha pogut trobar l'ID del partit a la URL"}
    
    match_id = match_id_search.group(1)
    
    result = {
        "match_url": match_url,
        "match_id": match_id,
        "cn_terrassa_players": [],
        "rival_team": ""
    }
    
    if not HAS_PLAYWRIGHT:
        return {"error": "Playwright no disponible. Instal·la: pip install playwright && playwright install chromium"}
    
    with sync_playwright() as p:
        print("🚀 Iniciant navegador...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        
        page = context.new_page()
        
        try:
            print(f"🌐 Accedint a: {match_url}")
            
            try:
                page.goto(match_url, wait_until="networkidle", timeout=40000)
            except Exception:
                try:
                    page.goto(match_url, wait_until="load", timeout=40000)
                except Exception:
                    page.goto(match_url, timeout=40000)
            
            page.wait_for_timeout(3000)
            
            print("🔍 Buscant jugadors...")
            
            # Buscar totes les taules
            tables = page.query_selector_all('table')
            print(f"📊 Trobades {len(tables)} taules\n")
            
            for idx, table in enumerate(tables):
                print(f"🔍 Taula {idx+1}:")
                
                rows = table.query_selector_all('tr')
                
                if len(rows) < 3:
                    print(f"   ⏭️  Massa petita ({len(rows)} files)\n")
                    continue
                
                # Mostrar preview
                table_text = table.inner_text()
                lines_preview = table_text.split('\n')[:3]
                for line in lines_preview:
                    if line.strip():
                        print(f"   {line.strip()[:70]}")
                
                # Processar files buscant patró: número + nom
                temp_players = []
                
                for row_idx, row in enumerate(rows):
                    cells = row.query_selector_all('td, th')
                    
                    if len(cells) < 2:
                        continue
                    
                    # Agafar text de cada cel·la
                    cell_values = []
                    for cell in cells[:5]:  # Només primeres 5 columnes
                        text = cell.inner_text().strip()
                        cell_values.append(text)
                    
                    # Buscar número + nom en les primeres columnes
                    for i in range(len(cell_values) - 1):
                        num_text = cell_values[i]
                        name_text = cell_values[i + 1]
                        
                        # Saltar capçaleres
                        if num_text.upper() in ['', 'NÚM', 'Nº', '#', 'NUM', 'DORSAL', 'G', 'GS', 'GI', 'GP']:
                            continue
                        
                        # Verificar patró: número (1-99) + nom (més de 3 caràcters)
                        if re.match(r'^\d{1,2}$', num_text) and name_text:
                            num = int(num_text)
                            name = name_text.upper()
                            
                            # Validar
                            if (1 <= num <= 99 and
                                len(name) > 3 and
                                not name.isdigit() and
                                name not in ['TERRASSA', 'MONTJUIC', 'CN', 'C.N.', 'TOTAL', 'EQUIP']):
                                
                                temp_players.append({
                                    "num": num,
                                    "name": name
                                })
                                break  # No buscar més en aquesta fila
                
                if temp_players:
                    print(f"   ✅ {len(temp_players)} jugadors trobats!")
                    for p in temp_players[:3]:
                        print(f"      {p['num']:2d}. {p['name']}")
                    if len(temp_players) > 3:
                        print(f"      ... i {len(temp_players)-3} més")
                    
                    result["cn_terrassa_players"].extend(temp_players)
                    break
                else:
                    print(f"   ❌ No s'han trobat jugadors\n")
            
            # Buscar equip rival
            if result["cn_terrassa_players"]:
                headers = page.query_selector_all('h1, h2, h3, h4, .team-name')
                for header in headers:
                    text = header.inner_text().strip()
                    if text and 'TERRASSA' not in text.upper() and len(text) > 3:
                        result["rival_team"] = text
                        break
            
            # Eliminar duplicats i ordenar
            seen = set()
            unique = []
            for p in result["cn_terrassa_players"]:
                key = (p["num"], p["name"])
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            
            result["cn_terrassa_players"] = sorted(unique, key=lambda x: x["num"])
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            context.close()
            browser.close()
    
    return result

def format_for_app(lineup_data):
    """Formata per a l'app"""
    if "error" in lineup_data:
        return lineup_data
    
    players = lineup_data["cn_terrassa_players"]
    
    return {
        "players": players,
        "rival_team": lineup_data.get("rival_team", ""),
        "rival_players": [],
        "js_code": "let players = " + json.dumps(players, ensure_ascii=False, indent=2) + ";",
        "count": len(players)
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ús: python match_lineup_parser.py <URL_PARTIT>")
        sys.exit(1)
    
    match_url = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("🏊 CN TERRASSA - Parser de Convocatòries")
    print(f"{'='*60}\n")
    
    lineup_data = get_match_lineup(match_url)
    formatted = format_for_app(lineup_data)
    
    if "error" in formatted:
        print(f"\n❌ ERROR: {formatted['error']}\n")
        sys.exit(1)
    
    print(f"\n✅ Jugadors trobats: {formatted['count']}")
    
    if formatted['count'] > 0:
        print("\n📋 Llista completa:")
        for player in formatted['players']:
            print(f"   {player['num']:2d}. {player['name']}")
    
    if formatted['rival_team']:
        print(f"\n🆚 Rival: {formatted['rival_team']}")
    
    # Guardar JSON
    match_id = lineup_data.get('match_id', 'unknown')
    output_file = f"match_{match_id}_lineup.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Fitxer: {output_file}\n")
    print("="*60 + "\n")
