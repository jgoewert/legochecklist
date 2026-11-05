import json
import re
from functools import cache
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from urllib.parse import quote

from django.http import HttpResponse
from django.shortcuts import render

from . import services

DEFAULT_SET = "1682-1"

# Several sets can be combined into one checklist by separating their numbers with
# commas or plus signs, such as "1682, 6080".
SET_SEPARATORS = re.compile(r"[,+]")
MAX_SETS = 10

SORTS = {
    "name": services.sort_by_name,
    "color": services.sort_by_color,
    "category": services.sort_by_category,
    "partnum": services.sort_by_partnum,
}
# Sorts that show a heading for each colour or category.
GROUPED_SORTS = {"color": "color", "category": "category"}
SPARES_HEADING = "Spare parts"

PWA_DIR = Path(__file__).resolve().parent / "pwa"


def split_sets(query):
    """Returns the set numbers in a query, or the whole query if it names one set."""
    if not SET_SEPARATORS.search(query):
        return [query] if query else []
    return [token.strip() for token in SET_SEPARATORS.split(query) if token.strip()]


def set_details(set_id, data):
    number = set_id.rsplit("-", 1)[0]
    return {
        "set_num": set_id,
        **data,
        "rebrickable_url": f"https://rebrickable.com/sets/{quote(set_id)}/",
        "instructions_url": (
            f"https://www.lego.com/service/buildinginstructions/{quote(number)}"
        ),
    }


def combine_parts(set_ids):
    """Adds up the parts of several sets, one entry per part, colour and spare."""
    combined = {}
    for set_id in set_ids:
        for part in services.fetch_parts_data(set_id)["results"]:
            key = (part["part"]["part_num"], part["color"]["name"], part["is_spare"])
            if key in combined:
                combined[key]["quantity"] += part["quantity"]
            else:
                combined[key] = dict(part)
    return list(combined.values())


def to_piece(part):
    return services.Piece(
        num=part["part"]["part_num"],
        color=part["color"]["name"],
        img=part["part"]["part_img_url"],
        qty=int(part["quantity"]),
        name=part["part"]["name"],
        color_rgb=part["color"].get("rgb"),
        category=part.get("category", {}).get("name", services.UNKNOWN_CATEGORY),
        spare=part["is_spare"] is True,
    )


def group_pieces(pieces, selected_sort):
    """Returns (heading, pieces) pairs. The heading is None when not grouping."""
    attribute = GROUPED_SORTS.get(selected_sort)
    if not attribute:
        return [(None, pieces)] if pieces else []
    return [
        (heading, list(group))
        for heading, group in groupby(pieces, key=attrgetter(attribute))
    ]


def index(request):
    query = request.GET.get("set_id", DEFAULT_SET).strip()
    selected_sort = request.GET.get("selected_sort", "name")
    if selected_sort not in SORTS:
        selected_sort = "name"
    show_spares = request.GET.get("spares") == "1"

    tokens = split_sets(query)
    if len(tokens) > MAX_SETS:
        return search(
            request, query, selected_sort,
            error=f"A checklist can combine up to {MAX_SETS} sets.", status=400,
        )

    try:
        found, missing = {}, []
        for token in dict.fromkeys(tokens):
            data, set_id = services.fetch_set_data(token)
            if data:
                found[set_id] = data
            else:
                missing.append(token)

        if not found or (len(tokens) == 1 and missing):
            return search(request, query, selected_sort)
        if missing:
            return search(
                request, query, selected_sort,
                error="Couldn't find set " + ", ".join(missing) + ".", status=404,
            )

        # Sorted, so the same sets always share one saved checklist.
        set_ids = sorted(found)
        parts = combine_parts(set_ids)
    except services.CatalogUnavailable:
        return HttpResponse("The parts catalog is not available.", status=503)

    # Sorting is stable, so parts that tie on the chosen key stay in name order.
    by_name = sorted(parts, key=services.sort_by_name)
    pieces = [to_piece(part) for part in sorted(by_name, key=SORTS[selected_sort])]

    groups = group_pieces([p for p in pieces if not p.spare], selected_sort)
    spares = [p for p in pieces if p.spare]
    if show_spares and spares:
        groups.append((SPARES_HEADING, spares))

    sets = [set_details(set_id, found[set_id]) for set_id in set_ids]
    return render(request, "index.html", {
        "set_id": "+".join(set_ids),
        "set_name": " + ".join(s["name"] for s in sets),
        "sets": sets,
        "groups": groups,
        "spare_count": len(spares),
        "show_spares": show_spares,
        "set_sort": selected_sort,
    })


def search(request, query, selected_sort, error=None, status=None):
    """Lists sets matching a query that isn't a set number. 404 if none match."""
    matches, total = ([], 0) if error else services.search_sets(query)
    return render(
        request,
        "search.html",
        {
            "query": query,
            "matches": matches,
            "total": total,
            "error": error,
            "set_sort": selected_sort,
        },
        status=status or (200 if matches else 404),
    )


# Installable app and offline support


@cache
def pwa_file(name):
    return (PWA_DIR / name).read_bytes()


def service_worker(request):
    response = HttpResponse(pwa_file("sw.js"), content_type="text/javascript")
    # Browsers check for a new worker on each visit, so updates arrive promptly.
    response["Cache-Control"] = "no-cache"
    return response


def manifest(request):
    data = {
        "name": "LEGO Checklist",
        "short_name": "LEGO Checklist",
        "description": "Printable checklists of the pieces in LEGO sets.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#2D2A2E",
        "theme_color": "#2D2A2E",
        "icons": [
            {"src": f"/icon-{size}.png", "sizes": f"{size}x{size}", "type": "image/png"}
            for size in (192, 512)
        ],
    }
    response = HttpResponse(
        json.dumps(data, indent=1), content_type="application/manifest+json"
    )
    response["Cache-Control"] = "max-age=86400"
    return response


def icon(request, size):
    response = HttpResponse(pwa_file(f"icon-{size}.png"), content_type="image/png")
    response["Cache-Control"] = "max-age=604800"
    return response
