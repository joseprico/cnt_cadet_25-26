#!/usr/bin/env python3
"""
Script per actualitzar automàticament rivals_database.json
Extreu la plantilla del pròxim rival a partir de la seva última acta

Ús:
    python update_rivals_database.py cadet
    python update_rivals_database.py juvenil
"""

import requests
import json
import re
import sys
from bs4 import BeautifulSoup
from datetime import datetime

class RivalsUpdater:
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_csrf_token(self, team_id, language='ca'):
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
    
    def get_tab_content(self, team_id, tab_name, language='ca'):
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
    
    def get_last_match_url(self, team_id, language='ca'):
        """Obté l'URL de l'última acta d'un equip"""
        print(f"  📥 Obtenint últims resultats del team_id: {team_id}")
        
        results_data = self.get_tab_content(team_id, 'last-results', language)
        
        if not results_data or results_data.get('code') != 0:
            print(f"  ❌ No s'han pogut obtenir els resultats")
            return None
        
        soup = BeautifulSoup(results_data.get('content', ''), 'html.parser')
        
        # Buscar el primer enllaç a una acta
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/match/' in href:
                match_url = href if href.startswith('http') else 'https://actawp.natacio.cat' + href
                
                # IMPORTANT: Canviar /results per /stats per obtenir la taula de jugadors
                match_url = match_url.replace('/results', '/stats')
                
                print(f"  ✅ Última acta trobada: {match_url}")
                return match_url
        
        print(f"  ⚠️ No s'ha trobat cap acta")
        return None
    
    def extract_roster_from_match(self, match_url, rival_name):
        """Extreu la plantilla d'un equip d'una acta de partit"""
        print(f"  📥 Accedint a l'acta: {match_url}")
        
        try:
            response = self.session.get(match_url)
            if response.status_code != 200:
                print(f"  ❌ Error HTTP {response.status_code}")
                return None
            
            html_text = response.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            players = []
            rival_normalized = rival_name.upper().replace('C.N.', '').replace('C.E.', '').replace('U.E.', '').replace("'", "").replace("'", "").strip()
            
            print(f"  🔍 Buscant jugadors de: {rival_normalized}")
            
            # Netejar HTML per treballar amb text pla
            full_text = soup.get_text()
            
            # Buscar TOTES les seccions de jugadors (hi haurà 2: local i visitant)
            # El patró és: nom equip seguit de "Gols igualtat" o "DorsalNom"
            
            # Buscar la secció del rival - ha de ser la que conté el nom del rival
            # seguit de les estadístiques de jugadors
            
            # Primer trobem on apareix el rival amb estadístiques
            # Format típic: "U.E. D'HORTA\nGols igualtat:\n..." seguit de "DorsalNom..."
            
            # Buscar totes les taules de jugadors
            tables = soup.find_all('table')
            
            print(f"  📋 Taules trobades: {len(tables)}")
            
            for idx, table in enumerate(tables):
                # Obtenir text de la taula
                table_text = table.get_text()
                
                # Buscar si té el patró de jugadors (Dorsal, Nom, G, GS, etc.)
                if 'Dorsal' in table_text or 'Nom' in table_text:
                    # Mirar el context - buscar quin equip és aquesta taula
                    # Mirar elements anteriors
                    prev_text = ""
                    for prev in table.find_all_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'div', 'span'])[:20]:
                        prev_text = prev.get_text(strip=True).upper() + " " + prev_text
                        # Parar si trobem un dels equips
                        if 'HORTA' in prev_text or 'TERRASSA' in prev_text:
                            break
                    
                    # És la taula del rival?
                    # Netejar apòstrofs i comparar
                    prev_text_clean = prev_text.replace("'", "").replace("'", "")
                    rival_clean = rival_normalized.replace("'", "").replace("'", "")
                    
                    is_rival = False
                    # Buscar paraules clau del rival (ignorant apòstrofs)
                    for part in rival_clean.split():
                        if len(part) > 3 and part in prev_text_clean:
                            is_rival = True
                            break
                    
                    # També comprovar si "HORTA" està al context (cas específic)
                    if 'HORTA' in rival_name.upper() and 'HORTA' in prev_text and 'TERRASSA' not in prev_text[:50]:
                        is_rival = True
                    
                    print(f"  📋 Taula {idx}: is_rival={is_rival}, context={prev_text[:50]}...")
                    
                    if is_rival:
                        print(f"  ✅ Taula del rival trobada!")
                        
                        # Extreure jugadors de la taula
                        rows = table.find_all('tr')
                        print(f"  📋 Files trobades: {len(rows)}")
                        
                        # Primer, identificar les columnes pels headers
                        headers = table.find_all('th')
                        header_texts = [h.get_text(strip=True).upper() for h in headers]
                        print(f"  📋 Headers: {header_texts[:10]}")
                        
                        # Trobar índex de DORSAL i JUGADOR/NOM
                        dorsal_idx = -1
                        name_idx = -1
                        for i, h in enumerate(header_texts):
                            if 'DORSAL' in h:
                                dorsal_idx = i
                            if 'JUGADOR' in h or 'NOM' in h:
                                name_idx = i
                        
                        print(f"  📋 Índexs: dorsal={dorsal_idx}, name={name_idx}")
                        
                        # Si no trobem pels headers, assumir posicions típiques
                        if dorsal_idx == -1:
                            dorsal_idx = 2  # Típicament la 3a columna (0-indexed)
                        if name_idx == -1:
                            name_idx = 3  # Típicament la 4a columna
                        
                        for row_idx, row in enumerate(rows):
                            cells = row.find_all('td')
                            
                            # Debug primera fila
                            if row_idx == 0 and cells:
                                print(f"  📋 Primera fila ({len(cells)} cel·les):")
                                for ci, c in enumerate(cells[:6]):
                                    print(f"      [{ci}]: {c.get_text(strip=True)[:30]}")
                            
                            if len(cells) > max(dorsal_idx, name_idx):
                                num_text = cells[dorsal_idx].get_text(strip=True)
                                name_text = cells[name_idx].get_text(strip=True)
                                
                                # Netejar "Veure" del text
                                num_clean = re.sub(r'Veure|Ver|View', '', num_text, flags=re.IGNORECASE).strip()
                                name_clean = re.sub(r'Veure|Ver|View', '', name_text, flags=re.IGNORECASE).strip().upper()
                                
                                if num_clean.isdigit():
                                    num = int(num_clean)
                                    if num > 0 and num <= 20 and name_clean and len(name_clean) > 3:
                                        players.append({'num': num, 'name': name_clean})
                                        if len(players) <= 3:
                                            print(f"      ✅ {num}. {name_clean}")
                        
                        # Si hem trobat jugadors, sortir
                        if players:
                            break
            
            # MÈTODE ALTERNATIU: Regex sobre text net
            if not players:
                print(f"  🔄 Intent amb regex sobre text net...")
                
                # Buscar on comença la secció del rival (després del seu nom)
                # Ha de tenir "Gols igualtat" o similar
                rival_section_pattern = rf'({rival_name}|U\.E\.\s*D.HORTA).*?Gols\s*igualtat.*?Dorsal'
                match_section = re.search(rival_section_pattern, full_text, re.IGNORECASE | re.DOTALL)
                
                if match_section:
                    start_pos = match_section.end() - 10  # Un poc abans de "Dorsal"
                    section = full_text[start_pos:start_pos + 3000]
                    
                    print(f"  📋 Secció trobada, snippet: {section[:200]}...")
                    
                    # Patró per capturar: número + nom + estadístiques
                    # El format és: "1ALVARO CAPILLA COBO000000" dins del text
                    pattern = r'(\d{1,2})([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][A-ZÁÉÍÓÚÀÈÌÒÙÑÇ\s]+?)(\d{6,})'
                    matches = re.findall(pattern, section)
                    
                    print(f"  🔍 Regex trobat: {len(matches)} coincidències")
                    
                    for m in matches:
                        num = int(m[0])
                        name = m[1].strip().upper()
                        
                        if num > 0 and num <= 20 and name and len(name) > 3:
                            invalid = ['TERRASSA', 'ENTRENADOR', 'GOLS', 'EFECTIVITAT', 'SUPERIORITAT']
                            if not any(x in name for x in invalid):
                                players.append({'num': num, 'name': name})
            
            # Eliminar duplicats i ordenar
            seen = set()
            unique_players = []
            for p in players:
                key = (p['num'], p['name'])
                if key not in seen:
                    seen.add(key)
                    unique_players.append(p)
            
            unique_players.sort(key=lambda x: x['num'])
            
            print(f"  📊 Jugadors extrets: {len(unique_players)}")
            if unique_players:
                for p in unique_players[:5]:
                    print(f"      {p['num']}. {p['name']}")
                if len(unique_players) > 5:
                    print(f"      ... i {len(unique_players) - 5} més")
            
            return unique_players if unique_players else None
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def update_rivals_database(self, team='cadet'):
        """Actualitza el rivals_database.json pel pròxim rival"""
        
        print(f"\n{'='*70}")
        print(f"🔄 ACTUALITZANT RIVALS DATABASE - {team.upper()}")
        print(f"{'='*70}")
        
        # URLs i fitxers
        base_urls = {
            'cadet': 'https://joseprico.github.io/cnt_cadet_25-26/',
            'juvenil': 'https://joseprico.github.io/CNT_juvenil_25_26/'
        }
        
        database_files = {
            'cadet': 'rivals_database_cadet.json',
            'juvenil': 'rivals_database_juvenil.json'
        }
        
        base_url = base_urls.get(team)
        database_file = database_files.get(team)
        
        if not base_url:
            print(f"❌ Equip no reconegut: {team}")
            return
        
        # 1. Carregar dades ACTAWP (local o remot)
        print(f"\n1️⃣ CARREGANT DADES ACTAWP...")
        
        actawp_data = None
        
        # Primer intentar fitxer local
        local_paths = [
            f"actawp_{team}_data.json",
            f"/mnt/user-data/uploads/actawp_{team}_data.json",
            f"/mnt/project/actawp_{team}_data.json"
        ]
        
        for local_path in local_paths:
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    actawp_data = json.load(f)
                print(f"  ✅ Dades carregades des de: {local_path}")
                break
            except FileNotFoundError:
                continue
        
        # Si no hi ha local, intentar remot
        if not actawp_data:
            try:
                actawp_url = f"{base_url}actawp_{team}_data.json"
                response = requests.get(actawp_url)
                response.raise_for_status()
                actawp_data = response.json()
                print(f"  ✅ Dades carregades des de URL")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                return
        
        if not actawp_data:
            print(f"  ❌ No s'han pogut carregar les dades")
            return
        
        # 2. Obtenir pròxim rival
        print(f"\n2️⃣ IDENTIFICANT PRÒXIM RIVAL...")
        upcoming = actawp_data.get('upcoming_matches', [])
        if not upcoming:
            print(f"  ⚠️ No hi ha pròxims partits")
            return
        
        next_match = upcoming[0]
        team1 = next_match.get('team1', '')
        team2 = next_match.get('team2', '')
        
        # Determinar quin és el rival
        if 'TERRASSA' in team1.upper():
            rival_name = team2
        else:
            rival_name = team1
        
        print(f"  📅 Pròxim partit: {team1} vs {team2}")
        print(f"  🎯 Rival: {rival_name}")
        
        # 2.5. Comprovar si ja tenim la plantilla actualitzada recentment
        print(f"\n2️⃣.5 COMPROVANT SI CAL ACTUALITZAR...")
        
        try:
            with open(database_file, 'r', encoding='utf-8') as f:
                existing_db = json.load(f)
            
            # Buscar el rival a la base de dades
            rival_db_key = rival_name.upper().strip()
            
            if rival_db_key in existing_db.get('teams', {}):
                last_updated = existing_db['teams'][rival_db_key].get('lastUpdated')
                
                if last_updated:
                    last_date = datetime.strptime(last_updated, '%Y-%m-%d')
                    days_since = (datetime.now() - last_date).days
                    
                    print(f"  📅 Última actualització: {last_updated} (fa {days_since} dies)")
                    
                    if days_since < 7:
                        print(f"  ⏭️ Plantilla actualitzada fa menys d'una setmana. Saltant...")
                        print(f"\n{'='*70}")
                        print(f"✅ NO CAL ACTUALITZAR - Plantilla recent")
                        print(f"{'='*70}")
                        return
                    else:
                        print(f"  🔄 Fa més d'una setmana. Actualitzant...")
                else:
                    print(f"  ⚠️ Rival trobat però sense data d'actualització. Actualitzant...")
            else:
                print(f"  🆕 Rival nou. Descarregant plantilla...")
                
        except FileNotFoundError:
            print(f"  📄 Fitxer {database_file} no existeix. Es crearà nou.")
        
        # 3. Buscar team_id del rival a rivals_form
        print(f"\n3️⃣ BUSCANT DADES DEL RIVAL...")
        rivals_form = actawp_data.get('rivals_form', {})
        
        rival_key = None
        rival_team_id = None
        
        for key, data in rivals_form.items():
            if key.upper().replace(' ', '') in rival_name.upper().replace(' ', '') or \
               rival_name.upper().replace(' ', '') in key.upper().replace(' ', ''):
                rival_key = key
                rival_team_id = data.get('team_id')
                break
        
        if not rival_team_id:
            print(f"  ⚠️ No s'ha trobat el team_id del rival")
            print(f"  📋 Rivals disponibles: {list(rivals_form.keys())}")
            return
        
        print(f"  ✅ Rival trobat: {rival_key} (team_id: {rival_team_id})")
        
        # 4. Obtenir última acta del rival
        print(f"\n4️⃣ OBTENINT ÚLTIMA ACTA DEL RIVAL...")
        match_url = self.get_last_match_url(rival_team_id)
        
        if not match_url:
            print(f"  ⚠️ No s'ha trobat l'última acta")
            return
        
        # 5. Extreure plantilla de l'acta
        print(f"\n5️⃣ EXTRAIENT PLANTILLA...")
        players = self.extract_roster_from_match(match_url, rival_name)
        
        if not players:
            print(f"  ⚠️ No s'han pogut extreure jugadors")
            return
        
        # 6. Actualitzar rivals_database.json
        print(f"\n6️⃣ ACTUALITZANT {database_file}...")
        
        try:
            # Llegir database existent
            try:
                with open(database_file, 'r', encoding='utf-8') as f:
                    database = json.load(f)
            except FileNotFoundError:
                database = {
                    'metadata': {
                        'version': '1.0',
                        'lastUpdated': datetime.now().strftime('%Y-%m-%d'),
                        'description': f'Base de dades de plantilles d\'equips rivals - CN Terrassa {team.upper()}'
                    },
                    'teams': {}
                }
            
            # Normalitzar nom del rival per usar com a clau
            rival_db_key = rival_name.upper().strip()
            
            # Actualitzar o crear entrada
            database['teams'][rival_db_key] = {
                'fullName': rival_name,
                'lastPlayed': datetime.now().strftime('%Y-%m-%d'),
                'lastUpdated': datetime.now().strftime('%Y-%m-%d'),
                'sourceMatch': match_url,
                'players': players
            }
            
            # Actualitzar metadata
            database['metadata']['lastUpdated'] = datetime.now().strftime('%Y-%m-%d')
            
            # Guardar
            with open(database_file, 'w', encoding='utf-8') as f:
                json.dump(database, f, ensure_ascii=False, indent=2)
            
            print(f"  ✅ {database_file} actualitzat!")
            print(f"  📊 {rival_db_key}: {len(players)} jugadors")
            
        except Exception as e:
            print(f"  ❌ Error actualitzant database: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*70}")
        print(f"✅ PROCÉS COMPLETAT!")
        print(f"{'='*70}")


if __name__ == '__main__':
    team = sys.argv[1] if len(sys.argv) > 1 else 'cadet'
    
    updater = RivalsUpdater()
    updater.update_rivals_database(team)
