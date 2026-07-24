import asyncio

from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit


class TheHarvesterAdapter(EnumerationAdapter):
    selector_type = "domain"
    FREE_SOURCES = ["duckduckgo", "crtsh", "dnsdumpster", "baidu", "hackertarget"]

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "theharvester", "sources": self.FREE_SOURCES})
        try:
            process = await asyncio.create_subprocess_exec(
                "theHarvester", "-d", selector, "-b", ",".join(self.FREE_SOURCES),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60.0)
        except Exception as exc:
            self.db.log_evidence(investigation_id, "search_failed", {"tool": "theharvester", "reason": str(exc)})
            return []

        hits: list[Hit] = []
        for line in stdout.decode(errors="ignore").splitlines():
            if "@" not in line or "." not in line:
                continue
            email_found = line.strip()
            hits.append(Hit(platform="Domain Recon", source_tool="theharvester", bio=f"Harvested Email: {email_found}", confidence_tier="high", confidence_score=0.80))
            self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "theharvester", "harvested": email_found})
        return hits
