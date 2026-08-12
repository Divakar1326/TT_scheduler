"""Integration tests for the Flask static file routing and frontend assets serving."""
import unittest
from app.api.app import create_app

class TestFrontendRouting(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_root_index_html_serving(self):
        # 1. Serving index page
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html_content = res.get_data(as_text=True)
        self.assertIn("UniSched", html_content)
        self.assertIn("app.js", html_content)
        self.assertIn("style.css", html_content)

    def test_stylesheet_serving(self):
        # 2. Serving style.css
        res = self.client.get("/style.css")
        self.assertEqual(res.status_code, 200)
        self.assertIn("body", res.get_data(as_text=True))

    def test_javascript_serving(self):
        # 3. Serving app.js
        res = self.client.get("/app.js")
        self.assertEqual(res.status_code, 200)
        self.assertIn("timetableData", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
