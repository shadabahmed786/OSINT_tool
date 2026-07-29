import asyncio
from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit
from backend.enumeration.fallback_modules import run_email_http_fallback

class HoleheAdapter(EnumerationAdapter):
    selector_type = "email"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "holehe", "selector": selector})
        hits: list[Hit] = []
        try:
            process = await asyncio.create_subprocess_exec(
                "holehe", selector, "--only-used", "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)
            for line in stdout.decode(errors="ignore").splitlines():
                if "[+]" not in line:
                    continue
                platform_name = line.replace("[+]", "").strip().split()[0] if line.strip() else "Unknown"
                hits.append(Hit(platform=platform_name, source_tool="holehe", account_status="live", confidence_tier="HIGH", confidence_score=0.85))
                self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "holehe", "platform": platform_name})
        except Exception as exc:
            self.db.log_evidence(investigation_id, "search_failed", {"tool": "holehe", "reason": str(exc)})

        if not hits:
            hits = await run_email_http_fallback(selector, investigation_id, self.db)

        return hits
