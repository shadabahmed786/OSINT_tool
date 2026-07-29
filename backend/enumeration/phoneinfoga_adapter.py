import asyncio
import json
from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit
from backend.enumeration.fallback_modules import run_phone_http_fallback

class PhoneInfogaAdapter(EnumerationAdapter):
    selector_type = "phone"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "phoneinfoga", "selector": selector})
        hits: list[Hit] = []
        try:
            process = await asyncio.create_subprocess_exec(
                "phoneinfoga", "scan", "-n", selector, "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)
            data = json.loads(stdout.decode(errors="ignore") or "{}")
            if data:
                hit = Hit(
                    platform="Telecom/Carrier Registry",
                    source_tool="phoneinfoga",
                    region=data.get("country", "Unknown"),
                    bio=f"Carrier: {data.get('carrier', 'Unknown')} | Line Type: {data.get('line_type', 'N/A')}",
                    account_status="live",
                    confidence_tier="HIGH",
                    confidence_score=0.85,
                )
                self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "phoneinfoga", "data": data})
                hits.append(hit)
        except Exception as exc:
            self.db.log_evidence(investigation_id, "search_failed", {"tool": "phoneinfoga", "reason": str(exc)})

        if not hits:
            hits = await run_phone_http_fallback(selector, investigation_id, self.db)

        return hits
