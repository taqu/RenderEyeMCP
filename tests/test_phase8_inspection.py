"""Tests for Phase 8 — Active Capture Inspection.

Covers:
- InspectCaptureRequestMessage / InspectCaptureResultMessage (protocol)
- ExtensionConnectionManager.request_capture_inspection()
- ToolExecutor._resolve_inspection_connection()
- ToolExecutor inspection tools: get_current_capture_info, list_capture_events,
  get_capture_event, get_selected_event, get_pipeline_state
- GUIContext.inspect() and sub-operations
- _action_to_dict() helper
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from rendereye_mcp.ipc.manager import ExtensionConnectionManager
from rendereye_mcp.ipc.protocol import (
    _TYPE_MAP,
    InspectCaptureRequestMessage,
    InspectCaptureResultMessage,
    deserialize,
    serialize,
)
from rendereye_mcp.service.tools import ToolExecutor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager() -> ExtensionConnectionManager:
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
) -> None:
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


def _mock_context(loaded=True, loading=False, path="D:/test.rdc"):
    """Return a minimal mock CaptureContext with required callables."""
    ctx = MagicMock()
    ctx.IsCaptureLoaded = MagicMock(return_value=loaded)
    ctx.IsCaptureLoading = MagicMock(return_value=loading)
    ctx.GetCaptureFilename = MagicMock(return_value=path)
    ctx.Extensions = MagicMock(return_value=[])
    return ctx


def _make_gui(ctx=None, set_thread=True):
    """Construct a GUIContext, optionally pinning thread_id to current thread."""
    from extensions.rendereye.gui_context import GUIContext

    if ctx is None:
        ctx = _mock_context()
    gui = GUIContext(ctx, "1.45")
    if set_thread:
        gui.thread_id = threading.get_ident()
    return gui, ctx


# ---------------------------------------------------------------------------
# Protocol: InspectCaptureRequestMessage
# ---------------------------------------------------------------------------


class TestInspectCaptureRequestMessage:
    def test_request_serializes(self):
        msg = InspectCaptureRequestMessage(
            request_id="req-1", operation="capture_info", params={"key": "val"}
        )
        raw = serialize(msg)
        result = deserialize(raw)
        assert isinstance(result, InspectCaptureRequestMessage)
        assert result.request_id == "req-1"
        assert result.operation == "capture_info"
        assert result.params == {"key": "val"}
        assert result.type == "inspect_capture"

    def test_request_default_params(self):
        msg = InspectCaptureRequestMessage(request_id="req-2", operation="selected_event")
        assert msg.params == {}
        raw = serialize(msg)
        result = deserialize(raw)
        assert result.params == {}

    def test_result_serializes(self):
        msg = InspectCaptureResultMessage(
            request_id="req-3",
            operation="capture_info",
            result={"capture_path": "D:/test.rdc", "frame_number": 1},
        )
        raw = serialize(msg)
        result = deserialize(raw)
        assert isinstance(result, InspectCaptureResultMessage)
        assert result.request_id == "req-3"
        assert result.operation == "capture_info"
        assert result.result["capture_path"] == "D:/test.rdc"
        assert result.error == ""

    def test_result_with_error_serializes(self):
        msg = InspectCaptureResultMessage(
            request_id="req-4",
            operation="list_events",
            result=None,
            error="capture_loading",
        )
        raw = serialize(msg)
        result = deserialize(raw)
        assert isinstance(result, InspectCaptureResultMessage)
        assert result.error == "capture_loading"
        assert result.result is None

    def test_message_types_in_type_map(self):
        assert "inspect_capture" in _TYPE_MAP
        assert "inspect_capture_result" in _TYPE_MAP
        assert _TYPE_MAP["inspect_capture"] is InspectCaptureRequestMessage
        assert _TYPE_MAP["inspect_capture_result"] is InspectCaptureResultMessage


# ---------------------------------------------------------------------------
# ExtensionConnectionManager.request_capture_inspection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_inspection_no_connection():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    # No send callback registered
    result = await mgr.request_capture_inspection(conn_id, "capture_info", {})
    assert result["error"] == "no_connection"


@pytest.mark.asyncio
async def test_request_inspection_success():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")

    async def fake_cb(msg):
        return InspectCaptureResultMessage(
            request_id=msg.request_id,
            operation=msg.operation,
            result={"capture_path": "D:/test.rdc", "frame_number": 5},
        )

    mgr.register_send_callback(conn_id, fake_cb)
    result = await mgr.request_capture_inspection(conn_id, "capture_info", {})
    assert result["capture_path"] == "D:/test.rdc"
    assert result["frame_number"] == 5
    assert "error" not in result


@pytest.mark.asyncio
async def test_request_inspection_timeout():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")

    async def slow_cb(msg):
        await asyncio.sleep(60)
        return InspectCaptureResultMessage(
            request_id=msg.request_id, operation=msg.operation, result={}
        )

    mgr.register_send_callback(conn_id, slow_cb)
    result = await mgr.request_capture_inspection(conn_id, "capture_info", {}, timeout=0.05)
    assert result["error"] == "timeout"
    assert "message" in result


@pytest.mark.asyncio
async def test_request_inspection_with_error_in_result():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")

    async def error_cb(msg):
        return InspectCaptureResultMessage(
            request_id=msg.request_id,
            operation=msg.operation,
            result=None,
            error="capture_loading",
        )

    mgr.register_send_callback(conn_id, error_cb)
    result = await mgr.request_capture_inspection(conn_id, "capture_info", {})
    assert result["error"] == "extension_error"
    assert "capture_loading" in result["message"]


@pytest.mark.asyncio
async def test_request_inspection_passes_params():
    """Verify the params dict is forwarded to the extension in the message."""
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    received_params = {}

    async def param_cb(msg):
        received_params.update(msg.params)
        return InspectCaptureResultMessage(
            request_id=msg.request_id, operation=msg.operation, result={"ok": True}
        )

    mgr.register_send_callback(conn_id, param_cb)
    await mgr.request_capture_inspection(
        conn_id, "list_events", {"limit": 25, "offset": 10}
    )
    assert received_params["limit"] == 25
    assert received_params["offset"] == 10


# ---------------------------------------------------------------------------
# _resolve_inspection_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_no_manager():
    ex = _make_executor(conn_manager=None)
    conn_id, err = await ex._resolve_inspection_connection()
    assert conn_id is None
    assert err["status"] == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_resolve_no_connections():
    mgr = _make_manager()
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection()
    assert conn_id is None
    assert err["status"] == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_resolve_single_connected():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection()
    assert err is None
    assert conn_id == cid


@pytest.mark.asyncio
async def test_resolve_disconnected_instance_id():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    mgr.disconnect_connection(cid)
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection(instance_id="i1")
    assert conn_id is None
    assert err["status"] == "session_disconnected"


@pytest.mark.asyncio
async def test_resolve_not_found_instance_id():
    mgr = _make_manager()
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection(instance_id="ghost")
    assert conn_id is None
    assert err["status"] == "session_not_found"


@pytest.mark.asyncio
async def test_resolve_multiple_with_one_loaded():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, False, None, "unloaded")
    _update_state(mgr, c2, 1, True, "D:/b.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection()
    assert err is None
    assert conn_id == c2


@pytest.mark.asyncio
async def test_resolve_multiple_all_loaded_ambiguous():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, True, "D:/a.rdc", "loaded")
    _update_state(mgr, c2, 1, True, "D:/b.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection()
    assert conn_id is None
    assert err["status"] == "ambiguous"
    assert len(err["sessions"]) == 2


@pytest.mark.asyncio
async def test_resolve_multiple_connected_none_loaded_ambiguous():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    _update_state(mgr, c1, 1, False, None, "unloaded")
    _update_state(mgr, c2, 1, False, None, "unloaded")
    ex = _make_executor(conn_manager=mgr)
    conn_id, err = await ex._resolve_inspection_connection()
    assert conn_id is None
    assert err["status"] == "ambiguous"


# ---------------------------------------------------------------------------
# get_current_capture_info tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_capture_info_success():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    mgr.request_capture_inspection = AsyncMock(
        return_value={"capture_path": "D:/test.rdc", "frame_number": 1}
    )
    result = await ex._get_current_capture_info()
    assert result["capture_path"] == "D:/test.rdc"
    mgr.request_capture_inspection.assert_awaited_once()
    call_args = mgr.request_capture_inspection.call_args
    assert call_args[0][1] == "capture_info"
    assert call_args[0][2] == {}


@pytest.mark.asyncio
async def test_get_current_capture_info_no_connection():
    ex = _make_executor(conn_manager=None)
    result = await ex._get_current_capture_info()
    assert result["status"] == "no_renderdoc_connected"


# ---------------------------------------------------------------------------
# list_capture_events tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_capture_events_passes_params():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    mgr.request_capture_inspection = AsyncMock(
        return_value={"events": [], "total": 0, "limit": 10, "offset": 5}
    )
    result = await ex._list_capture_events(
        limit=10,
        offset=5,
        include_markers=False,
        flags_filter="drawcall",
        parent_event_id=100,
    )
    assert result["total"] == 0
    call_args = mgr.request_capture_inspection.call_args
    params = call_args[0][2]
    assert params["limit"] == 10
    assert params["offset"] == 5
    assert params["include_markers"] is False
    assert params["flags_filter"] == "drawcall"
    assert params["parent_event_id"] == 100


@pytest.mark.asyncio
async def test_list_capture_events_defaults():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    mgr.request_capture_inspection = AsyncMock(return_value={"events": [], "total": 0})
    await ex._list_capture_events()
    params = mgr.request_capture_inspection.call_args[0][2]
    assert params["limit"] == 50
    assert params["offset"] == 0
    assert params["include_markers"] is True
    assert params["flags_filter"] == ""
    assert params["parent_event_id"] == 0


# ---------------------------------------------------------------------------
# get_capture_event tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_capture_event_passes_event_id():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    fake_event = {"event_id": 42, "action_type": "drawcall", "flags": ["Drawcall"]}
    mgr.request_capture_inspection = AsyncMock(return_value=fake_event)
    result = await ex._get_capture_event(event_id=42)
    assert result["event_id"] == 42
    call_args = mgr.request_capture_inspection.call_args
    assert call_args[0][1] == "get_event"
    assert call_args[0][2]["event_id"] == 42


@pytest.mark.asyncio
async def test_get_capture_event_no_connection():
    ex = _make_executor(conn_manager=None)
    result = await ex._get_capture_event(event_id=1)
    assert result["status"] == "no_renderdoc_connected"


# ---------------------------------------------------------------------------
# get_selected_event tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_selected_event_success():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    fake_result = {"selected_event_id": 450, "current_event_id": 450, "selected_action": None}
    mgr.request_capture_inspection = AsyncMock(return_value=fake_result)
    result = await ex._get_selected_event()
    assert result["selected_event_id"] == 450
    call_args = mgr.request_capture_inspection.call_args
    assert call_args[0][1] == "selected_event"
    assert call_args[0][2] == {}


# ---------------------------------------------------------------------------
# get_pipeline_state tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pipeline_state_default_section():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    mgr.request_capture_inspection = AsyncMock(
        return_value={"event_id": 10, "api": "D3D12", "section": "summary"}
    )
    await ex._get_pipeline_state()
    call_args = mgr.request_capture_inspection.call_args
    assert call_args[0][1] == "pipeline_state"
    assert call_args[0][2]["section"] == "summary"
    assert call_args[0][2]["event_id"] == 0


@pytest.mark.asyncio
async def test_get_pipeline_state_custom_section():
    mgr = _make_manager()
    cid = _register(mgr, "i1")
    _update_state(mgr, cid, 1, True, "D:/test.rdc", "loaded")
    ex = _make_executor(conn_manager=mgr)

    mgr.request_capture_inspection = AsyncMock(return_value={"section": "shaders"})
    await ex._get_pipeline_state(section="shaders", event_id=77)
    call_args = mgr.request_capture_inspection.call_args
    assert call_args[0][2]["section"] == "shaders"
    assert call_args[0][2]["event_id"] == 77


# ---------------------------------------------------------------------------
# GUIContext.inspect — no capture / loading
# ---------------------------------------------------------------------------


class TestGUIContextInspectNoCaptureOrLoading:
    def test_no_capture_loaded(self):
        ctx = _mock_context(loaded=False, loading=False)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        assert result["error"] == "no_capture_loaded"

    def test_capture_loading(self):
        ctx = _mock_context(loaded=False, loading=True)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        assert result["error"] == "capture_loading"

    def test_unknown_operation(self):
        ctx = _mock_context(loaded=True)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("frobnicate", {})
        assert result["error"] == "unsupported_operation"
        assert "frobnicate" in str(result["operation"])


# ---------------------------------------------------------------------------
# GUIContext.inspect — capture_info operation
# ---------------------------------------------------------------------------


class TestGUIContextInspectCaptureInfo:
    def test_capture_info_basic(self):
        ctx = _mock_context(loaded=True, path="D:/frame.rdc")
        ctx.APIProps = MagicMock(return_value=None)
        ctx.FrameInfo = MagicMock(return_value=None)
        ctx.CurRootActions = MagicMock(return_value=[])
        ctx.GetResources = MagicMock(return_value=[])
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        assert "error" not in result
        assert result["capture_path"] == "D:/frame.rdc"
        assert result["_capture_path"] == "D:/frame.rdc"

    def test_capture_info_with_api_props(self):
        ctx = _mock_context(loaded=True, path="D:/frame.rdc")
        api_props = MagicMock()
        api_props.pipelineType.name = "D3D12"
        api_props.vendor.name = "NV"
        api_props.degraded = False
        ctx.APIProps = MagicMock(return_value=api_props)
        ctx.FrameInfo = MagicMock(return_value=None)
        ctx.CurRootActions = MagicMock(return_value=[])
        ctx.GetResources = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        assert result["api"] == "D3D12"
        assert result["vendor"] == "NV"
        assert result["degraded"] is False

    def test_capture_info_counts_actions(self):
        ctx = _mock_context(loaded=True, path="D:/frame.rdc")
        ctx.APIProps = MagicMock(return_value=None)
        ctx.FrameInfo = MagicMock(return_value=None)
        ctx.GetResources = MagicMock(return_value=None)

        # Two drawcalls and one dispatch
        a1 = MagicMock()
        a1.flags = 2  # _FLAG_DRAWCALL
        a1.children = []
        a2 = MagicMock()
        a2.flags = 4  # _FLAG_DISPATCH
        a2.children = []
        a3 = MagicMock()
        a3.flags = 2  # _FLAG_DRAWCALL
        a3.children = []
        ctx.CurRootActions = MagicMock(return_value=[a1, a2, a3])
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        stats = result.get("statistics", {})
        assert stats["draw_calls"] == 2
        assert stats["dispatches"] == 1
        assert stats["total_events"] == 3

    def test_capture_info_resource_count(self):
        ctx = _mock_context(loaded=True)
        ctx.APIProps = MagicMock(return_value=None)
        ctx.FrameInfo = MagicMock(return_value=None)
        ctx.CurRootActions = MagicMock(return_value=[])
        ctx.GetResources = MagicMock(return_value=["r1", "r2", "r3"])
        gui, _ = _make_gui(ctx)
        result = gui.inspect("capture_info", {})
        assert result["resource_count"] == 3


# ---------------------------------------------------------------------------
# GUIContext.inspect — selected_event operation
# ---------------------------------------------------------------------------


class TestGUIContextInspectSelectedEvent:
    def test_selected_event_basic(self):
        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=450)
        ctx.CurEvent = MagicMock(return_value=450)
        ctx.CurSelectedAction = MagicMock(return_value=None)
        ctx.CurAction = MagicMock(return_value=None)
        ctx.GetStructuredFile = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("selected_event", {})
        assert "error" not in result
        assert result["selected_event_id"] == 450
        assert result["current_event_id"] == 450
        assert result["selected_action"] is None

    def test_selected_event_with_action(self):
        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=10)
        ctx.CurEvent = MagicMock(return_value=10)
        ctx.GetStructuredFile = MagicMock(return_value=None)
        action = MagicMock()
        action.eventId = 10
        action.actionId = 5
        action.flags = 2  # drawcall
        action.customName = "DrawIndexed"
        action.children = []
        ctx.CurSelectedAction = MagicMock(return_value=action)
        ctx.CurAction = MagicMock(return_value=action)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("selected_event", {})
        assert result["selected_action"]["event_id"] == 10
        assert result["selected_action"]["action_type"] == "drawcall"


# ---------------------------------------------------------------------------
# GUIContext.inspect — list_events operation
# ---------------------------------------------------------------------------


class TestGUIContextInspectListEvents:
    def test_list_events_empty(self):
        ctx = _mock_context(loaded=True)
        ctx.CurRootActions = MagicMock(return_value=[])
        gui, _ = _make_gui(ctx)
        result = gui.inspect("list_events", {})
        assert result["events"] == []
        assert result["total"] == 0

    def test_list_events_with_actions(self):
        ctx = _mock_context(loaded=True)
        actions = []
        for i in range(3):
            a = MagicMock()
            a.eventId = i + 1
            a.actionId = i + 1
            a.flags = 2  # drawcall
            a.customName = "Draw%d" % (i + 1)
            a.children = []
            actions.append(a)
        ctx.CurRootActions = MagicMock(return_value=actions)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("list_events", {"limit": 10, "offset": 0})
        assert result["total"] == 3
        assert len(result["events"]) == 3
        assert result["events"][0]["action_type"] == "drawcall"

    def test_list_events_pagination(self):
        ctx = _mock_context(loaded=True)
        actions = []
        for i in range(5):
            a = MagicMock()
            a.eventId = i + 1
            a.actionId = i + 1
            a.flags = 2  # drawcall
            a.customName = ""
            a.children = []
            actions.append(a)
        ctx.CurRootActions = MagicMock(return_value=actions)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("list_events", {"limit": 2, "offset": 2})
        assert result["total"] == 5
        assert len(result["events"]) == 2
        assert result["has_more"] is True

    def test_list_events_excludes_markers(self):
        ctx = _mock_context(loaded=True)
        marker = MagicMock()
        marker.eventId = 1
        marker.actionId = 1
        marker.flags = 64  # PushMarker
        marker.customName = "MyMarker"
        marker.children = []
        draw = MagicMock()
        draw.eventId = 2
        draw.actionId = 2
        draw.flags = 2  # drawcall
        draw.customName = "Draw"
        draw.children = []
        ctx.CurRootActions = MagicMock(return_value=[marker, draw])
        gui, _ = _make_gui(ctx)
        result = gui.inspect("list_events", {"include_markers": False})
        # Marker excluded, only draw
        assert all(e["action_type"] != "marker_begin" for e in result["events"])


# ---------------------------------------------------------------------------
# GUIContext.inspect — get_event operation
# ---------------------------------------------------------------------------


class TestGUIContextInspectGetEvent:
    def test_get_event_not_found(self):
        ctx = _mock_context(loaded=True)
        ctx.GetAction = MagicMock(return_value=None)
        ctx.GetStructuredFile = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("get_event", {"event_id": 999})
        assert result["error"] == "event_not_found"
        assert result["event_id"] == 999

    def test_get_event_found(self):
        ctx = _mock_context(loaded=True)
        action = MagicMock()
        action.eventId = 1
        action.actionId = 1
        action.flags = 2  # drawcall
        action.customName = "DrawCall"
        action.children = []
        ctx.GetAction = MagicMock(return_value=action)
        ctx.GetStructuredFile = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("get_event", {"event_id": 1})
        assert "error" not in result
        assert result["event_id"] == 1
        assert result["action_type"] == "drawcall"

    def test_get_event_invalid_id(self):
        ctx = _mock_context(loaded=True)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("get_event", {"event_id": 0})
        assert result["error"] == "invalid_event_id"

    def test_get_event_with_children(self):
        ctx = _mock_context(loaded=True)
        child = MagicMock()
        child.eventId = 2
        child.actionId = 2
        child.flags = 2
        child.customName = "Child"
        child.children = []
        action = MagicMock()
        action.eventId = 1
        action.actionId = 1
        action.flags = 64  # marker
        action.customName = "Begin"
        action.children = [child]
        ctx.GetAction = MagicMock(return_value=action)
        ctx.GetStructuredFile = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("get_event", {"event_id": 1})
        # get_event calls _action_to_dict with include_children=True
        assert "children" in result
        assert len(result["children"]) == 1
        assert result["children"][0]["event_id"] == 2


# ---------------------------------------------------------------------------
# GUIContext.inspect — pipeline_state operation
# ---------------------------------------------------------------------------


class TestGUIContextInspectPipelineState:
    def test_pipeline_no_curpipelinestate(self):
        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=10)
        ctx.CurPipelineState = MagicMock(side_effect=Exception("no pipeline"))
        gui, _ = _make_gui(ctx)
        result = gui.inspect("pipeline_state", {})
        assert result["error"] == "unsupported"

    def test_pipeline_event_not_selected(self):
        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=100)
        pipe = MagicMock()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurAction = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("pipeline_state", {"event_id": 200, "section": "summary"})
        assert result["error"] == "event_not_selected"
        assert result["requested_event_id"] == 200
        assert result["selected_event_id"] == 100

    def test_pipeline_summary_section(self):
        import sys
        import types

        # Provide a stub renderdoc module so _pipeline_summary can import it
        rd_stub = types.ModuleType("renderdoc")
        rd_stub.ShaderStage = MagicMock()
        rd_stub.ResourceId = MagicMock()
        rd_stub.ResourceId.Null = MagicMock(return_value="null-id")
        sys.modules.setdefault("renderdoc", rd_stub)

        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=10)
        pipe = MagicMock()
        pipe.IsCaptureLoaded = MagicMock(return_value=True)
        pipe.IsCaptureD3D11 = MagicMock(return_value=False)
        pipe.IsCaptureD3D12 = MagicMock(return_value=True)
        pipe.IsCaptureGL = MagicMock(return_value=False)
        pipe.IsCaptureVK = MagicMock(return_value=False)
        pipe.GetPrimitiveTopology = MagicMock(side_effect=Exception("no topology"))
        pipe.GetOutputTargets = MagicMock(return_value=["rt1", "rt2"])
        pipe.GetDepthTarget = MagicMock(return_value=None)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurAction = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("pipeline_state", {"section": "summary"})
        assert "error" not in result
        assert result["api"] == "D3D12"
        assert result["event_id"] == 10
        assert result["section"] == "summary"

    def test_pipeline_invalid_section(self):
        ctx = _mock_context(loaded=True)
        ctx.CurSelectedEvent = MagicMock(return_value=5)
        pipe = MagicMock()
        pipe.IsCaptureLoaded = MagicMock(return_value=True)
        pipe.IsCaptureD3D11 = MagicMock(return_value=False)
        pipe.IsCaptureD3D12 = MagicMock(return_value=False)
        pipe.IsCaptureGL = MagicMock(return_value=False)
        pipe.IsCaptureVK = MagicMock(return_value=False)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurAction = MagicMock(return_value=None)
        gui, _ = _make_gui(ctx)
        result = gui.inspect("pipeline_state", {"section": "bad_section"})
        assert result["error"] == "invalid_section"


# ---------------------------------------------------------------------------
# _action_to_dict helper
# ---------------------------------------------------------------------------


class TestActionToDict:
    @staticmethod
    def _action(event_id=1, action_id=1, flags=2, name="", children=None):
        a = MagicMock()
        a.eventId = event_id
        a.actionId = action_id
        a.flags = flags
        a.customName = name
        a.children = children if children is not None else []
        # Remove attributes that shouldn't be present to exercise exception paths
        del a.numInstances
        del a.numIndices
        del a.dispatchDimension
        return a

    def test_drawcall_action_type(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action(flags=2, name="DrawIndexed")
        d = _action_to_dict(a)
        assert d["action_type"] == "drawcall"
        assert "Drawcall" in d["flags"]
        assert d["event_id"] == 1

    def test_dispatch_action_type(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action(flags=4, name="Dispatch")
        d = _action_to_dict(a)
        assert d["action_type"] == "dispatch"
        assert "Dispatch" in d["flags"]

    def test_push_marker_action_type(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action(flags=64, name="BeginEvent")
        d = _action_to_dict(a)
        assert d["action_type"] == "marker_begin"
        assert "PushMarker" in d["flags"]

    def test_other_action_type(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action(flags=512, name="Clear")  # _FLAG_CLEAR
        d = _action_to_dict(a)
        assert d["action_type"] == "clear"

    def test_with_children_included(self):
        from extensions.rendereye.gui_context import _action_to_dict

        child = self._action(event_id=2, action_id=2, flags=2, name="Child")
        parent = self._action(event_id=1, action_id=1, flags=64, name="Marker", children=[child])
        d = _action_to_dict(parent, include_children=True)
        assert "children" in d
        assert len(d["children"]) == 1
        assert d["children"][0]["event_id"] == 2

    def test_without_children_has_child_count(self):
        from extensions.rendereye.gui_context import _action_to_dict

        child = self._action(event_id=2)
        parent = self._action(event_id=1, children=[child])
        d = _action_to_dict(parent, include_children=False)
        assert "child_count" in d
        assert d["child_count"] == 1
        assert "children" not in d

    def test_fallback_name(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action(event_id=99, name="")
        d = _action_to_dict(a)
        assert "99" in d["name"]

    def test_depth_field(self):
        from extensions.rendereye.gui_context import _action_to_dict

        a = self._action()
        d = _action_to_dict(a, depth=3)
        assert d["depth"] == 3
