#!/usr/bin/env python3
"""
Wrapper per ultra_robust_parser.py amb millor gestió d'errors
"""

import sys
import traceback
from datetime import datetime

def main():
    print("="*70)
    print(f"ðŸš€ ACTAWP Parser Wrapper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        # Importar i executar el parser original
        print("\nðŸ"¥ Carregant ultra_robust_parser...")
        
        # Això executarà el codi del __main__ del parser
        import ultra_robust_parser
        
        print("\nâœ… Parser executat correctament!")
        return 0
        
    except ImportError as e:
        print(f"\nâŒ Error important el parser: {e}")
        print("\nðŸ"Š Debugging info:")
        print(f"  - Python version: {sys.version}")
        print(f"  - Working directory: {sys.path[0]}")
        traceback.print_exc()
        return 1
        
    except requests.exceptions.ConnectionError as e:
        print(f"\nâŒ Error de connexiÃ³ a ACTAWP: {e}")
        print("\nâœ¨ Suggeriments:")
        print("  - Comprova la connexiÃ³ a internet")
        print("  - ACTAWP pot estar caigut temporalment")
        print("  - El workflow reintentarà automàticament")
        return 2
        
    except requests.exceptions.Timeout as e:
        print(f"\nâŒ Timeout connectant a ACTAWP: {e}")
        print("\nâœ¨ El servidor està lent, el workflow reintentarà")
        return 3
        
    except Exception as e:
        print(f"\nâŒ Error inesperat: {type(e).__name__}: {e}")
        print("\nðŸ"Š Traceback complet:")
        traceback.print_exc()
        
        print("\nðŸ"Š System info:")
        print(f"  - Python: {sys.version}")
        print(f"  - Platform: {sys.platform}")
        
        # Intentar mostrar info dels mòduls
        try:
            import requests
            import bs4
            print(f"  - requests: {requests.__version__}")
            print(f"  - beautifulsoup4: {bs4.__version__}")
        except:
            pass
        
        return 4

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
