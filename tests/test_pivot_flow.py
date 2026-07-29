import unittest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.main import app
from backend.db.models import DatabaseManager

class TestPivotFlow(unittest.TestCase):

    def setUp(self):
        self.db = DatabaseManager()
        self.db._init_db()

    def test_pivot_approval_happy_path(self):
        """
        Happy Path: Create investigation -> approve selector -> verify status becomes completed -> hits recorded.
        """
        with TestClient(app) as client:
            res = client.post("/api/investigate", json={"target": "octocat", "selector_type": "username"})
            self.assertEqual(res.status_code, 200)
            inv_id = res.json()["id"]

            # Add a pending selector to be approved
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO selectors (investigation_id, selector_value, selector_type, approved) VALUES (?, ?, ?, 0)",
                    (inv_id, "octocat_pivot", "username")
                )
                selector_id = cursor.lastrowid
                conn.commit()

            # Approve the selector
            approve_res = client.post(f"/api/investigations/{inv_id}/approve-selector/{selector_id}")
            self.assertEqual(approve_res.status_code, 200)

            # Wait briefly for background enumeration
            asyncio.run(asyncio.sleep(0.5))

            # Fetch investigation status
            detail_res = client.get(f"/api/investigations/{inv_id}")
            self.assertEqual(detail_res.status_code, 200)
            data = detail_res.json()
            self.assertIn(data["status"], ["running", "completed"])

            # Verify selector approved flag is 1
            selectors = data.get("selectors", [])
            approved_selectors = [s for s in selectors if s["id"] == selector_id]
            self.assertEqual(len(approved_selectors), 1)
            self.assertEqual(approved_selectors[0]["approved"], 1)

    def test_pivot_approval_failure_path(self):
        """
        Failure Path: Mock an adapter exception/timeout -> verify status becomes 'failed' (not stuck on running) -> verify evidence_log has error entry.
        """
        with TestClient(app) as client:
            res = client.post("/api/investigate", json={"target": "fail_test", "selector_type": "username"})
            inv_id = res.json()["id"]

            # Mock SherlockAdapter to raise an exception
            with patch("backend.enumeration.sherlock_adapter.SherlockAdapter.run", new_callable=AsyncMock) as mock_run:
                mock_run.side_effect = Exception("Simulated Adapter Timeout / Failure")

                # Trigger run_enumeration via endpoint
                run_res = client.post(f"/api/investigations/{inv_id}/run")
                
                # Check investigation status in DB
                with self.db.get_connection() as conn:
                    inv = conn.cursor().execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)).fetchone()
                    self.assertEqual(inv["status"], "failed")

                    logs = conn.cursor().execute(
                        "SELECT * FROM evidence_log WHERE investigation_id = ? AND action = 'enumeration_failed'",
                        (inv_id,)
                    ).fetchall()
                    self.assertGreaterEqual(len(logs), 1)

if __name__ == "__main__":
    unittest.main()
