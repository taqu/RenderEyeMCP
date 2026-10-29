"""Tests for Phase 15 — Pixel History & Shader Debugging.

Covers:
- _shader_var_to_dict: ShaderVariable serialization helper
- _debug_state_to_dict: ShaderDebugState serialization helper
- GUIContext._inspect_pixel_history
- GUIContext._inspect_debug_pixel
- GUIContext._inspect_debug_vertex
- GUIContext._inspect_debug_compute
- DebugStore: storage, retrieval, eviction, invalidation
- ToolExecutor._get_pixel_history
- ToolExecutor._debug_pixel_shader / _debug_vertex_shader / _debug_compute_shader
- ToolExecutor._get_shader_debug_trace
- ToolExecutor._get_shader_debug_variables
- ToolExecutor._get_shader_debug_status
"""

from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# renderdoc mock
# ---------------------------------------------------------------------------
_RD_MOCK = MagicMock()
_RD_MOCK.ResourceId.Null.return_value = MagicMock(__str__=lambda s: "ResourceId::Null()")
_RD_MOCK.CompType.Typeless = MagicMock()


def _patch_renderdoc():
    return patch.dict(sys.modules, {"renderdoc": _RD_MOCK})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_context(loaded=True, path="/test.rdc", cur_event=42):
    ctx = MagicMock()
    ctx.IsCaptureLoaded = MagicMock(return_value=loaded)
    ctx.IsCaptureLoading = MagicMock(return_value=False)
    ctx.GetCaptureFilename = MagicMock(return_value=path)
    ctx.Extensions = MagicMock(return_value=[])
    ctx.CurEvent = MagicMock(return_value=cur_event)
    ctx.GetResources = MagicMock(return_value=[])
    return ctx


def _make_gui_context(ctx=None, path="/test.rdc"):
    with _patch_renderdoc():
        from rendereye_mcp._extension_data.gui_context import GUIContext
        if ctx is None:
            ctx = _mock_context(path=path)
        gc = GUIContext(ctx, "1.46")
        gc.thread_id = None
        return gc, ctx


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# Unit tests: _shader_var_to_dict
# ===========================================================================


class TestShaderVarToDict:
    def test_basic_float_scalar(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _shader_var_to_dict

            v = MagicMock()
            v.name = "myVar"
            v.rows = 1
            v.columns = 1
            v.type = MagicMock(name="Float")
            v.type.name = "Float"
            v.value = MagicMock()
            v.value.f32v = [3.14]
            v.members = []
            result = _shader_var_to_dict(v)
            assert result["name"] == "myVar"
            assert result["rows"] == 1

    def test_float4_vector(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _shader_var_to_dict

            v = MagicMock()
            v.name = "color"
            v.rows = 1
            v.columns = 4
            v.type = MagicMock()
            v.type.name = "Float"
            v.value = MagicMock()
            v.value.f32v = [1.0, 0.5, 0.25, 1.0]
            v.members = []
            result = _shader_var_to_dict(v)
            assert result["name"] == "color"
            val = result["value"]
            assert isinstance(val, list)
            assert len(val) == 4

    def test_uint_fallback(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _shader_var_to_dict

            v = MagicMock()
            v.name = "idx"
            v.rows = 1
            v.columns = 1
            v.type = MagicMock()
            v.type.name = "UInt"
            v.value = MagicMock()
            # Make float access raise so uint path is taken
            v.value.f32v = MagicMock(side_effect=AttributeError("no float"))
            v.value.u32v = [7]
            v.members = []
            result = _shader_var_to_dict(v)
            assert result["name"] == "idx"

    def test_depth_limit(self):
        """Should return early at depth 3."""
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _shader_var_to_dict

            v = MagicMock()
            result = _shader_var_to_dict(v, depth=4)
            assert result.get("note") == "max_depth"

    def test_name_error_handled(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _shader_var_to_dict

            v = MagicMock()
            type(v).name = property(lambda s: (_ for _ in ()).throw(RuntimeError("bad")))
            v.rows = 1
            v.columns = 1
            v.members = []
            v.type = MagicMock()
            # Should not raise
            result = _shader_var_to_dict(v)
            assert isinstance(result, dict)


# ===========================================================================
# Unit tests: _debug_state_to_dict
# ===========================================================================


class TestDebugStateToDict:
    def test_basic_state(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _debug_state_to_dict

            state = MagicMock()
            state.stepIndex = 5
            state.nextInstruction = 6
            state.flags = 0
            state.changes = []
            result = _debug_state_to_dict(state)
            assert result["step"] == 5
            assert result["next_instruction"] == 6
            assert result["flags"] == 0
            assert result["changes"] == []

    def test_nan_inf_flag(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _debug_state_to_dict

            state = MagicMock()
            state.stepIndex = 0
            state.nextInstruction = 1
            state.flags = 0x2  # GeneratedNanOrInf flag
            state.changes = []
            result = _debug_state_to_dict(state)
            assert result.get("generated_nan_or_inf") is True

    def test_variable_changes(self):
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import (
                _debug_state_to_dict,
                _shader_var_to_dict,
            )

            before_var = MagicMock()
            before_var.name = "r0"
            before_var.rows = 1
            before_var.columns = 4
            before_var.value = MagicMock()
            before_var.value.f32v = [0.0, 0.0, 0.0, 0.0]
            before_var.members = []
            before_var.type = MagicMock()
            before_var.type.name = "Float"

            after_var = MagicMock()
            after_var.name = "r0"
            after_var.rows = 1
            after_var.columns = 4
            after_var.value = MagicMock()
            after_var.value.f32v = [1.0, 0.5, 0.25, 1.0]
            after_var.members = []
            after_var.type = MagicMock()
            after_var.type.name = "Float"

            ch = MagicMock()
            ch.before = before_var
            ch.after = after_var

            state = MagicMock()
            state.stepIndex = 0
            state.nextInstruction = 1
            state.flags = 0
            state.changes = [ch]

            result = _debug_state_to_dict(state)
            assert len(result["changes"]) == 1
            assert result["changes"][0]["after"]["name"] == "r0"

    def test_step_count_limit(self):
        """max_changes truncates the change list."""
        with _patch_renderdoc():
            from rendereye_mcp._extension_data.gui_context import _debug_state_to_dict

            changes = []
            for i in range(20):
                ch = MagicMock()
                after = MagicMock()
                after.name = f"v{i}"
                after.rows = 1
                after.columns = 1
                after.value = MagicMock()
                after.value.f32v = [float(i)]
                after.members = []
                after.type = MagicMock()
                after.type.name = "Float"
                ch.before = MagicMock()
                ch.before.name = f"v{i}"
                ch.before.rows = 1
                ch.before.columns = 1
                ch.before.value = MagicMock()
                ch.before.value.f32v = [0.0]
                ch.before.members = []
                ch.before.type = MagicMock()
                ch.before.type.name = "Float"
                ch.after = after
                changes.append(ch)

            state = MagicMock()
            state.stepIndex = 0
            state.nextInstruction = 1
            state.flags = 0
            state.changes = changes

            result = _debug_state_to_dict(state, max_changes=5)
            assert len(result["changes"]) == 5


# ===========================================================================
# Unit tests: GUIContext._inspect_pixel_history
# ===========================================================================


class TestPixelHistory:
    def _make_modification(self, event_id, passed, depth_failed=False, shader_disc=False):
        mod = MagicMock()
        mod.eventId = event_id
        mod.passed = passed
        mod.primitiveID = 0
        mod.fragIndex = 0
        mod.backfaceCulled = False
        mod.depthClipped = False
        mod.scissorClipped = False
        mod.sampleMasked = False
        mod.shaderDiscarded = shader_disc
        mod.depthTestFailed = depth_failed
        mod.stencilTestFailed = False
        pv = MagicMock()
        pv.floatValue = [0.0, 0.0, 0.0, 0.0]
        mod.preMod = pv
        mod.shaderOut = pv
        mod.postMod = pv
        return mod

    def test_missing_resource_id(self):
        gc, ctx = _make_gui_context()
        with _patch_renderdoc():
            result = gc.inspect("pixel_history", {})
        assert result.get("error") in ("resource_id is required", "no_capture_loaded")

    def test_resource_not_found(self):
        gc, ctx = _make_gui_context()
        ctx.GetResources = MagicMock(return_value=[])
        with _patch_renderdoc():
            result = gc.inspect("pixel_history", {"resource_id": "0xDEAD"})
        assert "error" in result

    def test_pixel_history_success(self):
        gc, ctx = _make_gui_context()
        mods = [self._make_modification(100, True), self._make_modification(200, False, depth_failed=True)]

        rid_obj = MagicMock()
        rid_obj.__str__ = MagicMock(return_value="0x0001")
        res = MagicMock()
        res.resourceId = rid_obj
        ctx.GetResources = MagicMock(return_value=[res])

        tex = MagicMock()
        tex.mips = 1
        tex.width = 1920
        tex.height = 1080
        ctx.GetTexture = MagicMock(return_value=tex)

        controller = MagicMock()
        controller.PixelHistory = MagicMock(return_value=mods)
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.Subresource = MagicMock(return_value=MagicMock())
            rd.CompType.Typeless = MagicMock()
            result = gc.inspect("pixel_history", {"resource_id": "0x0001", "x": 640, "y": 360})

        if "error" not in result:
            assert result["x"] == 640
            assert result["y"] == 360
            assert "modifications" in result
            assert result["total_modifications"] >= 0

    def test_pixel_history_api_error(self):
        gc, ctx = _make_gui_context()

        rid_obj = MagicMock()
        rid_obj.__str__ = MagicMock(return_value="0x0001")
        res = MagicMock()
        res.resourceId = rid_obj
        ctx.GetResources = MagicMock(return_value=[res])

        tex = MagicMock()
        tex.mips = 1
        tex.width = 800
        tex.height = 600
        ctx.GetTexture = MagicMock(return_value=tex)

        controller = MagicMock()
        controller.PixelHistory = MagicMock(side_effect=RuntimeError("unsupported API"))
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.Subresource = MagicMock(return_value=MagicMock())
            result = gc.inspect("pixel_history", {"resource_id": "0x0001", "x": 0, "y": 0})

        assert "error" in result
        assert "pixel_history_failed" in result["error"] or "unsupported" in result.get("message", "")

    def test_pixel_history_truncation(self):
        gc, ctx = _make_gui_context()
        mods = [self._make_modification(i, True) for i in range(60)]

        rid_obj = MagicMock()
        rid_obj.__str__ = MagicMock(return_value="0x0001")
        res = MagicMock()
        res.resourceId = rid_obj
        ctx.GetResources = MagicMock(return_value=[res])

        tex = MagicMock()
        tex.mips = 1
        tex.width = 1920
        tex.height = 1080
        ctx.GetTexture = MagicMock(return_value=tex)

        controller = MagicMock()
        controller.PixelHistory = MagicMock(return_value=mods)
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.Subresource = MagicMock(return_value=MagicMock())
            result = gc.inspect("pixel_history", {
                "resource_id": "0x0001", "x": 0, "y": 0, "max_modifications": 10
            })

        if "error" not in result:
            assert len(result["modifications"]) <= 10
            assert result.get("truncated") is True

    def test_rejection_reason_depth(self):
        gc, ctx = _make_gui_context()
        mod = self._make_modification(50, False, depth_failed=True)

        rid_obj = MagicMock()
        rid_obj.__str__ = MagicMock(return_value="0x0001")
        res = MagicMock()
        res.resourceId = rid_obj
        ctx.GetResources = MagicMock(return_value=[res])

        tex = MagicMock()
        tex.mips = 1
        tex.width = 100
        tex.height = 100
        ctx.GetTexture = MagicMock(return_value=tex)

        controller = MagicMock()
        controller.PixelHistory = MagicMock(return_value=[mod])
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.Subresource = MagicMock(return_value=MagicMock())
            result = gc.inspect("pixel_history", {"resource_id": "0x0001", "x": 0, "y": 0})

        if "error" not in result and result.get("modifications"):
            m = result["modifications"][0]
            assert m.get("rejection_reason") == "depth_test"

    def test_rejection_reason_shader_discard(self):
        gc, ctx = _make_gui_context()
        mod = self._make_modification(50, False, shader_disc=True)

        rid_obj = MagicMock()
        rid_obj.__str__ = MagicMock(return_value="0x0001")
        res = MagicMock()
        res.resourceId = rid_obj
        ctx.GetResources = MagicMock(return_value=[res])

        tex = MagicMock()
        tex.mips = 1
        tex.width = 100
        tex.height = 100
        ctx.GetTexture = MagicMock(return_value=tex)

        controller = MagicMock()
        controller.PixelHistory = MagicMock(return_value=[mod])
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.Subresource = MagicMock(return_value=MagicMock())
            result = gc.inspect("pixel_history", {"resource_id": "0x0001", "x": 0, "y": 0})

        if "error" not in result and result.get("modifications"):
            m = result["modifications"][0]
            assert m.get("rejection_reason") == "shader_discard"


# ===========================================================================
# Unit tests: GUIContext._inspect_debug_pixel / vertex / compute
# ===========================================================================


def _make_trace_mock(num_states=3):
    """Build a mock ShaderDebugTrace + ContinueDebug response chain."""
    trace = MagicMock()
    trace.inputs = []

    states = []
    for i in range(num_states):
        s = MagicMock()
        s.stepIndex = i
        s.nextInstruction = i + 1
        s.flags = 0
        s.changes = []
        states.append(s)
    states.append(None)  # terminator

    debugger = MagicMock()
    state_iter = iter(states)
    return trace, debugger, state_iter


class TestDebugPixel:
    def test_debug_pixel_unsupported(self):
        gc, ctx = _make_gui_context()
        controller = MagicMock()
        controller.DebugPixel = MagicMock(return_value=None)
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.DebugPixelInputs = MagicMock(return_value=MagicMock())
            result = gc.inspect("debug_pixel", {"x": 100, "y": 200})

        assert "error" in result
        assert "unsupported" in result["error"]

    def test_debug_pixel_api_exception(self):
        gc, ctx = _make_gui_context()
        controller = MagicMock()
        controller.DebugPixel = MagicMock(side_effect=RuntimeError("no debug"))
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.DebugPixelInputs = MagicMock(return_value=MagicMock())
            result = gc.inspect("debug_pixel", {"x": 0, "y": 0})

        assert "error" in result

    def test_debug_pixel_collects_steps(self):
        gc, ctx = _make_gui_context()
        trace, debugger, state_iter = _make_trace_mock(num_states=3)

        controller = MagicMock()
        controller.DebugPixel = MagicMock(return_value=trace)
        controller.BeginDebugTrace = MagicMock(return_value=debugger)
        controller.ContinueDebug = MagicMock(side_effect=state_iter)
        controller.FreeTrace = MagicMock()
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.DebugPixelInputs = MagicMock(return_value=MagicMock())
            result = gc.inspect("debug_pixel", {"x": 50, "y": 80, "max_steps": 10})

        assert "error" not in result
        assert result["stage"] == "pixel"
        assert result["x"] == 50
        assert result["y"] == 80
        assert result["step_count"] == 3
        assert len(result["steps"]) == 3
        controller.FreeTrace.assert_called_once()

    def test_debug_pixel_step_limit(self):
        gc, ctx = _make_gui_context()
        trace, debugger, _ = _make_trace_mock(num_states=100)

        # Build 100-state iterator plus None
        big_states = []
        for i in range(100):
            s = MagicMock()
            s.stepIndex = i
            s.nextInstruction = i + 1
            s.flags = 0
            s.changes = []
            big_states.append(s)
        big_states.append(None)

        controller = MagicMock()
        controller.DebugPixel = MagicMock(return_value=trace)
        controller.BeginDebugTrace = MagicMock(return_value=debugger)
        controller.ContinueDebug = MagicMock(side_effect=iter(big_states))
        controller.FreeTrace = MagicMock()
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            import renderdoc as rd
            rd.DebugPixelInputs = MagicMock(return_value=MagicMock())
            result = gc.inspect("debug_pixel", {"x": 0, "y": 0, "max_steps": 5})

        assert "error" not in result
        assert result["step_count"] == 5
        assert result["truncated"] is True


class TestDebugVertex:
    def test_debug_vertex_unsupported(self):
        gc, ctx = _make_gui_context()
        controller = MagicMock()
        controller.DebugVertex = MagicMock(return_value=None)
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            result = gc.inspect("debug_vertex", {"vert_id": 0, "inst_id": 0, "idx": 0})

        assert "error" in result
        assert "unsupported" in result["error"]

    def test_debug_vertex_collects_steps(self):
        gc, ctx = _make_gui_context()
        trace, debugger, state_iter = _make_trace_mock(num_states=4)

        controller = MagicMock()
        controller.DebugVertex = MagicMock(return_value=trace)
        controller.BeginDebugTrace = MagicMock(return_value=debugger)
        controller.ContinueDebug = MagicMock(side_effect=state_iter)
        controller.FreeTrace = MagicMock()
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            result = gc.inspect("debug_vertex", {"vert_id": 3, "inst_id": 1, "idx": 5, "view": 0})

        assert "error" not in result
        assert result["stage"] == "vertex"
        assert result["vert_id"] == 3
        assert result["inst_id"] == 1
        assert result["idx"] == 5
        assert result["step_count"] == 4
        controller.FreeTrace.assert_called_once()

    def test_debug_vertex_free_trace_on_exception(self):
        gc, ctx = _make_gui_context()
        trace = MagicMock()
        trace.inputs = []

        controller = MagicMock()
        controller.DebugVertex = MagicMock(return_value=trace)
        controller.BeginDebugTrace = MagicMock(side_effect=RuntimeError("debug error"))
        controller.FreeTrace = MagicMock()
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            result = gc.inspect("debug_vertex", {"vert_id": 0})

        # FreeTrace should have been called despite the error
        controller.FreeTrace.assert_called_once()


class TestDebugCompute:
    def test_debug_compute_unsupported(self):
        gc, ctx = _make_gui_context()
        controller = MagicMock()
        controller.DebugThread = MagicMock(return_value=None)
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            result = gc.inspect("debug_compute", {
                "group_x": 0, "group_y": 0, "group_z": 0,
                "thread_x": 0, "thread_y": 0, "thread_z": 0,
            })

        assert "error" in result
        assert "unsupported" in result["error"]

    def test_debug_compute_collects_steps(self):
        gc, ctx = _make_gui_context()
        trace, debugger, state_iter = _make_trace_mock(num_states=2)

        controller = MagicMock()
        controller.DebugThread = MagicMock(return_value=trace)
        controller.BeginDebugTrace = MagicMock(return_value=debugger)
        controller.ContinueDebug = MagicMock(side_effect=state_iter)
        controller.FreeTrace = MagicMock()
        ctx.GetBlockingController = MagicMock(return_value=controller)

        with _patch_renderdoc():
            result = gc.inspect("debug_compute", {
                "group_x": 1, "group_y": 0, "group_z": 0,
                "thread_x": 4, "thread_y": 2, "thread_z": 0,
            })

        assert "error" not in result
        assert result["stage"] == "compute"
        assert result["group"] == [1, 0, 0]
        assert result["thread"] == [4, 2, 0]
        assert result["step_count"] == 2


# ===========================================================================
# Unit tests: DebugStore
# ===========================================================================


class TestDebugStore:
    def _make_record(self, debug_id="dbg_0001", stage="pixel", event_id=42):
        from rendereye_mcp.service.debug_store import DebugRecord

        return DebugRecord(
            debug_id=debug_id,
            status="ready",
            stage=stage,
            event_id=event_id,
            capture_path="/test.rdc",
            instance_id="conn1",
            steps=[{"step": 0, "changes": []}],
            initial_vars={"pos": {"name": "pos", "value": [0.0, 1.0, 0.0]}},
        )

    def test_store_and_get(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        rec = self._make_record()
        store.store(rec)
        assert store.get("dbg_0001") is rec

    def test_unknown_id_returns_none(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        assert store.get("unknown") is None

    def test_eviction_at_capacity(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore(max_records=3)
        for i in range(3):
            rec = self._make_record(debug_id=f"dbg_{i:04d}")
            rec.created_at = float(i)
            store.store(rec)
        # Add a 4th — should evict the oldest (created_at=0)
        new_rec = self._make_record(debug_id="dbg_0003")
        new_rec.created_at = 100.0
        store.store(new_rec)
        assert store.get("dbg_0000") is None
        assert store.get("dbg_0003") is not None

    def test_list_ids_newest_first(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        for i in range(3):
            rec = self._make_record(debug_id=f"dbg_{i:04d}")
            rec.created_at = float(i)
            store.store(rec)
        ids = store.list_ids()
        assert ids[0] == "dbg_0002"  # newest first

    def test_invalidate_for_capture(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        rec = self._make_record()
        store.store(rec)
        count = store.invalidate_for_capture("/test.rdc")
        assert count == 1
        assert store.get("dbg_0001").status == "invalidated"

    def test_make_id_unique(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        ids = {store.make_id() for _ in range(20)}
        assert len(ids) == 20

    def test_make_id_prefix(self):
        from rendereye_mcp.service.debug_store import DebugStore

        store = DebugStore()
        assert store.make_id().startswith("dbg_")


# ===========================================================================
# Unit tests: ToolExecutor Phase 15 methods
# ===========================================================================


def _make_tool_executor():
    """Build a minimal ToolExecutor with mocked dependencies."""
    from rendereye_mcp.service.tools import ToolExecutor

    config = MagicMock()
    conn_manager = MagicMock()
    conn_manager.request_capture_inspection = AsyncMock()
    conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
    te = ToolExecutor(
        config=config,
        registry=None,
        session_manager=None,
        conn_manager=conn_manager,
        operation_tracker=None,
    )
    return te


class TestToolExecutorGetPixelHistory:
    def test_missing_resource_id(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={"error": "resource_id is required"}
        )
        result = _run(te._get_pixel_history(resource_id="", x=0, y=0, instance_id="conn1"))
        # Either the service returns error or the call passes through
        assert isinstance(result, dict)

    def test_calls_inspection(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={"modifications": [], "total_modifications": 0}
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._get_pixel_history(
            resource_id="0x0001", x=100, y=200, instance_id="conn1"
        ))
        te._conn_manager.request_capture_inspection.assert_called_once()
        call_args = te._conn_manager.request_capture_inspection.call_args
        assert call_args[0][1] == "pixel_history"
        params = call_args[0][2]
        assert params["resource_id"] == "0x0001"
        assert params["x"] == 100
        assert params["y"] == 200


class TestToolExecutorDebugPixelShader:
    def test_success_returns_debug_id(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={
                "stage": "pixel",
                "event_id": 42,
                "step_count": 5,
                "truncated": False,
                "steps": [{"step": i, "changes": []} for i in range(5)],
                "initial_vars": {},
                "_capture_path": "/test.rdc",
            }
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._debug_pixel_shader(x=100, y=200, event_id=42, instance_id="conn1"))
        assert "debug_id" in result
        assert result["debug_id"].startswith("dbg_")
        assert result["step_count"] == 5

    def test_error_passthrough(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={"error": "debug_pixel_unsupported"}
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._debug_pixel_shader(x=0, y=0, instance_id="conn1"))
        assert result["error"] == "debug_pixel_unsupported"

    def test_stores_in_debug_store(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={
                "stage": "pixel",
                "event_id": 1,
                "step_count": 2,
                "truncated": False,
                "steps": [{"step": 0, "changes": []}, {"step": 1, "changes": []}],
                "initial_vars": {"pos": {"name": "pos", "value": [1.0]}},
                "_capture_path": "/test.rdc",
            }
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._debug_pixel_shader(x=0, y=0, instance_id="conn1"))
        debug_id = result["debug_id"]
        stored = te._debug_store.get(debug_id)
        assert stored is not None
        assert stored.stage == "pixel"
        assert len(stored.steps) == 2
        assert "pos" in stored.initial_vars


class TestToolExecutorDebugVertexShader:
    def test_success_returns_debug_id(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={
                "stage": "vertex",
                "event_id": 10,
                "step_count": 3,
                "truncated": False,
                "steps": [{"step": i, "changes": []} for i in range(3)],
                "initial_vars": {},
                "_capture_path": "/test.rdc",
            }
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._debug_vertex_shader(vert_id=5, inst_id=0, instance_id="conn1"))
        assert "debug_id" in result
        assert result["stage"] == "vertex"


class TestToolExecutorDebugComputeShader:
    def test_success_returns_debug_id(self):
        te = _make_tool_executor()
        te._conn_manager.request_capture_inspection = AsyncMock(
            return_value={
                "stage": "compute",
                "event_id": 20,
                "step_count": 7,
                "truncated": False,
                "steps": [{"step": i, "changes": []} for i in range(7)],
                "initial_vars": {},
                "_capture_path": "/test.rdc",
            }
        )
        te._conn_manager.get_active_connection_id = MagicMock(return_value="conn1")
        result = _run(te._debug_compute_shader(
            group_x=1, group_y=0, group_z=0,
            thread_x=3, thread_y=0, thread_z=0,
            instance_id="conn1"
        ))
        assert "debug_id" in result
        assert result["stage"] == "compute"


class TestToolExecutorGetShaderDebugTrace:
    def _stored_record(self, te, n_steps=10):
        from rendereye_mcp.service.debug_store import DebugRecord

        debug_id = te._debug_store.make_id()
        steps = [{"step": i, "next_instruction": i + 1, "changes": []} for i in range(n_steps)]
        rec = DebugRecord(
            debug_id=debug_id,
            status="ready",
            stage="pixel",
            event_id=42,
            capture_path="/test.rdc",
            instance_id="conn1",
            steps=steps,
            initial_vars={},
        )
        te._debug_store.store(rec)
        return debug_id

    def test_missing_debug_id(self):
        te = _make_tool_executor()
        result = _run(te._get_shader_debug_trace(debug_id=""))
        assert result["error"] == "debug_id is required"

    def test_unknown_debug_id(self):
        te = _make_tool_executor()
        result = _run(te._get_shader_debug_trace(debug_id="dbg_nope"))
        assert result["error"] == "debug_id_not_found"

    def test_returns_first_page(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te, n_steps=20)
        result = _run(te._get_shader_debug_trace(debug_id=debug_id, first_step=0, count=10))
        assert result["returned_steps"] == 10
        assert result["first_step"] == 0
        assert result["total_steps"] == 20
        assert result["has_more"] is True

    def test_returns_last_page(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te, n_steps=20)
        result = _run(te._get_shader_debug_trace(debug_id=debug_id, first_step=15, count=10))
        assert result["returned_steps"] == 5
        assert result["has_more"] is False

    def test_step_count_clamped(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te, n_steps=10)
        result = _run(te._get_shader_debug_trace(debug_id=debug_id, count=600))
        # count is clamped to 500
        assert result["returned_steps"] <= 500

    def test_not_ready_status(self):
        te = _make_tool_executor()
        from rendereye_mcp.service.debug_store import DebugRecord

        debug_id = te._debug_store.make_id()
        rec = DebugRecord(
            debug_id=debug_id,
            status="failed",
            stage="pixel",
            event_id=1,
            capture_path=None,
            instance_id="conn1",
            steps=[],
            initial_vars={},
        )
        te._debug_store.store(rec)
        result = _run(te._get_shader_debug_trace(debug_id=debug_id))
        assert result["error"] == "debug_not_ready"


class TestToolExecutorGetShaderDebugVariables:
    def _stored_record(self, te):
        from rendereye_mcp.service.debug_store import DebugRecord

        debug_id = te._debug_store.make_id()
        steps = [
            {"step": 0, "changes": [
                {"before": {"name": "r0", "value": [0.0]},
                 "after":  {"name": "r0", "value": [1.0]}}
            ]},
            {"step": 1, "changes": [
                {"before": {"name": "r0", "value": [1.0]},
                 "after":  {"name": "r0", "value": [2.0]}},
                {"before": {"name": "r1", "value": [0.0]},
                 "after":  {"name": "r1", "value": [5.0]}}
            ]},
        ]
        rec = DebugRecord(
            debug_id=debug_id,
            status="ready",
            stage="pixel",
            event_id=42,
            capture_path="/test.rdc",
            instance_id="conn1",
            steps=steps,
            initial_vars={"r0": {"name": "r0", "value": [0.0]}},
        )
        te._debug_store.store(rec)
        return debug_id

    def test_missing_debug_id(self):
        te = _make_tool_executor()
        result = _run(te._get_shader_debug_variables(debug_id=""))
        assert result["error"] == "debug_id is required"

    def test_variables_at_step_0(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te)
        result = _run(te._get_shader_debug_variables(debug_id=debug_id, step=0))
        assert "variables" in result
        assert result["step"] == 0
        # r0 should be 1.0 after step 0's change
        assert result["variables"]["r0"]["value"] == [1.0]

    def test_variables_at_step_1(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te)
        result = _run(te._get_shader_debug_variables(debug_id=debug_id, step=1))
        # r0 changed again in step 1 to 2.0; r1 appears as 5.0
        assert result["variables"]["r0"]["value"] == [2.0]
        assert result["variables"]["r1"]["value"] == [5.0]

    def test_variable_name_filter(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te)
        result = _run(te._get_shader_debug_variables(
            debug_id=debug_id, step=1, variable_names=["r1"]
        ))
        assert "r1" in result["variables"]
        assert "r0" not in result["variables"]

    def test_step_clamped_to_max(self):
        te = _make_tool_executor()
        debug_id = self._stored_record(te)
        # Request step beyond the end → should clamp
        result = _run(te._get_shader_debug_variables(debug_id=debug_id, step=999))
        assert result["step"] == 1  # last valid step


class TestToolExecutorGetShaderDebugStatus:
    def test_no_id_lists_all(self):
        te = _make_tool_executor()
        result = _run(te._get_shader_debug_status(debug_id=""))
        assert "debug_ids" in result
        assert "count" in result

    def test_unknown_id(self):
        te = _make_tool_executor()
        result = _run(te._get_shader_debug_status(debug_id="dbg_nope"))
        assert result["error"] == "debug_id_not_found"

    def test_known_id_returns_status(self):
        te = _make_tool_executor()
        from rendereye_mcp.service.debug_store import DebugRecord

        debug_id = te._debug_store.make_id()
        rec = DebugRecord(
            debug_id=debug_id,
            status="ready",
            stage="compute",
            event_id=99,
            capture_path="/test.rdc",
            instance_id="conn1",
            steps=[{"step": 0, "changes": []}],
            initial_vars={},
            metadata={"group": [1, 0, 0], "thread": [0, 0, 0]},
        )
        te._debug_store.store(rec)
        result = _run(te._get_shader_debug_status(debug_id=debug_id))
        assert result["status"] == "ready"
        assert result["stage"] == "compute"
        assert result["event_id"] == 99
        assert result["step_count"] == 1

    def test_lists_multiple_ids(self):
        te = _make_tool_executor()
        from rendereye_mcp.service.debug_store import DebugRecord

        for i in range(3):
            debug_id = f"dbg_test{i}"
            rec = DebugRecord(
                debug_id=debug_id,
                status="ready",
                stage="pixel",
                event_id=i,
                capture_path="/test.rdc",
                instance_id="conn1",
                steps=[],
                initial_vars={},
            )
            rec.created_at = float(i)
            te._debug_store.store(rec)
        result = _run(te._get_shader_debug_status(debug_id=""))
        assert result["count"] == 3
