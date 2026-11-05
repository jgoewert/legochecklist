import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

API_ROOT = "https://rebrickable.com/api/v3/lego"
REQUEST_TIMEOUT_SECONDS = 10
CACHE_TTL_SECONDS = 60 * 60 * 24
MAX_SET_ID_LENGTH = 64

# Hyphen-separated runs of URL-safe characters. Rejecting "/", "?", "#" and "."
# keeps user input from reaching any other Rebrickable endpoint.
SET_ID_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*")
VERSION_SUFFIX_PATTERN = re.compile(r"-\d+$")


class InvalidSetId(ValueError):
    """The set ID is not in a format Rebrickable could recognise."""


class RebrickableError(Exception):
    """Rebrickable could not answer: network failure, throttling, bad key, etc."""


def _set_path(set_id):
    if len(set_id) > MAX_SET_ID_LENGTH or not SET_ID_PATTERN.fullmatch(set_id):
        raise InvalidSetId(set_id)
    return f"sets/{set_id}/"


def _get_json(path):
    """
    Returns the decoded response for an API path, or None if it does not exist.
    Raises RebrickableError for any other failure. Only successes are cached, so
    a temporary failure is not remembered once the API recovers.
    """
    cache_key = f"rebrickable:{path}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{API_ROOT}/{path}",
            headers={"Authorization": f"key {settings.REBRICKABLE_API_KEY}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Rebrickable request failed for %s: %s", path, exc)
        raise RebrickableError(path) from exc

    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.warning("Rebrickable returned %s for %s", response.status_code, path)
        raise RebrickableError(path)

    try:
        decoded = response.json()
    except ValueError as exc:
        logger.warning("Rebrickable returned invalid JSON for %s", path)
        raise RebrickableError(path) from exc

    cache.set(cache_key, decoded, CACHE_TTL_SECONDS)
    return decoded


def fetch_set_data(set_id):
    """
    Fetches set data from Rebrickable API, trying "<set_id>-1" if an unversioned
    ID such as "1682" does not exist.
    Returns a tuple of (decoded_data, set_id), or (None, None) if not found.
    """
    decoded = _get_json(_set_path(set_id))
    if decoded is not None:
        return decoded, set_id

    if not VERSION_SUFFIX_PATTERN.search(set_id):
        set_id_alt = f"{set_id}-1"
        decoded = _get_json(_set_path(set_id_alt))
        if decoded is not None:
            return decoded, set_id_alt

    return None, None


def fetch_parts_data(set_id):
    """
    Fetches parts data for a set from Rebrickable API, or None if not found.
    Expects the full set ID returned by fetch_set_data.
    """
    return _get_json(f"{_set_path(set_id)}parts/?page_size=1000")


def sort_by_name(part_entry):
    return part_entry["part"]["name"]


def sort_by_color(part_entry):
    return part_entry["color"]["name"]


def sort_by_partnum(part_entry):
    return part_entry["part"]["part_num"]
