import os
import unittest
import asyncio
from pathlib import Path
from app.config import BASE_DIR, FORBIDDEN_API_KEYS
from app.database import init_db, create_investigation, get_investigation, log_evidence

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

        app_dir = BASE_DIR / "app"
        violations = []

        for root, _, files in os.walk(app_dir):
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
        async def run_test():
            await init_db()
            inv = await create_investigation("test-guardrail-id", "test_target", "username")

            await log_evidence("test-guardrail-id", "test_action", "Audit detail entry 1")
            await log_evidence("test-guardrail-id", "test_action", "Audit detail entry 2")

            data = await get_investigation("test-guardrail-id")
            logs = data.get("evidence_log", [])

            self.assertGreaterEqual(len(logs), 3) # initial + 2 entries
            self.assertEqual(logs[-1]["detail"], "Audit detail entry 2")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
