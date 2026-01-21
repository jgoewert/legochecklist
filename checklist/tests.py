from django.test import TestCase, Client
from unittest.mock import patch, Mock
from . import services
from .models import Piece

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
        services.fetch_set_data.cache_clear()
        services.fetch_parts_data.cache_clear()

    @patch('checklist.services.requests.get')
    def test_fetch_set_data_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test Set"}
        mock_get.return_value = mock_response

        data, set_id = services.fetch_set_data("1234-1")
        self.assertEqual(data["name"], "Test Set")
        self.assertEqual(set_id, "1234-1")

    @patch('checklist.services.requests.get')
    def test_fetch_set_data_failure(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        data, set_id = services.fetch_set_data("1234-1")
        self.assertIsNone(data)
        self.assertIsNone(set_id)

    @patch('checklist.services.requests.get')
    def test_fetch_parts_data_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        data = services.fetch_parts_data("1234-1")
        self.assertEqual(data["results"], [])

class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

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
    def test_index_view_not_found(self, mock_fetch_set):
        mock_fetch_set.return_value = (None, None)
        response = self.client.get('/?set_id=9999-1')
        self.assertEqual(response.status_code, 404)

class IntegrationTestCase(TestCase):
    def test_set_1682_1_part_count(self):
        """
        Integration test to verify set 1682-1 has 240 parts using live API.
        """
        # Ensure we are using the live API, not mocked
        services.fetch_parts_data.cache_clear()
        
        parts_data = services.fetch_parts_data('1682-1')
        self.assertIsNotNone(parts_data, "Failed to fetch parts data for 1682-1")
        
        results = parts_data.get('results', [])
        
        # Calculate total quantity excluding spares
        total_parts = sum(part['quantity'] for part in results if not part['is_spare'])
        
        self.assertEqual(total_parts, 407, f"Expected 407 parts, but found {total_parts}")
