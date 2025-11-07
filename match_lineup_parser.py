"""
Parser per obtenir la convocatòria d'un partit específic de ACTAWP
Exemple d'ús:
    python match_lineup_parser.py https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results
"""

import requests
from bs4 import BeautifulSoup
import json
import sys
import re

def get_match_lineup(match_url):
    """
    Obté els jugadors convocats per CN Terrassa d'un partit específic
    """
    try:
        # Fer la petició amb headers per simular un navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        session = requests.Session()
        
        # Primer obtenir el CSRF token de la pàgina principal
        response = session.get(match_url, headers=headers)
        
        if response.status_code != 200:
            return {"error": f"Error {response.status_code} al accedir a la URL"}
        
        # Buscar el match_id a la URL
        match_id_search = re.search(r'/match/(\d+)', match_url)
        if not match_id_search:
            return {"error": "No s'ha pogut trobar l'ID del partit a la URL"}
        
        match_id = match_id_search.group(1)
        
        # Intentar obtenir les dades via AJAX (com fa la pàgina web)
        ajax_url = f"https://actawp.natacio.cat/ca/ajax/match/{match_id}/change-tab"
        
        # Buscar CSRF token
        csrf_token = None
        csrf_match = re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)["\']', response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        
        if not csrf_token:
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_input = soup.find('input', {'name': 'csrf_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
        
        result = {
            "match_url": match_url,
            "match_id": match_id,
            "cn_terrassa_players": [],
            "rival_team": "",
            "rival_players": []
        }
        
        # Intentar obtenir la pestanya de "lineup" o "players"
        if csrf_token:
            data = {
                'csrf_token': csrf_token,
                'tab': 'lineup'  # o 'players' segons la pàgina
            }
            
            ajax_headers = headers.copy()
            ajax_headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': match_url
            })
            
            ajax_response = session.post(ajax_url, data=data, headers=ajax_headers)
            
            if ajax_response.status_code == 200:
                try:
                    ajax_data = ajax_response.json()
                    if ajax_data.get('code') == 0:
                        content = ajax_data.get('content', '')
                        result = parse_lineup_content(content, result)
                except:
                    pass
        
        # Si no hem obtingut res via AJAX, intentar parsejar el HTML directe
        if not result["cn_terrassa_players"]:
            soup = BeautifulSoup(response.text, 'html.parser')
            result = parse_lineup_from_html(soup, result)
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

def parse_lineup_content(html_content, result):
    """
    Parseja el contingut HTML per obtenir les convocatòries
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Buscar taules de jugadors
    tables = soup.find_all('table')
    
    for table in tables:
        # Buscar capçalera que indiqui CN TERRASSA
        header = table.find_previous(['h3', 'h4', 'div'], string=re.compile(r'TERRASSA', re.I))
        
        if header:
            # És la taula de CN Terrassa
            result["cn_terrassa_players"] = extract_players_from_table(table)
        else:
            # Podria ser la taula rival
            rival_header = table.find_previous(['h3', 'h4', 'div'])
            if rival_header and result["rival_team"] == "":
                result["rival_team"] = rival_header.get_text(strip=True)
                result["rival_players"] = extract_players_from_table(table)
    
    return result

def parse_lineup_from_html(soup, result):
    """
    Parseja directament el HTML de la pàgina quan no hi ha AJAX
    """
    # Buscar seccions d'equips
    team_sections = soup.find_all(['div', 'section'], class_=re.compile(r'team|lineup', re.I))
    
    for section in team_sections:
        team_name_elem = section.find(['h2', 'h3', 'h4'])
        if team_name_elem:
            team_name = team_name_elem.get_text(strip=True)
            
            if 'TERRASSA' in team_name.upper():
                # Buscar taula de jugadors dins aquesta secció
                table = section.find('table')
                if table:
                    result["cn_terrassa_players"] = extract_players_from_table(table)
            else:
                if result["rival_team"] == "":
                    result["rival_team"] = team_name
                    table = section.find('table')
                    if table:
                        result["rival_players"] = extract_players_from_table(table)
    
    return result

def extract_players_from_table(table):
    """
    Extreu jugadors d'una taula HTML
    """
    players = []
    
    tbody = table.find('tbody')
    if not tbody:
        return players
    
    rows = tbody.find_all('tr')
    
    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 2:
            continue
        
        # Primer columna sol ser el número
        num_text = cols[0].get_text(strip=True)
        
        # Segon columna sol ser el nom
        name_text = cols[1].get_text(strip=True)
        
        # Intentar extraure número
        num_match = re.search(r'\d+', num_text)
        if num_match and name_text:
            player = {
                "num": int(num_match.group()),
                "name": name_text.strip().upper()
            }
            players.append(player)
    
    return players

def format_for_app(lineup_data):
    """
    Formata les dades per a l'app d'entrada de dades
    """
    if "error" in lineup_data:
        return lineup_data
    
    # Ordenar jugadors per número
    players = sorted(lineup_data["cn_terrassa_players"], key=lambda x: x["num"])
    
    # Format JavaScript per copiar directament
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
        print("Exemple: python match_lineup_parser.py https://actawp.natacio.cat/ca/tournament/1317474/match/143260144/results")
        sys.exit(1)
    
    match_url = sys.argv[1]
    
    print(f"\n🔍 Obtenint convocatòria de: {match_url}\n")
    
    lineup_data = get_match_lineup(match_url)
    formatted = format_for_app(lineup_data)
    
    if "error" in formatted:
        print(f"❌ Error: {formatted['error']}")
        sys.exit(1)
    
    print(f"✅ Trobats {formatted['count']} jugadors de CN Terrassa:")
    for player in formatted['players']:
        print(f"   {player['num']:2d}. {player['name']}")
    
    if formatted['rival_team']:
        print(f"\n🆚 Equip rival: {formatted['rival_team']}")
        if formatted['rival_players']:
            print(f"   Jugadors rivals: {len(formatted['rival_players'])}")
    
    # Guardar a fitxer JSON
    output_file = "match_lineup.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Dades guardades a: {output_file}")
    print("\n📋 Codi JavaScript per copiar a l'app:")
    print("=" * 60)
    print(formatted['js_code'])
    print("=" * 60)
