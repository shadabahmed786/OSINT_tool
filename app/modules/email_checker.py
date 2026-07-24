import hashlib
import httpx
import logging
from typing import List, Dict, Any
from app.modules.base_module import BaseModule
from app.config import DEFAULT_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class EmailChecker(BaseModule):
    """Enumeration module for email addresses."""

    @property
    def module_name(self) -> str:
        return "Email Enumeration Module"

    @property
    def supported_selector_types(self) -> List[str]:
        return ["email"]

    async def check(self, target: str, selector_type: str) -> List[Dict[str, Any]]:
        if selector_type != "email":
            return []

        target_clean = target.strip().lower()
        findings: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            # 1. Gravatar check (MD5 of trimmed lowercase email)
            gravatar_finding = await self._check_gravatar(client, target_clean)
            if gravatar_finding:
                findings.append(gravatar_finding)

            # 2. GitHub Email Search Check
            github_finding = await self._check_github_email(client, target_clean)
            if github_finding:
                findings.append(github_finding)

            # 3. Imgur check
            imgur_finding = await self._check_imgur(client, target_clean)
            if imgur_finding:
                findings.append(imgur_finding)

            # 4. Holehe-style endpoint check (Adobe/WordPress/Spotify registration signals)
            wp_finding = await self._check_wordpress_com(client, target_clean)
            if wp_finding:
                findings.append(wp_finding)

        return findings

    async def _check_gravatar(self, client: httpx.AsyncClient, email: str) -> Dict[str, Any] | None:
        email_md5 = hashlib.md5(email.encode("utf-8")).hexdigest()
        url = f"https://www.gravatar.com/{email_md5}.json"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                entry = data.get("entry", [{}])[0]
                return {
                    "platform": "Gravatar",
                    "matched_selector": email,
                    "display_name": entry.get("displayName") or entry.get("preferredUsername"),
                    "profile_url": entry.get("profileUrl") or f"https://gravatar.com/{email_md5}",
                    "avatar_url": entry.get("thumbnailUrl") or f"https://www.gravatar.com/avatar/{email_md5}",
                    "bio": entry.get("aboutMe", ""),
                    "status": "active",
                    "rarity_weight": 1.2,
                    "raw_data": {"gravatar_hash": email_md5, "entry": entry}
                }
            elif resp.status_code == 404:
                # Avatar image exists even if full profile JSON doesn't
                img_url = f"https://www.gravatar.com/avatar/{email_md5}?d=404"
                img_resp = await client.get(img_url)
                if img_resp.status_code == 200:
                    return {
                        "platform": "Gravatar",
                        "matched_selector": email,
                        "display_name": None,
                        "profile_url": f"https://gravatar.com/avatar/{email_md5}",
                        "avatar_url": f"https://www.gravatar.com/avatar/{email_md5}",
                        "bio": "Registered Gravatar avatar found",
                        "status": "active",
                        "rarity_weight": 1.1,
                        "raw_data": {"has_avatar": True}
                    }
        except Exception as e:
            logger.warning("Gravatar check error: %s", e)
        return None

    async def _check_github_email(self, client: httpx.AsyncClient, email: str) -> Dict[str, Any] | None:
        url = f"https://api.github.com/search/users?q={email}+in:email"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    user = items[0]
                    return {
                        "platform": "GitHub",
                        "matched_selector": email,
                        "display_name": user.get("login"),
                        "profile_url": user.get("html_url"),
                        "avatar_url": user.get("avatar_url"),
                        "bio": f"GitHub user linked via public email search ({user.get('type')})",
                        "status": "active",
                        "rarity_weight": 1.5,
                        "raw_data": user
                    }
        except Exception as e:
            logger.warning("GitHub email check error: %s", e)
        return None

    async def _check_imgur(self, client: httpx.AsyncClient, email: str) -> Dict[str, Any] | None:
        # Check via public endpoint header indicator
        url = "https://imgur.com/signin"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                # Placeholder for Imgur email lookup module
                pass
        except Exception as e:
            logger.warning("Imgur check error: %s", e)
        return None

    async def _check_wordpress_com(self, client: httpx.AsyncClient, email: str) -> Dict[str, Any] | None:
        url = f"https://public-api.wordpress.com/rest/v1.1/users/{email}"
        try:
            resp = await client.get(url)
            if resp.status_code in [200, 400]:
                # Status code indicates account existence response structure
                if "invalid_user" not in resp.text:
                    return {
                        "platform": "WordPress.com",
                        "matched_selector": email,
                        "display_name": None,
                        "profile_url": "https://wordpress.com",
                        "avatar_url": None,
                        "bio": "Email registered on WordPress.com network",
                        "status": "active",
                        "rarity_weight": 1.1,
                        "raw_data": {"status_code": resp.status_code}
                    }
        except Exception as e:
            logger.warning("WordPress check error: %s", e)
        return None
