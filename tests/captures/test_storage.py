"""Tests for CaptureStorage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus
from rendereye_mcp.captures.storage import CaptureStorage


def _make_record(
    capture_id: str = "cap-000001",
    path: str = "/tmp/capture.rdc",
    status: CaptureStatus = CaptureStatus.READY,
    source_dir: str = "/tmp",
    fs_modified_at: datetime | None = None,
) -> CaptureRecord:
    now = datetime.now(timezone.utc)
    return CaptureRecord(
        capture_id=capture_id,
        path=path,
        filename=Path(path).name,
        file_size=1024,
        fs_created_at=now,
        fs_modified_at=fs_modified_at or now,
        discovered_at=now,
        last_seen_at=now,
        readiness_confirmed_at=now if status == CaptureStatus.READY else None,
        status=status,
        source_directory=source_dir,
    )


@pytest.fixture()
def storage(tmp_path: Path) -> CaptureStorage:
    db = tmp_path / "test.db"
    s = CaptureStorage(db)
    s.initialize()
    yield s
    s.close()


class TestCaptureStorageInit:
    def test_creates_tables(self, tmp_path: Path) -> None:
        db = tmp_path / "init.db"
        s = CaptureStorage(db)
        s.initialize()
        assert db.exists()
        # Verify tables exist
        import sqlite3
        conn = sqlite3.connect(str(db))
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        s.close()
        assert "captures" in tables
        assert "registry_meta" in tables

    def test_double_initialize_ok(self, tmp_path: Path) -> None:
        db = tmp_path / "double.db"
        s = CaptureStorage(db)
        s.initialize()
        s.initialize()  # Should not raise
        s.close()


class TestUpsertAndGet:
    def test_upsert_and_get_roundtrip(self, storage: CaptureStorage) -> None:
        rec = _make_record()
        storage.upsert_capture(rec)
        retrieved = storage.get_capture("cap-000001")
        assert retrieved is not None
        assert retrieved.capture_id == "cap-000001"
        assert retrieved.path == "/tmp/capture.rdc"
        assert retrieved.status == CaptureStatus.READY

    def test_upsert_updates_existing(self, storage: CaptureStorage) -> None:
        rec = _make_record()
        storage.upsert_capture(rec)
        rec.status = CaptureStatus.MISSING
        rec.file_size = 2048
        storage.upsert_capture(rec)
        retrieved = storage.get_capture("cap-000001")
        assert retrieved.status == CaptureStatus.MISSING
        assert retrieved.file_size == 2048

    def test_get_nonexistent(self, storage: CaptureStorage) -> None:
        result = storage.get_capture("cap-999999")
        assert result is None

    def test_get_by_path(self, storage: CaptureStorage) -> None:
        rec = _make_record()
        storage.upsert_capture(rec)
        retrieved = storage.get_capture_by_path("/tmp/capture.rdc")
        assert retrieved is not None
        assert retrieved.capture_id == "cap-000001"

    def test_get_by_path_nonexistent(self, storage: CaptureStorage) -> None:
        result = storage.get_capture_by_path("/nonexistent/file.rdc")
        assert result is None

    def test_datetime_roundtrip(self, storage: CaptureStorage) -> None:
        rec = _make_record()
        storage.upsert_capture(rec)
        retrieved = storage.get_capture("cap-000001")
        assert retrieved.discovered_at is not None
        assert retrieved.discovered_at.tzinfo is not None
        assert retrieved.readiness_confirmed_at is not None


class TestListCaptures:
    def test_list_no_filter(self, storage: CaptureStorage) -> None:
        storage.upsert_capture(_make_record("cap-000001", "/tmp/a.rdc"))
        storage.upsert_capture(_make_record("cap-000002", "/tmp/b.rdc"))
        records, total = storage.list_captures()
        assert total == 2
        assert len(records) == 2

    def test_list_filter_by_status(self, storage: CaptureStorage) -> None:
        storage.upsert_capture(_make_record("cap-000001", "/tmp/a.rdc", status=CaptureStatus.READY))
        storage.upsert_capture(_make_record("cap-000002", "/tmp/b.rdc", status=CaptureStatus.MISSING))
        records, total = storage.list_captures(status=CaptureStatus.READY)
        assert total == 1
        assert records[0].status == CaptureStatus.READY

    def test_list_filter_by_directory(self, storage: CaptureStorage) -> None:
        storage.upsert_capture(_make_record("cap-000001", "/dir1/a.rdc", source_dir="/dir1"))
        storage.upsert_capture(_make_record("cap-000002", "/dir2/b.rdc", source_dir="/dir2"))
        records, total = storage.list_captures(directory="/dir1")
        assert total == 1
        assert records[0].source_directory == "/dir1"

    def test_list_pagination(self, storage: CaptureStorage) -> None:
        for i in range(1, 6):
            storage.upsert_capture(_make_record(f"cap-{i:06d}", f"/tmp/{i}.rdc"))
        records, total = storage.list_captures(limit=2, offset=0)
        assert total == 5
        assert len(records) == 2

        records2, total2 = storage.list_captures(limit=2, offset=2)
        assert total2 == 5
        assert len(records2) == 2

        records3, total3 = storage.list_captures(limit=2, offset=4)
        assert total3 == 5
        assert len(records3) == 1

    def test_list_total_count_correct(self, storage: CaptureStorage) -> None:
        for i in range(1, 11):
            storage.upsert_capture(_make_record(f"cap-{i:06d}", f"/tmp/{i}.rdc"))
        _, total = storage.list_captures(limit=3)
        assert total == 10


class TestGetLatestCapture:
    def test_returns_most_recent_ready(self, storage: CaptureStorage) -> None:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        old = _make_record("cap-000001", "/tmp/old.rdc", fs_modified_at=now - timedelta(hours=1))
        new = _make_record("cap-000002", "/tmp/new.rdc", fs_modified_at=now)
        storage.upsert_capture(old)
        storage.upsert_capture(new)
        latest = storage.get_latest_capture()
        assert latest is not None
        assert latest.capture_id == "cap-000002"

    def test_directory_filter(self, storage: CaptureStorage) -> None:
        r1 = _make_record("cap-000001", "/dir1/a.rdc", source_dir="/dir1")
        r2 = _make_record("cap-000002", "/dir2/b.rdc", source_dir="/dir2")
        storage.upsert_capture(r1)
        storage.upsert_capture(r2)
        latest = storage.get_latest_capture(directory="/dir2")
        assert latest is not None
        assert latest.source_directory == "/dir2"

    def test_no_ready_captures_returns_none(self, storage: CaptureStorage) -> None:
        rec = _make_record(status=CaptureStatus.PENDING)
        storage.upsert_capture(rec)
        latest = storage.get_latest_capture()
        assert latest is None

    def test_empty_storage_returns_none(self, storage: CaptureStorage) -> None:
        latest = storage.get_latest_capture()
        assert latest is None


class TestDeleteCapture:
    def test_delete(self, storage: CaptureStorage) -> None:
        rec = _make_record()
        storage.upsert_capture(rec)
        storage.delete_capture("cap-000001")
        assert storage.get_capture("cap-000001") is None

    def test_delete_nonexistent_no_error(self, storage: CaptureStorage) -> None:
        storage.delete_capture("cap-999999")  # Should not raise


class TestGetNextCaptureId:
    def test_increments_correctly(self, storage: CaptureStorage) -> None:
        id1 = storage.get_next_capture_id()
        id2 = storage.get_next_capture_id()
        id3 = storage.get_next_capture_id()
        assert id1 == "cap-000001"
        assert id2 == "cap-000002"
        assert id3 == "cap-000003"

    def test_persists_across_reopen(self, tmp_path: Path) -> None:
        db = tmp_path / "persist.db"
        s1 = CaptureStorage(db)
        s1.initialize()
        id1 = s1.get_next_capture_id()
        id2 = s1.get_next_capture_id()
        s1.close()

        s2 = CaptureStorage(db)
        s2.initialize()
        id3 = s2.get_next_capture_id()
        s2.close()

        assert id1 == "cap-000001"
        assert id2 == "cap-000002"
        assert id3 == "cap-000003"


class TestReopenPreservesData:
    def test_data_persists(self, tmp_path: Path) -> None:
        db = tmp_path / "persist.db"
        s1 = CaptureStorage(db)
        s1.initialize()
        rec = _make_record()
        s1.upsert_capture(rec)
        s1.close()

        s2 = CaptureStorage(db)
        s2.initialize()
        retrieved = s2.get_capture("cap-000001")
        s2.close()

        assert retrieved is not None
        assert retrieved.capture_id == "cap-000001"
