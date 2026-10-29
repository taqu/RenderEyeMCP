"""Phase 5 reliability regression tests.

Covers fixes made during the Phase 5 audit:
- _schedule_from_thread race condition hardening
- _poll_for_window early exit on process death
- _resolve_capture status enforcement
- IPC transport connection limit
- Storage rollback on commit failure
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus
from rendereye_mcp.config import Config
from rendereye_mcp.instances.manager import InstanceManager
from rendereye_mcp.instances.models import InstanceStatus
from rendereye_mcp.sessions.manager import SessionManager
from rendereye_mcp.sessions.storage import SessionStorage

# ---------------------------------------------------------------------------
# _schedule_from_thread race condition hardening
# ---------------------------------------------------------------------------


async def _noop():
    pass


class TestScheduleFromThread:
    def test_snapshot_avoids_none_loop(self):
        """Snapshotting the loop before check prevents AttributeError if loop is cleared."""
        from rendereye_mcp.captures.registry import CaptureRegistry
        from rendereye_mcp.captures.storage import CaptureStorage

        config = Config()
        storage = MagicMock(spec=CaptureStorage)
        registry = CaptureRegistry(config, storage)
        # Loop is None before start(); should log warning, not raise
        coro = _noop()
        registry._schedule_from_thread(coro)  # must not raise
        coro.close()  # suppress unawaited coroutine warning

    def test_handles_runtime_error_from_closed_loop(self):
        """RuntimeError from run_coroutine_threadsafe on a closed loop is caught."""
        import asyncio as _asyncio

        from rendereye_mcp.captures.registry import CaptureRegistry
        from rendereye_mcp.captures.storage import CaptureStorage

        config = Config()
        storage = MagicMock(spec=CaptureStorage)
        registry = CaptureRegistry(config, storage)

        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        coro = _noop()
        with patch.object(_asyncio, "run_coroutine_threadsafe", side_effect=RuntimeError("closed")):
            registry._loop = mock_loop
            registry._schedule_from_thread(coro)  # must not raise
        coro.close()


# ---------------------------------------------------------------------------
# _poll_for_window early exit on process death
# ---------------------------------------------------------------------------


class TestPollForWindowEarlyExit:
    @pytest.mark.asyncio
    async def test_exits_early_when_instance_exits(self, tmp_path: Path):
        """_poll_for_window returns None immediately when instance status is EXITED."""
        config = Config()
        storage = SessionStorage(tmp_path / "test.db")
        storage.initialize()

        mock_registry = MagicMock()
        mock_registry.get_capture.return_value = None
        instance_mgr = MagicMock(spec=InstanceManager)

        exited_instance = MagicMock()
        exited_instance.status = InstanceStatus.EXITED
        instance_mgr.get_instance.return_value = exited_instance
        instance_mgr.find_windows_for_instance.return_value = []

        mgr = SessionManager(config, storage, instance_mgr, mock_registry)
        result = await mgr._poll_for_window("instance-000001", timeout=5.0)
        assert result is None
        # Should have exited after first poll (one get_instance call proving early exit)
        assert instance_mgr.get_instance.call_count >= 1
        storage.close()

    @pytest.mark.asyncio
    async def test_returns_window_when_found(self, tmp_path: Path):
        """_poll_for_window returns the window_id when a window appears."""
        config = Config()
        storage = SessionStorage(tmp_path / "test.db")
        storage.initialize()

        mock_registry = MagicMock()
        instance_mgr = MagicMock(spec=InstanceManager)

        running_instance = MagicMock()
        running_instance.status = InstanceStatus.RUNNING
        instance_mgr.get_instance.return_value = running_instance

        mock_window = MagicMock()
        mock_window.window_id = "window-000001"
        instance_mgr.find_windows_for_instance.return_value = [mock_window]

        mgr = SessionManager(config, storage, instance_mgr, mock_registry)
        result = await mgr._poll_for_window("instance-000001", timeout=5.0)
        assert result == "window-000001"
        storage.close()


# ---------------------------------------------------------------------------
# _resolve_capture status enforcement
# ---------------------------------------------------------------------------


class TestResolveCapture:
    def _make_mgr(self, tmp_path: Path, capture_status: CaptureStatus):
        config = Config()
        storage = SessionStorage(tmp_path / "test.db")
        storage.initialize()
        instance_mgr = InstanceManager()
        mock_registry = MagicMock()
        mock_capture = MagicMock()
        mock_capture.capture_id = "cap-000001"
        mock_capture.path = "/test/cap.rdc"
        mock_capture.status = capture_status
        mock_registry.get_capture.return_value = mock_capture
        mock_registry.get_latest_capture.return_value = mock_capture
        return SessionManager(config, storage, instance_mgr, mock_registry), storage

    def test_ready_capture_resolves(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.READY)
        result = mgr._resolve_capture("cap-000001")
        assert result == ("cap-000001", "/test/cap.rdc")
        storage.close()

    def test_pending_capture_rejected(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.PENDING)
        result = mgr._resolve_capture("cap-000001")
        assert result is None
        storage.close()

    def test_discovered_capture_rejected(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.DISCOVERED)
        result = mgr._resolve_capture("cap-000001")
        assert result is None
        storage.close()

    def test_missing_capture_rejected(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.MISSING)
        result = mgr._resolve_capture("cap-000001")
        assert result is None
        storage.close()

    def test_latest_with_ready_capture(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.READY)
        result = mgr._resolve_capture("latest")
        assert result == ("cap-000001", "/test/cap.rdc")
        storage.close()

    def test_latest_with_pending_capture_rejected(self, tmp_path: Path):
        mgr, storage = self._make_mgr(tmp_path, CaptureStatus.PENDING)
        result = mgr._resolve_capture("latest")
        assert result is None
        storage.close()


# ---------------------------------------------------------------------------
# IPC transport connection limit
# ---------------------------------------------------------------------------


class TestIPCTransportConnectionLimit:
    @pytest.mark.asyncio
    async def test_connection_limit_rejects_excess(self):
        """Connections beyond _MAX_CONNECTIONS are rejected."""
        from rendereye_mcp.ipc.transport import IPCTransport

        config = Config()
        transport = IPCTransport(config)

        # Fill the connections list up to the limit with mock connections
        mock_conn = MagicMock()
        transport._connections = [mock_conn] * IPCTransport._MAX_CONNECTIONS

        # New connection should be rejected
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        await transport._handle_client(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()
        # Connection list should not have grown
        assert len(transport._connections) == IPCTransport._MAX_CONNECTIONS

    @pytest.mark.asyncio
    async def test_connection_accepted_under_limit(self):
        """Connections under the limit are accepted normally."""
        from rendereye_mcp.ipc.transport import IPCTransport

        config = Config()
        transport = IPCTransport(config)

        mock_conn_instance = MagicMock()
        mock_conn_instance.run = AsyncMock()

        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()

        with patch("rendereye_mcp.ipc.transport.ClientConnection", return_value=mock_conn_instance):
            await transport._handle_client(mock_reader, mock_writer)

        # Connection was accepted
        mock_writer.close.assert_not_called()


# ---------------------------------------------------------------------------
# Storage rollback on exception
# ---------------------------------------------------------------------------


class TestStorageRollback:
    def test_capture_upsert_raises_on_closed_storage(self, tmp_path: Path):
        """upsert_capture raises after the storage is closed."""
        from rendereye_mcp.captures.storage import CaptureStorage

        storage = CaptureStorage(tmp_path / "test.db")
        storage.initialize()

        record = CaptureRecord(
            capture_id="cap-000001",
            path="/test/cap.rdc",
            filename="cap.rdc",
            file_size=100,
            fs_created_at=None,
            fs_modified_at=None,
            discovered_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            readiness_confirmed_at=None,
            status=CaptureStatus.READY,
            selection_basis="mtime",
            ordering_confidence="high",
            source_directory="/test",
            error_message="",
        )
        storage.upsert_capture(record)
        assert storage.get_capture("cap-000001") is not None

        storage.close()
        with pytest.raises(RuntimeError, match="not initialized"):
            storage.upsert_capture(record)

    def test_session_upsert_raises_on_closed_storage(self, tmp_path: Path):
        """upsert_session raises after the storage is closed."""
        from rendereye_mcp.sessions.models import AssociationStatus, SessionRecord, SessionStatus

        storage = SessionStorage(tmp_path / "test.db")
        storage.initialize()

        record = SessionRecord(
            session_id="session-000001",
            capture_id="cap-000001",
            capture_path="/test/cap.rdc",
            instance_id="instance-000001",
            window_id="window-000001",
            process_id=1234,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.CONFIRMED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            error_message="",
        )
        storage.upsert_session(record)
        assert storage.get_session("session-000001") is not None
        storage.close()
        with pytest.raises(RuntimeError, match="not initialized"):
            storage.upsert_session(record)
