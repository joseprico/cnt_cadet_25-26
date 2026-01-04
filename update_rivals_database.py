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
            
            players = []
            rival_normalized = rival_name.upper().replace('C.N.', '').replace('C.E.', '').replace('U.E.', '').replace("'", "").replace("'", "").strip()
            
            print(f"  🔍 Buscant jugadors de: {rival_normalized}")
            
            # Buscar la secció del rival al HTML
            # Normalitzar el HTML per facilitar la cerca
            html_upper = html_text.upper().replace("'", "").replace("'", "")
            
            # Trobar on comença la secció del rival
            rival_patterns = [
                rival_normalized,
                rival_normalized.replace(' ', ''),
                rival_name.upper().replace("'", "").replace("'", ""),
            ]
            
            rival_section_start = -1
            for pattern in rival_patterns:
                # Buscar el patró dins del HTML
                idx = html_upper.find(pattern)
                if idx != -1:
                    rival_section_start = idx
                    print(f"  ✅ Secció del rival trobada a posició {idx}")
                    break
            
            if rival_section_start == -1:
                print(f"  ⚠️ No s'ha trobat la secció del rival al HTML")
                # Mostrar alguns fragments per debug
                print(f"  📋 Cercant fragments similars...")
                for word in rival_normalized.split()[:2]:
                    if len(word) > 3:
                        idx = html_upper.find(word)
                        if idx != -1:
                            snippet = html_text[max(0,idx-20):idx+50]
                            print(f"      Trobat '{word}' a pos {idx}: ...{snippet}...")
                return None
            
            # Agafar un tros del HTML des del rival (8000 caràcters hauria de ser suficient)
            section = html_text[rival_section_start:rival_section_start + 8000]
            
            # DEBUG: Mostrar un snippet de la secció per veure el format
            print(f"  📋 Snippet de la secció (500 chars):")
            # Netejar whitespace excessiu per veure millor
            clean_snippet = ' '.join(section[:500].split())
            print(f"      {clean_snippet[:300]}...")
            
            # MÈTODE PRINCIPAL: Regex que funciona
            # Buscar patró: Veure + número + NOM AMB ESPAIS + números estadístiques
            pattern = r'Veure(\d{1,2})([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][A-ZÁÉÍÓÚÀÈÌÒÙÑÇ\s\']+?)(\d{5,})'
            
            matches = re.findall(pattern, section, re.IGNORECASE)
            print(f"  🔍 Regex trobat: {len(matches)} coincidències")
            
            # Si no funciona, potser hi ha tags HTML enmig - treure'ls
            if not matches:
                print(f"  🔄 Netejant HTML tags...")
                soup_section = BeautifulSoup(section, 'html.parser')
                clean_section = soup_section.get_text()
                
                # DEBUG: mostrar secció netejada
                clean_snippet = ' '.join(clean_section[:500].split())
                print(f"  📋 Secció netejada (300 chars):")
                print(f"      {clean_snippet[:300]}...")
                
                matches = re.findall(pattern, clean_section, re.IGNORECASE)
                print(f"  🔍 Regex després de netejar: {len(matches)} coincidències")
            
            for match in matches:
                num = int(match[0])
                name = match[1].strip().upper()
                
                # Filtrar noms invàlids
                if num > 0 and num <= 20 and name and len(name) > 3:
                    # Verificar que no és un equip conegut o text no desitjat
                    invalid_names = ['TERRASSA', 'ENTRENADOR', 'GOLS', 'EFECTIVITAT', 'SUPERIORITAT', 'IGUALTAT', 'PENAL']
                    if not any(x in name for x in invalid_names):
                        players.append({'num': num, 'name': name})
                        if len(players) <= 3:
                            print(f"      ✅ {num}. {name}")
            
            # Si no trobem res amb el primer mètode, intentar sense "Veure"
            if not players:
                print(f"  🔄 Intent sense 'Veure'...")
                pattern2 = r'(\d{1,2})([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][A-ZÁÉÍÓÚÀÈÌÒÙÑÇ\s\']+?)(\d{6,})'
                matches2 = re.findall(pattern2, section)
                
                for match in matches2:
                    num = int(match[0])
                    name = match[1].strip().upper()
                    
                    if num > 0 and num <= 20 and name and len(name) > 3:
                        invalid_names = ['TERRASSA', 'ENTRENADOR', 'GOLS', 'EFECTIVITAT']
                        if not any(x in name for x in invalid_names):
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
