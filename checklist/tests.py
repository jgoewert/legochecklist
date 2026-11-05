import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, override_settings

from . import services

CSV_FIXTURES = {
    "sets": """set_num,name,year,theme_id,num_parts,img_url
1234-1,Test Set,2000,1,5,http://x
1224.1-1,Dotted Set,2000,1,1,http://x
5678-1,Versioned Set,2000,1,1,http://x
9000-1,Multipack,2000,1,0,http://x
7000-1,Empty Latest Version,2000,1,1,http://x
""",
    "inventories": """id,version,set_num
1,1,1234-1
2,1,1224.1-1
3,1,5678-1
4,2,5678-1
5,10,5678-1
6,1,9000-1
7,1,7000-1
8,2,7000-1
""",
    "inventory_parts": """inventory_id,part_num,color_id,quantity,is_spare,img_url
1,3001,4,3,False,http://img/3001.jpg
1,3001,4,1,True,http://img/3001.jpg
1,3002,0,2,False,
2,3001,4,1,False,http://img/3001.jpg
3,3001,4,1,False,http://img/old.jpg
4,3001,4,1,False,http://img/middle.jpg
5,3002,0,1,False,http://img/new.jpg
7,3001,4,1,False,http://img/only.jpg
""",
    "parts": """part_num,name,part_cat_id,part_material
3001,"Brick 2 x 4, Plain",11,Plastic
3002,Brick 2 x 3,11,Plastic
""",
    "colors": """id,name,rgb,is_trans,num_parts,num_sets,y1,y2
0,Black,05131D,False,1,1,2000,2000
4,Red,C91A09,False,1,1,2000,2000
""",
}


class CatalogTestCase(SimpleTestCase):
    """Builds a small catalog from fixture CSV files for each test class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.temp_dir = Path(directory.name)
        cls.csv_dir = cls.temp_dir / "csv"
        cls.csv_dir.mkdir()
        for table, content in CSV_FIXTURES.items():
            (cls.csv_dir / f"{table}.csv").write_text(content, encoding="utf-8")

        cls.catalog = cls.temp_dir / "catalog.sqlite3"
        override = override_settings(CATALOG_DB=cls.catalog)
        override.enable()
        cls.addClassCleanup(override.disable)
        call_command("build_catalog", csv_dir=cls.csv_dir, stdout=io.StringIO())


class SortingTestCase(SimpleTestCase):
    def test_sort_by_name(self):
        item = {"part": {"name": "Birck"}}
        self.assertEqual(services.sort_by_name(item), "Birck")

    def test_sort_by_color(self):
        item = {"color": {"name": "Red"}}
        self.assertEqual(services.sort_by_color(item), "Red")

    def test_sort_by_partnum(self):
        item = {"part": {"part_num": "3001"}}
        self.assertEqual(services.sort_by_partnum(item), "3001")


class ServicesTestCase(CatalogTestCase):
    def test_fetch_set_data_success(self):
        data, set_id = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Test Set")
        self.assertEqual(set_id, "1234-1")

    def test_id_without_suffix_finds_dash_one(self):
        data, set_id = services.fetch_set_data("1234")
        self.assertEqual(data["name"], "Test Set")
        self.assertEqual(set_id, "1234-1")

    def test_id_containing_a_dot_is_found(self):
        data, set_id = services.fetch_set_data("1224.1-1")
        self.assertEqual(data["name"], "Dotted Set")
        self.assertEqual(set_id, "1224.1-1")

    def test_unknown_or_hostile_ids_are_not_found(self):
        for set_id in ("9999-1", "", "' OR '1'='1", "../../colors", "x" * 5000):
            with self.subTest(set_id=set_id):
                self.assertEqual(services.fetch_set_data(set_id), (None, None))

    def test_fetch_parts_data_maps_every_field(self):
        results = services.fetch_parts_data("1234-1")["results"]

        self.assertIn(
            {
                "part": {
                    "part_num": "3001",
                    "name": "Brick 2 x 4, Plain",
                    "part_img_url": "http://img/3001.jpg",
                },
                "color": {"name": "Red", "rgb": "C91A09"},
                "quantity": 3,
                "is_spare": False,
            },
            results,
        )
        self.assertEqual(len(results), 3)

    def test_spare_flag_is_a_real_boolean(self):
        results = services.fetch_parts_data("1234-1")["results"]
        self.assertEqual(sum(1 for part in results if part["is_spare"] is True), 1)
        self.assertEqual(sum(1 for part in results if part["is_spare"] is False), 2)

    def test_missing_image_becomes_none(self):
        results = services.fetch_parts_data("1234-1")["results"]
        images = {part["part"]["part_num"]: part["part"]["part_img_url"]
                  for part in results}
        self.assertIsNone(images["3002"])

    def test_highest_version_is_used_comparing_numerically(self):
        results = services.fetch_parts_data("5678-1")["results"]
        self.assertEqual(
            [part["part"]["part_img_url"] for part in results],
            ["http://img/new.jpg"],
        )

    def test_empty_latest_version_falls_back_to_one_with_parts(self):
        results = services.fetch_parts_data("7000-1")["results"]
        self.assertEqual(
            [part["part"]["part_img_url"] for part in results],
            ["http://img/only.jpg"],
        )

    def test_set_without_parts_has_empty_results(self):
        self.assertEqual(services.fetch_parts_data("9000-1"), {"results": []})

    def test_missing_catalog_raises(self):
        with override_settings(CATALOG_DB=self.temp_dir / "does-not-exist.sqlite3"):
            with self.assertLogs("checklist.services", "ERROR"):
                with self.assertRaises(services.CatalogUnavailable):
                    services.fetch_set_data("1234-1")


class BuildCatalogTestCase(CatalogTestCase):
    def build(self, csv_dir):
        call_command("build_catalog", csv_dir=csv_dir, stdout=io.StringIO())

    def copy_csvs(self, name):
        directory = self.temp_dir / name
        directory.mkdir()
        for table, content in CSV_FIXTURES.items():
            (directory / f"{table}.csv").write_text(content, encoding="utf-8")
        return directory

    def test_rebuild_replaces_the_old_data(self):
        csv_dir = self.copy_csvs("rebuild")
        sets = csv_dir / "sets.csv"
        original = sets.read_text(encoding="utf-8")
        self.addCleanup(self.build, self.csv_dir)

        sets.write_text(original.replace("Test Set", "Renamed Set"), encoding="utf-8")
        self.build(csv_dir)

        data, _ = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Renamed Set")

    def test_missing_file_is_an_error_and_keeps_the_catalog(self):
        csv_dir = self.copy_csvs("missing-file")
        (csv_dir / "parts.csv").unlink()

        with self.assertRaisesMessage(CommandError, "Missing parts.csv"):
            self.build(csv_dir)

        data, _ = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Test Set")

    def test_missing_column_is_an_error_and_keeps_the_catalog(self):
        csv_dir = self.copy_csvs("missing-column")
        (csv_dir / "colors.csv").write_text("id,name\n0,Black\n", encoding="utf-8")

        with self.assertRaisesMessage(CommandError, "missing columns"):
            self.build(csv_dir)

        data, _ = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Test Set")
        self.assertFalse(self.catalog.with_name("catalog.sqlite3.tmp").exists())


class CatalogViewsTestCase(CatalogTestCase):
    def setUp(self):
        self.client = Client()

    def test_page_renders_from_the_catalog_without_spares(self):
        response = self.client.get('/?set_id=1234-1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Set")
        self.assertContains(response, "Brick 2 x 4, Plain")
        keys = re.findall(r'data-key="([^"]+)"', response.content.decode())
        self.assertEqual(len(keys), 5)

    def test_id_without_suffix_renders_the_full_id(self):
        response = self.client.get('/?set_id=1234')
        self.assertContains(response, "value='1234-1'")

    def test_unknown_and_empty_ids_return_404(self):
        for set_id in ("9999-1", "", "../../colors"):
            with self.subTest(set_id=set_id):
                response = self.client.get('/', {"set_id": set_id})
                self.assertEqual(response.status_code, 404)

    def test_set_without_parts_renders_an_empty_checklist(self):
        response = self.client.get('/?set_id=9000-1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Multipack")

    def test_missing_catalog_returns_503(self):
        with override_settings(CATALOG_DB=self.temp_dir / "does-not-exist.sqlite3"):
            with self.assertLogs("checklist.services", "ERROR"):
                response = self.client.get('/?set_id=1234-1')
        self.assertEqual(response.status_code, 503)


class ViewsTestCase(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    @patch('checklist.services.fetch_set_data')
    @patch('checklist.services.fetch_parts_data')
    def test_each_checkbox_has_its_own_key(self, mock_fetch_parts, mock_fetch_set):
        mock_fetch_set.return_value = ({"name": "Test Set"}, "1234-1")
        mock_fetch_parts.return_value = {"results": [
            {
                "part": {
                    "part_num": "3001",
                    "name": "Brick",
                    "part_img_url": "http://img",
                },
                "color": {"name": color, "id": 1},
                "quantity": 2,
                "is_spare": False
            }
            for color in ("Red", "Blue")
        ]}

        response = self.client.get('/?set_id=1234-1')

        keys = re.findall(r'data-key="([^"]+)"', response.content.decode())
        self.assertCountEqual(keys, [
            "1234-1:3001:Red:1", "1234-1:3001:Red:2",
            "1234-1:3001:Blue:1", "1234-1:3001:Blue:2",
        ])

    def render_page(self, parts, query=""):
        results = [
            {
                "part": {
                    "part_num": num,
                    "name": name,
                    "part_img_url": img,
                },
                "color": {"name": color, "rgb": "C91A09"},
                "quantity": 1,
                "is_spare": False,
            }
            for num, name, color, img in parts
        ]
        with patch(
            'checklist.services.fetch_set_data',
            return_value=({"name": "Test Set"}, "1234-1"),
        ), patch(
            'checklist.services.fetch_parts_data',
            return_value={"results": results},
        ):
            return self.client.get(f'/?set_id=1234-1{query}')

    def test_missing_image_renders_placeholder(self):
        response = self.render_page([("p1", "Brick", "Red", None)])
        self.assertNotContains(response, 'src="None"')
        self.assertContains(response, "No image")

    def test_image_has_alt_text_and_colour_swatch(self):
        response = self.render_page([("p1", "Brick", "Red", "http://img")])
        self.assertContains(response, 'alt="Brick"')
        self.assertContains(response, "background-color: #C91A09")

    def test_sort_label_points_at_the_select(self):
        response = self.render_page([("p1", "Brick", "Red", "http://img")])
        self.assertContains(response, '<label for="selected_sort">Sort by:</label>')
        self.assertContains(response, '<select id="selected_sort"')

    def test_colour_sort_groups_parts_and_orders_them_by_name(self):
        response = self.render_page([
            ("p1", "Plate", "Red", "http://img"),
            ("p2", "Brick", "Blue", "http://img"),
            ("p3", "Brick", "Red", "http://img"),
        ], "&selected_sort=color")
        html = response.content.decode()

        self.assertEqual(re.findall(r"<h2>(.+?)</h2>", html), ["Blue", "Red"])
        self.assertLess(html.index('"1234-1:p3:'), html.index('"1234-1:p1:'))

    def test_other_sorts_have_no_colour_groups(self):
        response = self.render_page([("p1", "Brick", "Red", "http://img")])
        self.assertNotContains(response, "<h2>")

    @patch('checklist.services.fetch_set_data')
    def test_set_id_is_trimmed(self, mock_fetch_set):
        mock_fetch_set.return_value = (None, None)
        self.client.get('/', {"set_id": " 1234-1 "})
        mock_fetch_set.assert_called_once_with("1234-1")


@unittest.skipUnless(
    Path(settings.CATALOG_DB).exists(),
    "Run build_catalog to check real data",
)
class RealCatalogTestCase(SimpleTestCase):
    def test_set_1682_1_part_count(self):
        """Set 1682-1 has 407 parts, excluding spares and minifigure parts."""
        results = services.fetch_parts_data('1682-1')['results']

        total_parts = sum(part['quantity'] for part in results if not part['is_spare'])

        self.assertEqual(total_parts, 407)
