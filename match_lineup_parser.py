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
                '--disable-http2',  # Desactivar HTTP/2
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        # Crear context amb user agent realista
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        
        page = context.new_page()
        
        try:
            print(f"🌐 Accedint a: {match_url}")
            
            # Intentar amb diferents estratègies
            try:
                page.goto(match_url, wait_until="networkidle", timeout=40000)
            except Exception as e1:
                print(f"⚠️  Primer intent fallit, provant alternativa...")
                try:
                    page.goto(match_url, wait_until="load", timeout=40000)
                except Exception as e2:
                    print(f"⚠️  Segon intent fallit, últim intent...")
                    page.goto(match_url, timeout=40000)
            
            page.wait_for_timeout(4000)  # Esperar JavaScript
            
            print("🔍 Buscant jugadors...")
            
            # Primer, intentar clicar pestanya de lineup/convocatòria
            try:
                print("🔎 Buscant pestanya de convocatòria...")
                links = page.query_selector_all('a, button, .tab, [role="tab"]')
                for link in links:
                    text = link.inner_text().lower()
                    if any(word in text for word in ['lineup', 'convocatoria', 'convocatòria', 'alineació', 'jugador']):
                        print(f"✅ Clicant pestanya: {link.inner_text()}")
                        link.click()
                        page.wait_for_timeout(2000)
                        break
            except Exception as e:
                print(f"⚠️  No s'ha trobat pestanya específica: {e}")
            
            # Buscar taules
            tables = page.query_selector_all('table')
            print(f"📊 Trobades {len(tables)} taules")
            
            for idx, table in enumerate(tables):
                table_text = table.inner_text().upper()
                table_html = table.inner_html()
                
                # Ignorar taula de marcador (conté molts números seguits)
                if re.search(r'\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+', table_text):
                    print(f"⏭️  Taula {idx+1}: Marcador/Estadístiques (ignorada)")
                    continue
                
                # Buscar taula amb TERRASSA i format de jugadors
                if 'TERRASSA' in table_text:
                    print(f"✅ Taula {idx+1}: CN Terrassa trobada!")
                    
                    # DEBUG: Mostrar estructura
                    lines_sample = table_text.split('\n')[:15]
                    print(f"📝 Contingut (primeres 15 línies):")
                    for i, line in enumerate(lines_sample):
                        if line.strip():
                            print(f"   {i+1:2d}. '{line.strip()[:80]}'")
                    
                    # Buscar capçalera amb "Nº" o "#" o "Dorsal"
                    has_number_header = any(word in table_html for word in ['Nº', '#', 'NUM', 'DORSAL', 'NUMBER'])
                    if has_number_header:
                        print("✓ Taula sembla tenir jugadors (té capçalera de números)")
                    
                    # Estratègia 1: Cel·les td/th tradicionals
                    rows = table.query_selector_all('tr')
                    print(f"📋 Files trobades: {len(rows)}")
                    
                    for row_idx, row in enumerate(rows):
                        cells = row.query_selector_all('td, th')
                        if len(cells) >= 2:
                            cell0 = cells[0].inner_text().strip()
                            cell1 = cells[1].inner_text().strip()
                            
                            # Verificar que el primer no és una capçalera
                            if cell0.upper() in ['Nº', '#', 'NUM', 'DORSAL', 'NUMBER', 'NÚMERO']:
                                continue
                            
                            num_match = re.search(r'^(\d{1,2})$', cell0)
                            if num_match and cell1 and len(cell1) > 2 and not cell1.isdigit():
                                print(f"   → Fila {row_idx}: {cell0} - {cell1}")
                                result["cn_terrassa_players"].append({
                                    "num": int(num_match.group(1)),
                                    "name": cell1.upper()
                                })
                    
                    print(f"✓ Estratègia 1: {len(result['cn_terrassa_players'])} jugadors")
                    
                    # Estratègia 2: Text amb patró número + nom
                    if not result["cn_terrassa_players"]:
                        print("🔍 Estratègia 2: cerca per patró...")
                        lines = table_text.split('\n')
                        for line in lines:
                            line = line.strip()
                            # Buscar: número (1-2 dígits) al principi + nom
                            match = re.match(r'^(\d{1,2})\s+([A-ZÀÈÉÍÒÓÚÇ][A-ZÀÈÉÍÒÓÚÇ\s\-\',\.]{3,})', line)
                            if match:
                                num = int(match.group(1))
                                name = match.group(2).strip()
                                # Filtrar noms vàlids
                                if (1 <= num <= 99 and 
                                    len(name) > 2 and 
                                    name not in ['TERRASSA', 'CN', 'C.N.', 'MONTJUIC'] and
                                    not re.match(r'^\d+$', name)):  # No és tot números
                                    print(f"   → {num} - {name}")
                                    result["cn_terrassa_players"].append({
                                        "num": num,
                                        "name": name.upper()
                                    })
                        print(f"✓ Estratègia 2: {len(result['cn_terrassa_players'])} jugadors")
                    
                    # Si hem trobat jugadors, sortir
                    if result["cn_terrassa_players"]:
                        break
            
            # Buscar equip rival
            if result["cn_terrassa_players"]:
                headers = page.query_selector_all('h2, h3, h4')
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
        print("\n📋 Llista:")
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
