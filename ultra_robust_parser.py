"""
Parser FINAL ACTAWP v5.0
Descarrega + Normalitza automàticament
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
    
    def extract_header_text(self, th):
        """Extreu el text del header"""
        candidates = []
        
        title = th.get('title', '').strip()
        if title:
            candidates.append(('title', title))
        
        span = th.find('span')
        if span:
            span_title = span.get('title', '').strip()
            if span_title:
                candidates.append(('span_title', span_title))
            
            span_text = span.get_text(strip=True)
            if span_text:
                candidates.append(('span_text', span_text))
        
        th_text = th.get_text(strip=True)
        if th_text:
            candidates.append(('th_text', th_text))
        
        data_title = th.get('data-original-title', '').strip()
        if data_title:
            candidates.append(('data_title', data_title))
        
        priority = ['title', 'span_title', 'data_title', 'span_text', 'th_text']
        
        for method in priority:
            for candidate_method, candidate_text in candidates:
                if candidate_method == method and candidate_text:
                    return candidate_text
        
        if candidates:
            return candidates[0][1]
        
        return ''
    
    def normalize_field_name(self, field_name):
        """Normalitza nom de camp al format curt esperat per l'index.html"""
        # Mapping CATALÀ i ESPANYOL → curt
        field_mapping = {
            # Català
            'Nom': 'Nombre',
            'Partits jugats': 'PJ',
            'Total goals': 'GT',
            'Gols': 'G',
            'Gols penal': 'GP',
            'Gols en tanda de penals': 'G5P',
            'Targetes grogues': 'TA',
            'Targetes vermelles': 'TR',
            'Expulsions per 20 segons': 'EX',
            'Expulsions definitives, amb substitució disciplinària': 'ED',
            'Expulsions definitives per brutalitat, amb substitució als 4 minuts': 'EB',
            'Expulsions definitives, amb substitució no disciplinària': 'EN',
            'Expulsions i penal': 'EP',
            'Faltes per penal': 'P',
            'Penals fallats': 'PF',
            'Altres': 'O',
            'Temps morts': 'TM',
            'Joc net': 'JL',
            'Vinculat': 'Vinculado',
            
            # Espanyol
            'Nombre': 'Nombre',
            'Partidos jugados': 'PJ',
            'Goles totales': 'GT',
            'Goles': 'G',
            'Goles de penalti': 'GP',
            'Goles en tanda de penaltis': 'G5P',
            'Tarjetas amarillas': 'TA',
            'Tarjetas rojas': 'TR',
            'Expulsiones por 20 segundos': 'EX',
            'Expulsiones definitivas, con sustitución disciplinaria': 'ED',
            'Expulsiones definitivas por brutalidad, con sustitución a los 4 minutos': 'EB',
            'Expulsiones definitivas, con sustitución no disciplinaria': 'EN',
            'Expulsiones y penalti': 'EP',
            'Faltas por penalti': 'P',
            'Penaltis fallados': 'PF',
            'Otros': 'O',
            'Tiempos muertos': 'TM',
            'Juego limpio': 'JL',
            'Vinculado': 'Vinculado',
            'MVP': 'MVP'
        }
        
        return field_mapping.get(field_name, field_name)
    
    def parse_players(self, html_content):
        """Parser de jugadors amb normalització automàtica"""
        soup = BeautifulSoup(html_content, 'html.parser')
        players = []
        
        table = soup.find('table')
        if not table:
            return players
        
        # Extreure headers
        headers = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all('th'):
                header_text = self.extract_header_text(th)
                headers.append(header_text)
        
        if not headers:
            return players
        
        # Extreure dades
        tbody = table.find('tbody')
        if not tbody:
            return players
        
        rows = tbody.find_all('tr')
        
        for row in rows:
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
                
                # Normalitzar nom del camp
                normalized_field = self.normalize_field_name(header)
                
                # Extreure valor
                value = cell.get_text(strip=True)
                value = re.sub(r'\s+', ' ', value)
                
                # Netejar "Ver" dels noms
                if normalized_field == 'Nombre' and value:
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
                    # Si està buit i no és text, posar 0
                    if i > 0 and normalized_field not in ['Nombre', 'Vinculado']:
                        value = 0
                
                player_data[normalized_field] = value
            
            if player_data:
                players.append(player_data)
        
        return players
    
    def parse_matches(self, html_content):
        """Parser per partits"""
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
                
                # Equip 1
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
                
                # Data
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
                
                # Equip 2
                col3 = cols[2]
                team2_span = col3.find('span', class_='ellipsis')
                if team2_span:
                    match_info['team2'] = team2_span.get_text(strip=True)
                
                # Home/Away
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
        """Genera JSON amb normalització automàtica"""
        print(f"\n{'='*70}")
        print(f"📥 {team_name} - Parser Final v5.0 (Auto-Normalize)")
        print(f"{'='*70}")
        
        result = {
            "metadata": {
                "source": "ACTAWP",
                "team_key": team_key,
                "team_id": team_id,
                "team_name": team_name,
                "coach": coach,
                "downloaded_at": datetime.now().isoformat(),
                "parser_version": "5.0_auto_normalize"
            }
        }
        
        # Jugadors
        print("\n1️⃣ JUGADORS:")
        players_data = self.get_tab_content(team_id, 'players', language)
        if players_data and players_data.get('code') == 0:
            result['players'] = self.parse_players(players_data.get('content', ''))
            print(f"  ✅ {len(result['players'])} jugadors")
            
            if result['players']:
                first = result['players'][0]
                print(f"\n  📊 Primer jugador (normalitzat):")
                print(f"     Nombre: {first.get('Nombre', '?')}")
                print(f"     PJ: {first.get('PJ', 0)}")
                print(f"     GT: {first.get('GT', 0)}")
                print(f"     G: {first.get('G', 0)}")
                print(f"     EX: {first.get('EX', 0)}")
        else:
            result['players'] = []
        
        # Estadístiques
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
            result['upcoming_matches'] = self.parse_matches(upcoming_data.get('content', ''))
            print(f"  ✅ {len(result['upcoming_matches'])} partits")
        else:
            result['upcoming_matches'] = []
        
        # Últims resultats
        print("\n4️⃣ ÚLTIMS RESULTATS:")
        results_data = self.get_tab_content(team_id, 'last-results', language)
        if results_data and results_data.get('code') == 0:
            result['last_results'] = self.parse_matches(results_data.get('content', ''))
            print(f"  ✅ {len(result['last_results'])} resultats")
        else:
            result['last_results'] = []
        
        return result


if __name__ == "__main__":
    parser = FinalActawpParser()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║   PARSER FINAL ACTAWP v5.0                                  ║
║   ✅ Descarrega automàtica                                  ║
║   ✅ Normalitza automàticament (PJ, GT, G, EX...)           ║
║   ✅ Suporta català i espanyol                              ║
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
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70)
    
    print("""
✅ FITXERS GENERATS AMB NORMALITZACIÓ AUTOMÀTICA!

📤 Puja'ls a GitHub:
   git add actawp_*.json
   git commit -m "✨ Dades ACTAWP normalitzades automàticament"
   git push

🔄 Aquest parser ja pots usar-lo a la GitHub Action!
""")
