import hashlib

import httpx


async def check_password_exposure_kanonymity(password: str) -> dict:
    """Send only the first 5 SHA-1 hex chars to HIBP."""
    sha1_pwd = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = sha1_pwd[:5]
    suffix = sha1_pwd[5:]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
        if response.status_code != 200:
            return {"exposed": False, "count": 0, "error": "API Unavailable"}

        for line in response.text.splitlines():
            if ":" not in line:
                continue
            h_suffix, count = line.split(":", 1)
            if h_suffix == suffix:
                return {"exposed": True, "count": int(count)}

    return {"exposed": False, "count": 0}
