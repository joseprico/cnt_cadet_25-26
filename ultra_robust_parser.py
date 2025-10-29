"""
Parser ACTAWP v5.4 - AMB LOGOS
Estructura correcta segons captures:
- Pròxims: [Equip1] [Data/Hora/Lloc] [Equip2]
- Resultats: [Equip1] [MARCADOR] [Equip2]
- NOVITAT: Extreu logos dels equips en tots els partits i classificació
"""

import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

class ActawpParserV53:
    
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
    
    def clean_player_name(self, name):
        """Neteja el nom del jugador eliminant Ver/Veure"""
        if not name:
            return name
        
        name = re.sub(r'^Veure', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^Ver', '', name, flags=re.IGNORECASE)
        
        return name.strip()
    
    def normalize_field_name(self, field_name):
        """Normalitza nom de camp al format curt esperat per l'index.html"""
        field_mapping = {
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
        
        headers = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all('th'):
                header_text = self.extract_header_text(th)
                headers.append(header_text)
        
        if not headers:
            return players
        
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
                
                normalized_field = self.normalize_field_name(header)
                value = cell.get_text(strip=True)
                value = re.sub(r'\s+', ' ', value)
                
                if normalized_field == 'Nombre' and value:
                    value = self.clean_player_name(value)
                
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
                    if i > 0 and normalized_field not in ['Nombre', 'Vinculado']:
                        value = 0
                
                player_data[normalized_field] = value
            
            if player_data:
                players.append(player_data)
        
        return players
    
    def parse_upcoming_matches(self, html_content):
        """
        Parser per PRÒXIMS PARTITS
        Estructura: [Equip1] [Data/Hora/Lloc] [Equip2]
        """
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
                cols = row.find_all('td')
                
                if len(cols) < 3:
                    continue
                
                match_info = {}
                
                # Columna 0: Equip 1 (local)
                team1_span = cols[0].find('span', class_='ellipsis')
                if team1_span:
                    match_info['team1'] = team1_span.get_text(strip=True)
                
                # Logo equip 1
                team1_logo = cols[0].find('img')
                if team1_logo and team1_logo.get('src'):
                    logo_src = team1_logo['src']
                    match_info['team1_logo'] = logo_src if logo_src.startswith('http') else 'https://actawp.natacio.cat' + logo_src
                else:
                    match_info['team1_logo'] = None
                
                # Enllaç
                link = cols[0].find('a', href=True)
                if link:
                    href = link['href']
                    match_info['url'] = href if href.startswith('http') else 'https://actawp.natacio.cat' + href
                    match_id_search = re.search(r'/match/(\d+)', href)
                    if match_id_search:
                        match_info['match_id'] = match_id_search.group(1)
                
                # Columna 1: Data/Hora/Lloc
                date_col = cols[1]
                date_text = date_col.get_text(strip=True)
                
                # Extreure data i hora
                date_match = re.search(r'(\w+,?\s+\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2})', date_text)
                if date_match:
                    match_info['date'] = date_match.group(1).replace(',', '').strip()
                    match_info['time'] = date_match.group(2)
                    match_info['date_time'] = f"{match_info['date']} {match_info['time']}"
                
                # Extreure lloc
                venue_match = re.search(r'(\d{1,2}:\d{2})\s*-\s*([^$]+)', date_text)
                if venue_match:
                    match_info['venue'] = venue_match.group(2).strip()
                
                # Columna 2: Equip 2 (visitant)
                team2_span = cols[2].find('span', class_='ellipsis')
                if team2_span:
                    match_info['team2'] = team2_span.get_text(strip=True)
                
                # Logo equip 2
                team2_logo = cols[2].find('img')
                if team2_logo and team2_logo.get('src'):
                    logo_src = team2_logo['src']
                    match_info['team2_logo'] = logo_src if logo_src.startswith('http') else 'https://actawp.natacio.cat' + logo_src
                else:
                    match_info['team2_logo'] = None
                
                if match_info.get('match_id'):
                    matches.append(match_info)
                
            except Exception as e:
                print(f"  ⚠️ Error processant pròxim partit: {e}")
                continue
        
        return matches
    
    def parse_last_results(self, html_content):
        """
        Parser per ÚLTIMS RESULTATS
        Estructura: [Equip1] [MARCADOR] [Equip2]
        """
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
                cols = row.find_all('td')
                
                if len(cols) < 3:
                    continue
                
                match_info = {}
                
                # Columna 0: Equip 1
                team1_span = cols[0].find('span', class_='ellipsis')
                if team1_span:
                    match_info['team1'] = team1_span.get_text(strip=True)
                
                # Logo equip 1
                team1_logo = cols[0].find('img')
                if team1_logo and team1_logo.get('src'):
                    logo_src = team1_logo['src']
                    match_info['team1_logo'] = logo_src if logo_src.startswith('http') else 'https://actawp.natacio.cat' + logo_src
                else:
                    match_info['team1_logo'] = None
                
                # Enllaç
                link = cols[0].find('a', href=True)
                if link:
                    href = link['href']
                    match_info['url'] = href if href.startswith('http') else 'https://actawp.natacio.cat' + href
                    match_id_search = re.search(r'/match/(\d+)', href)
                    if match_id_search:
                        match_info['match_id'] = match_id_search.group(1)
                
                # Columna 1: MARCADOR
                score_text = cols[1].get_text(strip=True)
                score_match = re.search(r'(\d+)\s*-\s*(\d+)', score_text)
                if score_match:
                    match_info['score_team1'] = int(score_match.group(1))
                    match_info['score_team2'] = int(score_match.group(2))
                    match_info['score'] = score_text
                
                # Columna 2: Equip 2
                team2_span = cols[2].find('span', class_='ellipsis')
                if team2_span:
                    match_info['team2'] = team2_span.get_text(strip=True)
                
                # Logo equip 2
                team2_logo = cols[2].find('img')
                if team2_logo and team2_logo.get('src'):
                    logo_src = team2_logo['src']
                    match_info['team2_logo'] = logo_src if logo_src.startswith('http') else 'https://actawp.natacio.cat' + logo_src
                else:
                    match_info['team2_logo'] = None
                
                if match_info.get('match_id'):
                    matches.append(match_info)
                
            except Exception as e:
                print(f"  ⚠️ Error processant resultat: {e}")
                continue
        
        return matches
    
    def parse_ranking(self, ranking_url):
        """
        Parser per CLASSIFICACIÓ
        Extreu la taula de classificació des d'una URL específica
        """
        try:
            response = self.session.get(ranking_url)
            if response.status_code != 200:
                print(f"  ⚠️ Error HTTP {response.status_code} al obtenir classificació")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            ranking = []
            
            # Buscar la taula de classificació
            table = soup.find('table', class_='table')
            if not table:
                table = soup.find('table')
            
            if not table:
                print("  ⚠️ No s'ha trobat cap taula de classificació")
                return []
            
            # Debug: mostrar headers
            headers = []
            thead = table.find('thead')
            if thead:
                for th in thead.find_all('th'):
                    header_text = th.get_text(strip=True)
                    headers.append(header_text)
                print(f"  📋 Headers trobats: {headers}")
            
            tbody = table.find('tbody')
            if not tbody:
                print("  ⚠️ No s'ha trobat tbody a la taula")
                return []
            
            rows = tbody.find_all('tr')
            print(f"  📊 Files trobades: {len(rows)}")
            
            for idx, row in enumerate(rows):
                try:
                    cols = row.find_all('td')
                    
                    if len(cols) < 3:
                        continue
                    
                    # Debug primera fila
                    if idx == 0:
                        print(f"  🔍 Primera fila ({len(cols)} columnes):")
                        for i, col in enumerate(cols):
                            print(f"      Col {i}: '{col.get_text(strip=True)[:50]}'")
                    
                    # Identificar quina columna és quina
                    # Típicament: [Pos] [Equip] [PJ] [V] [E] [P] [GF] [GC] [Pts]
                    # Però pot variar, així que busquem l'equip (text més llarg)
                    
                    posicio_idx = 0
                    equip_idx = 1
                    
                    # Buscar la columna amb el nom de l'equip (normalment la més llarga o amb logo)
                    for i, col in enumerate(cols[:3]):
                        if col.find('img') or len(col.get_text(strip=True)) > 5:
                            equip_idx = i
                            break
                    
                    # La posició sol ser la columna anterior a l'equip
                    if equip_idx > 0:
                        posicio_idx = equip_idx - 1
                    
                    # Extreure posició
                    posicio_text = cols[posicio_idx].get_text(strip=True)
                    # Netejar "Veure" o altres textos
                    posicio_text = re.sub(r'Veure|Ver|View', '', posicio_text, flags=re.IGNORECASE).strip()
                    
                    # Extreure nom de l'equip i logo
                    equip_cell = cols[equip_idx]
                    equip_text = equip_cell.get_text(strip=True)
                    # Netejar "Veure" del nom
                    equip_text = re.sub(r'Veure|Ver|View', '', equip_text, flags=re.IGNORECASE).strip()
                    
                    # Buscar logo
                    logo_url = None
                    logo_img = equip_cell.find('img')
                    if logo_img and logo_img.get('src'):
                        logo_src = logo_img['src']
                        logo_url = logo_src if logo_src.startswith('http') else 'https://actawp.natacio.cat' + logo_src
                    
                    # Les estadístiques comencen després de l'equip
                    stats_start = equip_idx + 1
                    
                    team_data = {
                        'posicio': posicio_text,
                        'equip': equip_text,
                        'logo': logo_url,
                        'partits': 0,
                        'guanyats': 0,
                        'empatats': 0,
                        'perduts': 0,
                        'gols_favor': 0,
                        'gols_contra': 0,
                        'punts': 0
                    }
                    
                    # Extreure estadístiques (ordre típic: PJ, V, E, P, GF, GC, Pts)
                    stat_fields = ['partits', 'guanyats', 'empatats', 'perduts', 'gols_favor', 'gols_contra', 'punts']
                    
                    for i, field in enumerate(stat_fields):
                        col_idx = stats_start + i
                        if col_idx < len(cols):
                            value_text = cols[col_idx].get_text(strip=True)
                            if value_text.isdigit():
                                team_data[field] = int(value_text)
                    
                    # Només afegir si té dades vàlides
                    if team_data['equip'] and len(team_data['equip']) > 1:
                        ranking.append(team_data)
                    
                except Exception as e:
                    print(f"  ⚠️ Error processant fila {idx}: {e}")
                    continue
            
            return ranking
            
        except Exception as e:
            print(f"  ❌ Error obtenint classificació: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def generate_json(self, team_id, team_key, team_name, coach, language='es', ranking_url=None):
        """Genera JSON amb normalització automàtica"""
        print(f"\n{'='*70}")
        print(f"📥 {team_name} - Parser v5.3 (DEFINITIU)")
        print(f"{'='*70}")
        
        result = {
            "metadata": {
                "source": "ACTAWP",
                "team_key": team_key,
                "team_id": team_id,
                "team_name": team_name,
                "coach": coach,
                "downloaded_at": datetime.now().isoformat(),
                "parser_version": "5.4_logos"
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
                print(f"  📊 Primer: {first.get('Nombre', '?')} - PJ:{first.get('PJ', 0)} GT:{first.get('GT', 0)}")
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
            result['upcoming_matches'] = self.parse_upcoming_matches(upcoming_data.get('content', ''))
            print(f"  ✅ {len(result['upcoming_matches'])} partits")
            if result['upcoming_matches']:
                first = result['upcoming_matches'][0]
                print(f"  📅 Pròxim: {first.get('team1', '?')} vs {first.get('team2', '?')} - {first.get('date', '?')}")
        else:
            result['upcoming_matches'] = []
        
        # Últims resultats
        print("\n4️⃣ ÚLTIMS RESULTATS:")
        results_data = self.get_tab_content(team_id, 'last-results', language)
        if results_data and results_data.get('code') == 0:
            result['last_results'] = self.parse_last_results(results_data.get('content', ''))
            print(f"  ✅ {len(result['last_results'])} resultats")
            if result['last_results']:
                first = result['last_results'][0]
                score = first.get('score', '?')
                print(f"  📊 Últim: {first.get('team1', '?')} {score} {first.get('team2', '?')}")
        else:
            result['last_results'] = []
        
        # Classificació (si s'especifica URL)
        if ranking_url:
            print("\n5️⃣ CLASSIFICACIÓ:")
            result['ranking'] = self.parse_ranking(ranking_url)
            print(f"  ✅ {len(result['ranking'])} equips a la classificació")
            if result['ranking']:
                # Buscar CN Terrassa a la classificació
                cnt_position = None
                for team in result['ranking']:
                    if 'TERRASSA' in team['equip'].upper():
                        cnt_position = team
                        break
                if cnt_position:
                    print(f"  🏆 CN Terrassa: Posició {cnt_position['posicio']} - {cnt_position['punts']} punts")
        else:
            result['ranking'] = []
        
        # Afegir timestamp d'actualització amb timezone Europe/Madrid
        from datetime import timezone, timedelta
        tz_madrid = timezone(timedelta(hours=1))  # UTC+1 (o +2 en horari d'estiu)
        result['last_update'] = datetime.now(tz_madrid).isoformat()
        
        return result


if __name__ == "__main__":
    parser = ActawpParserV53()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║   PARSER ACTAWP v5.4 - AMB LOGOS                            ║
║   ✅ Noms nets (sense Ver/Veure)                           ║
║   ✅ Camps normalitzats (PJ, GT, G, EX...)                 ║
║   ✅ MARCADORS correctes dels resultats                     ║
║   ✅ DATES correctes dels pròxims partits                   ║
║   ⭐ LOGOS dels equips en partits i classificació           ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    teams = {
        'juvenil': {
            'id': '15621223',
            'name': 'CN Terrassa Juvenil',
            'coach': 'Jordi Busquets',
            'language': 'es',
            'ranking_url': 'https://actawp.natacio.cat/ca/tournament/1317471/ranking/3654570'
        },
        'cadet': {
            'id': '15621224',
            'name': 'CN Terrassa Cadet',
            'coach': 'Didac Cobacho',
            'language': 'ca',
            'ranking_url': 'https://actawp.natacio.cat/ca/tournament/1317474/ranking/3654582'
        }
    }
    
    for team_key, team_info in teams.items():
        try:
            data = parser.generate_json(
                team_info['id'],
                team_key,
                team_info['name'],
                team_info['coach'],
                team_info['language'],
                team_info.get('ranking_url')
            )
            
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
✅ JSON GENERATS CORRECTAMENT!

📤 Puja'ls a GitHub:
   git add actawp_*.json
   git commit -m "✨ Parser v5.3 definitiu amb marcadors"
   git push
""")