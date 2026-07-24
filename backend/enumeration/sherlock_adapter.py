import asyncio

from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit


class SherlockAdapter(EnumerationAdapter):
    selector_type = "username"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "sherlock", "selector": selector})
        try:
            process = await asyncio.create_subprocess_exec(
                "sherlock", selector, "--timeout", "5", "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60.0)
        except Exception as exc:
            self.db.log_evidence(investigation_id, "search_failed", {"tool": "sherlock", "reason": str(exc)})
            return []

        hits: list[Hit] = []
        for line in stdout.decode(errors="ignore").splitlines():
            if "[+]" not in line or ":" not in line:
                continue
            platform, url = line.replace("[+]", "").strip().split(":", 1)
            platform = platform.strip()
            url = url.strip()
            hits.append(Hit(platform=platform, source_tool="sherlock", bio=f"Profile URL: {url}", account_status="live", confidence_tier="medium", confidence_score=0.55))
            self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "sherlock", "platform": platform, "url": url})
        return hits
