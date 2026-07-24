import hashlib
import httpx
import logging
from typing import Dict, Any
from app.config import DEFAULT_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

async def check_password_exposure(password_or_hash: str) -> Dict[str, Any]:
    """
    Check password exposure using the HIBP Pwned Passwords k-Anonymity API.
    Zero paid API keys needed; anonymous, keyless SHA-1 range query.
    """
    clean_input = password_or_hash.strip()
    
    # Check if input is already a 40-character SHA-1 hex string
    if len(clean_input) == 40 and all(c in "0123456789abcdefABCDEF" for c in clean_input):
        sha1_hex = clean_input.upper()
    else:
        sha1_hex = hashlib.sha1(clean_input.encode("utf-8")).hexdigest().upper()

    prefix = sha1_hex[:5]
    suffix = sha1_hex[5:]

    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    headers = {
        "User-Agent": "OSINT-Platform-Checker/1.0",
        "Accept": "*/*"
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    lines = resp.text.splitlines()
                    for line in lines:
                        if ":" in line:
                            h_suffix, count_str = line.split(":", 1)
                            if h_suffix.strip().upper() == suffix:
                                count = int(count_str.strip())
                                return {
                                    "exposed": True,
                                    "count": count,
                                    "sha1_hash": sha1_hex,
                                    "prefix": prefix,
                                    "message": f"CRITICAL: Password hash was found {count:,} times in known data breaches!"
                                }
                    
                    return {
                        "exposed": False,
                        "count": 0,
                        "sha1_hash": sha1_hex,
                        "prefix": prefix,
                        "message": "CLEAN: Password hash was NOT found in the HIBP Pwned Passwords database."
                    }
                elif resp.status_code == 429:
                    # Rate limited, pause briefly and retry
                    await asyncio.sleep(1.0)
                    continue
                else:
                    return {
                        "exposed": False,
                        "count": 0,
                        "sha1_hash": sha1_hex,
                        "error": f"API HTTP Error {resp.status_code}"
                    }
        except Exception as e:
            if attempt == 2:
                logger.error("HIBP Pwned Passwords API error after retries: %s", e)
                return {
                    "exposed": False,
                    "count": 0,
                    "sha1_hash": sha1_hex,
                    "error": str(e)
                }
            await asyncio.sleep(0.5)
