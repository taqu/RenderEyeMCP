"""SQLite storage for session records. Reuses the same DB file as captures."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import AssociationStatus, SessionRecord, SessionStatus

SESSION_SCHEMA_VERSION = 1

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    capture_path TEXT NOT NULL,
    instance_id TEXT,
    window_id TEXT,
    process_id INTEGER,
    status TEXT NOT NULL,
    managed INTEGER NOT NULL DEFAULT 1,
    protected INTEGER NOT NULL DEFAULT 0,
    association_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);
"""


def _parse_dt(val: Optional[str]) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def _row_to_record(row: tuple) -> SessionRecord:
    (
        session_id,
        capture_id,
        capture_path,
        instance_id,
        window_id,
        process_id,
        status,
        managed,
        protected,
        association_status,
        created_at,
        updated_at,
        last_activity_at,
        error_message,
    ) = row
    return SessionRecord(
        session_id=session_id,
        capture_id=capture_id,
        capture_path=capture_path,
        instance_id=instance_id,
        window_id=window_id,
        process_id=process_id,
        status=SessionStatus(status),
        managed=bool(managed),
        protected=bool(protected),
        association_status=AssociationStatus(association_status),
        created_at=_parse_dt(created_at),
        updated_at=_parse_dt(updated_at),
        last_activity_at=_parse_dt(last_activity_at),
        error_message=error_message or "",
    )


class SessionStorage:
    def __init__(self, db_path: Path):
        """Reuse the same SQLite file as CaptureStorage. Thread-safe."""
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create sessions table if not exists; initialize session counter."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = None
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(_CREATE_SESSIONS)
            # Also create registry_meta if not present (may be separate DB in tests)
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS registry_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            cur.execute(
                "INSERT OR IGNORE INTO registry_meta (key, value) VALUES (?, ?)",
                ("next_session_id", "1"),
            )
            self._conn.commit()

    def _ensure_connected(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SessionStorage not initialized; call initialize() first")
        return self._conn

    def upsert_session(self, record: SessionRecord) -> None:
        conn = self._ensure_connected()
        with self._lock:
            try:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, capture_id, capture_path, instance_id, window_id,
                        process_id, status, managed, protected, association_status,
                        created_at, updated_at, last_activity_at, error_message
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        capture_id=excluded.capture_id,
                        capture_path=excluded.capture_path,
                        instance_id=excluded.instance_id,
                        window_id=excluded.window_id,
                        process_id=excluded.process_id,
                        status=excluded.status,
                        managed=excluded.managed,
                        protected=excluded.protected,
                        association_status=excluded.association_status,
                        updated_at=excluded.updated_at,
                        last_activity_at=excluded.last_activity_at,
                        error_message=excluded.error_message
                    """,
                    (
                        record.session_id,
                        record.capture_id,
                        record.capture_path,
                        record.instance_id,
                        record.window_id,
                        record.process_id,
                        record.status.value,
                        1 if record.managed else 0,
                        1 if record.protected else 0,
                        record.association_status.value,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                        record.last_activity_at.isoformat(),
                        record.error_message,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        conn = self._ensure_connected()
        with self._lock:
            cur = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_sessions(
        self,
        status: Optional[SessionStatus] = None,
        managed_only: bool = False,
        capture_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SessionRecord], int]:
        """Return (records, total_count)."""
        conn = self._ensure_connected()
        conditions: list[str] = []
        params: list = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if managed_only:
            conditions.append("managed = 1")
        if capture_id is not None:
            conditions.append("capture_id = ?")
            params.append(capture_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._lock:
            count_cur = conn.execute(f"SELECT COUNT(*) FROM sessions {where}", params)
            total = count_cur.fetchone()[0]

            data_cur = conn.execute(
                f"SELECT * FROM sessions {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            )
            rows = data_cur.fetchall()

        records = [_row_to_record(r) for r in rows]
        return records, total

    def delete_session(self, session_id: str) -> None:
        conn = self._ensure_connected()
        with self._lock:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    def get_next_session_id(self) -> str:
        """Return next 'session-NNNNNN' ID (auto-increment stored in DB)."""
        conn = self._ensure_connected()
        with self._lock:
            cur = conn.execute(
                "SELECT value FROM registry_meta WHERE key = 'next_session_id'"
            )
            row = cur.fetchone()
            n = int(row[0]) if row else 1
            new_n = n + 1
            conn.execute(
                "INSERT OR REPLACE INTO registry_meta (key, value) VALUES (?, ?)",
                ("next_session_id", str(new_n)),
            )
            conn.commit()
        return f"session-{n:06d}"

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
