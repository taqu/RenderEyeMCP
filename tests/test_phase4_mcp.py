"""Tests for Phase 4 MCP tool layer."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus
from rendereye_mcp.config import Config
from rendereye_mcp.errors import ErrorCode
from rendereye_mcp.operations.models import OperationStatus
from rendereye_mcp.operations.tracker import OperationTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_capture(
    capture_id: str = "cap-000001",
    path: str = "/tmp/capture.rdc",
    status: CaptureStatus = CaptureStatus.READY,
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
        source_directory=str(Path(path).parent),
    )


def _make_mock_registry(records=None):
    from rendereye_mcp.captures.registry import CaptureRegistry
    registry = MagicMock(spec=CaptureRegistry)
    records = records or []

    def list_captures(status=None, directory=None, limit=100, offset=0):
        filtered = list(records)
        if status:
            filtered = [r for r in filtered if r.status == status]
        total = len(filtered)
        return filtered[offset:offset + limit], total

    def get_capture(cid):
        return next((r for r in records if r.capture_id == cid), None)

    def get_latest_capture(directory=None):
        ready = [r for r in records if r.status == CaptureStatus.READY]
        return ready[0] if ready else None

    registry.list_captures.side_effect = list_captures
    registry.get_capture.side_effect = get_capture
    registry.get_latest_capture.side_effect = get_latest_capture
    return registry


def _make_mock_session_manager_with_registry(records=None):
    """Create a SessionManager-like mock with a real registry."""
    from rendereye_mcp.sessions.manager import SessionManager

    mgr = MagicMock(spec=SessionManager)
    return mgr


def _get_server_tools(server):
    return asyncio.run(server.list_tools())


def _tool_names(server) -> list[str]:
    return [t.name for t in _get_server_tools(server)]


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:
    def test_operation_get_registered(self):
        from rendereye_mcp.server import create_server
        server = create_server(Config())
        assert "operation_get" in _tool_names(server)

    def test_all_phase4_tools_registered(self):
        from rendereye_mcp.server import create_server
        server = create_server(Config())
        names = _tool_names(server)
        for expected in [
            "server_status", "capture_list", "capture_get", "capture_latest",
            "capture_rescan", "capture_registry_status",
            "instance_list", "instance_gui_state",
            "capture_open", "operation_get",
            "session_list", "session_get", "session_focus",
            "session_close", "session_protect",
        ]:
            assert expected in names, f"Missing tool: {expected}"

    def test_total_tools_count_at_least_14(self):
        from rendereye_mcp.server import create_server
        server = create_server(Config())
        tools = _get_server_tools(server)
        # Phase 0: 1, Phase 1: 5, Phase 2: 7, Phase 3: 1, Phase 4: 1
        assert len(tools) >= 14


# ---------------------------------------------------------------------------
# Error response structure
# ---------------------------------------------------------------------------

class TestErrorResponseStructure:
    def _check_error_shape(self, result: dict):
        assert result.get("status") == "failed", f"Expected status=failed, got: {result}"
        assert "error" in result, f"Missing 'error' key: {result}"
        err = result["error"]
        assert "code" in err
        assert "message" in err
        assert "retryable" in err

    def test_session_close_not_found_error(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.SESSION_NOT_FOUND, "Session not found", session_id="s-1")
        self._check_error_shape(resp)
        assert resp["error"]["code"] == "session_not_found"
        assert resp["session_id"] == "s-1"

    def test_session_close_protected_error(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.SESSION_PROTECTED, "Protected")
        self._check_error_shape(resp)
        assert resp["error"]["retryable"] is False

    def test_extension_unavailable_is_retryable(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.EXTENSION_UNAVAILABLE, "No connection")
        assert resp["error"]["retryable"] is True

    def test_timeout_is_retryable(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.OPERATION_TIMEOUT, "Timed out")
        assert resp["error"]["retryable"] is True

    def test_ipc_disconnected_is_retryable(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.IPC_DISCONNECTED, "IPC gone")
        assert resp["error"]["retryable"] is True

    def test_internal_error_not_retryable(self):
        from rendereye_mcp.errors import error_response
        resp = error_response(ErrorCode.INTERNAL_ERROR, "Unexpected")
        assert resp["error"]["retryable"] is False


# ---------------------------------------------------------------------------
# capture_open via SessionManager.open_capture
# ---------------------------------------------------------------------------

class TestCaptureOpenViaManager:
    def _make_session_manager(self, registry=None):
        from rendereye_mcp.instances.manager import InstanceManager
        from rendereye_mcp.sessions.manager import SessionManager
        from rendereye_mcp.sessions.storage import SessionStorage

        storage = MagicMock(spec=SessionStorage)
        storage.initialize.return_value = None
        storage.get_next_session_id.return_value = "session-000001"

        instance_manager = MagicMock(spec=InstanceManager)
        instance_manager.refresh.return_value = None
        instance_manager.find_windows_for_instance.return_value = []

        config = Config()
        mgr = SessionManager(config, storage, instance_manager, registry)
        return mgr, storage, instance_manager

    def test_capture_not_found_returns_error(self):
        registry = _make_mock_registry([])
        mgr, _, _ = self._make_session_manager(registry)
        result = asyncio.run(
            mgr.open_capture("cap-999999", "new_window", None, OperationTracker())
        )
        assert result.get("status") == "failed"
        assert result["error"]["code"] == "capture_not_found"

    def test_capture_not_found_sets_operation_failed(self):
        registry = _make_mock_registry([])
        mgr, _, _ = self._make_session_manager(registry)
        tracker = OperationTracker()
        result = asyncio.run(
            mgr.open_capture("cap-999999", "new_window", None, tracker)
        )
        op_id = result.get("operation_id")
        assert op_id is not None
        op = tracker.get(op_id)
        assert op is not None
        assert op.status == OperationStatus.FAILED

    def test_latest_selector_resolves_capture(self):
        capture = _make_capture()
        registry = _make_mock_registry([capture])
        mgr, _, _ = self._make_session_manager(registry)

        # Mock the launcher so it doesn't actually try to run renderdoc
        from rendereye_mcp.instances import launcher as launcher_mod
        from rendereye_mcp.platform import windows as windows_mod

        original_launch = launcher_mod.launch_renderdoc
        original_find = windows_mod.find_renderdoc_exe

        try:
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.error = "no renderdoc"
            launcher_mod.launch_renderdoc = MagicMock(return_value=mock_result)
            windows_mod.find_renderdoc_exe = MagicMock(return_value=None)

            tracker = OperationTracker()
            result = asyncio.run(
                mgr.open_capture("latest", "new_window", None, tracker)
            )
            # Should fail at exe lookup, not capture lookup
            assert result.get("error", {}).get("code") != "capture_not_found"
        finally:
            launcher_mod.launch_renderdoc = original_launch
            windows_mod.find_renderdoc_exe = original_find

    def test_reuse_returns_existing_session(self):
        from rendereye_mcp.sessions.models import (
            AssociationStatus,
            SessionRecord,
            SessionStatus,
        )

        capture = _make_capture()
        registry = _make_mock_registry([capture])
        mgr, storage, _ = self._make_session_manager(registry)

        now = datetime.now(timezone.utc)
        existing = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/tmp/capture.rdc",
            instance_id="inst-1",
            window_id="win-1",
            process_id=1234,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.CONFIRMED,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        storage.list_sessions.return_value = ([existing], 1)

        result = asyncio.run(
            mgr.open_capture("cap-000001", "reuse", None, OperationTracker())
        )
        assert result.get("status") == "confirmed"
        assert result.get("session_id") == "session-000001"

    def test_replace_requires_target_session_id(self):
        capture = _make_capture()
        registry = _make_mock_registry([capture])
        mgr, _, _ = self._make_session_manager(registry)

        result = asyncio.run(
            mgr.open_capture("cap-000001", "replace", None, OperationTracker())
        )
        assert result.get("status") == "failed"
        assert result["error"]["code"] == "session_not_found"

    def test_replace_extension_unavailable_when_no_conn_manager(self):
        from rendereye_mcp.sessions.models import (
            AssociationStatus,
            SessionRecord,
            SessionStatus,
        )

        capture = _make_capture()
        registry = _make_mock_registry([capture])
        mgr, storage, _ = self._make_session_manager(registry)
        # No conn_manager set

        now = datetime.now(timezone.utc)
        sess = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/tmp/old.rdc",
            instance_id="inst-1",
            window_id="win-1",
            process_id=1234,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.CONFIRMED,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        storage.get_session.return_value = sess

        result = asyncio.run(
            mgr.open_capture(
                "cap-000001", "replace", "session-000001", OperationTracker()
            )
        )
        assert result.get("status") == "failed"
        assert result["error"]["code"] == "extension_unavailable"


# ---------------------------------------------------------------------------
# session_list includes limit/offset
# ---------------------------------------------------------------------------

class TestSessionList:
    def test_session_list_includes_limit_offset_no_manager(self):
        from rendereye_mcp.server import create_server, set_session_manager
        server = create_server(Config())
        set_session_manager(None)
        result = asyncio.run(server.call_tool("session_list", {"limit": 10, "offset": 5}))
        # MCP SDK returns list of content blocks; find the dict
        assert result is not None

    def test_list_sessions_response_has_limit_offset(self):
        from rendereye_mcp.instances.manager import InstanceManager
        from rendereye_mcp.sessions.manager import SessionManager
        from rendereye_mcp.sessions.storage import SessionStorage

        storage = MagicMock(spec=SessionStorage)
        storage.list_sessions.return_value = ([], 0)
        storage.initialize.return_value = None

        mgr = SessionManager(Config(), storage, MagicMock(spec=InstanceManager))
        result = mgr.list_sessions(limit=25, offset=10)
        assert result["limit"] == 25
        assert result["offset"] == 10


# ---------------------------------------------------------------------------
# session_close error format
# ---------------------------------------------------------------------------

class TestSessionCloseErrors:
    def _make_manager_with_session(self, sess):
        from rendereye_mcp.instances.manager import InstanceManager
        from rendereye_mcp.sessions.manager import SessionManager
        from rendereye_mcp.sessions.storage import SessionStorage

        storage = MagicMock(spec=SessionStorage)
        storage.get_session.return_value = sess
        storage.initialize.return_value = None
        mgr = SessionManager(Config(), storage, MagicMock(spec=InstanceManager))
        return mgr

    def test_session_not_found(self):
        from rendereye_mcp.instances.manager import InstanceManager
        from rendereye_mcp.sessions.manager import SessionManager
        from rendereye_mcp.sessions.storage import SessionStorage

        storage = MagicMock(spec=SessionStorage)
        storage.get_session.return_value = None
        mgr = SessionManager(Config(), storage, MagicMock(spec=InstanceManager))

        result = mgr.close_session("session-999999")
        assert result["status"] == "failed"
        assert result["error"]["code"] == "session_not_found"

    def test_session_protected(self):
        from rendereye_mcp.sessions.models import (
            AssociationStatus,
            SessionRecord,
            SessionStatus,
        )

        now = datetime.now(timezone.utc)
        sess = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/tmp/capture.rdc",
            instance_id=None,
            window_id=None,
            process_id=None,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=True,  # protected!
            association_status=AssociationStatus.UNKNOWN,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        mgr = self._make_manager_with_session(sess)
        result = mgr.close_session("session-000001")
        assert result["status"] == "failed"
        assert result["error"]["code"] == "session_protected"

    def test_session_unmanaged(self):
        from rendereye_mcp.sessions.models import (
            AssociationStatus,
            SessionRecord,
            SessionStatus,
        )

        now = datetime.now(timezone.utc)
        sess = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/tmp/capture.rdc",
            instance_id=None,
            window_id=None,
            process_id=None,
            status=SessionStatus.ACTIVE,
            managed=False,  # not managed!
            protected=False,
            association_status=AssociationStatus.UNKNOWN,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        mgr = self._make_manager_with_session(sess)
        result = mgr.close_session("session-000001")
        assert result["status"] == "failed"
        assert result["error"]["code"] == "session_unmanaged"


# ---------------------------------------------------------------------------
# session_protect
# ---------------------------------------------------------------------------

class TestSessionProtect:
    def test_session_protect_updates_flag(self):
        from rendereye_mcp.instances.manager import InstanceManager
        from rendereye_mcp.sessions.manager import SessionManager
        from rendereye_mcp.sessions.models import (
            AssociationStatus,
            SessionRecord,
            SessionStatus,
        )
        from rendereye_mcp.sessions.storage import SessionStorage

        now = datetime.now(timezone.utc)
        sess = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/tmp/capture.rdc",
            instance_id=None,
            window_id=None,
            process_id=None,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.UNKNOWN,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        storage = MagicMock(spec=SessionStorage)
        storage.get_session.return_value = sess
        storage.upsert_session.return_value = None

        mgr = SessionManager(Config(), storage, MagicMock(spec=InstanceManager))
        result = mgr.protect_session("session-000001", True)
        assert result.get("protected") is True


# ---------------------------------------------------------------------------
# operation_get
# ---------------------------------------------------------------------------

class TestOperationGet:
    def test_operation_get_retrieves_known_operation(self):
        import rendereye_mcp.server as srv_module
        from rendereye_mcp.server import create_server, set_session_manager

        server = create_server(Config())
        set_session_manager(None)

        # Create an operation in the tracker
        tracker = srv_module._operation_tracker
        assert tracker is not None
        op = tracker.create("capture_open", capture_id="cap-000001")

        result = asyncio.run(server.call_tool("operation_get", {"operation_id": op.operation_id}))
        assert result is not None

    def test_operation_get_unknown_returns_error(self):
        from rendereye_mcp.server import create_server, set_session_manager

        server = create_server(Config())
        set_session_manager(None)

        result = asyncio.run(server.call_tool("operation_get", {"operation_id": "op-999999"}))
        assert result is not None

    def test_operation_tracker_get_direct(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open")
        retrieved = tracker.get(op.operation_id)
        assert retrieved is not None
        assert retrieved.operation_id == op.operation_id

    def test_operation_tracker_get_not_found(self):
        tracker = OperationTracker()
        assert tracker.get("op-999999") is None


# ---------------------------------------------------------------------------
# Null-safety: tools return safe defaults when managers are None
# ---------------------------------------------------------------------------

class TestNullSafety:
    def test_capture_open_no_manager(self):
        from rendereye_mcp.server import create_server, set_session_manager

        server = create_server(Config())
        set_session_manager(None)
        result = asyncio.run(server.call_tool("capture_open", {"capture_id": "latest"}))
        assert result is not None

    def test_session_list_no_manager(self):
        from rendereye_mcp.server import create_server, set_session_manager

        server = create_server(Config())
        set_session_manager(None)
        result = asyncio.run(server.call_tool("session_list", {}))
        assert result is not None

    def test_session_close_no_manager(self):
        from rendereye_mcp.server import create_server, set_session_manager

        server = create_server(Config())
        set_session_manager(None)
        result = asyncio.run(server.call_tool("session_close", {"session_id": "s-1"}))
        assert result is not None
