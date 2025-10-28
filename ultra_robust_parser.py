"""
Parser ULTRA-ROBUST per jugadors ACTAWP
Prova tots els mètodes possibles per extreure headers correctament
"""

import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

class UltraRobustActawpParser:
    
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
    
    def extract_header_text(self, th):
        """
        Extreu el text del header provant múltiples mètodes
        Retorna el text més descriptiu possible
        """
        candidates = []
        
        # Mètode 1: Atribut title
        title = th.get('title', '').strip()
        if title:
            candidates.append(('title', title))
        
        # Mètode 2: Span amb title
        span = th.find('span')
        if span:
            span_title = span.get('title', '').strip()
            if span_title:
                candidates.append(('span_title', span_title))
            
            span_text = span.get_text(strip=True)
            if span_text:
                candidates.append(('span_text', span_text))
        
        # Mètode 3: Text directe del th
        th_text = th.get_text(strip=True)
        if th_text:
            candidates.append(('th_text', th_text))
        
        # Mètode 4: data-original-title (Bootstrap tooltips)
        data_title = th.get('data-original-title', '').strip()
        if data_title:
            candidates.append(('data_title', data_title))
        
        # Prioritat: title > span_title > span_text > th_text
        priority = ['title', 'span_title', 'data_title', 'span_text', 'th_text']
        
        for method in priority:
            for candidate_method, candidate_text in candidates:
                if candidate_method == method and candidate_text:
                    return candidate_text
        
        # Si no hem trobat res, retornar el primer que hi hagi
        if candidates:
            return candidates[0][1]
        
        return ''
    
    def parse_players_ultra_robust(self, html_content):
        """Parser ultra-robust per jugadors"""
        soup = BeautifulSoup(html_content, 'html.parser')
        players = []
        
        table = soup.find('table')
        if not table:
            print("  ⚠️ No s'ha trobat cap taula")
            return players
        
        # Extreure headers amb mètode robust
        headers = []
        thead = table.find('thead')
        if thead:
            ths = thead.find_all('th')
            print(f"  📋 Trobats {len(ths)} headers")
            
            for i, th in enumerate(ths):
                header_text = self.extract_header_text(th)
                headers.append(header_text)
                print(f"     {i+1}. \"{header_text}\"")
        
        if not headers:
            print("  ⚠️ No s'han trobat headers!")
            return players
        
        # Extreure dades
        tbody = table.find('tbody')
        if not tbody:
            print("  ⚠️ No s'ha trobat tbody")
            return players
        
        rows = tbody.find_all('tr')
        print(f"  👥 Trobades {len(rows)} files de jugadors")
        
        for row_idx, row in enumerate(rows, 1):
            cells = row.find_all('td')
            
            if len(cells) < 2:
                continue
            
            player_data = {}
            
            for i, cell in enumerate(cells):
                if i >= len(headers):
                    break
                
                header = headers[i]
                if not header:
                    continue
                
                # Extreure text de la cel·la
                value = cell.get_text(strip=True)
                value = re.sub(r'\s+', ' ', value)
                
                # Netejar "Ver" dels noms
                if i == 0 or 'nombre' in header.lower() or 'nom' in header.lower():
                    value = re.sub(r'\bVer\b\s*', '', value, flags=re.IGNORECASE).strip()
                
                # Convertir a número si és possible
                if value and value not in ['', '-', '—', 'N/A']:
                    try:
                        if value.isdigit():
                            value = int(value)
                        elif ',' in value or '.' in value:
                            value_cleaned = value.replace(',', '.')
                            if value_cleaned.replace('.', '').isdigit():
                                value = float(value_cleaned)
                    except:
                        pass
                else:
                    # Si està buit i no és un camp de text, posar 0
                    if i > 0 and header.lower() not in ['nombre', 'nom', 'name', 'vinculado', 'posición', 'posicio']:
                        value = 0
                
                player_data[header] = value
            
            if player_data:
                players.append(player_data)
                
                # Debug: mostrar primer jugador complet
                if row_idx == 1:
                    print(f"\n  🔍 Primer jugador (debug):")
                    for key, val in player_data.items():
                        print(f"     {key}: {val}")
                    print()
        
        return players
    
    def parse_table_matches(self, html_content):
        """Parser per partits (igual que abans)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        matches = []
        
        table = soup.find('table')
        if not table:
            return matches
        
        tbody = table.find('tbody')
        if not tbody:
            return matches
        
        rows = tbody.find_all('tr')
        
        for row in rows:
            try:
                match_info = {}
                cols = row.find_all('td')
                
                if len(cols) < 3:
                    continue
                
                # Columna 1: Equip 1
                col1 = cols[0]
                team1_span = col1.find('span', class_='ellipsis')
                if team1_span:
                    match_info['team1'] = team1_span.get_text(strip=True)
                
                # Enllaç
                link = col1.find('a', href=True)
                if link:
                    href = link['href']
                    match_info['url'] = href if href.startswith('http') else 'https://actawp.natacio.cat' + href
                    match_id_search = re.search(r'/match/(\d+)', href)
                    if match_id_search:
                        match_info['match_id'] = match_id_search.group(1)
                
                # Columna 2: Data
                col2 = cols[1]
                date_span = col2.find('span', attrs={'data-sort': True})
                if date_span:
                    date_text = date_span.get_text(strip=True)
                    date_match = re.search(r'([A-Za-z]{3},?\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', date_text)
                    if date_match:
                        full_date = date_match.group(1)
                        match_info['date_time'] = full_date
                        parts = full_date.split()
                        if len(parts) >= 3:
                            match_info['date'] = parts[1]
                            match_info['time'] = parts[2]
                    
                    venue_span = date_span.find('span', class_='ellipsis')
                    if venue_span:
                        match_info['venue'] = venue_span.get('title') or venue_span.get_text(strip=True)
                
                # Columna 3: Equip 2
                col3 = cols[2]
                team2_span = col3.find('span', class_='ellipsis')
                if team2_span:
                    match_info['team2'] = team2_span.get_text(strip=True)
                
                # Determinar home/away
                if 'team1' in match_info and 'TERRASSA' in match_info['team1'].upper():
                    match_info['home_team'] = match_info['team1']
                    match_info['away_team'] = match_info.get('team2', '')
                else:
                    match_info['home_team'] = match_info.get('team2', '')
                    match_info['away_team'] = match_info.get('team1', '')
                
                if match_info.get('match_id'):
                    matches.append(match_info)
                
            except Exception as e:
                continue
        
        return matches
    
    def generate_json(self, team_id, team_key, team_name, coach, language='es'):
        """Genera JSON amb parser ultra-robust"""
        print(f"\n{'='*70}")
        print(f"📥 {team_name} - Parser Ultra-Robust")
        print(f"{'='*70}")
        
        result = {
            "metadata": {
                "source": "ACTAWP",
                "team_key": team_key,
                "team_id": team_id,
                "team_name": team_name,
                "coach": coach,
                "downloaded_at": datetime.now().isoformat(),
                "parser_version": "4.0_ultra_robust"
            }
        }
        
        # Jugadors
        print("\n1️⃣ JUGADORS:")
        players_data = self.get_tab_content(team_id, 'players', language)
        if players_data and players_data.get('code') == 0:
            result['players'] = self.parse_players_ultra_robust(players_data.get('content', ''))
            print(f"  ✅ {len(result['players'])} jugadors extrets")
            
            if result['players']:
                first_player = result['players'][0]
                print(f"\n  📊 Camps disponibles:")
                for key in first_player.keys():
                    print(f"     • {key}")
        else:
            result['players'] = []
            print("  ❌ Error obtenint jugadors")
        
        # Estadístiques (igual que abans)
        print("\n2️⃣ ESTADÍSTIQUES:")
        stats_data = self.get_tab_content(team_id, 'stats', language)
        team_stats = {}
        if stats_data and stats_data.get('code') == 0:
            soup = BeautifulSoup(stats_data.get('content', ''), 'html.parser')
            table = soup.find('table')
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
        
        # Pròxims partits
        print("\n3️⃣ PRÒXIMS PARTITS:")
        upcoming_data = self.get_tab_content(team_id, 'upcoming-matches', language)
        if upcoming_data and upcoming_data.get('code') == 0:
            result['upcoming_matches'] = self.parse_table_matches(upcoming_data.get('content', ''))
            print(f"  ✅ {len(result['upcoming_matches'])} partits")
        else:
            result['upcoming_matches'] = []
        
        # Últims resultats
        print("\n4️⃣ ÚLTIMS RESULTATS:")
        results_data = self.get_tab_content(team_id, 'last-results', language)
        if results_data and results_data.get('code') == 0:
            result['last_results'] = self.parse_table_matches(results_data.get('content', ''))
            print(f"  ✅ {len(result['last_results'])} resultats")
        else:
            result['last_results'] = []
        
        return result


if __name__ == "__main__":
    parser = UltraRobustActawpParser()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║   PARSER ULTRA-ROBUST ACTAWP v4.0                           ║
║   Múltiples mètodes per extreure headers i dades            ║
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
            data = parser.generate_json(
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
            
            # Mostrar exemple
            if data['players']:
                print(f"\n📊 Exemple primer jugador:")
                first = data['players'][0]
                for k, v in list(first.items())[:5]:
                    print(f"   {k}: {v}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70)
    
    print("""
✅ FITXERS GENERATS!

🔍 REVISA LA SORTIDA:
- Mira quins headers s'han detectat
- Comprova les dades del primer jugador
- Si els valors són 0, els headers no són correctes

📤 Puja els nous JSON a GitHub per veure si ara funciona!
""")
