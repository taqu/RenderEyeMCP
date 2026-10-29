"""Tests for Phase 14 — Geometry & Mesh Inspection.

Covers:
- _comp_type_str: enum-to-string conversion helper
- _decode_vertex_attr: binary vertex attribute decoder
- GUIContext._inspect_draw_geometry_info
- GUIContext._inspect_vertex_input_layout
- GUIContext._inspect_mesh_indices
- GUIContext._inspect_mesh_vertices
- GUIContext._inspect_post_vs_geometry
- GUIContext._inspect_mesh_statistics
"""

from __future__ import annotations

import math
import struct
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants mirrored from gui_context (tested indirectly, but used to verify
# clamping behaviour).
# ---------------------------------------------------------------------------
_FLAG_DRAWCALL = 2
_FLAG_INDEXED = 8192
_FLAG_INSTANCED = 16384
_FLAG_INDIRECT = 4096

# ---------------------------------------------------------------------------
# Module-level renderdoc mock — injected once so that the import of
# gui_context itself never tries to load the real extension.
# ---------------------------------------------------------------------------
_RD_MOCK = MagicMock()
_RD_MOCK.ResourceId.Null.return_value = MagicMock(__str__=lambda s: "ResourceId::Null()")


def _patch_renderdoc():
    """Return a context manager that injects the fake renderdoc module."""
    return patch.dict(sys.modules, {"renderdoc": _RD_MOCK})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_context(loaded=True, path="/test.rdc", cur_event=1):
    ctx = MagicMock()
    ctx.IsCaptureLoaded = MagicMock(return_value=loaded)
    ctx.IsCaptureLoading = MagicMock(return_value=False)
    ctx.GetCaptureFilename = MagicMock(return_value=path)
    ctx.Extensions = MagicMock(return_value=[])
    ctx.CurEvent = MagicMock(return_value=cur_event)
    ctx.GetResources = MagicMock(return_value=[])
    return ctx


def _make_gui(ctx=None, cur_event=1):
    """Construct a GUIContext with a fake ctx and mark it on the current thread."""
    with _patch_renderdoc():
        from extensions.rendereye.gui_context import GUIContext

        if ctx is None:
            ctx = _mock_context(cur_event=cur_event)
        gui = GUIContext(ctx, "1.45")
        gui.thread_id = threading.get_ident()
    return gui, ctx


def _make_draw_action(flags=_FLAG_DRAWCALL, num_indices=6, num_instances=1,
                      base_vertex=0, index_offset=0, event_id=1):
    """Create a mock action that looks like a draw call."""
    action = MagicMock()
    action.flags = flags
    action.numIndices = num_indices
    action.numInstances = num_instances
    action.baseVertex = base_vertex
    action.indexOffset = index_offset
    action.eventId = event_id
    action.customName = ""
    return action


def _make_pipeline(topology_name="TriangleList", vbufs=None, ibuf=None, inputs=None):
    """Create a mock pipeline state."""
    pipe = MagicMock()
    topo = MagicMock()
    topo.name = topology_name
    pipe.GetPrimitiveTopology.return_value = topo
    pipe.GetVBuffers.return_value = vbufs or []
    pipe.GetIBuffer.return_value = ibuf
    pipe.GetVertexInputs.return_value = inputs or []
    pipe.GetShaderReflection.return_value = None
    return pipe


def _make_vbuf(resource_id_str="ResourceId::1", byte_offset=0, byte_stride=12):
    vb = MagicMock()
    vb.resourceId = MagicMock(__str__=lambda s: resource_id_str)
    vb.byteOffset = byte_offset
    vb.byteStride = byte_stride
    return vb


def _make_ibuf(resource_id_str="ResourceId::2", byte_offset=0, byte_stride=2):
    ib = MagicMock()
    ib.resourceId = MagicMock(__str__=lambda s: resource_id_str)
    ib.byteOffset = byte_offset
    ib.byteStride = byte_stride
    return ib


def _make_vertex_input(name, vb_slot=0, byte_offset=0, comp_type_str="Float",
                       comp_count=3, comp_bw=4, per_instance=False):
    """Create a mock vertex input attribute descriptor."""
    inp = MagicMock()
    inp.name = name
    inp.vertexBuffer = vb_slot
    inp.byteOffset = byte_offset
    inp.perInstance = per_instance
    inp.instanceRate = 1
    inp.location = 0
    fmt = MagicMock()
    ct = MagicMock()
    ct.__str__ = lambda s: ("CompType." + comp_type_str)
    fmt.compType = ct
    fmt.compCount = comp_count
    fmt.compByteWidth = comp_bw
    fmt.type = MagicMock()
    inp.format = fmt
    return inp


# ===========================================================================
# 1. _comp_type_str
# ===========================================================================


class TestCompTypeStr:
    def _fn(self):
        with _patch_renderdoc():
            from extensions.rendereye.gui_context import _comp_type_str
            return _comp_type_str

    def test_strips_class_prefix_float(self):
        fn = self._fn()
        ct = MagicMock(__str__=lambda s: "CompType.Float")
        assert fn(ct) == "Float"

    def test_strips_class_prefix_uint(self):
        fn = self._fn()
        ct = MagicMock(__str__=lambda s: "CompType.UInt")
        assert fn(ct) == "UInt"

    def test_strips_class_prefix_unorm(self):
        fn = self._fn()
        ct = MagicMock(__str__=lambda s: "CompType.UNorm")
        assert fn(ct) == "UNorm"

    def test_strips_class_prefix_snorm(self):
        fn = self._fn()
        ct = MagicMock(__str__=lambda s: "CompType.SNorm")
        assert fn(ct) == "SNorm"

    def test_no_dot_returns_string_as_is(self):
        fn = self._fn()
        # plain string without a dot
        assert fn("Float") == "Float"

    def test_no_dot_arbitrary_string(self):
        fn = self._fn()
        assert fn("Unknown") == "Unknown"

    def test_handles_exception_from_str(self):
        fn = self._fn()
        bad = MagicMock()
        bad.__str__ = MagicMock(side_effect=RuntimeError("boom"))
        result = fn(bad)
        assert result == "Unknown"

    def test_multi_dot_uses_last_segment(self):
        fn = self._fn()
        ct = MagicMock(__str__=lambda s: "module.CompType.Double")
        assert fn(ct) == "Double"


# ===========================================================================
# 2. _decode_vertex_attr
# ===========================================================================


class TestDecodeVertexAttr:
    def _fn(self):
        with _patch_renderdoc():
            from extensions.rendereye.gui_context import _decode_vertex_attr
            return _decode_vertex_attr

    # --- Float32 ---

    def test_float32_single_component(self):
        fn = self._fn()
        data = struct.pack("<f", 3.14)
        result = fn(data, 0, "Float", 4, 1)
        assert result is not None
        assert len(result) == 1
        assert result[0] == pytest.approx(3.14, abs=1e-5)

    def test_float32_three_components(self):
        fn = self._fn()
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        result = fn(data, 0, "Float", 4, 3)
        assert result == pytest.approx([1.0, 2.0, 3.0], abs=1e-5)

    def test_float32_four_components(self):
        fn = self._fn()
        data = struct.pack("<ffff", 0.5, 1.5, 2.5, 3.5)
        result = fn(data, 0, "Float", 4, 4)
        assert result == pytest.approx([0.5, 1.5, 2.5, 3.5], abs=1e-5)

    def test_float32_with_byte_offset(self):
        fn = self._fn()
        # 4 bytes padding, then float
        data = struct.pack("<If", 0xDEADBEEF, 7.0)
        result = fn(data, 4, "Float", 4, 1)
        assert result == pytest.approx([7.0], abs=1e-5)

    # --- Float16 ---

    def test_float16_single_component(self):
        fn = self._fn()
        val = 1.5
        data = struct.pack("<e", val)
        result = fn(data, 0, "Float", 2, 1)
        assert result is not None
        assert result[0] == pytest.approx(val, abs=0.01)

    def test_float16_two_components(self):
        fn = self._fn()
        data = struct.pack("<ee", 1.0, 2.0)
        result = fn(data, 0, "Float", 2, 2)
        assert result is not None
        assert len(result) == 2
        assert result[0] == pytest.approx(1.0, abs=0.01)
        assert result[1] == pytest.approx(2.0, abs=0.01)

    # --- UInt32 ---

    def test_uint32_single(self):
        fn = self._fn()
        data = struct.pack("<I", 42)
        result = fn(data, 0, "UInt", 4, 1)
        assert result == [42]

    def test_uint8_single(self):
        fn = self._fn()
        data = struct.pack("<B", 255)
        result = fn(data, 0, "UInt", 1, 1)
        assert result == [255]

    # --- UNorm ---

    def test_unorm8_zero(self):
        fn = self._fn()
        data = struct.pack("<B", 0)
        result = fn(data, 0, "UNorm", 1, 1)
        assert result is not None
        assert result[0] == pytest.approx(0.0)

    def test_unorm8_full(self):
        fn = self._fn()
        data = struct.pack("<B", 255)
        result = fn(data, 0, "UNorm", 1, 1)
        assert result is not None
        assert result[0] == pytest.approx(1.0)

    def test_unorm8_midpoint(self):
        fn = self._fn()
        data = struct.pack("<B", 128)
        result = fn(data, 0, "UNorm", 1, 1)
        assert result is not None
        assert 0.49 < result[0] < 0.51

    def test_unorm_four_components(self):
        fn = self._fn()
        data = struct.pack("<BBBB", 255, 0, 128, 64)
        result = fn(data, 0, "UNorm", 1, 4)
        assert result is not None
        assert len(result) == 4
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)

    # --- SNorm ---

    def test_snorm8_max_positive(self):
        fn = self._fn()
        data = struct.pack("<b", 127)
        result = fn(data, 0, "SNorm", 1, 1)
        assert result is not None
        assert result[0] == pytest.approx(1.0, abs=0.01)

    def test_snorm8_most_negative(self):
        fn = self._fn()
        data = struct.pack("<b", -128)
        result = fn(data, 0, "SNorm", 1, 1)
        assert result is not None
        # clamped to -1.0
        assert result[0] == pytest.approx(-1.0, abs=0.02)

    def test_snorm8_zero(self):
        fn = self._fn()
        data = struct.pack("<b", 0)
        result = fn(data, 0, "SNorm", 1, 1)
        assert result is not None
        assert result[0] == pytest.approx(0.0)

    # --- NaN / inf via _json_safe_float ---

    def test_nan_float_returns_string_nan(self):
        fn = self._fn()
        data = struct.pack("<f", float("nan"))
        result = fn(data, 0, "Float", 4, 1)
        assert result is not None
        assert result[0] == "nan"

    def test_inf_float_returns_string_inf(self):
        fn = self._fn()
        data = struct.pack("<f", float("inf"))
        result = fn(data, 0, "Float", 4, 1)
        assert result is not None
        assert result[0] == "inf"

    def test_neg_inf_float_returns_string_neg_inf(self):
        fn = self._fn()
        data = struct.pack("<f", float("-inf"))
        result = fn(data, 0, "Float", 4, 1)
        assert result is not None
        assert result[0] == "-inf"

    # --- Insufficient data ---

    def test_returns_none_when_data_too_short(self):
        fn = self._fn()
        data = struct.pack("<f", 1.0)  # 4 bytes
        # Request 2 floats starting at offset 0 → needs 8 bytes
        result = fn(data, 0, "Float", 4, 2)
        assert result is None

    def test_returns_none_when_offset_out_of_bounds(self):
        fn = self._fn()
        data = struct.pack("<f", 1.0)  # 4 bytes
        result = fn(data, 8, "Float", 4, 1)
        assert result is None

    def test_returns_none_when_empty_data(self):
        fn = self._fn()
        result = fn(b"", 0, "Float", 4, 1)
        assert result is None

    # --- SInt ---

    def test_sint32_negative(self):
        fn = self._fn()
        data = struct.pack("<i", -1000)
        result = fn(data, 0, "SInt", 4, 1)
        assert result == [-1000]


# ===========================================================================
# 3. _inspect_draw_geometry_info
# ===========================================================================


class TestDrawGeometryInfo:
    def test_not_a_draw_when_flags_not_draw(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=0)  # no draw flag
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("error") == "not_a_draw"

    def test_event_not_selected_when_id_differs(self):
        gui, ctx = _make_gui(cur_event=5)
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"
        assert result.get("current_event_id") == 5

    def test_event_id_zero_passes_event_check(self):
        gui, ctx = _make_gui(cur_event=5)
        action = _make_draw_action(flags=_FLAG_DRAWCALL, event_id=5)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {"event_id": 0})
        assert result.get("error") is None

    def test_returns_is_indexed_false_for_non_indexed(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("is_indexed") is False

    def test_returns_is_indexed_true_for_indexed_draw(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL | _FLAG_INDEXED)
        ctx.CurAction.return_value = action
        ibuf = _make_ibuf()
        pipe = _make_pipeline(ibuf=ibuf)
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("is_indexed") is True

    def test_returns_is_instanced(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL | _FLAG_INSTANCED, num_instances=4)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("is_instanced") is True
        assert result.get("num_instances") == 4

    def test_returns_num_indices(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL, num_indices=24)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("num_indices") == 24

    def test_returns_topology_from_pipeline(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline(topology_name="TriangleList")
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert result.get("topology") == "TriangleList"

    def test_returns_vertex_buffer_bindings(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL)
        ctx.CurAction.return_value = action
        vb = _make_vbuf(resource_id_str="ResourceId::10", byte_stride=32)
        ctx.CurPipelineState.return_value = _make_pipeline(vbufs=[vb])
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        vbufs = result.get("vertex_buffers", [])
        assert len(vbufs) == 1
        assert vbufs[0]["slot"] == 0
        assert vbufs[0]["byte_stride"] == 32

    def test_returns_index_buffer_when_indexed(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL | _FLAG_INDEXED)
        ctx.CurAction.return_value = action
        ibuf = _make_ibuf(resource_id_str="ResourceId::5", byte_stride=4)
        pipe = _make_pipeline(ibuf=ibuf)
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert "index_buffer" in result
        assert result["index_buffer"]["byte_stride"] == 4

    def test_no_index_buffer_key_when_non_indexed(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=_FLAG_DRAWCALL)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_draw_geometry_info(ctx, {})
        assert "index_buffer" not in result


# ===========================================================================
# 4. _inspect_vertex_input_layout
# ===========================================================================


class TestVertexInputLayout:
    def test_event_not_selected_when_id_differs(self):
        gui, ctx = _make_gui(cur_event=3)
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"

    def test_no_pipeline_state_returns_error(self):
        gui, ctx = _make_gui()
        ctx.CurPipelineState.return_value = None
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {})
        assert result.get("error") == "no_pipeline_state"

    def test_returns_attribute_list(self):
        gui, ctx = _make_gui()
        inp = _make_vertex_input("POSITION", comp_type_str="Float", comp_count=3, comp_bw=4)
        pipe = _make_pipeline(inputs=[inp])
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {})
        assert result.get("attribute_count") == 1
        assert result["attributes"][0]["name"] == "POSITION"
        assert result["attributes"][0]["component_type"] == "Float"
        assert result["attributes"][0]["component_count"] == 3

    def test_empty_input_layout_returns_zero_attrs(self):
        gui, ctx = _make_gui()
        pipe = _make_pipeline(inputs=[])
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {})
        assert result.get("attribute_count") == 0
        assert result.get("attributes") == []

    def test_returns_vertex_buffers_from_pipeline(self):
        gui, ctx = _make_gui()
        vb = _make_vbuf(resource_id_str="ResourceId::7", byte_stride=16)
        pipe = _make_pipeline(vbufs=[vb])
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {})
        vbufs = result.get("vertex_buffers", [])
        assert len(vbufs) == 1
        assert vbufs[0]["byte_stride"] == 16

    def test_vs_input_signature_when_reflection_available(self):
        gui, ctx = _make_gui()
        pipe = _make_pipeline()

        sig = MagicMock()
        sig.semanticName = "POSITION"
        sig.semanticIndex = 0
        sig.regIndex = 0
        sig.compMask = 0b0111
        ct = MagicMock(__str__=lambda s: "CompType.Float")
        sig.compType = ct
        sv = MagicMock()
        sv.name = "Undefined"
        sig.systemValue = sv

        refl = MagicMock()
        refl.inputSignature = [sig]
        pipe.GetShaderReflection.return_value = refl
        ctx.CurPipelineState.return_value = pipe

        rd_mock = MagicMock()
        rd_mock.ShaderStage.Vertex = MagicMock()
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            from extensions.rendereye.gui_context import GUIContext
            gui2 = GUIContext(ctx, "1.45")
            gui2.thread_id = threading.get_ident()
            result = gui2._inspect_vertex_input_layout(ctx, {})

        assert "vs_input_signature" in result
        assert result["vs_input_signature"][0]["semantic_name"] == "POSITION"

    def test_multiple_attributes_returned(self):
        gui, ctx = _make_gui()
        pos = _make_vertex_input("POSITION", comp_count=3)
        nrm = _make_vertex_input("NORMAL", byte_offset=12, comp_count=3)
        uv = _make_vertex_input("TEXCOORD", byte_offset=24, comp_count=2)
        pipe = _make_pipeline(inputs=[pos, nrm, uv])
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_vertex_input_layout(ctx, {})
        assert result.get("attribute_count") == 3


# ===========================================================================
# 5. _inspect_mesh_indices
# ===========================================================================


def _setup_index_read(gui, ctx, indices_bytes, stride=2, base_vertex=0):
    """Wire up ctx so that _inspect_mesh_indices can read the given raw bytes."""
    ibuf = _make_ibuf(resource_id_str="ResourceId::IB", byte_stride=stride)
    pipe = _make_pipeline(ibuf=ibuf)
    ctx.CurPipelineState.return_value = pipe

    action = _make_draw_action(flags=_FLAG_DRAWCALL | _FLAG_INDEXED, base_vertex=base_vertex)
    ctx.CurAction.return_value = action

    # Make _find_resource_id_obj return a sentinel object
    rid_sentinel = MagicMock(__str__=lambda s: "ResourceId::IB")
    resource_entry = MagicMock()
    resource_entry.resourceId = rid_sentinel
    ctx.GetResources.return_value = [resource_entry]

    controller = MagicMock()
    controller.GetBufferData.return_value = indices_bytes
    ctx.GetBlockingController.return_value = controller


class TestMeshIndices:
    def test_no_index_buffer_returns_error(self):
        gui, ctx = _make_gui()
        pipe = _make_pipeline(ibuf=None)
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {})
        assert result.get("error") == "no_index_buffer"

    def test_event_not_selected(self):
        gui, ctx = _make_gui(cur_event=5)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"

    def test_decodes_16bit_indices(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<HHH", 0, 1, 2)
        _setup_index_read(gui, ctx, raw, stride=2)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"count": 3})
        assert result.get("error") is None
        indices = result.get("indices", [])
        assert len(indices) == 3
        assert indices[0]["raw_index"] == 0
        assert indices[1]["raw_index"] == 1
        assert indices[2]["raw_index"] == 2

    def test_decodes_32bit_indices(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<III", 100, 200, 300)
        _setup_index_read(gui, ctx, raw, stride=4)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"count": 3})
        assert result.get("error") is None
        indices = result.get("indices", [])
        assert indices[0]["raw_index"] == 100
        assert indices[2]["raw_index"] == 300

    def test_applies_base_vertex_to_vertex_ref(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<H", 5)
        _setup_index_read(gui, ctx, raw, stride=2, base_vertex=10)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"count": 1})
        indices = result.get("indices", [])
        assert indices[0]["raw_index"] == 5
        assert indices[0]["vertex_ref"] == 15  # 5 + 10

    def test_respects_first_index_offset(self):
        gui, ctx = _make_gui(cur_event=1)
        # Pack indices 0,1,2,3 — first_index=2 means we start reading from index 2
        raw = struct.pack("<HHHH", 0, 1, 2, 3)
        # GetBufferData will be called with offset= buf_off + first_index*stride
        # For simplicity, return only last 2 index bytes
        ibuf = _make_ibuf(resource_id_str="ResourceId::IB", byte_stride=2)
        pipe = _make_pipeline(ibuf=ibuf)
        ctx.CurPipelineState.return_value = pipe
        action = _make_draw_action(flags=_FLAG_DRAWCALL | _FLAG_INDEXED)
        ctx.CurAction.return_value = action
        rid_sentinel = MagicMock(__str__=lambda s: "ResourceId::IB")
        re = MagicMock()
        re.resourceId = rid_sentinel
        ctx.GetResources.return_value = [re]
        controller = MagicMock()
        # Return data for the 2 indices starting at position 2
        controller.GetBufferData.return_value = struct.pack("<HH", 2, 3)
        ctx.GetBlockingController.return_value = controller
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"first_index": 2, "count": 2})
        indices = result.get("indices", [])
        assert indices[0]["position"] == 2
        assert indices[1]["position"] == 3

    def test_clamps_count_to_max_index_read(self):
        """Requesting more than _MAX_INDEX_READ (1000) indices is clamped."""
        gui, ctx = _make_gui(cur_event=1)
        # Build 1000 uint16 indices
        raw = struct.pack("<" + "H" * 1000, *range(1000))
        _setup_index_read(gui, ctx, raw, stride=2)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"count": 9999})
        # requested_count should be clamped to 1000
        assert result.get("requested_count") == 1000

    def test_returns_index_stride_in_result(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<II", 1, 2)
        _setup_index_read(gui, ctx, raw, stride=4)
        with _patch_renderdoc():
            result = gui._inspect_mesh_indices(ctx, {"count": 2})
        assert result.get("index_byte_stride") == 4


# ===========================================================================
# 6. _inspect_mesh_vertices
# ===========================================================================


def _setup_vertex_read(ctx, vertex_bytes, stride=12):
    """Wire ctx so that _inspect_mesh_vertices can decode the given raw vertex data."""
    vb = _make_vbuf(resource_id_str="ResourceId::VB", byte_stride=stride)
    pipe = _make_pipeline(vbufs=[vb])

    pos = _make_vertex_input("POSITION", vb_slot=0, byte_offset=0,
                             comp_type_str="Float", comp_count=3, comp_bw=4)
    pipe.GetVertexInputs.return_value = [pos]
    ctx.CurPipelineState.return_value = pipe

    rid_sentinel = MagicMock(__str__=lambda s: "ResourceId::VB")
    re = MagicMock()
    re.resourceId = rid_sentinel
    ctx.GetResources.return_value = [re]

    controller = MagicMock()
    controller.GetBufferData.return_value = vertex_bytes
    ctx.GetBlockingController.return_value = controller


class TestMeshVertices:
    def test_no_vertex_attributes_returns_error(self):
        gui, ctx = _make_gui()
        vb = _make_vbuf()
        pipe = _make_pipeline(vbufs=[vb])
        pipe.GetVertexInputs.return_value = []
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {})
        assert result.get("error") == "no_vertex_attributes"

    def test_event_not_selected(self):
        gui, ctx = _make_gui(cur_event=5)
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"

    def test_decodes_float32_position(self):
        gui, ctx = _make_gui(cur_event=1)
        # One vertex: POSITION(1.0, 2.0, 3.0)
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        _setup_vertex_read(ctx, raw, stride=12)
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"count": 1})
        assert result.get("error") is None
        verts = result.get("vertices", [])
        assert len(verts) == 1
        attrs = verts[0]["attributes"]
        pos = attrs.get("POSITION")
        assert pos == pytest.approx([1.0, 2.0, 3.0], abs=1e-5)

    def test_two_vertices_decoded(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<ffffff", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        _setup_vertex_read(ctx, raw, stride=12)
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"count": 2})
        verts = result.get("vertices", [])
        assert len(verts) == 2
        assert verts[0]["attributes"]["POSITION"] == pytest.approx([1.0, 2.0, 3.0], abs=1e-5)
        assert verts[1]["attributes"]["POSITION"] == pytest.approx([4.0, 5.0, 6.0], abs=1e-5)

    def test_attr_filter_includes_only_matching(self):
        gui, ctx = _make_gui(cur_event=1)
        vb = _make_vbuf(resource_id_str="ResourceId::VB", byte_stride=24)
        pos = _make_vertex_input("POSITION", vb_slot=0, byte_offset=0,
                                 comp_type_str="Float", comp_count=3, comp_bw=4)
        nrm = _make_vertex_input("NORMAL", vb_slot=0, byte_offset=12,
                                 comp_type_str="Float", comp_count=3, comp_bw=4)
        pipe = _make_pipeline(vbufs=[vb])
        pipe.GetVertexInputs.return_value = [pos, nrm]
        ctx.CurPipelineState.return_value = pipe

        rid_sentinel = MagicMock(__str__=lambda s: "ResourceId::VB")
        re = MagicMock()
        re.resourceId = rid_sentinel
        ctx.GetResources.return_value = [re]

        raw = struct.pack("<ffffff", 1.0, 2.0, 3.0, 0.0, 1.0, 0.0)
        controller = MagicMock()
        controller.GetBufferData.return_value = raw
        ctx.GetBlockingController.return_value = controller

        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"count": 1, "attributes": ["POSITION"]})
        # With only POSITION filtered in, NORMAL should not appear
        verts = result.get("vertices", [])
        assert len(verts) == 1
        assert "POSITION" in verts[0]["attributes"]
        assert "NORMAL" not in verts[0]["attributes"]

    def test_attr_filter_no_match_returns_error(self):
        gui, ctx = _make_gui(cur_event=1)
        vb = _make_vbuf(resource_id_str="ResourceId::VB", byte_stride=12)
        pos = _make_vertex_input("POSITION", comp_count=3)
        pipe = _make_pipeline(vbufs=[vb])
        pipe.GetVertexInputs.return_value = [pos]
        ctx.CurPipelineState.return_value = pipe
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"attributes": ["NONEXISTENT"]})
        assert result.get("error") == "no_matching_attributes"

    def test_skips_per_instance_attributes(self):
        gui, ctx = _make_gui(cur_event=1)
        vb = _make_vbuf(resource_id_str="ResourceId::VB", byte_stride=12)
        pos = _make_vertex_input("POSITION", vb_slot=0, byte_offset=0,
                                 comp_type_str="Float", comp_count=3, comp_bw=4)
        inst = _make_vertex_input("INSTANCE_ID", vb_slot=0, byte_offset=0,
                                  comp_type_str="UInt", comp_count=1, comp_bw=4,
                                  per_instance=True)
        pipe = _make_pipeline(vbufs=[vb])
        pipe.GetVertexInputs.return_value = [pos, inst]
        ctx.CurPipelineState.return_value = pipe

        rid_sentinel = MagicMock(__str__=lambda s: "ResourceId::VB")
        re = MagicMock()
        re.resourceId = rid_sentinel
        ctx.GetResources.return_value = [re]

        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        controller = MagicMock()
        controller.GetBufferData.return_value = raw
        ctx.GetBlockingController.return_value = controller

        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"count": 1})
        verts = result.get("vertices", [])
        assert len(verts) == 1
        attrs = verts[0]["attributes"]
        # per-instance attribute should not appear
        assert "INSTANCE_ID" not in attrs
        assert "POSITION" in attrs

    def test_first_vertex_sets_vertex_id(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<fff", 7.0, 8.0, 9.0)
        _setup_vertex_read(ctx, raw, stride=12)
        with _patch_renderdoc():
            result = gui._inspect_mesh_vertices(ctx, {"first_vertex": 10, "count": 1})
        verts = result.get("vertices", [])
        assert verts[0]["vertex_id"] == 10


# ===========================================================================
# 7. _inspect_post_vs_geometry
# ===========================================================================


class TestPostVsGeometry:
    def _setup_basic(self, gui, ctx, stage="vs_out"):
        """Wire ctx for a minimal post-VS scenario with no data."""
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        null_rid = MagicMock()
        null_rid.__str__ = lambda s: "ResourceId::Null()"
        _RD_MOCK.ResourceId.Null.return_value = null_rid

        mesh = MagicMock()
        mesh.vertexResourceId = null_rid
        mesh.numIndices = 0
        mesh.vertexByteStride = 0
        mesh.vertexByteOffset = 0
        mesh.topology = MagicMock()
        mesh.topology.name = "TriangleList"
        controller.GetPostVSData.return_value = mesh

        ctx.CurPipelineState.return_value = MagicMock()
        ctx.CurPipelineState.return_value.GetShaderReflection.return_value = None

        return controller, mesh

    def test_invalid_stage_returns_error(self):
        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller
        rd_mock = MagicMock()
        rd_mock.MeshDataStage = MagicMock()
        rd_mock.MeshDataStage.VSIn = "vs_in_enum"
        rd_mock.MeshDataStage.VSOut = "vs_out_enum"
        rd_mock.MeshDataStage.GSOut = "gs_out_enum"
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_post_vs_geometry(ctx, {"stage": "bad_stage"})
        assert result.get("error") == "invalid_stage"

    def test_event_not_selected(self):
        gui, ctx = _make_gui(cur_event=5)
        with _patch_renderdoc():
            result = gui._inspect_post_vs_geometry(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"
        assert result.get("current_event_id") == 5

    def test_no_post_vs_data_when_vertex_resource_null(self):
        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller
        ctx.CurPipelineState.return_value = MagicMock()
        ctx.CurPipelineState.return_value.GetShaderReflection.return_value = None

        null_rid = MagicMock()
        null_rid.__str__ = lambda s: "ResourceId::Null()"

        mesh = MagicMock()
        mesh.vertexResourceId = null_rid
        mesh.numIndices = 0
        mesh.vertexByteStride = 0
        controller.GetPostVSData.return_value = mesh

        rd_mock = MagicMock()
        rd_mock.MeshDataStage.VSIn = "vs_in"
        rd_mock.MeshDataStage.VSOut = "vs_out"
        rd_mock.MeshDataStage.GSOut = "gs_out"
        rd_mock.ResourceId.Null.return_value = null_rid
        rd_mock.ShaderStage = MagicMock()

        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_post_vs_geometry(ctx, {"stage": "vs_out"})
        assert result.get("error") == "no_post_vs_data"

    def test_sv_position_clip_decoded_from_data(self):
        """Verify SV_Position_clip is produced when data has real vertex buffer."""
        gui, ctx = _make_gui(cur_event=1)
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        # Build vertex data: one vertex with float4 at offset 0
        raw = struct.pack("<ffff", 0.5, 0.5, 0.1, 1.0)
        controller.GetBufferData.return_value = raw

        # Non-null resource id
        real_rid = MagicMock(__str__=lambda s: "ResourceId::99")
        mesh = MagicMock()
        mesh.vertexResourceId = real_rid
        mesh.numIndices = 1
        mesh.vertexByteStride = 16
        mesh.vertexByteOffset = 0
        mesh.topology = MagicMock()
        mesh.topology.name = "TriangleList"
        controller.GetPostVSData.return_value = mesh

        # Signature: SV_POSITION at reg 0, 4 components
        sig = MagicMock()
        sig.semanticName = "SV_POSITION"
        sig.semanticIndex = 0
        sig.regIndex = 0
        sig.compMask = 0xF
        ct = MagicMock(__str__=lambda s: "CompType.Float")
        sig.compType = ct
        sv = MagicMock()
        sv.name = "Position"
        sig.systemValue = sv

        refl = MagicMock()
        refl.outputSignature = [sig]

        pipe = MagicMock()
        pipe.GetShaderReflection.return_value = refl
        ctx.CurPipelineState.return_value = pipe

        rd_mock = MagicMock()
        rd_mock.MeshDataStage.VSIn = "vs_in"
        rd_mock.MeshDataStage.VSOut = "vs_out"
        rd_mock.MeshDataStage.GSOut = "gs_out"
        null_rid = MagicMock(__str__=lambda s: "ResourceId::Null()")
        rd_mock.ResourceId.Null.return_value = null_rid
        rd_mock.ShaderStage.Vertex = MagicMock()

        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_post_vs_geometry(ctx, {"stage": "vs_out", "max_vertices": 1})

        assert result.get("error") is None
        verts = result.get("vertices", [])
        assert len(verts) == 1
        attrs = verts[0].get("attributes", {})
        assert "SV_Position_clip" in attrs
        clip = attrs["SV_Position_clip"]
        assert clip == pytest.approx([0.5, 0.5, 0.1, 1.0], abs=1e-5)

    def test_sv_position_ndc_computed(self):
        """Verify NDC is x/w, y/w, z/w when w != 0."""
        gui, ctx = _make_gui(cur_event=1)
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        # Position (2.0, 4.0, 0.5, 2.0) → NDC (1.0, 2.0, 0.25)
        raw = struct.pack("<ffff", 2.0, 4.0, 0.5, 2.0)
        controller.GetBufferData.return_value = raw

        real_rid = MagicMock(__str__=lambda s: "ResourceId::99")
        mesh = MagicMock()
        mesh.vertexResourceId = real_rid
        mesh.numIndices = 1
        mesh.vertexByteStride = 16
        mesh.vertexByteOffset = 0
        mesh.topology = MagicMock()
        mesh.topology.name = "TriangleList"
        controller.GetPostVSData.return_value = mesh

        sig = MagicMock()
        sig.semanticName = "SV_POSITION"
        sig.semanticIndex = 0
        sig.regIndex = 0
        sig.compMask = 0xF
        ct = MagicMock(__str__=lambda s: "CompType.Float")
        sig.compType = ct
        sv = MagicMock()
        sv.name = "Position"
        sig.systemValue = sv

        refl = MagicMock()
        refl.outputSignature = [sig]
        pipe = MagicMock()
        pipe.GetShaderReflection.return_value = refl
        ctx.CurPipelineState.return_value = pipe

        rd_mock = MagicMock()
        rd_mock.MeshDataStage.VSIn = "vs_in"
        rd_mock.MeshDataStage.VSOut = "vs_out"
        rd_mock.MeshDataStage.GSOut = "gs_out"
        null_rid = MagicMock(__str__=lambda s: "ResourceId::Null()")
        rd_mock.ResourceId.Null.return_value = null_rid
        rd_mock.ShaderStage.Vertex = MagicMock()

        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_post_vs_geometry(ctx, {"stage": "vs_out", "max_vertices": 1})

        verts = result.get("vertices", [])
        attrs = verts[0].get("attributes", {})
        assert "SV_Position_ndc" in attrs
        ndc = attrs["SV_Position_ndc"]
        assert ndc == pytest.approx([1.0, 2.0, 0.25], abs=1e-5)

    def test_ndc_skipped_when_w_is_zero(self):
        """When w=0 NDC should not be computed (would be division by zero)."""
        gui, ctx = _make_gui(cur_event=1)
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        raw = struct.pack("<ffff", 1.0, 1.0, 1.0, 0.0)  # w=0
        controller.GetBufferData.return_value = raw

        real_rid = MagicMock(__str__=lambda s: "ResourceId::99")
        mesh = MagicMock()
        mesh.vertexResourceId = real_rid
        mesh.numIndices = 1
        mesh.vertexByteStride = 16
        mesh.vertexByteOffset = 0
        mesh.topology = MagicMock()
        mesh.topology.name = "TriangleList"
        controller.GetPostVSData.return_value = mesh

        sig = MagicMock()
        sig.semanticName = "SV_POSITION"
        sig.semanticIndex = 0
        sig.regIndex = 0
        sig.compMask = 0xF
        ct = MagicMock(__str__=lambda s: "CompType.Float")
        sig.compType = ct
        sv = MagicMock()
        sv.name = "Position"
        sig.systemValue = sv

        refl = MagicMock()
        refl.outputSignature = [sig]
        pipe = MagicMock()
        pipe.GetShaderReflection.return_value = refl
        ctx.CurPipelineState.return_value = pipe

        rd_mock = MagicMock()
        rd_mock.MeshDataStage.VSIn = "vs_in"
        rd_mock.MeshDataStage.VSOut = "vs_out"
        rd_mock.MeshDataStage.GSOut = "gs_out"
        null_rid = MagicMock(__str__=lambda s: "ResourceId::Null()")
        rd_mock.ResourceId.Null.return_value = null_rid
        rd_mock.ShaderStage.Vertex = MagicMock()

        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_post_vs_geometry(ctx, {"stage": "vs_out", "max_vertices": 1})

        verts = result.get("vertices", [])
        attrs = verts[0].get("attributes", {})
        assert "SV_Position_ndc" not in attrs
        assert "SV_Position_clip" in attrs


# ===========================================================================
# 8. _inspect_mesh_statistics
# ===========================================================================


def _setup_stats(ctx, vertex_bytes, stride=12, num_indices=2,
                 pos_name="POSITION", resource_id_str="ResourceId::VB"):
    """Wire ctx for _inspect_mesh_statistics with a float3 position attribute."""
    action = _make_draw_action(flags=_FLAG_DRAWCALL, num_indices=num_indices)
    ctx.CurAction.return_value = action

    vb = _make_vbuf(resource_id_str=resource_id_str, byte_stride=stride)
    pos = _make_vertex_input(pos_name, vb_slot=0, byte_offset=0,
                             comp_type_str="Float", comp_count=3, comp_bw=4)
    pipe = _make_pipeline(vbufs=[vb])
    pipe.GetVertexInputs.return_value = [pos]
    pipe.GetPrimitiveTopology.return_value = MagicMock(name="TriangleList")
    ctx.CurPipelineState.return_value = pipe

    rid_sentinel = MagicMock(__str__=lambda s: resource_id_str)
    re = MagicMock()
    re.resourceId = rid_sentinel
    ctx.GetResources.return_value = [re]

    controller = MagicMock()
    controller.GetBufferData.return_value = vertex_bytes
    ctx.GetBlockingController.return_value = controller


class TestMeshStatistics:
    def test_not_a_draw_returns_error(self):
        gui, ctx = _make_gui()
        action = _make_draw_action(flags=0)
        ctx.CurAction.return_value = action
        ctx.CurPipelineState.return_value = _make_pipeline()
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("error") == "not_a_draw"

    def test_event_not_selected(self):
        gui, ctx = _make_gui(cur_event=5)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {"event_id": 99})
        assert result.get("error") == "event_not_selected"

    def test_valid_bounding_box_two_vertices(self):
        gui, ctx = _make_gui(cur_event=1)
        # Two vertices: (0,0,0) and (1,2,3)
        raw = struct.pack("<ffffff", 0.0, 0.0, 0.0, 1.0, 2.0, 3.0)
        _setup_stats(ctx, raw, stride=12, num_indices=2)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("error") is None
        pa = result.get("position_analysis", {})
        bb = pa.get("bounding_box")
        assert bb is not None
        assert bb["min"] == pytest.approx([0.0, 0.0, 0.0], abs=1e-5)
        assert bb["max"] == pytest.approx([1.0, 2.0, 3.0], abs=1e-5)

    def test_nan_component_count_incremented(self):
        gui, ctx = _make_gui(cur_event=1)
        nan_val = float("nan")
        raw = struct.pack("<fff", nan_val, 0.0, 0.0)
        _setup_stats(ctx, raw, stride=12, num_indices=1)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        pa = result.get("position_analysis", {})
        assert pa.get("nan_component_count", 0) >= 1

    def test_valid_vertex_count_excludes_nan_vertices(self):
        gui, ctx = _make_gui(cur_event=1)
        nan_val = float("nan")
        # 3 vertices: 2 valid, 1 with NaN
        raw = struct.pack("<fffffffff",
                          1.0, 2.0, 3.0,
                          nan_val, 0.0, 0.0,
                          4.0, 5.0, 6.0)
        _setup_stats(ctx, raw, stride=12, num_indices=3)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        pa = result.get("position_analysis", {})
        assert pa.get("valid_vertex_count") == 2

    def test_sampled_true_when_fewer_verts_than_num_indices(self):
        gui, ctx = _make_gui(cur_event=1)
        # Only supply 1 vertex worth of data but claim num_indices=500
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        _setup_stats(ctx, raw, stride=12, num_indices=500)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("sampled") is True

    def test_sampled_false_when_all_verts_covered(self):
        gui, ctx = _make_gui(cur_event=1)
        # 2 vertices, num_indices=2 → full coverage
        raw = struct.pack("<ffffff", 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
        _setup_stats(ctx, raw, stride=12, num_indices=2)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("sampled") is False

    def test_no_position_attribute_returns_error_in_analysis(self):
        gui, ctx = _make_gui(cur_event=1)
        action = _make_draw_action(flags=_FLAG_DRAWCALL, num_indices=3)
        ctx.CurAction.return_value = action

        # Pipeline with no vertex inputs at all
        pipe = _make_pipeline()
        pipe.GetVertexInputs.return_value = []
        ctx.CurPipelineState.return_value = pipe

        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("error") is None  # outer result is not an error
        pa = result.get("position_analysis", {})
        assert pa.get("error") == "no_position_attribute"

    def test_bounding_box_coordinate_space_label(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<fff", 0.0, 0.0, 0.0)
        _setup_stats(ctx, raw, stride=12, num_indices=1)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        pa = result.get("position_analysis", {})
        bb = pa.get("bounding_box")
        if bb is not None:
            assert "object_space" in bb.get("coordinate_space", "")

    def test_returns_num_indices_in_result(self):
        gui, ctx = _make_gui(cur_event=1)
        raw = struct.pack("<fff", 1.0, 0.0, 0.0)
        _setup_stats(ctx, raw, stride=12, num_indices=6)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        assert result.get("num_indices") == 6

    def test_inf_component_counted(self):
        gui, ctx = _make_gui(cur_event=1)
        inf_val = float("inf")
        raw = struct.pack("<fff", inf_val, 0.0, 0.0)
        _setup_stats(ctx, raw, stride=12, num_indices=1)
        with _patch_renderdoc():
            result = gui._inspect_mesh_statistics(ctx, {})
        pa = result.get("position_analysis", {})
        assert pa.get("inf_component_count", 0) >= 1
