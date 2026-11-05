import logging
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Returns a set's own parts plus the parts of its minifigures, which are inventoried
# separately under the minifigure's number. A part appearing in both is combined, so
# each part and colour has one line.
#
# Sets can have several inventory versions. The highest is the latest correction,
# and it agrees with the part counts in sets.csv far more often than the lowest.
# A few have an empty latest version, so only versions with contents are considered.
PARTS_QUERY = """
    WITH set_inventory AS (
        SELECT id FROM inventories
        WHERE set_num = ? AND (
            EXISTS (
                SELECT 1 FROM inventory_parts
                WHERE inventory_parts.inventory_id = inventories.id
            )
            OR EXISTS (
                SELECT 1 FROM inventory_minifigs
                WHERE inventory_minifigs.inventory_id = inventories.id
            )
        )
        ORDER BY version DESC
        LIMIT 1
    ),
    set_lines AS (
        SELECT part_num, color_id, quantity, is_spare, img_url
        FROM inventory_parts
        WHERE inventory_id = (SELECT id FROM set_inventory)

        UNION ALL

        SELECT
            inventory_parts.part_num,
            inventory_parts.color_id,
            inventory_parts.quantity * inventory_minifigs.quantity,
            inventory_parts.is_spare,
            inventory_parts.img_url
        FROM inventory_minifigs
        JOIN inventory_parts ON inventory_parts.inventory_id = (
            SELECT id FROM inventories
            WHERE set_num = inventory_minifigs.fig_num AND EXISTS (
                SELECT 1 FROM inventory_parts
                WHERE inventory_parts.inventory_id = inventories.id
            )
            ORDER BY version DESC
            LIMIT 1
        )
        WHERE inventory_minifigs.inventory_id = (SELECT id FROM set_inventory)
    )
    SELECT
        parts.part_num,
        parts.name,
        MAX(set_lines.img_url),
        colors.name,
        colors.rgb,
        SUM(set_lines.quantity),
        set_lines.is_spare = 'True',
        part_categories.name
    FROM set_lines
    JOIN parts ON parts.part_num = set_lines.part_num
    JOIN colors ON colors.id = set_lines.color_id
    LEFT JOIN part_categories ON part_categories.id = parts.part_cat_id
    GROUP BY set_lines.part_num, set_lines.color_id, set_lines.is_spare
"""

# Used for parts whose category is missing from part_categories.
UNKNOWN_CATEGORY = "Other"


@dataclass
class Piece:
    num: str
    color: str
    img: str
    qty: int
    name: str
    color_rgb: str | None = None
    category: str = UNKNOWN_CATEGORY
    spare: bool = False


class CatalogUnavailable(Exception):
    """The catalog database is missing or unreadable. Run build_catalog."""


def _query(sql, params):
    uri = f"{Path(settings.CATALOG_DB).resolve().as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            return connection.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        logger.error("Could not read catalog %s: %s", settings.CATALOG_DB, exc)
        raise CatalogUnavailable from exc


def fetch_set_data(set_id):
    """
    Looks up a set in the catalog, trying "<set_id>-1" so that "1682" finds "1682-1".
    Returns a tuple of ({"name", "year", "num_parts", "img_url"}, set_id), or
    (None, None) if not found.
    """
    for candidate in (set_id, f"{set_id}-1"):
        rows = _query(
            "SELECT name, year, num_parts, img_url FROM sets WHERE set_num = ?",
            (candidate,),
        )
        if rows:
            name, year, num_parts, img_url = rows[0]
            data = {
                "name": name,
                "year": year,
                "num_parts": num_parts,
                "img_url": img_url or None,
            }
            return data, candidate
    return None, None


SEARCH_LIMIT = 50


def search_sets(query, limit=SEARCH_LIMIT):
    """
    Finds sets whose name contains every word of the query, or whose number starts
    with it. Returns (matches, total), newest first, with at most `limit` matches.
    """
    words = [word for word in re.split(r"[\s,+]+", query) if word]
    if not words:
        return [], 0

    conditions, params = [], []
    for word in words:
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            "(name LIKE ? ESCAPE '\\' OR set_num LIKE ? ESCAPE '\\')"
        )
        params += [f"%{escaped}%", f"{escaped}%"]
    where = " AND ".join(conditions)

    total = _query(f"SELECT COUNT(*) FROM sets WHERE {where}", params)[0][0]
    rows = _query(
        f"SELECT set_num, name, year, num_parts, img_url FROM sets WHERE {where} "
        "ORDER BY year DESC, set_num LIMIT ?",
        [*params, limit],
    )
    matches = [
        {
            "set_num": set_num,
            "name": name,
            "year": year,
            "num_parts": num_parts,
            "img_url": img_url or None,
        }
        for set_num, name, year, num_parts, img_url in rows
    ]
    return matches, total


def fetch_parts_data(set_id):
    """
    Returns {"results": [...]} with the parts in a set's latest inventory, including
    its minifigures. The list is empty for sets with neither, such as multipacks.
    Expects the full set ID returned by fetch_set_data.
    """
    results = [
        {
            "part": {"part_num": num, "name": name, "part_img_url": img or None},
            "color": {"name": color, "rgb": rgb},
            "quantity": quantity,
            "is_spare": bool(is_spare),
            "category": {"name": category or UNKNOWN_CATEGORY},
        }
        for num, name, img, color, rgb, quantity, is_spare, category in _query(
            PARTS_QUERY, (set_id,)
        )
    ]
    return {"results": results}


def sort_by_name(part_entry):
    return part_entry["part"]["name"]


def sort_by_color(part_entry):
    return part_entry["color"]["name"]


def sort_by_partnum(part_entry):
    return part_entry["part"]["part_num"]


def sort_by_category(part_entry):
    return part_entry.get("category", {}).get("name", UNKNOWN_CATEGORY)
