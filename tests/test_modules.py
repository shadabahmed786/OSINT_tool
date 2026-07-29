import unittest
import asyncio
from backend.main import detect_selector_type
from backend.breach.hibp_pwned_passwords import check_password_exposure_kanonymity
from backend.correlation.scoring import compute_rule_confidence
from backend.enumeration.base import Hit
from backend.db.models import DatabaseManager

class TestOSINTModules(unittest.TestCase):

    def test_selector_type_detection(self):
        self.assertEqual(detect_selector_type("user@example.com"), "email")
        self.assertEqual(detect_selector_type("+14155552671"), "phone")
        self.assertEqual(detect_selector_type("john_doe_99"), "username")
        self.assertEqual(detect_selector_type("John Doe"), "name")

    def test_phone_checker(self):
        db = DatabaseManager()
        db._init_db()
        from backend.enumeration.fallback_modules import run_phone_http_fallback
        hits = asyncio.run(run_phone_http_fallback("+14155552671", "test-inv-id", db))
        self.assertEqual(len(hits), 1)
        self.assertIn("United States", hits[0].region)
        self.assertEqual(hits[0].platform, "Telephony Metadata Registry")

    def test_hibp_k_anonymity_check(self):
        # "123456" is a well known breached password
        res = asyncio.run(check_password_exposure_kanonymity("123456"))
        self.assertTrue(res["exposed"])
        self.assertGreater(res["count"], 1000)

    def test_scoring_engine(self):
        hit = Hit(platform="GitHub", source_tool="sherlock", account_status="live")
        tier, score = compute_rule_confidence(hit, total_hits_in_case=2, profile_picture_reused=False)
        self.assertIn(tier.upper(), ["HIGH", "MEDIUM", "LOW"])
        self.assertGreaterEqual(score, 0.0)

if __name__ == "__main__":
    unittest.main()
