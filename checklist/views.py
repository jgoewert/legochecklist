from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings

#from .models import Greeting
import requests
import json

class Piece:
    def __init__(self, num, color, img, qty, name):
        self.num = num
        self.name = name
        self.color = color
        self.img = img
        self.qty = qty

def sort_by_name(list):
    return list["part"]["name"]

def sort_by_color(list):
    return list["color"]["id"]

def sort_by_partnum(list):
    return list["part"]["part_num"]

def fetch_set_data(set_id):
        url = f'https://rebrickable.com/api/v3/lego/sets/{set_id}?key={settings.REBRICKABLE_API_KEY}'
        fp = requests.get(url)
        if fp.status_code != 200:
            # Try with -1 appended to set_id
            set_id_alt = set_id + '-1' if not set_id.endswith('-1') else set_id
            url_alt = f'https://rebrickable.com/api/v3/lego/sets/{set_id_alt}?key={settings.REBRICKABLE_API_KEY}'
            fp = requests.get(url_alt)
            if fp.status_code != 200:
                fp.close()
                return None, None
            set_id = set_id_alt
        decoded = json.loads(fp.text)
        fp.close()
        return decoded, set_id

def fetch_parts_data(set_id):
        url = f'https://rebrickable.com/api/v3/lego/sets/{set_id}/parts/?page_size=1000&key={settings.REBRICKABLE_API_KEY}'
        fp = requests.get(url)
        if fp.status_code != 200:
            # Try with -1 appended to set_id
            set_id_alt = set_id + '-1' if not set_id.endswith('-1') else set_id
            url_alt = f'https://rebrickable.com/api/v3/lego/sets/{set_id_alt}/parts/?page_size=1000&key={settings.REBRICKABLE_API_KEY}'
            fp = requests.get(url_alt)
            if fp.status_code != 200:
                fp.close()
                return None
            set_id = set_id_alt
        decoded = json.loads(fp.text)
        fp.close()
        return decoded

# Create your views here.
def index(request, set_id="1682-1", sort_algorithm="name"):
    set_id = request.GET.get('set_id', '1682-1')
    sort_algorithm = request.GET.get('sort_algorithm', 'name')

    decoded, set_id = fetch_set_data(set_id)
    if not decoded:
        return HttpResponse("Set not found.", status=404)

    set_name = decoded["name"]

    decoded_parts = fetch_parts_data(set_id)
    if not decoded_parts:
        return HttpResponse("Set parts not found.", status=404)

    match (sort_algorithm):
        case 'name':
            sortedresults = sorted(decoded_parts["results"], key=sort_by_name)
        case 'color':
            sortedresults = sorted(decoded_parts["results"], key=sort_by_color)
        case 'partnum':
            sortedresults = sorted(decoded_parts["results"], key=sort_by_partnum)

    set_pieces = []
    for part in sortedresults:
        if (part['is_spare'] is not True):
            piece = Piece(part["part"]["part_num"], part["color"]["name"], part["part"]["part_img_url"], int(part["quantity"]), part["part"]["name"])
            set_pieces.append(piece)

    return render(request, "index.html", {"set_id": set_id, "set_name": set_name, "set_pieces": set_pieces, "selected_sort": sort_algorithm})