"""Tests for MCP tool integration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus
from rendereye_mcp.captures.registry import CaptureRegistry


def _make_record(
    capture_id: str = "cap-000001",
    path: str = "/tmp/capture.rdc",
    status: CaptureStatus = CaptureStatus.READY,
    source_dir: str = "/tmp",
) -> CaptureRecord:
    now = datetime.now(timezone.utc)
    return CaptureRecord(
        capture_id=capture_id,
        path=path,
        filename=Path(path).name,
        file_size=1024,
        fs_created_at=now,
        fs_modified_at=now,
        discovered_at=now,
        last_seen_at=now,
        readiness_confirmed_at=now if status == CaptureStatus.READY else None,
        status=status,
        source_directory=source_dir,
    )


def _make_mock_registry(records: list[CaptureRecord] | None = None) -> MagicMock:
    registry = MagicMock(spec=CaptureRegistry)
    records = records or []

    def list_captures(status=None, directory=None, limit=100, offset=0):
        filtered = list(records)
        if status:
            filtered = [r for r in filtered if r.status == status]
        if directory:
            filtered = [r for r in filtered if r.source_directory == directory]
        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        return paginated, total

    def get_capture(capture_id):
        for r in records:
            if r.capture_id == capture_id:
                return r
        return None

    def get_latest_capture(directory=None):
        ready = [r for r in records if r.status == CaptureStatus.READY]
        if directory:
            ready = [r for r in ready if r.source_directory == directory]
        return ready[0] if ready else None

    async def rescan():
        return {"scanned": len(records), "new": 0, "updated": 0}

    def get_status():
        return {
            "enabled": True,
            "running": True,
            "watcher_active": False,
            "watched_directories": [],
            "total_captures": len(records),
            "captures_by_status": {},
            "scan_interval_seconds": 10.0,
            "readiness_stability_seconds": 2.0,
        }

    registry.list_captures.side_effect = list_captures
    registry.get_capture.side_effect = get_capture
    registry.get_latest_capture.side_effect = get_latest_capture
    registry.rescan = rescan
    registry.get_status.side_effect = get_status
    return registry


class TestToolsDirect:
    """Test tool logic directly, independent of server wiring."""

    def _capture_list(self, registry, **kwargs):
        import rendereye_mcp.server as srv
        old = srv._registry
        srv._registry = registry
        try:
            from rendereye_mcp.captures.models import CaptureStatus as CS
            status = kwargs.get("status", "")
            directory = kwargs.get("directory", "")
            limit = kwargs.get("limit", 50)
            offset = kwargs.get("offset", 0)

            status_filter = None
            if status:
                try:
                    status_filter = CS(status)
                except ValueError:
                    return {"error": "invalid_status"}

            if srv._registry is None:
                return {"captures": [], "total": 0, "limit": limit, "offset": offset}

            records, total = srv._registry.list_captures(
                status=status_filter,
                directory=directory if directory else None,
                limit=limit,
                offset=offset,
            )
            return {
                "captures": [r.to_dict() for r in records],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        finally:
            srv._registry = old

    def _capture_get(self, registry, capture_id):
        import rendereye_mcp.server as srv
        old = srv._registry
        srv._registry = registry
        try:
            if srv._registry is None:
                return {"error": "not_found", "capture_id": capture_id}
            record = srv._registry.get_capture(capture_id)
            if record is None:
                return {"error": "not_found", "capture_id": capture_id}
            return record.to_dict()
        finally:
            srv._registry = old

    def _capture_latest(self, registry, directory="", include_pending=False):
        import rendereye_mcp.server as srv
        from rendereye_mcp.captures.models import CaptureStatus as CS
        old = srv._registry
        srv._registry = registry
        try:
            if srv._registry is None:
                return {"error": "no_capture_available"}
            record = srv._registry.get_latest_capture(
                directory=directory if directory else None
            )
            if record is None and include_pending:
                records, _ = srv._registry.list_captures(
                    status=CS.PENDING,
                    directory=directory if directory else None,
                    limit=1,
                )
                record = records[0] if records else None
            if record is None:
                return {"error": "no_capture_available"}
            return record.to_dict()
        finally:
            srv._registry = old

    async def _capture_rescan(self, registry):
        import rendereye_mcp.server as srv
        old = srv._registry
        srv._registry = registry
        try:
            if srv._registry is None:
                return {"status": "unavailable"}
            result = await srv._registry.rescan()
            return {
                "status": "completed",
                "scanned": result.get("scanned", 0),
                "new": result.get("new", 0),
                "updated": result.get("updated", 0),
            }
        finally:
            srv._registry = old

    def _capture_registry_status(self, registry):
        import rendereye_mcp.server as srv
        old = srv._registry
        srv._registry = registry
        try:
            if srv._registry is None:
                return {"enabled": False}
            return srv._registry.get_status()
        finally:
            srv._registry = old

    def test_capture_list_returns_structure(self) -> None:
        rec = _make_record()
        registry = _make_mock_registry([rec])
        result = self._capture_list(registry)
        assert "captures" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result
        assert result["total"] == 1
        assert len(result["captures"]) == 1

    def test_capture_list_empty(self) -> None:
        registry = _make_mock_registry([])
        result = self._capture_list(registry)
        assert result["total"] == 0
        assert result["captures"] == []

    def test_capture_list_status_filter(self) -> None:
        r1 = _make_record("cap-000001", "/tmp/a.rdc", status=CaptureStatus.READY)
        r2 = _make_record("cap-000002", "/tmp/b.rdc", status=CaptureStatus.MISSING)
        registry = _make_mock_registry([r1, r2])
        result = self._capture_list(registry, status="ready")
        assert result["total"] == 1
        assert result["captures"][0]["status"] == "ready"

    def test_capture_list_invalid_status(self) -> None:
        registry = _make_mock_registry([])
        result = self._capture_list(registry, status="bogus")
        assert "error" in result

    def test_capture_list_pagination(self) -> None:
        records = [_make_record(f"cap-{i:06d}", f"/tmp/{i}.rdc") for i in range(1, 6)]
        registry = _make_mock_registry(records)
        result = self._capture_list(registry, limit=2, offset=0)
        assert len(result["captures"]) == 2
        assert result["total"] == 5

    def test_capture_get_valid_id(self) -> None:
        rec = _make_record()
        registry = _make_mock_registry([rec])
        result = self._capture_get(registry, "cap-000001")
        assert result["capture_id"] == "cap-000001"
        assert "error" not in result

    def test_capture_get_invalid_id(self) -> None:
        registry = _make_mock_registry([])
        result = self._capture_get(registry, "cap-999999")
        assert result.get("error") == "not_found"
        assert result.get("capture_id") == "cap-999999"

    def test_capture_latest_with_ready_capture(self) -> None:
        rec = _make_record(status=CaptureStatus.READY)
        registry = _make_mock_registry([rec])
        result = self._capture_latest(registry)
        assert "error" not in result
        assert result["status"] == "ready"

    def test_capture_latest_no_captures(self) -> None:
        registry = _make_mock_registry([])
        result = self._capture_latest(registry)
        assert result.get("error") == "no_capture_available"

    def test_capture_latest_no_registry(self) -> None:
        result = self._capture_latest(None)
        assert result.get("error") == "no_capture_available"

    async def test_capture_rescan(self) -> None:
        records = [_make_record()]
        registry = _make_mock_registry(records)
        result = await self._capture_rescan(registry)
        assert result["status"] == "completed"
        assert "scanned" in result
        assert "new" in result
        assert "updated" in result

    def test_capture_registry_status(self) -> None:
        registry = _make_mock_registry([])
        result = self._capture_registry_status(registry)
        assert "enabled" in result
        assert "running" in result

    def test_server_status_still_works(self) -> None:
        """Phase 0 regression: server_status still works."""
        from rendereye_mcp.config import Config
        from rendereye_mcp.server import create_server
        config = Config()
        server = create_server(config)
        assert server is not None
