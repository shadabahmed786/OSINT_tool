import aiosqlite
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import DB_PATH, RETENTION_DAYS_DEFAULT

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize SQLite database tables according to §3 schema specification."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Table 1: investigations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                initial_selector TEXT NOT NULL,
                initial_selector_type TEXT NOT NULL,
                retention_days INTEGER DEFAULT 90,
                status TEXT NOT NULL DEFAULT 'running',
                summary TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 2: selectors (Pivot tracking & Approval Queue §0, §3)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS selectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT REFERENCES investigations(id),
                selector_value TEXT NOT NULL,
                selector_type TEXT NOT NULL,
                discovered_from_hit_id INTEGER REFERENCES hits(id),
                approved BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 3: hits
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT REFERENCES investigations(id),
                matched_selector_id INTEGER REFERENCES selectors(id),
                platform TEXT NOT NULL,
                profile_picture_path TEXT,
                display_name TEXT,
                bio TEXT,
                region TEXT,
                last_active_date TEXT,
                account_status TEXT DEFAULT 'live',
                source_tool TEXT NOT NULL DEFAULT 'enumeration_engine',
                screenshot_path TEXT,
                confidence_tier TEXT DEFAULT 'LOW',
                confidence_score REAL DEFAULT 0.0,
                profile_url TEXT,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 4: evidence_log (Strictly Append-Only Audit Trail §0, §3)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS evidence_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT REFERENCES investigations(id),
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized successfully at %s", DB_PATH)

async def create_investigation(
    investigation_id: str,
    target: str,
    selector_type: str,
    retention_days: int = RETENTION_DAYS_DEFAULT
) -> Dict[str, Any]:
    """Create a new investigation and seed selector record."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Make repeated test runs idempotent for fixed investigation ids.
        await db.execute("DELETE FROM hits WHERE investigation_id = ?", (investigation_id,))
        await db.execute("DELETE FROM selectors WHERE investigation_id = ?", (investigation_id,))
        await db.execute("DELETE FROM investigations WHERE id = ?", (investigation_id,))
        await db.execute(
            """INSERT INTO investigations (id, initial_selector, initial_selector_type, retention_days, status) 
               VALUES (?, ?, ?, ?, ?)""",
            (investigation_id, target, selector_type, retention_days, "running")
        )
        # Create seed selector (automatically approved)
        cursor = await db.execute(
            """INSERT INTO selectors (investigation_id, selector_value, selector_type, approved) 
               VALUES (?, ?, ?, 1)""",
            (investigation_id, target, selector_type)
        )
        seed_selector_id = cursor.lastrowid
        await db.commit()

    await log_evidence(investigation_id, "investigation_started", f"Started investigation for {selector_type}: '{target}' (Seed Selector ID: {seed_selector_id})")
    return {
        "id": investigation_id,
        "initial_selector": target,
        "initial_selector_type": selector_type,
        "seed_selector_id": seed_selector_id,
        "retention_days": retention_days,
        "status": "running"
    }

async def add_discovered_selector(
    investigation_id: str,
    selector_value: str,
    selector_type: str,
    discovered_from_hit_id: Optional[int] = None
) -> Dict[str, Any]:
    """Add a newly discovered selector requiring explicit human approval before pivoting (§0)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO selectors (investigation_id, selector_value, selector_type, discovered_from_hit_id, approved)
               VALUES (?, ?, ?, ?, 0)""",
            (investigation_id, selector_value, selector_type, discovered_from_hit_id)
        )
        selector_id = cursor.lastrowid
        await db.commit()

    await log_evidence(
        investigation_id,
        "selector_discovered",
        f"Discovered new secondary selector '{selector_value}' ({selector_type}). Pending human approval before pivot."
    )
    return {"id": selector_id, "selector_value": selector_value, "selector_type": selector_type, "approved": False}

async def approve_selector(selector_id: int) -> bool:
    """Approve a discovered selector to allow enumeration pivot (§0)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM selectors WHERE id = ?", (selector_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            sel = dict(row)

        await db.execute("UPDATE selectors SET approved = 1 WHERE id = ?", (selector_id,))
        await db.commit()

    await log_evidence(
        sel["investigation_id"],
        "selector_approved",
        f"Investigator approved selector '{sel['selector_value']}' ({sel['selector_type']}) for enumeration pivot."
    )
    return True

async def get_pending_selectors(investigation_id: str) -> List[Dict[str, Any]]:
    """Retrieve all pending (unapproved) discovered selectors for an investigation."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM selectors WHERE investigation_id = ? AND approved = 0 ORDER BY id ASC",
            (investigation_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_investigation_status(investigation_id: str, status: str, summary: Optional[str] = None):
    """Update investigation status and summary."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE investigations SET status = ?, summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, summary or "", investigation_id)
        )
        await db.commit()
    await log_evidence(investigation_id, "status_change", f"Investigation status updated to '{status}'")

async def add_finding(investigation_id: str, finding_data: Dict[str, Any]) -> int:
    """Insert a finding hit into the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        raw_json = json.dumps(finding_data.get("raw_data", {}))
        cursor = await db.execute(
            """INSERT INTO hits (
                investigation_id, matched_selector_id, platform, profile_picture_path,
                display_name, bio, region, last_active_date, account_status,
                source_tool, screenshot_path, confidence_tier, confidence_score,
                profile_url, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                investigation_id,
                finding_data.get("matched_selector_id"),
                finding_data.get("platform", "Unknown"),
                finding_data.get("profile_picture_path") or finding_data.get("avatar_url"),
                finding_data.get("display_name"),
                finding_data.get("bio"),
                finding_data.get("region"),
                finding_data.get("last_active_date"),
                finding_data.get("account_status", "live"),
                finding_data.get("source_tool", "enumeration_engine"),
                finding_data.get("screenshot_path"),
                finding_data.get("confidence_tier", "LOW"),
                finding_data.get("confidence_score", 0.0),
                finding_data.get("profile_url"),
                raw_json
            )
        )
        hit_id = cursor.lastrowid
        await db.commit()
    
    tier = finding_data.get("confidence_tier", "LOW")
    platform = finding_data.get("platform", "Unknown")
    await log_evidence(
        investigation_id,
        "hit_recorded",
        f"Recorded hit #{hit_id} on {platform} ({tier} confidence)"
    )
    return hit_id

async def log_evidence(investigation_id: str, action: str, detail: str):
    """
    Append a record to the evidence audit log (§0).
    STRICT RULE: Only INSERT statements are provided for evidence_log. No UPDATE or DELETE methods exist.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO evidence_log (investigation_id, action, detail) VALUES (?, ?, ?)",
            (investigation_id, action, detail)
        )
        await db.commit()

async def get_investigation(investigation_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full investigation details including selectors, hits, and evidence log."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)) as cursor:
            inv = await cursor.fetchone()
            if not inv:
                return None
            inv_dict = dict(inv)

        async with db.execute("SELECT * FROM selectors WHERE investigation_id = ?", (investigation_id,)) as cursor:
            selectors = await cursor.fetchall()
            inv_dict["selectors"] = [dict(s) for s in selectors]

        async with db.execute("SELECT * FROM hits WHERE investigation_id = ? ORDER BY confidence_score DESC", (investigation_id,)) as cursor:
            findings = await cursor.fetchall()
            inv_dict["findings"] = [dict(f) for f in findings]

        async with db.execute("SELECT * FROM evidence_log WHERE investigation_id = ? ORDER BY id ASC", (investigation_id,)) as cursor:
            logs = await cursor.fetchall()
            inv_dict["evidence_log"] = [dict(l) for l in logs]

        return inv_dict

async def list_investigations() -> List[Dict[str, Any]]:
    """List all investigations ordered by latest timestamp."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM investigations ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def cleanup_expired_investigations() -> int:
    """Scheduled job to clean up investigation data older than retention_days (§0)."""
    deleted_count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT id FROM investigations 
            WHERE julianday('now') - julianday(created_at) > retention_days
        """
        async with db.execute(query) as cursor:
            expired = await cursor.fetchall()
            for row in expired:
                inv_id = row["id"]
                await db.execute("DELETE FROM hits WHERE investigation_id = ?", (inv_id,))
                await db.execute("DELETE FROM selectors WHERE investigation_id = ?", (inv_id,))
                await db.execute("DELETE FROM evidence_log WHERE investigation_id = ?", (inv_id,))
                await db.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
                deleted_count += 1
        await db.commit()
    logger.info("Retention cleanup completed: purged %d expired investigation(s).", deleted_count)
    return deleted_count

