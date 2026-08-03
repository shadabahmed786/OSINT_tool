import asyncio
import json
import tempfile
from pathlib import Path

from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit
from backend.enumeration.fallback_modules import run_username_http_fallback


class MaigretAdapter(EnumerationAdapter):
    selector_type = "username"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "maigret", "selector": selector})
        hits: list[Hit] = []

        with tempfile.TemporaryDirectory() as out_dir:
            try:
                process = await asyncio.create_subprocess_exec(
                    "maigret", selector,
                    "--tags", "pk,global",
                    "--json", "ndjson",
                    "-o", out_dir,
                    "--timeout", "10",
                    "--no-color",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(process.communicate(), timeout=45.0)

                report_files = list(Path(out_dir).glob(f"report_{selector}*.ndjson"))
                for report_file in report_files:
                    for line in report_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        if entry.get("status") != "Claimed":
                            continue
                        platform = entry.get("sitename") or entry.get("site_name") or "Unknown"
                        url = entry.get("url_user") or entry.get("url") or ""
                        hit = Hit(
                            platform=platform,
                            source_tool="maigret",
                            bio=f"Profile URL: {url}",
                            account_status="live",
                            confidence_tier="HIGH",
                            confidence_score=0.85,
                        )
                        hits.append(hit)
                        self.db.log_evidence(investigation_id, "hit_recorded", {"tool": "maigret", "platform": platform, "url": url})
            except Exception as exc:
                self.db.log_evidence(investigation_id, "search_failed", {"tool": "maigret", "reason": str(exc)})

        if not hits:
            hits = await run_username_http_fallback(selector, investigation_id, self.db)

        return hits
