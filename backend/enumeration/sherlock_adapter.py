import asyncio
from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit
from backend.enumeration.fallback_modules import run_username_http_fallback

class SherlockAdapter(EnumerationAdapter):
    selector_type = "username"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "sherlock", "selector": selector})
        hits: list[Hit] = []
        try:
            process = await asyncio.create_subprocess_exec(
                "sherlock", selector, "--timeout", "5", "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)
            for line in stdout.decode(errors="ignore").splitlines():
                if "[+]" not in line or ":" not in line:
                    continue
                platform, url = line.replace("[+]", "").strip().split(":", 1)
                platform = platform.strip()
                url = url.strip()
                hits.append(Hit(platform=platform, source_tool="sherlock", bio=f"Profile URL: {url}", account_status="live", confidence_tier="HIGH", confidence_score=0.85))
                self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "sherlock", "platform": platform, "url": url})
        except Exception as exc:
            self.db.log_evidence(investigation_id, "search_failed", {"tool": "sherlock", "reason": str(exc)})

        if not hits:
            # Fallback to direct HTTP module if Sherlock binary is missing or returned 0 hits
            hits = await run_username_http_fallback(selector, investigation_id, self.db)

        return hits
