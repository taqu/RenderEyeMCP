"""Tests for SessionManager."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rendereye_mcp.captures.models import CaptureStatus
from rendereye_mcp.config import Config
from rendereye_mcp.instances.manager import InstanceManager
from rendereye_mcp.sessions.manager import SessionManager
from rendereye_mcp.sessions.models import AssociationStatus, SessionRecord, SessionStatus
from rendereye_mcp.sessions.storage import SessionStorage


def make_manager(tmp_path: Path):
    config = Config()
    storage = SessionStorage(tmp_path / "test.db")
    storage.initialize()
    instance_mgr = InstanceManager()

    # Mock capture registry with a ready capture
    mock_registry = MagicMock()
    mock_capture = MagicMock()
    mock_capture.capture_id = "cap-000001"
    mock_capture.path = "/test/cap.rdc"
    mock_capture.status = CaptureStatus.READY
    mock_registry.get_capture.return_value = mock_capture
    mock_registry.get_latest_capture.return_value = mock_capture

    mgr = SessionManager(config, storage, instance_mgr, mock_registry)
    return mgr, storage


def test_create_session_unknown_capture(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    mgr._registry.get_capture.return_value = None
    mgr._registry.get_latest_capture.return_value = None
    result = mgr.create_session("cap-nonexistent")
    assert result.get("error") == "capture_not_found"
    storage.close()


def test_create_session_no_exe(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    mgr._config.renderdoc_exe = "/nonexistent/qrenderdoc.exe"
    result = mgr.create_session("cap-000001")
    assert "error" in result
    storage.close()


def test_create_session_launch_failure(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe", return_value="D:/test.exe"
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=False,
            process_id=None,
            process_create_time=None,
            exe_path="",
            error="failed",
        )
        result = mgr.create_session("cap-000001")
    assert "error" in result
    storage.close()


def test_create_session_success(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe",
        return_value="C:/Program Files/RenderDoc/qrenderdoc.exe",
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=True,
            process_id=1234,
            process_create_time=1.0,
            exe_path="C:/Program Files/RenderDoc/qrenderdoc.exe",
            note="may reuse",
        )
        result = mgr.create_session("cap-000001")
    assert result.get("error") is None
    assert "session_id" in result
    storage.close()


def test_create_session_stores_in_db(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe", return_value="D:/test.exe"
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=True, process_id=1234, process_create_time=1.0, exe_path="D:/test.exe", note=""
        )
        result = mgr.create_session("cap-000001")

    sid = result["session_id"]
    stored = storage.get_session(sid)
    assert stored is not None
    assert stored.capture_id == "cap-000001"
    storage.close()


def test_protect_session(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe", return_value="D:/test.exe"
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=True, process_id=1234, process_create_time=1.0, exe_path="D:/test.exe", note=""
        )
        create_result = mgr.create_session("cap-000001")

    sid = create_result["session_id"]
    protect_result = mgr.protect_session(sid, True)
    assert protect_result.get("protected") is True
    storage.close()


def test_close_protected_session_rejected(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe", return_value="D:/test.exe"
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=True, process_id=1234, process_create_time=1.0, exe_path="D:/test.exe", note=""
        )
        create_result = mgr.create_session("cap-000001")

    sid = create_result["session_id"]
    mgr.protect_session(sid, True)
    close_result = mgr.close_session(sid)
    assert close_result.get("status") == "failed"
    assert close_result.get("error", {}).get("code") == "session_protected"
    storage.close()


def test_close_unmanaged_session_rejected(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    now = datetime.now(timezone.utc)
    rec = SessionRecord(
        session_id="session-000001",
        capture_id="cap-000001",
        capture_path="/test.rdc",
        instance_id=None,
        window_id=None,
        process_id=None,
        status=SessionStatus.ACTIVE,
        managed=False,
        protected=False,
        association_status=AssociationStatus.UNKNOWN,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )
    storage.upsert_session(rec)
    close_result = mgr.close_session("session-000001")
    assert close_result.get("status") == "failed"
    assert close_result.get("error", {}).get("code") == "session_unmanaged"
    storage.close()


def test_list_sessions_empty(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.list_sessions()
    assert result["sessions"] == []
    assert result["total"] == 0
    storage.close()


def test_get_session_not_found(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.get_session("session-999999")
    assert result is None
    storage.close()


def test_close_session_not_found(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.close_session("session-999999")
    assert result.get("status") == "failed"
    assert result.get("error", {}).get("code") == "session_not_found"
    storage.close()


def test_focus_session_not_found(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.focus_session("session-999999")
    assert result.get("error") == "session_not_found"
    storage.close()


def test_protect_session_not_found(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.protect_session("session-999999", True)
    assert result.get("error") == "session_not_found"
    storage.close()


def test_reconcile_marks_missing_processes(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    now = datetime.now(timezone.utc)
    rec = SessionRecord(
        session_id="session-000001",
        capture_id="cap-000001",
        capture_path="/test.rdc",
        instance_id="instance-000001",
        window_id="window-000001",
        process_id=99999,
        status=SessionStatus.ACTIVE,
        managed=True,
        protected=False,
        association_status=AssociationStatus.CONFIRMED,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )
    storage.upsert_session(rec)
    # psutil won't find pid 99999
    result = mgr.reconcile()
    assert result["lost"] >= 1 or result["reconciled"] >= 1
    storage.close()


def test_reuse_mode_returns_existing_session(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    # Pre-create an active session
    now = datetime.now(timezone.utc)
    rec = SessionRecord(
        session_id="session-000001",
        capture_id="cap-000001",
        capture_path="/test/cap.rdc",
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
    storage.upsert_session(rec)
    result = mgr.create_session("cap-000001", open_mode="reuse")
    assert result.get("session_id") == "session-000001"
    storage.close()


def test_replace_mode_not_supported(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    result = mgr.create_session("cap-000001", open_mode="replace")
    assert result.get("error") == "not_supported"
    storage.close()


def test_list_sessions_with_status_filter(tmp_path: Path):
    mgr, storage = make_manager(tmp_path)
    with patch("rendereye_mcp.sessions.manager.launch_renderdoc") as mock_launch, patch(
        "rendereye_mcp.sessions.manager.find_renderdoc_exe", return_value="D:/test.exe"
    ):
        from rendereye_mcp.instances.launcher import LaunchResult

        mock_launch.return_value = LaunchResult(
            success=True, process_id=1234, process_create_time=1.0, exe_path="D:/test.exe", note=""
        )
        mgr.create_session("cap-000001")

    active_result = mgr.list_sessions(status="active")
    assert active_result["total"] >= 1

    closed_result = mgr.list_sessions(status="closed")
    assert closed_result["total"] == 0
    storage.close()
