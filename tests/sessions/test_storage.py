"""Tests for SessionStorage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rendereye_mcp.sessions.models import AssociationStatus, SessionRecord, SessionStatus
from rendereye_mcp.sessions.storage import SessionStorage


def make_session(
    session_id: str = "session-000001",
    capture_id: str = "cap-000001",
    status: SessionStatus = SessionStatus.ACTIVE,
    managed: bool = True,
) -> SessionRecord:
    now = datetime.now(timezone.utc)
    return SessionRecord(
        session_id=session_id,
        capture_id=capture_id,
        capture_path="/test/cap.rdc",
        instance_id="instance-000001",
        window_id="window-000001",
        process_id=1234,
        status=status,
        managed=managed,
        protected=False,
        association_status=AssociationStatus.CONFIRMED,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )


def test_upsert_and_get(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    rec = make_session()
    storage.upsert_session(rec)
    result = storage.get_session("session-000001")
    assert result is not None
    assert result.capture_id == "cap-000001"
    storage.close()


def test_list_sessions_empty(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    records, total = storage.list_sessions()
    assert records == []
    assert total == 0
    storage.close()


def test_list_sessions_status_filter(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    storage.upsert_session(make_session("session-000001", status=SessionStatus.ACTIVE))
    storage.upsert_session(make_session("session-000002", status=SessionStatus.CLOSED))
    records, total = storage.list_sessions(status=SessionStatus.ACTIVE)
    assert len(records) == 1
    assert total == 1
    storage.close()


def test_get_next_session_id_increments(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    id1 = storage.get_next_session_id()
    id2 = storage.get_next_session_id()
    assert id1 == "session-000001"
    assert id2 == "session-000002"
    storage.close()


def test_persistence_across_reopen(tmp_path: Path):
    db = tmp_path / "test.db"
    storage1 = SessionStorage(db)
    storage1.initialize()
    storage1.upsert_session(make_session())
    storage1.close()

    storage2 = SessionStorage(db)
    storage2.initialize()
    result = storage2.get_session("session-000001")
    assert result is not None
    storage2.close()


def test_delete_session(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    storage.upsert_session(make_session())
    storage.delete_session("session-000001")
    assert storage.get_session("session-000001") is None
    storage.close()


def test_managed_only_filter(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    s1 = make_session("session-000001", managed=True)
    s2 = make_session("session-000002", managed=False)
    storage.upsert_session(s1)
    storage.upsert_session(s2)
    records, total = storage.list_sessions(managed_only=True)
    assert total == 1
    assert records[0].managed is True
    storage.close()


def test_get_nonexistent_session(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    assert storage.get_session("session-999999") is None
    storage.close()


def test_upsert_updates_existing(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    rec = make_session()
    storage.upsert_session(rec)
    rec.status = SessionStatus.CLOSED
    storage.upsert_session(rec)
    result = storage.get_session("session-000001")
    assert result is not None
    assert result.status == SessionStatus.CLOSED
    storage.close()


def test_capture_id_filter(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    storage.upsert_session(make_session("session-000001", capture_id="cap-000001"))
    storage.upsert_session(make_session("session-000002", capture_id="cap-000002"))
    records, total = storage.list_sessions(capture_id="cap-000001")
    assert total == 1
    assert records[0].capture_id == "cap-000001"
    storage.close()


def test_protected_field_persisted(tmp_path: Path):
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    rec = make_session()
    rec.protected = True
    storage.upsert_session(rec)
    result = storage.get_session("session-000001")
    assert result is not None
    assert result.protected is True
    storage.close()


def test_session_id_counter_persists(tmp_path: Path):
    db = tmp_path / "test.db"
    storage1 = SessionStorage(db)
    storage1.initialize()
    id1 = storage1.get_next_session_id()
    storage1.close()

    storage2 = SessionStorage(db)
    storage2.initialize()
    id2 = storage2.get_next_session_id()
    storage2.close()

    assert id1 == "session-000001"
    assert id2 == "session-000002"
