import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DatabaseManager:
    db_path: str = "./data/osint.db"

    def __post_init__(self) -> None:
        db_parent = Path(self.db_path).parent
        db_parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
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
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS selectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id TEXT REFERENCES investigations(id),
                    selector_value TEXT NOT NULL,
                    selector_type TEXT NOT NULL,
                    discovered_from_hit_id INTEGER REFERENCES hits(id),
                    approved BOOLEAN DEFAULT 0
                )
                """
            )
            cursor.execute(
                """
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
                    account_status TEXT,
                    source_tool TEXT NOT NULL,
                    screenshot_path TEXT,
                    confidence_tier TEXT,
                    confidence_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id TEXT REFERENCES investigations(id),
                    action TEXT NOT NULL,
                    detail TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_investigation_columns(cursor)
            conn.commit()

    def _ensure_investigation_columns(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("PRAGMA table_info(investigations)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        column_definitions = {
            "status": "ALTER TABLE investigations ADD COLUMN status TEXT",
            "summary": "ALTER TABLE investigations ADD COLUMN summary TEXT",
            "updated_at": "ALTER TABLE investigations ADD COLUMN updated_at TIMESTAMP",
        }
        for column_name, ddl in column_definitions.items():
            if column_name not in existing_columns:
                cursor.execute(ddl)
        if "status" in existing_columns or True:
            cursor.execute("UPDATE investigations SET status = COALESCE(status, 'running')")
        if "updated_at" in existing_columns or True:
            cursor.execute("UPDATE investigations SET updated_at = COALESCE(updated_at, created_at)")

    def log_evidence(self, investigation_id: str, action: str, detail: dict | str) -> None:
        if isinstance(detail, dict):
            detail = json.dumps(detail)
        with self.get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO evidence_log (investigation_id, action, detail) VALUES (?, ?, ?)",
                (investigation_id, action, detail),
            )
            conn.commit()

    def update_investigation_status(self, investigation_id: str, status: str, summary: str | None = None) -> None:
        with self.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE investigations SET status = ?, summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, summary or "", investigation_id),
            )
            conn.commit()

    def purge_expired_investigations(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM investigations WHERE datetime(created_at, '+' || retention_days || ' days') < datetime('now')"
            )
            expired = cursor.fetchall()
            for row in expired:
                investigation_id = row["id"]
                cursor.execute("DELETE FROM evidence_log WHERE investigation_id = ?", (investigation_id,))
                cursor.execute("DELETE FROM hits WHERE investigation_id = ?", (investigation_id,))
                cursor.execute("DELETE FROM selectors WHERE investigation_id = ?", (investigation_id,))
                cursor.execute("DELETE FROM investigations WHERE id = ?", (investigation_id,))
            conn.commit()
        return len(expired)
