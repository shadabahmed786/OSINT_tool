import unittest
import asyncio
from app.modules.scoring_engine import score_and_rank_findings
from app.modules.phone_checker import PhoneChecker
from app.modules.hibp_checker import check_password_exposure
from app.main import detect_selector_type

class TestOSINTModules(unittest.TestCase):

    def test_selector_type_detection(self):
        self.assertEqual(detect_selector_type("user@example.com"), "email")
        self.assertEqual(detect_selector_type("+14155552671"), "phone")
        self.assertEqual(detect_selector_type("john_doe_99"), "username")
        self.assertEqual(detect_selector_type("John Doe"), "name")

    def test_phone_checker(self):
        checker = PhoneChecker()
        findings = asyncio.run(checker.check("+14155552671", "phone"))
        self.assertEqual(len(findings), 1)
        self.assertIn("United States", findings[0]["display_name"])
        self.assertEqual(findings[0]["platform"], "Telephony Metadata")

    def test_hibp_k_anonymity_check(self):
        # "123456" is a well known breached password
        res = asyncio.run(check_password_exposure("123456"))
        self.assertTrue(res["exposed"])
        self.assertGreater(res["count"], 1000)

    def test_scoring_engine(self):
        raw_hits = [
            {
                "platform": "GitHub",
                "matched_selector": "testuser",
                "display_name": "Test User",
                "profile_url": "https://github.com/testuser",
                "avatar_url": "https://avatars.githubusercontent.com/u/1",
                "bio": "Software developer creating open source software",
                "rarity_weight": 1.4
            },
            {
                "platform": "HackerNews",
                "matched_selector": "testuser",
                "display_name": "testuser",
                "bio": "Karma: 50",
                "rarity_weight": 1.5
            }
        ]

        scored = score_and_rank_findings(raw_hits)
        self.assertEqual(len(scored), 2)
        self.assertIn(scored[0]["confidence_tier"], ["HIGH", "MEDIUM"])
        self.assertGreaterEqual(scored[0]["confidence_score"], 50.0)

if __name__ == "__main__":
    unittest.main()
