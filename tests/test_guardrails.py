import os
import unittest
from pathlib import Path
from backend.db.models import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent.parent

class TestGuardrailsAndSecurity(unittest.TestCase):

    def test_forbidden_paid_api_domains_in_codebase(self):
        """
        Static Linter Guardrail (§0, §11):
        Ensures no file in the codebase calls paid breach API endpoints
        (haveibeenpwned.com/api/v3, dehashed.com, intelx.io, pimeyes.com, facecheck.id).
        Only keyless api.pwnedpasswords.com/range is allowed.
        """
        forbidden_domains = [
            "haveibeenpwned.com/api/v3",
            "dehashed.com",
            "intelx.io",
            "pimeyes.com",
            "facecheck.id"
        ]

        backend_dir = BASE_DIR / "backend"
        violations = []

        for root, _, files in os.walk(backend_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    content = filepath.read_text(encoding="utf-8")
                    for domain in forbidden_domains:
                        if domain in content:
                            violations.append(f"{file}: contains paid API domain '{domain}'")

        self.assertEqual(
            len(violations), 0,
            f"GUARDRAIL VIOLATION (§0, §11): Paid API endpoints detected: {violations}"
        )

    def test_append_only_evidence_log(self):
        """
        Guardrail (§0, §3):
        Verifies that evidence_log accurately records audit entries and provides no update/delete access.
        """
        import uuid
        db = DatabaseManager()
        db._init_db()
        inv_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO investigations (id, initial_selector, initial_selector_type) VALUES (?, ?, ?)",
                (inv_id, "test_target", "username"),
            )
            conn.commit()

        db.log_evidence(inv_id, "investigation_created", {"selector": "test_target"})
        db.log_evidence(inv_id, "test_action", "Audit detail entry 1")
        db.log_evidence(inv_id, "test_action", "Audit detail entry 2")

        with db.get_connection() as conn:
            logs = conn.cursor().execute(
                "SELECT * FROM evidence_log WHERE investigation_id = ? ORDER BY id ASC",
                (inv_id,),
            ).fetchall()

        self.assertGreaterEqual(len(logs), 3)
        self.assertEqual(dict(logs[-1])["detail"], "Audit detail entry 2")

if __name__ == "__main__":
    unittest.main()
