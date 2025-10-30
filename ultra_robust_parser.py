#!/usr/bin/env python3
"""
Ultra Robust Parser amb CachÃ© Intel·ligent
Millores:
- CachÃ© local per reduir peticions
- Retry logic amb backoff exponencial
- Detecció de canvis abans de fer scraping complet
- Logging millorat
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# ConfiguraciÃ³
CACHE_DIR = Path('.cache')
CACHE_DURATION = timedelta(hours=3)  # CachÃ© vÃ lid durant 3 hores
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # segons

def setup_cache():
    """Crear directori de cachÃ© si no existeix"""
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"ðŸ"‚ Directori de cachÃ©: {CACHE_DIR}")

def get_cache_key(url):
    """Generar clau de cachÃ© basada en URL"""
    return hashlib.md5(url.encode()).hexdigest()

def get_cached_response(url):
    """Obtenir resposta del cachÃ© si Ã©s vÃ lida"""
    cache_key = get_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        cached_time = datetime.fromisoformat(cached['timestamp'])
        if datetime.now() - cached_time < CACHE_DURATION:
            print(f"âœ… CachÃ© vÃ lid per {url[:50]}... (edat: {datetime.now() - cached_time})")
            return cached['content']
        else:
            print(f"â³ CachÃ© expirat per {url[:50]}...")
            return None
    except Exception as e:
        print(f"âš ï¸ Error llegint cachÃ©: {e}")
        return None

def save_to_cache(url, content):
    """Guardar resposta al cachÃ©"""
    cache_key = get_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'content': content
            }, f, ensure_ascii=False)
        print(f"ðŸ'¾ Contingut guardat al cachÃ©")
    except Exception as e:
        print(f"âš ï¸ Error guardant al cachÃ©: {e}")

def fetch_with_retry(url, max_retries=MAX_RETRIES):
    """
    Fer peticiÃ³ HTTP amb retry logic i backoff exponencial
    """
    # Primer, intentar obtenir del cachÃ©
    cached_content = get_cached_response(url)
    if cached_content:
        return cached_content
    
    print(f"ðŸ"„ Descarregant: {url}")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            content = response.text
            save_to_cache(url, content)
            
            print(f"âœ… Descà rrega exitosa (intent {attempt + 1}/{max_retries})")
            return content
            
        except requests.exceptions.RequestException as e:
            wait_time = INITIAL_BACKOFF * (2 ** attempt)  # Backoff exponencial
            
            if attempt < max_retries - 1:
                print(f"âš ï¸ Error: {e}")
                print(f"â³ Esperant {wait_time}s abans de reintentar...")
                time.sleep(wait_time)
            else:
                print(f"âŒ Error després de {max_retries} intents: {e}")
                raise
    
    return None

def check_if_data_changed(url, last_hash_file):
    """
    ComprC ³var si les dades han canviat comparant hash
    RetC ³rna True si han canviat, False si no
    """
    try:
        content = fetch_with_retry(url)
        current_hash = hashlib.md5(content.encode()).hexdigest()
        
        if Path(last_hash_file).exists():
            with open(last_hash_file, 'r') as f:
                last_hash = f.read().strip()
            
            if current_hash == last_hash:
                print(f"â„¹ï¸ No hi ha canvis detectats (hash: {current_hash[:8]}...)")
                return False, content
        
        # Guardar nou hash
        with open(last_hash_file, 'w') as f:
            f.write(current_hash)
        
        print(f"ðŸ†• Canvis detectats! (hash: {current_hash[:8]}...)")
        return True, content
        
    except Exception as e:
        print(f"âš ï¸ Error comprovant canvis: {e}")
        return True, None  # En cas d'error, assumir que hi ha canvis

def parse_actawp_data(html_content):
    """
    Parsejar el contingut HTML d'ACTAWP
    (Aquesta funciÃ³ hauria de contenir la lÃ²gica de parsing actual)
    """
    # AQUÃ CD hauries de posar la lÃ²gica del teu ultra_robust_parser.py actual
    # Per ara retorno un placeholder
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # TODO: Implementar parsing real
    data = {
        'last_update': datetime.now().isoformat(),
        'teams': [],
        'ranking': [],
        'matches': []
    }
    
    return data

def main():
    """FunciÃ³ principal"""
    print("="*60)
    print("ðŸ ðŸ'¦ ACTAWP Parser - Mode Intel·ligent")
    print("="*60)
    
    setup_cache()
    
    # URLs (adapta amb les teves URLs reals)
    ACTAWP_CADET_URL = "https://actawp.fcn.cat/..."  # Posa la URL real
    ACTAWP_JUVENIL_URL = "https://actawp.fcn.cat/..."  # Posa la URL real
    
    try:
        # Processar Cadet
        print("\nðŸ"Š Processant equip CADET...")
        changed, content = check_if_data_changed(
            ACTAWP_CADET_URL, 
            '.cache/cadet_last_hash.txt'
        )
        
        if changed and content:
            cadet_data = parse_actawp_data(content)
            with open('actawp_cadet_data.json', 'w', encoding='utf-8') as f:
                json.dump(cadet_data, f, ensure_ascii=False, indent=2)
            print("âœ… Dades CADET actualitzades")
        else:
            print("â„¹ï¸ Dades CADET sense canvis, no cal actualitzar")
        
        # Processar Juvenil
        print("\nðŸ"Š Processant equip JUVENIL...")
        changed, content = check_if_data_changed(
            ACTAWP_JUVENIL_URL,
            '.cache/juvenil_last_hash.txt'
        )
        
        if changed and content:
            juvenil_data = parse_actawp_data(content)
            with open('actawp_juvenil_data.json', 'w', encoding='utf-8') as f:
                json.dump(juvenil_data, f, ensure_ascii=False, indent=2)
            print("âœ… Dades JUVENIL actualitzades")
        else:
            print("â„¹ï¸ Dades JUVENIL sense canvis, no cal actualitzar")
        
        print("\n" + "="*60)
        print("âœ… Procés completat amb Ã¨xit!")
        print("="*60)
        
    except Exception as e:
        print(f"\nâŒ Error crÃtic: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
