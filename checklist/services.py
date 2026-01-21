import requests
import json
from django.conf import settings
from functools import lru_cache

@lru_cache(maxsize=128)
def fetch_set_data(set_id):
    """
    Fetches set data from Rebrickable API.
    Returns a tuple of (decoded_data, set_id).
    """
    url = f'https://rebrickable.com/api/v3/lego/sets/{set_id}?key={settings.REBRICKABLE_API_KEY}'
    fp = requests.get(url)
    if fp.status_code != 200:
        # Try with -1 appended to set_id
        set_id_alt = set_id + '-1' if not set_id.endswith('-1') else set_id
        url_alt = f'https://rebrickable.com/api/v3/lego/sets/{set_id_alt}?key={settings.REBRICKABLE_API_KEY}'
        fp = requests.get(url_alt)
        if fp.status_code != 200:
            return None, None
        set_id = set_id_alt
    
    try:
        decoded = fp.json()
    except json.JSONDecodeError:
        return None, None
        
    return decoded, set_id

@lru_cache(maxsize=128)
def fetch_parts_data(set_id):
    """
    Fetches parts data for a set from Rebrickable API.
    """
    url = f'https://rebrickable.com/api/v3/lego/sets/{set_id}/parts/?page_size=1000&key={settings.REBRICKABLE_API_KEY}'
    fp = requests.get(url)
    if fp.status_code != 200:
        # Try with -1 appended to set_id
        set_id_alt = set_id + '-1' if not set_id.endswith('-1') else set_id
        url_alt = f'https://rebrickable.com/api/v3/lego/sets/{set_id_alt}/parts/?page_size=1000&key={settings.REBRICKABLE_API_KEY}'
        fp = requests.get(url_alt)
        if fp.status_code != 200:
            return None
        set_id = set_id_alt
    
    try:
        decoded = fp.json()
    except json.JSONDecodeError:
        return None
        
    return decoded

def sort_by_name(part_entry):
    return part_entry["part"]["name"]

def sort_by_color(part_entry):
    return part_entry["color"]["name"]

def sort_by_partnum(part_entry):
    return part_entry["part"]["part_num"]
