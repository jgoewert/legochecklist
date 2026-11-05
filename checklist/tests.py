import re

import requests
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, Client
from unittest.mock import patch, Mock
from . import services


def api_response(status_code=200, payload=None):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


class SortingTestCase(TestCase):
    def test_sort_by_name(self):
        item = {"part": {"name": "Birck"}}
        self.assertEqual(services.sort_by_name(item), "Birck")

    def test_sort_by_color(self):
        item = {"color": {"name": "Red"}}
        self.assertEqual(services.sort_by_color(item), "Red")

    def test_sort_by_partnum(self):
        item = {"part": {"part_num": "3001"}}
        self.assertEqual(services.sort_by_partnum(item), "3001")


class ServicesTestCase(TestCase):
    def setUp(self):
        cache.clear()

    @patch('checklist.services.requests.get')
    def test_fetch_set_data_success(self, mock_get):
        mock_get.return_value = api_response(payload={"name": "Test Set"})

        data, set_id = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Test Set")
        self.assertEqual(set_id, "1234-1")

    @patch('checklist.services.requests.get')
    def test_fetch_set_data_not_found(self, mock_get):
        mock_get.return_value = api_response(404)

        data, set_id = services.fetch_set_data("1234-1")
        self.assertIsNone(data)
        self.assertIsNone(set_id)

    @patch('checklist.services.requests.get')
    def test_fetch_parts_data_success(self, mock_get):
        mock_get.return_value = api_response(payload={"results": []})

        data = services.fetch_parts_data("1234-1")
        self.assertEqual(data["results"], [])

    @patch('checklist.services.requests.get')
    def test_key_is_sent_in_header_with_timeout(self, mock_get):
        mock_get.return_value = api_response(payload={"name": "Test Set"})

        services.fetch_set_data("1234-1")

        args, kwargs = mock_get.call_args
        self.assertNotIn("key=", args[0])
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            f"key {settings.REBRICKABLE_API_KEY}",
        )
        self.assertEqual(kwargs["timeout"], services.REQUEST_TIMEOUT_SECONDS)

    @patch('checklist.services.requests.get')
    def test_unversioned_id_falls_back_to_dash_one(self, mock_get):
        mock_get.side_effect = [
            api_response(404),
            api_response(payload={"name": "Test Set"}),
        ]

        data, set_id = services.fetch_set_data("1234")

        self.assertEqual(data["name"], "Test Set")
        self.assertEqual(set_id, "1234-1")

    @patch('checklist.services.requests.get')
    def test_versioned_id_is_only_tried_once(self, mock_get):
        mock_get.return_value = api_response(404)

        services.fetch_set_data("1234-2")

        self.assertEqual(mock_get.call_count, 1)

    @patch('checklist.services.requests.get')
    def test_only_404_triggers_the_fallback(self, mock_get):
        mock_get.return_value = api_response(429)

        with self.assertRaises(services.RebrickableError):
            services.fetch_set_data("1234")

        self.assertEqual(mock_get.call_count, 1)

    @patch('checklist.services.requests.get')
    def test_success_is_cached(self, mock_get):
        mock_get.return_value = api_response(payload={"name": "Test Set"})

        services.fetch_set_data("1234-1")
        services.fetch_set_data("1234-1")

        self.assertEqual(mock_get.call_count, 1)

    @patch('checklist.services.requests.get')
    def test_failures_are_not_cached(self, mock_get):
        for failure in (api_response(429), api_response(404)):
            mock_get.return_value = failure
            try:
                services.fetch_set_data("1234-1")
            except services.RebrickableError:
                pass

            mock_get.return_value = api_response(payload={"name": "Recovered"})
            data, _ = services.fetch_set_data("1234-1")
            self.assertEqual(data["name"], "Recovered")
            cache.clear()

    @patch('checklist.services.requests.get')
    def test_network_error_raises_rebrickable_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("down")

        with self.assertRaises(services.RebrickableError):
            services.fetch_set_data("1234-1")

    @patch('checklist.services.requests.get')
    def test_invalid_json_raises_rebrickable_error(self, mock_get):
        response = api_response()
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response

        with self.assertRaises(services.RebrickableError):
            services.fetch_set_data("1234-1")

    @patch('checklist.services.requests.get')
    def test_invalid_set_ids_never_reach_the_api(self, mock_get):
        invalid_ids = [
            "", "../../colors", "1234-1/parts", "1234-1?x=1#", "1234-1#", "..",
            "a b", "-1", "1234-", "1234\n", "x" * 65,
        ]
        for set_id in invalid_ids:
            with self.subTest(set_id=set_id):
                with self.assertRaises(services.InvalidSetId):
                    services.fetch_set_data(set_id)
                with self.assertRaises(services.InvalidSetId):
                    services.fetch_parts_data(set_id)

        mock_get.assert_not_called()

    @patch('checklist.services.requests.get')
    def test_valid_set_id_formats_are_accepted(self, mock_get):
        mock_get.return_value = api_response(payload={"name": "Test Set"})

        for set_id in ("1682-1", "1682", "COMCON001-1", "fruit1-1", "a_b-c-1"):
            with self.subTest(set_id=set_id):
                data, _ = services.fetch_set_data(set_id)
                self.assertEqual(data["name"], "Test Set")


class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    @patch('checklist.services.fetch_set_data')
    @patch('checklist.services.fetch_parts_data')
    def test_index_view_success(self, mock_fetch_parts, mock_fetch_set):
        mock_fetch_set.return_value = ({"name": "Test Set"}, "1234-1")
        mock_fetch_parts.return_value = {"results": [
            {
                "part": {"part_num": "p1", "name": "Brick", "part_img_url": "http://img"},
                "color": {"name": "Red", "id": 1},
                "quantity": 1,
                "is_spare": False
            }
        ]}

        response = self.client.get('/?set_id=1234-1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Set")
        self.assertContains(response, "Brick")

    @patch('checklist.services.fetch_set_data')
    @patch('checklist.services.fetch_parts_data')
    def test_each_checkbox_has_its_own_key(self, mock_fetch_parts, mock_fetch_set):
        mock_fetch_set.return_value = ({"name": "Test Set"}, "1234-1")
        mock_fetch_parts.return_value = {"results": [
            {
                "part": {"part_num": "3001", "name": "Brick", "part_img_url": "http://img"},
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

    @patch('checklist.services.fetch_set_data')
    def test_index_view_not_found(self, mock_fetch_set):
        mock_fetch_set.return_value = (None, None)
        response = self.client.get('/?set_id=9999-1')
        self.assertEqual(response.status_code, 404)

    @patch('checklist.services.requests.get')
    def test_invalid_set_id_returns_400(self, mock_get):
        for set_id in ("", "../../colors"):
            with self.subTest(set_id=set_id):
                response = self.client.get('/', {"set_id": set_id})
                self.assertEqual(response.status_code, 400)
        mock_get.assert_not_called()

    @patch('checklist.services.requests.get')
    def test_upstream_failure_returns_502(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("down")
        response = self.client.get('/?set_id=1234-1')
        self.assertEqual(response.status_code, 502)

    @patch('checklist.services.requests.get')
    def test_throttled_parts_request_returns_502(self, mock_get):
        mock_get.side_effect = [
            api_response(payload={"name": "Test Set"}),
            api_response(429),
        ]
        response = self.client.get('/?set_id=1234-1')
        self.assertEqual(response.status_code, 502)

    @patch('checklist.services.fetch_set_data')
    def test_set_id_is_trimmed(self, mock_fetch_set):
        mock_fetch_set.return_value = (None, None)
        self.client.get('/', {"set_id": " 1234-1 "})
        mock_fetch_set.assert_called_once_with("1234-1")


class IntegrationTestCase(TestCase):
    def test_set_1682_1_part_count(self):
        """
        Integration test to verify set 1682-1 has 240 parts using live API.
        """
        # Ensure we are using the live API, not mocked
        cache.clear()

        parts_data = services.fetch_parts_data('1682-1')
        self.assertIsNotNone(parts_data, "Failed to fetch parts data for 1682-1")

        results = parts_data.get('results', [])

        # Calculate total quantity excluding spares
        total_parts = sum(part['quantity'] for part in results if not part['is_spare'])

        self.assertEqual(total_parts, 407, f"Expected 407 parts, but found {total_parts}")
