from backend.db.models import DatabaseManager
from backend.enumeration.base import EnumerationAdapter, Hit


class MaigretAdapter(EnumerationAdapter):
    selector_type = "username"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        self.db.log_evidence(investigation_id, "search_attempted", {"tool": "maigret", "selector": selector})
        self.db.log_evidence(investigation_id, "search_failed", {"tool": "maigret", "reason": "Maigret CLI integration not configured"})
        return []
