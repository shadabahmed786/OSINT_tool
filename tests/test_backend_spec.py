import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.breach.hibp_pwned_passwords import check_password_exposure_kanonymity
from backend.correlation.scoring import compute_rule_confidence
from backend.enumeration.base import Hit
from backend.main import app
from backend.models_runtime.model_manager import ModelManager


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.calls.append((url, json))
        return FakeResponse(status_code=200, json_data={"response": "ok"})

    async def get(self, url):
        return FakeResponse(status_code=200, text="1E4C9B93F3F0682250B6CF8331B7EE68FD8:1\n")


class TestBackendSpec(unittest.TestCase):
    def test_compute_rule_confidence(self):
        hit = Hit(platform="Keybase", source_tool="test", bio="Long enough bio", display_name="alice")
        tier, score = compute_rule_confidence(hit, total_hits_in_case=3, profile_picture_reused=True)
        self.assertEqual(tier, "high")
        self.assertGreaterEqual(score, 0.7)

    def test_model_manager_load_then_unload(self):
        manager = ModelManager(ollama_url="http://localhost:11434")

        with patch("backend.models_runtime.model_manager.httpx.AsyncClient", return_value=FakeAsyncClient()):
            asyncio.run(manager.load("llama3.1:8b"))
            self.assertEqual(manager.current_heavy_model, "llama3.1:8b")
            asyncio.run(manager.unload("llama3.1:8b"))
            self.assertIsNone(manager.current_heavy_model)

    def test_hibp_kanonymity_helper(self):
        with patch("backend.breach.hibp_pwned_passwords.httpx.AsyncClient", return_value=FakeAsyncClient()):
            result = asyncio.run(check_password_exposure_kanonymity("password"))
        self.assertTrue(result["exposed"])
        self.assertGreater(result["count"], 0)

    def test_api_investigate_retention_days_override(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/investigate",
                json={"target": "octocat", "selector_type": "username", "retention_days": 7},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["retention_days"], 7)

            investigation = client.get(f"/investigations/{data['id']}").json()
            self.assertEqual(investigation["retention_days"], 7)


if __name__ == "__main__":
    unittest.main()
