import asyncio
import httpx
import logging
from typing import List, Dict, Any
from app.modules.base_module import BaseModule
from app.config import DEFAULT_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# List of platforms with profile URL template, error response indicator, and rarity weight
PLATFORMS = [
    {
        "name": "GitHub",
        "url": "https://github.com/{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.4,
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{username}/about.json",
        "check_type": "json_field",
        "json_field": "data",
        "rarity_weight": 1.3,
    },
    {
        "name": "Twitter / X",
        "url": "https://x.com/{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.2,
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.2,
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.3,
    },
    {
        "name": "HackerNews",
        "url": "https://hacker-news.firebaseio.com/v0/user/{username}.json",
        "check_type": "json_not_null",
        "rarity_weight": 1.5,
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/api/v4/users?username={username}",
        "check_type": "json_non_empty_list",
        "rarity_weight": 1.4,
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/v2/users/{username}/",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.5,
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{username}/",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.6,
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={username}",
        "check_type": "keybase",
        "rarity_weight": 1.7,
    },
    {
        "name": "CodePen",
        "url": "https://codepen.io/{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.3,
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{username}",
        "check_type": "content_not_contains",
        "absent_text": "If you have Telegram, you can contact",
        "rarity_weight": 1.3,
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{username}/",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.1,
    },
    {
        "name": "Spotify",
        "url": "https://open.spotify.com/user/{username}",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.2,
    },
    {
        "name": "Substack",
        "url": "https://{username}.substack.com",
        "check_type": "status_code",
        "error_code": 404,
        "rarity_weight": 1.3,
    }
]

class UsernameChecker(BaseModule):
    """Enumeration module for usernames across top platforms."""

    @property
    def module_name(self) -> str:
        return "Username Enumeration Module"

    @property
    def supported_selector_types(self) -> List[str]:
        return ["username"]

    async def check(self, target: str, selector_type: str) -> List[Dict[str, Any]]:
        if selector_type != "username":
            return []

        username = target.strip().lstrip("@")
        if not username:
            return []

        findings: List[Dict[str, Any]] = []

        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, limits=limits, follow_redirects=True) as client:
            tasks = [self._check_platform(client, p, username) for p in PLATFORMS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, dict) and res is not None:
                    findings.append(res)

        return findings

    async def _check_platform(self, client: httpx.AsyncClient, platform: Dict[str, Any], username: str) -> Dict[str, Any] | None:
        name = platform["name"]
        url = platform["url"].format(username=username)
        check_type = platform["check_type"]
        rarity = platform.get("rarity_weight", 1.0)

        try:
            resp = await client.get(url)

            is_hit = False
            display_name = username
            avatar_url = None
            bio = f"Profile found on {name}"

            if check_type == "status_code":
                if resp.status_code == 200:
                    is_hit = True

            elif check_type == "json_field":
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get(platform["json_field"]):
                        is_hit = True
                        if name == "Reddit":
                            user_data = data["data"]
                            display_name = user_data.get("name")
                            avatar_url = user_data.get("icon_img")
                            bio = f"Karma: {user_data.get('total_karma', 0)}"

            elif check_type == "json_not_null":
                if resp.status_code == 200 and resp.json() is not None:
                    is_hit = True
                    if name == "HackerNews":
                        user_data = resp.json()
                        bio = f"Karma: {user_data.get('karma', 0)} | Created: {user_data.get('created', '')}"

            elif check_type == "json_non_empty_list":
                if resp.status_code == 200 and isinstance(resp.json(), list) and len(resp.json()) > 0:
                    is_hit = True
                    user_data = resp.json()[0]
                    display_name = user_data.get("name") or user_data.get("username")
                    avatar_url = user_data.get("avatar_url")
                    url = user_data.get("web_url") or url

            elif check_type == "keybase":
                if resp.status_code == 200:
                    data = resp.json()
                    them = data.get("them", [])
                    if them and len(them) > 0 and them[0] is not None:
                        is_hit = True
                        user_data = them[0]
                        profile = user_data.get("profile", {})
                        display_name = profile.get("full_name") or username
                        bio = profile.get("bio", "")

            elif check_type == "content_not_contains":
                if resp.status_code == 200 and platform["absent_text"] not in resp.text:
                    is_hit = True

            if is_hit:
                return {
                    "platform": name,
                    "matched_selector": username,
                    "display_name": display_name,
                    "profile_url": url,
                    "avatar_url": avatar_url,
                    "bio": bio,
                    "status": "active",
                    "rarity_weight": rarity,
                    "raw_data": {"url": url, "http_status": resp.status_code}
                }

        except Exception as e:
            logger.debug("Check failed for platform %s: %s", name, e)

        return None
