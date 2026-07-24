import re
import logging
from typing import List, Dict, Any
from app.modules.base_module import BaseModule

logger = logging.getLogger(__name__)

# Common Country Dialing Codes
COUNTRY_CODES = {
    "1": {"country": "United States / Canada", "iso": "US/CA", "flag": "🇺🇸/🇨🇦"},
    "44": {"country": "United Kingdom", "iso": "GB", "flag": "🇬🇧"},
    "91": {"country": "India", "iso": "IN", "flag": "🇮🇳"},
    "49": {"country": "Germany", "iso": "DE", "flag": "🇩🇪"},
    "33": {"country": "France", "iso": "FR", "flag": "🇫🇷"},
    "61": {"country": "Australia", "iso": "AU", "flag": "🇦🇺"},
    "81": {"country": "Japan", "iso": "JP", "flag": "🇯🇵"},
    "86": {"country": "China", "iso": "CN", "flag": "🇨🇳"},
    "7": {"country": "Russia / Kazakhstan", "iso": "RU/KZ", "flag": "🇷🇺"},
    "55": {"country": "Brazil", "iso": "BR", "flag": "🇧🇷"},
    "34": {"country": "Spain", "iso": "ES", "flag": "🇪🇸"},
    "39": {"country": "Italy", "iso": "IT", "flag": "🇮🇹"},
    "31": {"country": "Netherlands", "iso": "NL", "flag": "🇳🇱"},
    "41": {"country": "Switzerland", "iso": "CH", "flag": "🇨🇭"},
    "48": {"country": "Poland", "iso": "PL", "flag": "🇵🇱"},
    "62": {"country": "Indonesia", "iso": "ID", "flag": "🇮🇩"},
    "971": {"country": "United Arab Emirates", "iso": "AE", "flag": "🇦🇪"},
}

class PhoneChecker(BaseModule):
    """Enumeration & metadata parsing module for phone numbers."""

    @property
    def module_name(self) -> str:
        return "Phone Number Lookup Module"

    @property
    def supported_selector_types(self) -> List[str]:
        return ["phone"]

    async def check(self, target: str, selector_type: str) -> List[Dict[str, Any]]:
        if selector_type != "phone":
            return []

        # Sanitize input digits
        digits = re.sub(r"\D", "", target)
        if len(digits) < 7:
            return []

        e164 = f"+{digits}" if not target.startswith("+") else target

        # Detect Country Code
        detected_country = "International / Unknown"
        country_flag = "🌐"
        iso_code = "UNKNOWN"

        for code in sorted(COUNTRY_CODES.keys(), key=lambda k: len(k), reverse=True):
            if digits.startswith(code):
                info = COUNTRY_CODES[code]
                detected_country = info["country"]
                country_flag = info["flag"]
                iso_code = info["iso"]
                break

        # Line type estimation based on digit count / format
        line_type = "Mobile / Landline"
        if len(digits) == 10 and digits.startswith("1800") or digits.startswith("1888") or digits.startswith("1877"):
            line_type = "Toll-Free"

        finding = {
            "platform": "Telephony Metadata",
            "matched_selector": e164,
            "display_name": f"{country_flag} {detected_country} ({iso_code})",
            "profile_url": None,
            "avatar_url": None,
            "bio": f"E.164 Format: {e164} | Country: {detected_country} | Estimated Type: {line_type} | Total Digits: {len(digits)}",
            "status": "active",
            "rarity_weight": 1.2,
            "raw_data": {
                "e164": e164,
                "digits": digits,
                "country": detected_country,
                "iso": iso_code,
                "line_type": line_type
            }
        }

        return [finding]
