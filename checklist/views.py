from django.shortcuts import render
from django.http import HttpResponse    
from .models import Piece
from . import services

# Create your views here.
def index(request, set_id="1682-1", selected_sort="name"):
    set_id = request.GET.get('set_id', '1682-1')
    selected_sort = request.GET.get('selected_sort', 'name')

    decoded, set_id = services.fetch_set_data(set_id)
    if not decoded:
        return HttpResponse("Set not found.", status=404)

    set_name = decoded["name"]

    decoded_parts = services.fetch_parts_data(set_id)
    if not decoded_parts:
        return HttpResponse("Set parts not found.", status=404)

    sort_key = services.sort_by_name
    match (selected_sort):
        case 'name':
            sort_key = services.sort_by_name
        case 'color':
            sort_key = services.sort_by_color
        case 'partnum':
            sort_key = services.sort_by_partnum
    
    sortedresults = sorted(decoded_parts["results"], key=sort_key)

    set_pieces = []
    for part in sortedresults:
        if (part['is_spare'] is not True):
            piece = Piece(
                num=part["part"]["part_num"], 
                color=part["color"]["name"], 
                img=part["part"]["part_img_url"], 
                qty=int(part["quantity"]), 
                name=part["part"]["name"]
            )
            set_pieces.append(piece)

    return render(request, "index.html", {"set_id": set_id, "set_name": set_name, "set_pieces": set_pieces, "set_sort": selected_sort})