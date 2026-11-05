"""Renders the checklist page with fixed parts for checklist.test.js to load."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

os.environ.update(
    DJANGO_SETTINGS_MODULE="legochecklist.settings",
    DEBUG="True",
    SECRET_KEY=os.environ.get("SECRET_KEY", "frontend-tests-only"),
)

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402


def part(num, color, quantity):
    return {
        "part": {"part_num": num, "name": "Brick", "part_img_url": "http://img/x.png"},
        "color": {"name": color, "rgb": "C91A09"},
        "quantity": quantity,
        "is_spare": False,
    }


PARTS = {
    "results": [
        part("3001", "Red", 2),
        part("3001", "Trans-Dark Blue", 2),
        part("3002", "Red", 1),
    ]
}

with patch(
    "checklist.services.fetch_set_data", return_value=({"name": "Test Set"}, "1-1")
), patch("checklist.services.fetch_parts_data", return_value=PARTS):
    response = Client(HTTP_HOST="localhost").get("/?set_id=1-1&selected_sort=partnum")

(HERE / "rendered.html").write_bytes(response.content)
