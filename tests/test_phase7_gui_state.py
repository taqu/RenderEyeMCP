"""Phase 7 — GUI State Discovery tests.

Covers:
- ExtensionConnection.connection_state property
- ExtensionConnection.to_gui_session_dict()
- ExtensionConnectionManager.get_any_connection_for_instance()
- list_renderdoc_sessions tool
- get_renderdoc_session_state tool
- get_current_capture tool (auto-select + explicit instance_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

from rendereye_mcp.ipc.manager import ExtensionConnection, ExtensionConnectionManager
from rendereye_mcp.service.tools import ToolExecutor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager():
    return ExtensionConnectionManager(auth_manager=None)


def _register(mgr: ExtensionConnectionManager, instance_id: str, pid: int = 1) -> str:
    conn_id, _ = mgr.register_connection(
        instance_id=instance_id,
        process_id=pid,
        extension_version="1.0.0",
        renderdoc_version="1.45",
        auth_token="",
    )
    return conn_id


def _update_state(
    mgr: ExtensionConnectionManager,
    conn_id: str,
    revision: int,
    loaded: bool,
    path: Optional[str],
    state: str,
):
    mgr.update_gui_state(
        connection_id=conn_id,
        revision=revision,
        capture_loaded=loaded,
        capture_path=path,
        capture_state=state,
    )


def _make_executor(conn_manager=None) -> ToolExecutor:
    config = MagicMock()
    config.renderdoc_path = None
    return ToolExecutor(
        config=config,
        registry=None,
        session_manager=None,
        conn_manager=conn_manager,
        operation_tracker=None,
    )


# ---------------------------------------------------------------------------
# ExtensionConnection.connection_state
# ---------------------------------------------------------------------------


class TestConnectionState:
    def test_connected_returns_connected(self):
        conn = ExtensionConnection(
            connection_id="c1",
            instance_id="i1",
            process_id=1,
            extension_version="1.0",
            renderdoc_version="1.45",
            authenticated=True,
            connected=True,
        )
        assert conn.connection_state == "connected"

    def test_disconnected_with_state_returns_disconnected(self):
        conn = ExtensionConnection(
            connection_id="c1",
            instance_id="i1",
            process_id=1,
            extension_version="1.0",
            renderdoc_version="1.45",
            authenticated=True,
            connected=False,
            last_state_at=datetime.now(timezone.utc),
        )
        assert conn.connection_state == "disconnected"

    def test_disconnected_without_state_returns_unknown(self):
        conn = ExtensionConnection(
            connection_id="c1",
            instance_id="i1",
            process_id=1,
            extension_version="1.0",
            renderdoc_version="1.45",
            authenticated=True,
            connected=False,
            last_state_at=None,
        )
        assert conn.connection_state == "unknown"

    def test_to_dict_includes_connection_state(self):
        conn = ExtensionConnection(
            connection_id="c1",
            instance_id="i1",
            process_id=1,
            extension_version="1.0",
            renderdoc_version="1.45",
            authenticated=True,
            connected=True,
        )
        d = conn.to_dict()
        assert "connection_state" in d
        assert d["connection_state"] == "connected"


# ---------------------------------------------------------------------------
# ExtensionConnection.to_gui_session_dict()
# ---------------------------------------------------------------------------


class TestToGuiSessionDict:
    def test_connected_with_loaded_capture(self):
        mgr = _make_manager()
        conn_id = _register(mgr, "i1", 1234)
        _update_state(mgr, conn_id, 5, True, "D:/frame.rdc", "loaded")
        conn = mgr.get_connection(conn_id)
        d = conn.to_gui_session_dict()

        assert d["instance_id"] == "i1"
        assert d["process_id"] == 1234
        assert d["connection_state"] == "connected"
        assert d["capture"] == {"state": "loaded", "path": "D:/frame.rdc"}
        assert d["last_known_capture"] is None
        assert d["state_version"] == 5

    def test_connected_without_capture(self):
        mgr = _make_manager()
        conn_id = _register(mgr, "i1")
        _update_state(mgr, conn_id, 1, False, None, "unloaded")
        conn = mgr.get_connection(conn_id)
        d = conn.to_gui_session_dict()

        assert d["connection_state"] == "connected"
        assert d["capture"] == {"state": "unloaded", "path": None}
        assert d["last_known_capture"] is None

    def test_disconnected_has_last_known(self):
        mgr = _make_manager()
        conn_id = _register(mgr, "i1")
        _update_state(mgr, conn_id, 3, True, "D:/old.rdc", "loaded")
        mgr.disconnect_connection(conn_id)
        conn = mgr.get_connection(conn_id)
        d = conn.to_gui_session_dict()

        assert d["connection_state"] == "disconnected"
        assert d["capture"] is None
        assert d["last_known_capture"] == {"state": "loaded", "path": "D:/old.rdc"}

    def test_disconnected_without_any_state(self):
        conn = ExtensionConnection(
            connection_id="c1",
            instance_id="i1",
            process_id=1,
            extension_version="1.0",
            renderdoc_version="1.45",
            authenticated=True,
            connected=False,
            last_state_at=None,
        )
        d = conn.to_gui_session_dict()
        assert d["connection_state"] == "unknown"
        assert d["capture"] is None
        assert d["last_known_capture"] is None


# ---------------------------------------------------------------------------
# ExtensionConnectionManager.get_any_connection_for_instance()
# ---------------------------------------------------------------------------


class TestGetAnyConnectionForInstance:
    def test_returns_connected_connection(self):
        mgr = _make_manager()
        conn_id = _register(mgr, "i1")
        conn = mgr.get_any_connection_for_instance("i1")
        assert conn is not None
        assert conn.connection_id == conn_id

    def test_returns_disconnected_connection(self):
        mgr = _make_manager()
        conn_id = _register(mgr, "i1")
        _update_state(mgr, conn_id, 1, True, "D:/f.rdc", "loaded")
        mgr.disconnect_connection(conn_id)
        conn = mgr.get_any_connection_for_instance("i1")
        assert conn is not None
        assert conn.connection_id == conn_id
        assert conn.connected is False

    def test_prefers_connected_over_disconnected(self):
        mgr = _make_manager()
        conn_id1 = _register(mgr, "i1", pid=10)
        _update_state(mgr, conn_id1, 1, True, "D:/old.rdc", "loaded")
        mgr.disconnect_connection(conn_id1)
        conn_id2 = _register(mgr, "i1", pid=11)
        _update_state(mgr, conn_id2, 2, True, "D:/new.rdc", "loaded")

        conn = mgr.get_any_connection_for_instance("i1")
        assert conn is not None
        assert conn.connection_id == conn_id2
        assert conn.connected is True

    def test_returns_none_for_unknown_instance(self):
        mgr = _make_manager()
        conn = mgr.get_any_connection_for_instance("nonexistent")
        assert conn is None


# ---------------------------------------------------------------------------
# list_renderdoc_sessions tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_no_conn_manager():
    ex = _make_executor(conn_manager=None)
    result = await ex._list_renderdoc_sessions()
    assert result["sessions"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_list_sessions_returns_all():
    mgr = _make_manager()
    _register(mgr, "i1", 1)
    _register(mgr, "i2", 2)
    ex = _make_executor(conn_manager=mgr)
    result = await ex._list_renderdoc_sessions()
    assert result["total"] == 2
    ids = {s["instance_id"] for s in result["sessions"]}
    assert ids == {"i1", "i2"}


@pytest.mark.asyncio
async def test_list_sessions_includes_disconnected():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1", 1)
    _update_state(mgr, conn_id, 1, True, "D:/f.rdc", "loaded")
    mgr.disconnect_connection(conn_id)
    ex = _make_executor(conn_manager=mgr)
    result = await ex._list_renderdoc_sessions()
    assert result["total"] == 1
    s = result["sessions"][0]
    assert s["connection_state"] == "disconnected"
    assert s["last_known_capture"] is not None
    assert s["capture"] is None


@pytest.mark.asyncio
async def test_list_sessions_live_capture():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1", 1)
    _update_state(mgr, conn_id, 5, True, "D:/live.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._list_renderdoc_sessions()
    s = result["sessions"][0]
    assert s["connection_state"] == "connected"
    assert s["capture"] == {"state": "loaded", "path": "D:/live.rdc"}


@pytest.mark.asyncio
async def test_list_sessions_multiple_independent():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, True, "D:/a.rdc", "loaded")
    _update_state(mgr, c2, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._list_renderdoc_sessions()
    by_id = {s["instance_id"]: s for s in result["sessions"]}
    assert by_id["i1"]["capture"]["path"] == "D:/a.rdc"
    assert by_id["i2"]["capture"]["path"] is None


# ---------------------------------------------------------------------------
# get_renderdoc_session_state tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_state_connected_loaded():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1", 42)
    _update_state(mgr, conn_id, 7, True, "D:/frame.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_renderdoc_session_state("i1")
    assert result["connection_state"] == "connected"
    assert result["capture"] == {"state": "loaded", "path": "D:/frame.rdc"}
    assert result["state_version"] == 7


@pytest.mark.asyncio
async def test_session_state_connected_no_capture():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_renderdoc_session_state("i1")
    assert result["connection_state"] == "connected"
    assert result["capture"]["state"] == "unloaded"


@pytest.mark.asyncio
async def test_session_state_disconnected_last_known():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 3, True, "D:/stale.rdc", "loaded")
    mgr.disconnect_connection(conn_id)
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_renderdoc_session_state("i1")
    assert result["connection_state"] == "disconnected"
    assert result["capture"] is None
    assert result["last_known_capture"]["path"] == "D:/stale.rdc"


@pytest.mark.asyncio
async def test_session_state_unknown_instance():
    mgr = _make_manager()
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_renderdoc_session_state("nonexistent")
    assert result["error"] == "session_not_found"
    assert result["instance_id"] == "nonexistent"


@pytest.mark.asyncio
async def test_session_state_no_conn_manager():
    ex = _make_executor(conn_manager=None)
    result = await ex._get_renderdoc_session_state("i1")
    assert result["error"] == "conn_manager_unavailable"


# ---------------------------------------------------------------------------
# get_current_capture tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_current_capture_no_conn_manager():
    ex = _make_executor(conn_manager=None)
    result = await ex._get_current_capture()
    assert result["status"] == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_current_capture_no_renderdoc():
    mgr = _make_manager()
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_current_capture_connected_no_capture():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "no_capture_loaded"
    assert len(result["sessions"]) == 1


@pytest.mark.asyncio
async def test_current_capture_single_loaded():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1", 777)
    _update_state(mgr, conn_id, 9, True, "D:/frame.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "loaded"
    assert result["capture_path"] == "D:/frame.rdc"
    assert result["connection_state"] == "connected"
    assert result["instance_id"] == "i1"
    assert result["process_id"] == 777


@pytest.mark.asyncio
async def test_current_capture_multiple_ambiguous():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, True, "D:/a.rdc", "loaded")
    _update_state(mgr, c2, 1, True, "D:/b.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "ambiguous"
    assert len(result["sessions"]) == 2


@pytest.mark.asyncio
async def test_current_capture_loading_state():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 1, False, None, "loading")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "capture_loading"


@pytest.mark.asyncio
async def test_current_capture_explicit_instance_loaded():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 10)
    c2 = _register(mgr, "i2", 20)
    _update_state(mgr, c1, 1, True, "D:/a.rdc", "loaded")
    _update_state(mgr, c2, 1, True, "D:/b.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture(instance_id="i1")
    assert result["status"] == "loaded"
    assert result["capture_path"] == "D:/a.rdc"
    assert result["instance_id"] == "i1"


@pytest.mark.asyncio
async def test_current_capture_explicit_instance_no_capture():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture(instance_id="i1")
    assert result["status"] == "no_capture_loaded"


@pytest.mark.asyncio
async def test_current_capture_explicit_instance_disconnected():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 3, True, "D:/old.rdc", "loaded")
    mgr.disconnect_connection(conn_id)
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture(instance_id="i1")
    assert result["status"] == "session_disconnected"
    assert result["last_known_capture"]["path"] == "D:/old.rdc"


@pytest.mark.asyncio
async def test_current_capture_explicit_instance_not_found():
    mgr = _make_manager()
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture(instance_id="ghost")
    assert result["status"] == "session_not_found"


@pytest.mark.asyncio
async def test_current_capture_disconnected_not_counted():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 5, True, "D:/frame.rdc", "loaded")
    mgr.disconnect_connection(conn_id)
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    # Disconnected session must NOT be returned as an active loaded capture
    assert result["status"] == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_current_capture_one_loaded_one_unloaded():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, True, "D:/frame.rdc", "loaded")
    _update_state(mgr, c2, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "loaded"
    assert result["instance_id"] == "i1"


@pytest.mark.asyncio
async def test_current_capture_stale_update_ignored():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    _update_state(mgr, conn_id, 10, True, "D:/new.rdc", "loaded")
    _update_state(mgr, conn_id, 5, False, None, "unloaded")  # stale — ignored
    ex = _make_executor(conn_manager=mgr)
    result = await ex._get_current_capture()
    assert result["status"] == "loaded"
    assert result["capture_path"] == "D:/new.rdc"
