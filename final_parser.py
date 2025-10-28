"""
Parser DEFINITIU ACTAWP - Extreu dates i tota la informació correctament
Basat en l'estructura real de l'HTML
"""

import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

class FinalActawpParser:
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_csrf_token(self, team_id, language='es'):
        """Obté el token CSRF"""
        url = f"https://actawp.natacio.cat/{language}/team/{team_id}"
        response = self.session.get(url)
        
        match = re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)["\']', response.text)
        if match:
            return match.group(1)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            return csrf_input.get('value')
        
        return None
    
    def get_tab_content(self, team_id, tab_name, language='es'):
        """Obté el contingut d'una pestanya"""
        csrf_token = self.get_csrf_token(team_id, language)
        
        if not csrf_token:
            return None
        
        url = f"https://actawp.natacio.cat/{language}/ajax/team/{team_id}/change-tab"
        
        data = {
            'csrf_token': csrf_token,
            'tab': tab_name
        }
        
        headers = {
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'x-requested-with': 'XMLHttpRequest',
            'referer': f'https://actawp.natacio.cat/{language}/team/{team_id}'
        }
        
        response = self.session.post(url, data=data, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    
    def parse_table_matches(self, html_content):
        """Parser específic per la taula de partits d'ACTAWP"""
        soup = BeautifulSoup(html_content, 'html.parser')
        matches = []
        
        print("  🔍 Parseant taula de partits...")
        
        # Trobar la taula
        table = soup.find('table')
        if not table:
            print("  ⚠️ No s'ha trobat cap taula")
            return matches
        
        tbody = table.find('tbody')
        if not tbody:
            print("  ⚠️ No s'ha trobat tbody")
            return matches
        
        rows = tbody.find_all('tr')
        print(f"  📊 Trobades {len(rows)} files")
        
        for i, row in enumerate(rows, 1):
            try:
                match_info = {}
                
                # Trobar totes les columnes
                cols = row.find_all('td')
                
                if len(cols) < 3:
                    continue
                
                # COLUMNA 1: Equip 1 (colstyle-equipo-1)
                col1 = cols[0]
                team1_span = col1.find('span', class_='ellipsis')
                if team1_span:
                    match_info['team1'] = team1_span.get_text(strip=True)
                
                # Enllaç del partit
                link = col1.find('a', href=True)
                if link:
                    href = link['href']
                    match_info['url'] = href if href.startswith('http') else 'https://actawp.natacio.cat' + href
                    match_id_search = re.search(r'/match/(\d+)', href)
                    if match_id_search:
                        match_info['match_id'] = match_id_search.group(1)
                
                # COLUMNA 2: Resultat/Data (colstyle-resultado)
                col2 = cols[1]
                
                # Buscar el span amb data-sort que conté el timestamp i la data
                date_span = col2.find('span', attrs={'data-sort': True})
                if date_span:
                    # El text del span conté la data legible
                    date_text = date_span.get_text(strip=True)
                    
                    # Extreure la data (abans del primer <span> intern)
                    # Format: "Dom, 09/11/2025 13:55"
                    date_match = re.search(r'([A-Za-z]{3},?\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', date_text)
                    if date_match:
                        full_date = date_match.group(1)
                        match_info['date_time'] = full_date
                        
                        # Separar data i hora
                        parts = full_date.split()
                        if len(parts) >= 3:
                            match_info['date'] = parts[1]  # DD/MM/YYYY
                            match_info['time'] = parts[2]  # HH:MM
                    
                    # Buscar el lloc (span intern amb ellipsis)
                    venue_span = date_span.find('span', class_='ellipsis')
                    if venue_span:
                        venue_text = venue_span.get('title') or venue_span.get_text(strip=True)
                        match_info['venue'] = venue_text
                
                # COLUMNA 3: Equip 2 (colstyle-equipo-2)
                col3 = cols[2]
                team2_span = col3.find('span', class_='ellipsis')
                if team2_span:
                    match_info['team2'] = team2_span.get_text(strip=True)
                
                # Determinar qui és home i qui és away
                # Si l'equip 1 és CN TERRASSA, és home
                if 'team1' in match_info and 'TERRASSA' in match_info['team1'].upper():
                    match_info['home_team'] = match_info['team1']
                    match_info['away_team'] = match_info.get('team2', '')
                else:
                    match_info['home_team'] = match_info.get('team2', '')
                    match_info['away_team'] = match_info.get('team1', '')
                
                if match_info.get('match_id'):
                    matches.append(match_info)
                    print(f"    ✓ Partit {i}: {match_info.get('date', '?')} {match_info.get('time', '?')} - {match_info.get('home_team', '?')} vs {match_info.get('away_team', '?')}")
                
            except Exception as e:
                print(f"    ⚠️ Error processant fila {i}: {e}")
                continue
        
        return matches
    
    def parse_players_complete(self, html_content):
        """Parser complet per jugadors"""
        soup = BeautifulSoup(html_content, 'html.parser')
        players = []
        
        table = soup.find('table')
        if not table:
            return players
        
        # Headers
        headers = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all('th'):
                title = th.get('title')
                if not title:
                    span = th.find('span')
                    if span:
                        title = span.get('title') or span.text
                    else:
                        title = th.text
                header = title.strip()
                if header:
                    headers.append(header)
        
        print(f"  📋 Columnes: {', '.join(headers)}")
        
        # Dades
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                player_data = {}
                
                for i, cell in enumerate(cells):
                    if i >= len(headers):
                        break
                    
                    header = headers[i]
                    value = cell.get_text(strip=True)
                    value = re.sub(r'\s+', ' ', value)
                    
                    # Netejar noms
                    if header in ['Nombre', 'Nom', 'Name']:
                        value = re.sub(r'\bVer\b\s*', '', value, flags=re.IGNORECASE).strip()
                    
                    # Convertir números
                    if value and value not in ['', '-', '—', 'N/A']:
                        try:
                            if value.isdigit():
                                value = int(value)
                            elif ',' in value or '.' in value:
                                value = float(value.replace(',', '.'))
                        except:
                            pass
                    else:
                        value = 0 if header not in ['Nombre', 'Nom', 'Name', 'Vinculado', 'Posición'] else value
                    
                    player_data[header] = value
                
                if player_data:
                    players.append(player_data)
        
        return players
    
    def generate_complete_json(self, team_id, team_key, team_name, coach, language='es'):
        """Genera JSON complet amb totes les dades"""
        print(f"\n{'='*70}")
        print(f"📥 {team_name} - Parser Definitiu")
        print(f"{'='*70}")
        
        result = {
            "metadata": {
                "source": "ACTAWP",
                "team_key": team_key,
                "team_id": team_id,
                "team_name": team_name,
                "coach": coach,
                "downloaded_at": datetime.now().isoformat(),
                "parser_version": "3.0_final"
            }
        }
        
        # Jugadors
        print("\n1️⃣ JUGADORS:")
        players_data = self.get_tab_content(team_id, 'players', language)
        if players_data and players_data.get('code') == 0:
            result['players'] = self.parse_players_complete(players_data.get('content', ''))
            print(f"  ✅ {len(result['players'])} jugadors")
        else:
            result['players'] = []
            print("  ❌ No s'han pogut obtenir jugadors")
        
        # Estadístiques
        print("\n2️⃣ ESTADÍSTIQUES:")
        stats_data = self.get_tab_content(team_id, 'stats', language)
        if stats_data and stats_data.get('code') == 0:
            soup = BeautifulSoup(stats_data.get('content', ''), 'html.parser')
            table = soup.find('table')
            team_stats = {}
            if table:
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        try:
                            if value.isdigit():
                                value = int(value)
                            elif ',' in value:
                                value = float(value.replace(',', '.'))
                        except:
                            pass
                        team_stats[key] = value
            result['team_stats'] = team_stats
            print(f"  ✅ {len(team_stats)} estadístiques")
        else:
            result['team_stats'] = {}
            print("  ❌ No s'han pogut obtenir estadístiques")
        
        # Pròxims partits
        print("\n3️⃣ PRÒXIMS PARTITS:")
        upcoming_data = self.get_tab_content(team_id, 'upcoming-matches', language)
        if upcoming_data and upcoming_data.get('code') == 0:
            result['upcoming_matches'] = self.parse_table_matches(upcoming_data.get('content', ''))
            print(f"  ✅ {len(result['upcoming_matches'])} partits")
        else:
            result['upcoming_matches'] = []
            print("  ❌ No s'han pogut obtenir pròxims partits")
        
        # Últims resultats
        print("\n4️⃣ ÚLTIMS RESULTATS:")
        results_data = self.get_tab_content(team_id, 'last-results', language)
        if results_data and results_data.get('code') == 0:
            result['last_results'] = self.parse_table_matches(results_data.get('content', ''))
            print(f"  ✅ {len(result['last_results'])} resultats")
        else:
            result['last_results'] = []
            print("  ❌ No s'han pogut obtenir últims resultats")
        
        return result


if __name__ == "__main__":
    parser = FinalActawpParser()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║   PARSER DEFINITIU ACTAWP v3.0                              ║
║   ✅ Extreu dates correctament (DD/MM/YYYY HH:MM)           ║
║   ✅ Extreu TOTS els camps de jugadors                      ║
║   ✅ Estructura basada en l'HTML real d'ACTAWP              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    teams = {
        'juvenil': {
            'id': '15621223',
            'name': 'CN Terrassa Juvenil',
            'coach': 'Jordi Busquets',
            'language': 'es'
        },
        'cadet': {
            'id': '15621224',
            'name': 'CN Terrassa Cadet',
            'coach': 'Didac Cobacho',
            'language': 'ca'
        }
    }
    
    for team_key, team_info in teams.items():
        try:
            data = parser.generate_complete_json(
                team_info['id'],
                team_key,
                team_info['name'],
                team_info['coach'],
                team_info['language']
            )
            
            # Guardar
            filename = f"actawp_{team_key}_data.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Guardat: {filename}")
            
            # Mostrar exemple de partit
            if data['upcoming_matches']:
                first_match = data['upcoming_matches'][0]
                print(f"\n📋 Exemple de partit:")
                print(f"   Data: {first_match.get('date', 'N/A')}")
                print(f"   Hora: {first_match.get('time', 'N/A')}")
                print(f"   Partit: {first_match.get('home_team', '?')} vs {first_match.get('away_team', '?')}")
                print(f"   Lloc: {first_match.get('venue', 'N/A')}")
            
        except Exception as e:
            print(f"\n❌ Error amb {team_key}: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70)
    
    print("""
✅ FITXERS GENERATS!

📤 PRÒXIMS PASSOS:
1. Puja els fitxers JSON a GitHub:
   git add actawp_*.json
   git commit -m "✨ Actualitzar amb parser definitiu (dates completes)"
   git push

2. Refresca la web i comprova que ara surten les dates!
""")
