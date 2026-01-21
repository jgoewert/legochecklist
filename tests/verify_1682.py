import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legochecklist.settings')
django.setup()

from checklist import services

def check_1682_1():
    print("Fetching data for 1682-1...")
    parts_data = services.fetch_parts_data('1682-1')
    
    if not parts_data:
        print("Failed to fetch data")
        return

    results = parts_data.get('results', [])
    print(f"Total entries: {len(results)}")
    
    total_qty = 0
    total_qty_no_spares = 0
    
    for part in results:
        qty = part.get('quantity', 0)
        total_qty += qty
        if not part.get('is_spare'):
            total_qty_no_spares += qty
            
    print(f"Total Quantity: {total_qty}")
    print(f"Total Quantity (no spares): {total_qty_no_spares}")

if __name__ == "__main__":
    check_1682_1()
