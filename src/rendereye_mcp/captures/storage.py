"""SQLite-backed persistence for capture records."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus

SCHEMA_VERSION = 1

_CREATE_CAPTURES = """
CREATE TABLE IF NOT EXISTS captures (
    capture_id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    fs_created_at TEXT,
    fs_modified_at TEXT,
    discovered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    readiness_confirmed_at TEXT,
    status TEXT NOT NULL,
    selection_basis TEXT NOT NULL DEFAULT 'filesystem_modification_time',
    ordering_confidence TEXT NOT NULL DEFAULT 'heuristic',
    source_directory TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT ''
);
"""

_CREATE_REGISTRY_META = """
CREATE TABLE IF NOT EXISTS registry_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _row_to_record(row: tuple) -> CaptureRecord:
    (
        capture_id,
        path,
        filename,
        file_size,
        fs_created_at,
        fs_modified_at,
        discovered_at,
        last_seen_at,
        readiness_confirmed_at,
        status,
        selection_basis,
        ordering_confidence,
        source_directory,
        error_message,
    ) = row
    return CaptureRecord(
        capture_id=capture_id,
        path=path,
        filename=filename,
        file_size=file_size,
        fs_created_at=_parse_dt(fs_created_at),
        fs_modified_at=_parse_dt(fs_modified_at),
        discovered_at=_parse_dt(discovered_at),
        last_seen_at=_parse_dt(last_seen_at),
        readiness_confirmed_at=_parse_dt(readiness_confirmed_at),
        status=CaptureStatus(status),
        selection_basis=selection_basis,
        ordering_confidence=ordering_confidence,
        source_directory=source_directory,
        error_message=error_message,
    )


class CaptureStorage:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create tables if not exists, run migrations."""
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
            cur.executescript(_CREATE_CAPTURES + _CREATE_REGISTRY_META)
            # Initialize next_capture_id if not set
            cur.execute(
                "INSERT OR IGNORE INTO registry_meta (key, value) VALUES (?, ?)",
                ("next_capture_id", "1"),
            )
            cur.execute(
                "INSERT OR IGNORE INTO registry_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            self._conn.commit()

    def _ensure_connected(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CaptureStorage not initialized; call initialize() first")
        return self._conn

    def upsert_capture(self, record: CaptureRecord) -> None:
        conn = self._ensure_connected()
        with self._lock:
            try:
                conn.execute(
                    """
                    INSERT INTO captures (
                        capture_id, path, filename, file_size,
                        fs_created_at, fs_modified_at, discovered_at, last_seen_at,
                        readiness_confirmed_at, status, selection_basis,
                        ordering_confidence, source_directory, error_message
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(capture_id) DO UPDATE SET
                        path=excluded.path,
                        filename=excluded.filename,
                        file_size=excluded.file_size,
                        fs_created_at=excluded.fs_created_at,
                        fs_modified_at=excluded.fs_modified_at,
                        last_seen_at=excluded.last_seen_at,
                        readiness_confirmed_at=excluded.readiness_confirmed_at,
                        status=excluded.status,
                        selection_basis=excluded.selection_basis,
                        ordering_confidence=excluded.ordering_confidence,
                        source_directory=excluded.source_directory,
                        error_message=excluded.error_message
                    """,
                    (
                        record.capture_id,
                        record.path,
                        record.filename,
                        record.file_size,
                        record.fs_created_at.isoformat() if record.fs_created_at else None,
                        record.fs_modified_at.isoformat() if record.fs_modified_at else None,
                        record.discovered_at.isoformat(),
                        record.last_seen_at.isoformat(),
                        record.readiness_confirmed_at.isoformat()
                        if record.readiness_confirmed_at
                        else None,
                        record.status.value,
                        record.selection_basis,
                        record.ordering_confidence,
                        record.source_directory,
                        record.error_message,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def get_capture(self, capture_id: str) -> Optional[CaptureRecord]:
        conn = self._ensure_connected()
        with self._lock:
            cur = conn.execute(
                "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def get_capture_by_path(self, path: str) -> Optional[CaptureRecord]:
        conn = self._ensure_connected()
        with self._lock:
            cur = conn.execute(
                "SELECT * FROM captures WHERE path = ?", (path,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_captures(
        self,
        status: Optional[CaptureStatus] = None,
        directory: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CaptureRecord], int]:
        """Return (records, total_count)."""
        conn = self._ensure_connected()
        conditions = []
        params: list = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if directory is not None and directory != "":
            conditions.append("source_directory = ?")
            params.append(directory)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._lock:
            count_cur = conn.execute(
                f"SELECT COUNT(*) FROM captures {where}", params
            )
            total = count_cur.fetchone()[0]

            data_cur = conn.execute(
                f"SELECT * FROM captures {where} ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            )
            rows = data_cur.fetchall()

        records = [_row_to_record(r) for r in rows]
        return records, total

    def get_latest_capture(self, directory: Optional[str] = None) -> Optional[CaptureRecord]:
        """Return the latest READY capture ordered by fs_modified_at DESC."""
        conn = self._ensure_connected()
        conditions = ["status = ?"]
        params: list = [CaptureStatus.READY.value]

        if directory is not None and directory != "":
            conditions.append("source_directory = ?")
            params.append(directory)

        where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            cur = conn.execute(
                f"""
                SELECT * FROM captures {where}
                ORDER BY
                    fs_modified_at DESC NULLS LAST,
                    fs_created_at DESC NULLS LAST,
                    discovered_at DESC,
                    capture_id DESC
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()

        if row is None:
            return None
        return _row_to_record(row)

    def delete_capture(self, capture_id: str) -> None:
        conn = self._ensure_connected()
        with self._lock:
            conn.execute("DELETE FROM captures WHERE capture_id = ?", (capture_id,))
            conn.commit()

    def get_next_capture_id(self) -> str:
        """Return next 'cap-NNNNNN' ID (auto-increment stored in DB)."""
        conn = self._ensure_connected()
        with self._lock:
            cur = conn.execute(
                "SELECT value FROM registry_meta WHERE key = 'next_capture_id'"
            )
            row = cur.fetchone()
            n = int(row[0]) if row else 1
            new_n = n + 1
            conn.execute(
                "INSERT OR REPLACE INTO registry_meta (key, value) VALUES (?, ?)",
                ("next_capture_id", str(new_n)),
            )
            conn.commit()
        return f"cap-{n:06d}"

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
