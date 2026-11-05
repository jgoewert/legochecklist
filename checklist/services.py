import logging
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
        set_lines.is_spare = 'True'
    FROM set_lines
    JOIN parts ON parts.part_num = set_lines.part_num
    JOIN colors ON colors.id = set_lines.color_id
    GROUP BY set_lines.part_num, set_lines.color_id, set_lines.is_spare
"""


@dataclass
class Piece:
    num: str
    color: str
    img: str
    qty: int
    name: str
    color_rgb: str | None = None


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
    Returns a tuple of ({"name": name}, set_id), or (None, None) if not found.
    """
    for candidate in (set_id, f"{set_id}-1"):
        rows = _query("SELECT name FROM sets WHERE set_num = ?", (candidate,))
        if rows:
            return {"name": rows[0][0]}, candidate
    return None, None


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
        }
        for num, name, img, color, rgb, quantity, is_spare in _query(
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
