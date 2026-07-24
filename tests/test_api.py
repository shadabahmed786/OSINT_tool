import unittest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

class TestAPIEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_investigate_endpoint(self):
        with TestClient(app) as client:
            response = client.post("/api/investigate", json={"target": "octocat", "selector_type": "username"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("id", data)
            self.assertEqual(data.get("initial_selector") or data.get("target"), "octocat")
            self.assertEqual(data.get("initial_selector_type") or data.get("selector_type"), "username")

    def test_list_investigations(self):
        with TestClient(app) as client:
            response = client.get("/api/investigations")
            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.json(), list)

    def test_password_exposure_endpoint(self):
        with TestClient(app) as client:
            response = client.post("/api/check-password-hash", json={"password": "password123"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["exposed"])
            self.assertGreater(data["count"], 0)

    def test_ai_summary_endpoint(self):
        with TestClient(app) as client:
            # Create an investigation
            res = client.post("/api/investigate", json={"target": "octocat", "selector_type": "username"})
            inv_id = res.json()["id"]

            summary_res = client.post(f"/api/investigations/{inv_id}/ai-summary")
            self.assertEqual(summary_res.status_code, 200)
            data = summary_res.json()
            self.assertEqual(data["target"], "octocat")
            self.assertIn("summary", data)

if __name__ == "__main__":
    unittest.main()
