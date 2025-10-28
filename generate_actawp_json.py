"""
Genera fitxers JSON amb dades ACTAWP per pujar a GitHub
Compatible amb l'estructura actual de l'aplicació
"""

import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

class ActawpToGithub:
    
    TEAMS = {
        'cadet': {
            'url': 'https://actawp.natacio.cat/ca/team/15621224',
            'id': '15621224',
            'name': 'CN Terrassa Cadet',
            'language': 'ca',
            'coach': 'Didac Cobacho',
            'repo': 'joseprico/cnt_cadet_25-26'
        },
        'juvenil': {
            'url': 'https://actawp.natacio.cat/es/team/15621223',
            'id': '15621223',
            'name': 'CN Terrassa Juvenil',
            'language': 'es',
            'coach': 'Jordi Busquets',
            'repo': 'joseprico/CNT_juvenil_25_26'
        }
    }
    
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
    
    def parse_players(self, html_content):
        """Extreu jugadors amb estadístiques"""
        soup = BeautifulSoup(html_content, 'html.parser')
        players = []
        
        table = soup.find('table')
        if not table:
            return players
        
        headers = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all('th'):
                title = th.get('title', th.find('span').text if th.find('span') else th.text)
                headers.append(title.strip())
        
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    player_data = {}
                    
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            value = cell.text.strip()
                            value = re.sub(r'\s+', ' ', value)
                            
                            if headers[i] in ['Nombre', 'Nom']:
                                value = value.replace('Ver ', '').strip()
                            
                            header = headers[i]
                            
                            try:
                                if ',' in value:
                                    value = float(value.replace(',', '.'))
                                elif value.isdigit():
                                    value = int(value)
                            except:
                                pass
                            
                            player_data[header] = value
                    
                    if player_data:
                        players.append(player_data)
        
        return players
    
    def parse_team_stats(self, html_content):
        """Extreu estadístiques de l'equip"""
        soup = BeautifulSoup(html_content, 'html.parser')
        stats = {}
        
        table = soup.find('table')
        if not table:
            return stats
        
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stat_name = cells[0].text.strip()
                    stat_name = re.sub(r'\s+', ' ', stat_name)
                    
                    stat_value = cells[1].text.strip()
                    stat_value = re.sub(r'\s+', ' ', stat_value)
                    
                    try:
                        if ',' in stat_value:
                            stat_value = float(stat_value.replace(',', '.'))
                        elif stat_value.isdigit():
                            stat_value = int(stat_value)
                    except:
                        pass
                    
                    stats[stat_name] = stat_value
        
        return stats
    
    def parse_upcoming_matches(self, html_content):
        """Extreu pròxims partits"""
        soup = BeautifulSoup(html_content, 'html.parser')
        matches = []
        
        # Buscar elements amb enllaç a /match/
        match_links = soup.find_all('a', href=re.compile(r'/match/\d+'))
        
        for link in match_links:
            match_info = {}
            
            # URL i ID del partit
            href = link.get('href')
            match_info['url'] = 'https://actawp.natacio.cat' + href
            match_id_match = re.search(r'/match/(\d+)', href)
            if match_id_match:
                match_info['match_id'] = match_id_match.group(1)
            
            # Buscar el contenidor del partit
            parent = link
            for _ in range(5):  # Buscar fins a 5 nivells amunt
                parent = parent.parent
                if not parent:
                    break
                
                # Buscar data, hora, equips dins del contenidor
                date_elem = parent.find(class_=re.compile(r'date|data|fecha'))
                if date_elem and 'date' not in match_info:
                    match_info['date'] = date_elem.text.strip()
                
                time_elem = parent.find(class_=re.compile(r'time|hora'))
                if time_elem and 'time' not in match_info:
                    match_info['time'] = time_elem.text.strip()
                
                # Equips
                team_elems = parent.find_all(class_=re.compile(r'team|equip'))
                if len(team_elems) >= 2 and 'home_team' not in match_info:
                    match_info['home_team'] = team_elems[0].text.strip()
                    match_info['away_team'] = team_elems[1].text.strip()
                
                if 'date' in match_info and 'home_team' in match_info:
                    break
            
            # Si no ha trobat equips, buscar-los al text del link
            if 'home_team' not in match_info:
                text = link.get_text()
                if ' vs ' in text:
                    teams = text.split(' vs ')
                    if len(teams) == 2:
                        match_info['home_team'] = teams[0].strip()
                        match_info['away_team'] = teams[1].strip()
                elif ' - ' in text:
                    teams = text.split(' - ')
                    if len(teams) == 2:
                        match_info['home_team'] = teams[0].strip()
                        match_info['away_team'] = teams[1].strip()
            
            if match_info and 'match_id' in match_info:
                matches.append(match_info)
        
        # Eliminar duplicats per match_id
        unique_matches = {}
        for match in matches:
            match_id = match.get('match_id')
            if match_id and match_id not in unique_matches:
                unique_matches[match_id] = match
        
        return list(unique_matches.values())
    
    def generate_github_json(self, team_key):
        """Genera el fitxer JSON per pujar a GitHub"""
        team_info = self.TEAMS[team_key]
        team_id = team_info['id']
        language = team_info['language']
        
        print(f"\n{'='*70}")
        print(f"📥 Descarregant dades ACTAWP per {team_info['name']}")
        print(f"{'='*70}")
        
        # Obtenir dades
        print("   Obtenint jugadors...", end=' ')
        players_data = self.get_tab_content(team_id, 'players', language)
        players = []
        if players_data and players_data.get('code') == 0:
            players = self.parse_players(players_data.get('content', ''))
            print(f"✅ ({len(players)} jugadors)")
        else:
            print("❌")
        
        print("   Obtenint estadístiques...", end=' ')
        stats_data = self.get_tab_content(team_id, 'stats', language)
        team_stats = {}
        if stats_data and stats_data.get('code') == 0:
            team_stats = self.parse_team_stats(stats_data.get('content', ''))
            print(f"✅ ({len(team_stats)} estadístiques)")
        else:
            print("❌")
        
        print("   Obtenint pròxims partits...", end=' ')
        upcoming_data = self.get_tab_content(team_id, 'upcoming-matches', language)
        upcoming_matches = []
        if upcoming_data and upcoming_data.get('code') == 0:
            upcoming_matches = self.parse_upcoming_matches(upcoming_data.get('content', ''))
            print(f"✅ ({len(upcoming_matches)} partits)")
        else:
            print("❌")
        
        print("   Obtenint últims resultats...", end=' ')
        results_data = self.get_tab_content(team_id, 'last-results', language)
        last_results = []
        if results_data and results_data.get('code') == 0:
            last_results = self.parse_upcoming_matches(results_data.get('content', ''))
            print(f"✅ ({len(last_results)} resultats)")
        else:
            print("❌")
        
        # Generar JSON compatible amb l'estructura de GitHub
        github_json = {
            "metadata": {
                "source": "ACTAWP",
                "team_key": team_key,
                "team_name": team_info['name'],
                "team_id": team_id,
                "coach": team_info['coach'],
                "actawp_url": team_info['url'],
                "downloaded_at": datetime.now().isoformat(),
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "players": players,
            "team_stats": team_stats,
            "upcoming_matches": upcoming_matches,
            "last_results": last_results
        }
        
        # Guardar JSON
        filename = f"actawp_{team_key}_data.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(github_json, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Fitxer generat: {filename}")
        print(f"📤 Puja aquest fitxer al repositori GitHub: {team_info['repo']}")
        
        return github_json


if __name__ == "__main__":
    generator = ActawpToGithub()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║   ACTAWP → GitHub JSON Generator                            ║
║   Genera fitxers JSON amb dades ACTAWP per pujar a GitHub   ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Generar per tots dos equips
    for team_key in ['cadet', 'juvenil']:
        try:
            data = generator.generate_github_json(team_key)
            
            print(f"\n📊 Resum:")
            print(f"   Jugadors: {len(data['players'])}")
            print(f"   Estadístiques: {len(data['team_stats'])}")
            print(f"   Pròxims partits: {len(data['upcoming_matches'])}")
            print(f"   Últims resultats: {len(data['last_results'])}")
            
        except Exception as e:
            print(f"\n❌ Error generant dades per {team_key}: {e}")
        
        print("\n" + "="*70)
    
    print("""
✅ FITXERS GENERATS!

📝 PRÒXIMS PASSOS:

1. Puja els fitxers JSON generats als repositoris de GitHub:
   - actawp_cadet_data.json → joseprico/cnt_cadet_25-26
   - actawp_juvenil_data.json → joseprico/CNT_juvenil_25_26

2. Modifica l'index.html per carregar i mostrar aquestes dades

3. Configura una GitHub Action per actualitzar automàticament
""")
