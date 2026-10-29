"""Tests for Phase 10 — Shader Inspection & Reflection.

Covers:
- _normalize_stage, _get_rd_stage helper functions
- _sig_param_to_dict, _const_type_to_dict, _shader_const_to_dict
- _cbuf_to_dict, _shader_res_to_dict, _sampler_to_dict
- GUIContext._inspect_list_shaders
- GUIContext._inspect_get_shader_info
- GUIContext._inspect_get_shader_reflection (all sections)
- GUIContext._inspect_get_shader_bindings
- GUIContext._inspect_get_shader_disassembly
- GUIContext._inspect_get_shader_debug_info
- GUIContext.inspect() dispatch for Phase 10 operations
- ToolExecutor Phase 10 tool wrappers
"""

from __future__ import annotations

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from rendereye_mcp.ipc.manager import ExtensionConnectionManager
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
    ctx = MagicMock()
    ctx.IsCaptureLoaded = MagicMock(return_value=loaded)
    ctx.IsCaptureLoading = MagicMock(return_value=loading)
    ctx.GetCaptureFilename = MagicMock(return_value=path)
    ctx.Extensions = MagicMock(return_value=[])
    return ctx


def _make_gui(ctx=None, set_thread=True):
    from extensions.rendereye.gui_context import GUIContext

    if ctx is None:
        ctx = _mock_context()
    gui = GUIContext(ctx, "1.45")
    if set_thread:
        gui.thread_id = threading.get_ident()
    return gui, ctx


def _null_shader_id():
    m = MagicMock()
    m.__str__ = lambda self: "ResourceId::Null()"
    return m


def _real_shader_id(val="shader-101"):
    m = MagicMock()
    m.__str__ = lambda self: val
    return m


def _make_pipe(stage_to_shader=None, selected_event=1):
    """Build a minimal mock PipeState."""
    null_id = _null_shader_id()
    pipe = MagicMock()
    pipe.IsCaptureLoaded = MagicMock(return_value=True)

    def _get_shader(stage):
        if stage_to_shader and stage in stage_to_shader:
            return stage_to_shader[stage]
        return null_id

    pipe.GetShader = MagicMock(side_effect=_get_shader)
    pipe.GetShaderEntryPoint = MagicMock(return_value="main")
    pipe.GetShaderReflection = MagicMock(return_value=None)
    pipe.GetConstantBlocks = MagicMock(return_value=[])
    pipe.GetReadOnlyResources = MagicMock(return_value=[])
    pipe.GetReadWriteResources = MagicMock(return_value=[])
    pipe.GetBindpointMapping = MagicMock(return_value=None)
    pipe.GetCurrentPipelineObject = MagicMock(return_value=null_id)
    return pipe


def _make_reflection(
    input_sigs=None,
    output_sigs=None,
    cbuffers=None,
    ro_resources=None,
    rw_resources=None,
    samplers=None,
    debug_info=None,
    encoding_name="DXBC",
):
    refl = MagicMock()
    refl.entryPoint = "main"
    refl.inputSignature = input_sigs or []
    refl.outputSignature = output_sigs or []
    refl.constantBlocks = cbuffers or []
    refl.readOnlyResources = ro_resources or []
    refl.readWriteResources = rw_resources or []
    refl.samplers = samplers or []
    refl.debugInfo = debug_info
    enc = MagicMock()
    enc.name = encoding_name
    refl.encoding = enc
    return refl


def _make_sig_param(var_name="POSITION", semantic_name="SV_Position", reg_index=0):
    sp = MagicMock()
    sp.varName = var_name
    sp.semanticName = semantic_name
    sp.semanticIndex = 0
    sp.regIndex = reg_index
    sv = MagicMock()
    sv.name = "Undefined"
    sp.systemValue = sv
    ct = MagicMock()
    ct.name = "Float"
    sp.compType = ct
    sp.regChannelMask = 0xF
    sp.channelUsedMask = 0xF
    return sp


def _make_cbuf(name="PerObject", bind_number=0, variables=None):
    cb = MagicMock()
    cb.name = name
    cb.bufferBacked = True
    cb.fixedBindNumber = bind_number
    cb.fixedBindSetOrSpace = 0
    cb.bindArraySize = 1
    cb.variables = variables or []
    return cb


def _make_shader_const(name="WorldMatrix", byte_offset=0, base_type="Float", rows=4, cols=4):
    sc = MagicMock()
    sc.name = name
    sc.byteOffset = byte_offset
    ctype = MagicMock()
    ctype.name = "float4x4"
    bt = MagicMock()
    bt.name = base_type
    ctype.baseType = bt
    ctype.rows = rows
    ctype.columns = cols
    ctype.elements = 0
    ctype.arrayByteStride = 0
    ctype.matrixByteStride = 16
    ctype.members = []
    sc.type = ctype
    return sc


def _make_shader_res(name="AlbedoTex", bind_number=0):
    res = MagicMock()
    res.name = name
    res.fixedBindNumber = bind_number
    res.fixedBindSetOrSpace = 0
    res.bindArraySize = 1
    res.isTexture = True
    rt = MagicMock()
    rt.name = "Texture2D"
    res.resType = rt
    return res


def _make_sampler(name="LinearSampler", bind_number=0):
    samp = MagicMock()
    samp.name = name
    samp.fixedBindNumber = bind_number
    samp.fixedBindSetOrSpace = 0
    samp.bindArraySize = 1
    return samp


def _make_debug_info(has_source=True, files=None):
    di = MagicMock()
    di.sourceDebugInformation = has_source
    di.files = files or []
    di.compileFlags = None
    return di


def _make_source_file(filename="shader.hlsl", contents="line1\nline2\nline3"):
    sf = MagicMock()
    sf.filename = filename
    sf.contents = contents
    return sf


def _make_bound_descriptor(resource_id_str):
    desc = MagicMock()
    rid = MagicMock()
    rid.__str__ = lambda self: resource_id_str
    desc.descriptor.resource = rid
    desc.descriptor.byteOffset = 0
    desc.descriptor.byteSize = 256
    return desc


# ---------------------------------------------------------------------------
# _normalize_stage
# ---------------------------------------------------------------------------


class TestNormalizeStage:
    def test_vertex_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("vertex") == "Vertex"
        assert _normalize_stage("VS") == "Vertex"
        assert _normalize_stage("Vertex") == "Vertex"

    def test_pixel_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("pixel") == "Pixel"
        assert _normalize_stage("ps") == "Pixel"
        assert _normalize_stage("fragment") == "Pixel"
        assert _normalize_stage("fs") == "Pixel"

    def test_compute_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("compute") == "Compute"
        assert _normalize_stage("CS") == "Compute"

    def test_hull_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("hull") == "Hull"
        assert _normalize_stage("HS") == "Hull"

    def test_domain_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("domain") == "Domain"
        assert _normalize_stage("ds") == "Domain"

    def test_geometry_aliases(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("geometry") == "Geometry"
        assert _normalize_stage("GS") == "Geometry"

    def test_unknown_returns_none(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("raytracing") is None
        assert _normalize_stage("") is None
        assert _normalize_stage("XYZ") is None

    def test_case_insensitive(self):
        from extensions.rendereye.gui_context import _normalize_stage

        assert _normalize_stage("VERTEX") == "Vertex"
        assert _normalize_stage("Pixel") == "Pixel"


# ---------------------------------------------------------------------------
# Reflection serialization helpers
# ---------------------------------------------------------------------------


class TestSigParamToDict:
    def test_basic_fields(self):
        from extensions.rendereye.gui_context import _sig_param_to_dict

        sp = _make_sig_param("POSITION", "SV_Position", reg_index=0)
        d = _sig_param_to_dict(sp)
        assert d["var_name"] == "POSITION"
        assert d["semantic_name"] == "SV_Position"
        assert d["reg_index"] == 0
        assert d["reg_channel_mask"] == 0xF

    def test_system_value_name(self):
        from extensions.rendereye.gui_context import _sig_param_to_dict

        sp = _make_sig_param()
        sp.systemValue.name = "Position"
        d = _sig_param_to_dict(sp)
        assert d["system_value"] == "Position"

    def test_raises_on_none_gracefully(self):
        from extensions.rendereye.gui_context import _sig_param_to_dict

        class _Empty:
            pass

        d = _sig_param_to_dict(_Empty())
        assert "var_name" not in d  # AttributeError on bare object is caught gracefully


class TestShaderConstToDict:
    def test_basic_fields(self):
        from extensions.rendereye.gui_context import _shader_const_to_dict

        sc = _make_shader_const("WorldMatrix", byte_offset=0)
        d = _shader_const_to_dict(sc)
        assert d["name"] == "WorldMatrix"
        assert d["byte_offset"] == 0
        assert "type" in d

    def test_type_contains_base_type(self):
        from extensions.rendereye.gui_context import _shader_const_to_dict

        sc = _make_shader_const("v", base_type="Float", rows=1, cols=4)
        d = _shader_const_to_dict(sc)
        assert d["type"]["base_type"] == "Float"
        assert d["type"]["rows"] == 1
        assert d["type"]["columns"] == 4

    def test_matrix_stride_included(self):
        from extensions.rendereye.gui_context import _shader_const_to_dict

        sc = _make_shader_const("M", rows=4, cols=4)
        d = _shader_const_to_dict(sc)
        assert d["type"]["matrix_byte_stride"] == 16

    def test_nested_members(self):
        from extensions.rendereye.gui_context import _const_type_to_dict

        inner = _make_shader_const("inner_field", 0)
        outer_type = MagicMock()
        outer_type.name = "MyStruct"
        outer_type.baseType = MagicMock()
        outer_type.baseType.name = "Struct"
        outer_type.rows = 1
        outer_type.columns = 1
        outer_type.elements = 0
        outer_type.arrayByteStride = 0
        outer_type.matrixByteStride = 0
        outer_type.members = [inner]
        d = _const_type_to_dict(outer_type)
        assert "members" in d
        assert d["members"][0]["name"] == "inner_field"

    def test_max_depth_guard(self):
        from extensions.rendereye.gui_context import _const_type_to_dict

        ctype = MagicMock()
        d = _const_type_to_dict(ctype, depth=5)
        assert d.get("note") == "max_depth"


class TestCbufToDict:
    def test_basic_fields(self):
        from extensions.rendereye.gui_context import _cbuf_to_dict

        cb = _make_cbuf("PerObject", bind_number=2)
        d = _cbuf_to_dict(cb)
        assert d["name"] == "PerObject"
        assert d["bind_number"] == 2
        assert d["buffer_backed"] is True

    def test_variables_listed(self):
        from extensions.rendereye.gui_context import _cbuf_to_dict

        vars_ = [_make_shader_const("WorldMatrix"), _make_shader_const("Color", 64)]
        cb = _make_cbuf("PerObj", variables=vars_)
        d = _cbuf_to_dict(cb)
        assert d["variable_count"] == 2
        assert len(d["variables"]) == 2
        assert d["variables"][0]["name"] == "WorldMatrix"

    def test_empty_variables(self):
        from extensions.rendereye.gui_context import _cbuf_to_dict

        cb = _make_cbuf("Empty", variables=[])
        d = _cbuf_to_dict(cb)
        assert d["variable_count"] == 0


class TestShaderResToDict:
    def test_basic(self):
        from extensions.rendereye.gui_context import _shader_res_to_dict

        res = _make_shader_res("AlbedoTex", bind_number=0)
        d = _shader_res_to_dict(res)
        assert d["name"] == "AlbedoTex"
        assert d["bind_number"] == 0
        assert d["res_type"] == "Texture2D"
        assert d["is_texture"] is True


class TestSamplerToDict:
    def test_basic(self):
        from extensions.rendereye.gui_context import _sampler_to_dict

        samp = _make_sampler("LinearSampler", bind_number=1)
        d = _sampler_to_dict(samp)
        assert d["name"] == "LinearSampler"
        assert d["bind_number"] == 1


# ---------------------------------------------------------------------------
# GUIContext._inspect_list_shaders
# ---------------------------------------------------------------------------


class TestInspectListShaders:
    def _setup_pipe_with_shader(self, ctx, stage_enum_name="Vertex", shader_id_str="shader-101"):
        """Patch CurPipelineState to return a pipe with one bound shader."""
        import renderdoc as rd

        shader_id = _real_shader_id(shader_id_str)
        stage_map = {rd.ShaderStage.Vertex: shader_id}
        pipe = _make_pipe(stage_to_shader=stage_map)
        pipe.GetShaderReflection = MagicMock(return_value=_make_reflection())
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=42)
        ctx.CurAction = MagicMock(return_value=None)
        return pipe

    def test_no_shaders_bound(self):
        try:
            import renderdoc  # noqa: F401
        except ImportError:
            pytest.skip("renderdoc not available")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        ctx.CurAction = MagicMock(return_value=None)
        result = gui.inspect("list_shaders", {})
        assert "error" not in result
        assert result["shaders"] == []
        assert result["shader_count"] == 0

    def test_one_shader_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        self._setup_pipe_with_shader(ctx)
        result = gui.inspect("list_shaders", {})
        assert "error" not in result
        assert result["shader_count"] == 1
        assert result["shaders"][0]["stage"] == "Vertex"
        assert result["shaders"][0]["shader_id"] == "shader-101"

    def test_event_id_in_result(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        self._setup_pipe_with_shader(ctx)
        result = gui.inspect("list_shaders", {})
        assert result["event_id"] == 42

    def test_pipeline_type_graphics(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        ctx.CurAction = MagicMock(return_value=None)
        result = gui.inspect("list_shaders", {})
        assert result["pipeline_type"] == "graphics"

    def test_no_capture_loaded(self):
        gui, ctx = _make_gui()
        ctx.IsCaptureLoaded = MagicMock(return_value=False)
        ctx.IsCaptureLoading = MagicMock(return_value=False)
        result = gui.inspect("list_shaders", {})
        assert result["error"] == "no_capture_loaded"

    def test_reflection_summary_included(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        refl = _make_reflection(cbuffers=[_make_cbuf()], input_sigs=[_make_sig_param()])
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        ctx.CurAction = MagicMock(return_value=None)
        result = gui.inspect("list_shaders", {})
        assert result["shaders"][0]["has_reflection"] is True
        assert result["shaders"][0]["cbuffer_count"] == 1
        assert result["shaders"][0]["input_sig_count"] == 1


# ---------------------------------------------------------------------------
# GUIContext._inspect_get_shader_info
# ---------------------------------------------------------------------------


class TestInspectGetShaderInfo:
    def test_missing_stage_param(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_info", {})
        assert "error" in result
        assert "stage" in result["error"].lower()

    def test_invalid_stage(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_info", {"stage": "raytracing"})
        assert result["error"] == "invalid_stage"
        assert "valid_stages" in result

    def test_shader_not_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_info", {"stage": "pixel"})
        assert result["error"] == "shader_not_bound"
        assert result["stage"] == "Pixel"

    def test_shader_bound_returns_info(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s-VS")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=_make_reflection(
            cbuffers=[_make_cbuf()],
            input_sigs=[_make_sig_param()],
        ))
        controller = MagicMock()
        controller.GetDisassemblyTargets = MagicMock(return_value=["DXBC"])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.GetBlockingController = MagicMock(return_value=controller)
        result = gui.inspect("get_shader_info", {"stage": "vs"})
        assert "error" not in result
        assert result["stage"] == "Vertex"
        assert result["shader_id"] == "s-VS"
        assert result["entry_point"] == "main"
        assert result["cbuffer_count"] == 1
        assert result["input_sig_count"] == 1
        assert result["has_reflection"] is True
        assert "DXBC" in result.get("disassembly_targets", [])

    def test_no_reflection_returns_has_reflection_false(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Compute: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=None)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.GetBlockingController = MagicMock(return_value=None)
        result = gui.inspect("get_shader_info", {"stage": "cs"})
        assert "error" not in result
        assert result["has_reflection"] is False

    def test_capture_path_stamped(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.GetBlockingController = MagicMock(return_value=None)
        result = gui.inspect("get_shader_info", {"stage": "vertex"})
        assert "_capture_path" in result


# ---------------------------------------------------------------------------
# GUIContext._inspect_get_shader_reflection
# ---------------------------------------------------------------------------


class TestInspectGetShaderReflection:
    def _setup(self, ctx, refl, stage_enum=None):
        try:
            import renderdoc as rd
            stage_enum = stage_enum or rd.ShaderStage.Vertex
        except ImportError:
            pytest.skip("renderdoc not available")
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={stage_enum: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=5)

    def test_missing_stage(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_reflection", {})
        assert "error" in result

    def test_invalid_section(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "badSection"})
        assert result["error"] == "invalid_section"
        assert "valid_sections" in result

    def test_section_all_contains_all_fields(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(
            input_sigs=[_make_sig_param()],
            output_sigs=[_make_sig_param("OUT")],
            cbuffers=[_make_cbuf()],
            ro_resources=[_make_shader_res()],
            rw_resources=[],
            samplers=[_make_sampler()],
        )
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "all"})
        assert "error" not in result
        assert "input_signature" in result
        assert "output_signature" in result
        assert "constant_buffers" in result
        assert "read_only_resources" in result
        assert "read_write_resources" in result
        assert "samplers" in result

    def test_section_cbuffers_only(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(cbuffers=[_make_cbuf("CB0"), _make_cbuf("CB1", 1)])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vertex", "section": "cbuffers"})
        assert "error" not in result
        assert "constant_buffers" in result
        assert len(result["constant_buffers"]) == 2
        assert "input_signature" not in result

    def test_section_input_only(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(input_sigs=[_make_sig_param("POS"), _make_sig_param("UV", reg_index=1)])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "input"})
        assert len(result["input_signature"]) == 2
        assert "constant_buffers" not in result

    def test_section_output_only(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(output_sigs=[_make_sig_param("OUT")])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "output"})
        assert "output_signature" in result
        assert "input_signature" not in result

    def test_section_resources(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(ro_resources=[_make_shader_res("Tex0")])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "resources"})
        assert "read_only_resources" in result
        assert "read_write_resources" in result
        assert len(result["read_only_resources"]) == 1

    def test_section_samplers(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection(samplers=[_make_sampler("S0"), _make_sampler("S1", 1)])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "samplers"})
        assert len(result["samplers"]) == 2

    def test_cbuffer_variable_layout(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        vars_ = [_make_shader_const("WorldMatrix", 0), _make_shader_const("Color", 64)]
        refl = _make_reflection(cbuffers=[_make_cbuf("PerObj", variables=vars_)])
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vs", "section": "cbuffers"})
        cb = result["constant_buffers"][0]
        assert cb["name"] == "PerObj"
        assert cb["variable_count"] == 2
        assert cb["variables"][0]["name"] == "WorldMatrix"
        assert cb["variables"][0]["byte_offset"] == 0
        assert cb["variables"][1]["byte_offset"] == 64

    def test_event_id_in_result(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        refl = _make_reflection()
        self._setup(ctx, refl)
        result = gui.inspect("get_shader_reflection", {"stage": "vertex", "section": "all"})
        assert result["event_id"] == 5

    def test_shader_not_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_reflection", {"stage": "pixel"})
        assert result["error"] == "shader_not_bound"

    def test_reflection_unavailable(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=None)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_reflection", {"stage": "vs"})
        assert result["error"] == "reflection_unavailable"


# ---------------------------------------------------------------------------
# GUIContext._inspect_get_shader_bindings
# ---------------------------------------------------------------------------


class TestInspectGetShaderBindings:
    def test_missing_stage(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_bindings", {})
        assert "error" in result

    def test_shader_not_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_bindings", {"stage": "pixel"})
        assert result["error"] == "shader_not_bound"

    def test_cbuffer_bound(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(cbuffers=[_make_cbuf("PerObject", bind_number=0)])
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        bound_desc = _make_bound_descriptor("resource-cb1")
        pipe.GetConstantBlocks = MagicMock(return_value=[bound_desc])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        result = gui.inspect("get_shader_bindings", {"stage": "vs"})
        assert "error" not in result
        cbuf_bindings = [b for b in result["bindings"] if b["binding_type"] == "cbuffer"]
        assert len(cbuf_bindings) == 1
        assert cbuf_bindings[0]["name"] == "PerObject"
        assert cbuf_bindings[0]["bound"] is True
        assert cbuf_bindings[0]["resource_id"] == "resource-cb1"

    def test_texture_bound(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(ro_resources=[_make_shader_res("AlbedoTex", 0)])
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        bound_desc = _make_bound_descriptor("resource-tex1")
        pipe.GetReadOnlyResources = MagicMock(return_value=[bound_desc])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        result = gui.inspect("get_shader_bindings", {"stage": "ps"})
        tex_bindings = [b for b in result["bindings"] if b["binding_type"] == "texture"]
        assert len(tex_bindings) == 1
        assert tex_bindings[0]["bound"] is True
        assert tex_bindings[0]["resource_id"] == "resource-tex1"

    def test_unbound_resource(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(ro_resources=[_make_shader_res("NormalTex", 1)])
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        # Return empty list (no slot 1)
        pipe.GetReadOnlyResources = MagicMock(return_value=[])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        result = gui.inspect("get_shader_bindings", {"stage": "pixel"})
        tex_bindings = [b for b in result["bindings"] if b["binding_type"] == "texture"]
        assert tex_bindings[0]["bound"] is False
        assert tex_bindings[0]["resource_id"] is None

    def test_uav_bound(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(rw_resources=[_make_shader_res("OutputBuf", 0)])
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Compute: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        bound_desc = _make_bound_descriptor("resource-uav1")
        pipe.GetReadWriteResources = MagicMock(return_value=[bound_desc])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        result = gui.inspect("get_shader_bindings", {"stage": "cs"})
        uav_bindings = [b for b in result["bindings"] if b["binding_type"] == "uav"]
        assert len(uav_bindings) == 1
        assert uav_bindings[0]["bound"] is True

    def test_binding_count_in_result(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(
            cbuffers=[_make_cbuf()],
            ro_resources=[_make_shader_res()],
        )
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        pipe.GetConstantBlocks = MagicMock(return_value=[_make_bound_descriptor("cb1")])
        pipe.GetReadOnlyResources = MagicMock(return_value=[_make_bound_descriptor("tex1")])
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.CurSelectedEvent = MagicMock(return_value=1)
        result = gui.inspect("get_shader_bindings", {"stage": "ps"})
        assert result["binding_count"] == 2


# ---------------------------------------------------------------------------
# GUIContext._inspect_get_shader_disassembly
# ---------------------------------------------------------------------------


class TestInspectGetShaderDisassembly:
    def _setup_for_disasm(self, ctx, disasm_text, targets=None):
        rd = pytest.importorskip("renderdoc")
        shader_id = _real_shader_id("s1")
        refl = _make_reflection()
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        controller = MagicMock()
        controller.GetDisassemblyTargets = MagicMock(return_value=targets or ["DXBC"])
        controller.DisassembleShader = MagicMock(return_value=disasm_text)
        ctx.GetBlockingController = MagicMock(return_value=controller)
        return pipe, controller

    def test_missing_stage(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_disassembly", {})
        assert "error" in result

    def test_shader_not_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_disassembly", {"stage": "vertex"})
        assert result["error"] == "shader_not_bound"

    def test_basic_disassembly(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        disasm = "\n".join("line %d" % i for i in range(10))
        self._setup_for_disasm(ctx, disasm)
        result = gui.inspect("get_shader_disassembly", {"stage": "vertex"})
        assert "error" not in result
        assert result["total_lines"] == 10
        assert result["target"] == "DXBC"
        assert len(result["lines"]) == 10

    def test_pagination_offset_limit(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        disasm = "\n".join("line %d" % i for i in range(50))
        self._setup_for_disasm(ctx, disasm)
        result = gui.inspect("get_shader_disassembly", {"stage": "vertex", "offset": 10, "limit": 5})
        assert result["offset"] == 10
        assert result["limit"] == 5
        assert len(result["lines"]) == 5
        assert result["lines"][0] == "line 10"
        assert result["has_more"] is True

    def test_has_more_false_when_exhausted(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        disasm = "line 0\nline 1\nline 2"
        self._setup_for_disasm(ctx, disasm)
        result = gui.inspect("get_shader_disassembly", {"stage": "vs", "offset": 0, "limit": 200})
        assert result["has_more"] is False

    def test_limit_capped_at_max(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        disasm = "\n".join("line" for _ in range(10))
        self._setup_for_disasm(ctx, disasm)
        result = gui.inspect("get_shader_disassembly", {"stage": "vs", "limit": 9999})
        assert result["limit"] == 200  # capped at _MAX_DISASM_LINES

    def test_search_filters_lines(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        disasm = "mov r0, r1\nadd r0, r1\ntexld r0, t0\nmov r1, r2"
        self._setup_for_disasm(ctx, disasm)
        result = gui.inspect("get_shader_disassembly", {"stage": "vs", "search": "texld"})
        # Should contain the texld line and context
        combined = " ".join(result["lines"])
        assert "texld" in combined

    def test_invalid_target(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        self._setup_for_disasm(ctx, "some disasm", targets=["DXBC"])
        result = gui.inspect("get_shader_disassembly", {"stage": "vs", "target": "SPIR-V"})
        assert result["error"] == "invalid_disassembly_target"
        assert "available_targets" in result

    def test_available_targets_in_result(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        self._setup_for_disasm(ctx, "some disasm", targets=["DXBC", "DXIL"])
        result = gui.inspect("get_shader_disassembly", {"stage": "vs"})
        assert "DXBC" in result["available_targets"]
        assert "DXIL" in result["available_targets"]

    def test_replay_unavailable(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=_make_reflection())
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        ctx.GetBlockingController = MagicMock(return_value=None)
        result = gui.inspect("get_shader_disassembly", {"stage": "vs"})
        assert result["error"] == "replay_unavailable"

    def test_disassembly_failed(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Vertex: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=_make_reflection())
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        controller = MagicMock()
        controller.GetDisassemblyTargets = MagicMock(return_value=["DXBC"])
        controller.DisassembleShader = MagicMock(side_effect=RuntimeError("disasm error"))
        ctx.GetBlockingController = MagicMock(return_value=controller)
        result = gui.inspect("get_shader_disassembly", {"stage": "vs"})
        assert result["error"] == "disassembly_failed"


# ---------------------------------------------------------------------------
# GUIContext._inspect_get_shader_debug_info
# ---------------------------------------------------------------------------


class TestInspectGetShaderDebugInfo:
    def _setup_with_debug_info(self, ctx, has_source=True, files=None):
        rd = pytest.importorskip("renderdoc")
        shader_id = _real_shader_id("s1")
        di = _make_debug_info(has_source=has_source, files=files or [])
        refl = _make_reflection(debug_info=di)
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        ctx.CurPipelineState = MagicMock(return_value=pipe)

    def test_missing_stage(self):
        gui, ctx = _make_gui()
        result = gui.inspect("get_shader_debug_info", {})
        assert "error" in result

    def test_shader_not_bound(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        pipe = _make_pipe()
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_debug_info", {"stage": "pixel"})
        assert result["error"] == "shader_not_bound"

    def test_no_debug_info(self):
        rd = pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        shader_id = _real_shader_id("s1")
        refl = _make_reflection(debug_info=None)
        pipe = _make_pipe(stage_to_shader={rd.ShaderStage.Pixel: shader_id})
        pipe.GetShaderReflection = MagicMock(return_value=refl)
        ctx.CurPipelineState = MagicMock(return_value=pipe)
        result = gui.inspect("get_shader_debug_info", {"stage": "ps"})
        assert result["error"] == "debug_info_unavailable"

    def test_with_source_files(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("shader.hlsl", "line 0\nline 1\nline 2\nline 3")
        self._setup_with_debug_info(ctx, has_source=True, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps"})
        assert "error" not in result
        assert result["source_debug_information"] is True
        assert result["source_file_count"] == 1
        assert result["source_files"][0]["filename"] == "shader.hlsl"

    def test_source_content_retrieval(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("shader.hlsl", "\n".join("line %d" % i for i in range(10)))
        self._setup_with_debug_info(ctx, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps", "file_index": 0, "start_line": 0, "max_lines": 5})
        assert "source" in result
        assert len(result["source"]["lines"]) == 5
        assert result["source"]["has_more"] is True

    def test_source_pagination(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("shader.hlsl", "\n".join("line %d" % i for i in range(20)))
        self._setup_with_debug_info(ctx, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps", "file_index": 0, "start_line": 10, "max_lines": 5})
        assert result["source"]["start_line"] == 10
        assert result["source"]["lines"][0] == "line 10"

    def test_source_has_more_false(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("s.hlsl", "a\nb\nc")
        self._setup_with_debug_info(ctx, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps", "max_lines": 100})
        assert result["source"]["has_more"] is False

    def test_max_lines_capped(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("s.hlsl", "\n".join("x" for _ in range(10)))
        self._setup_with_debug_info(ctx, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps", "max_lines": 999999})
        # max_lines capped at _MAX_SOURCE_LINES (500), result still fits since only 10 lines
        assert len(result["source"]["lines"]) == 10

    def test_invalid_file_index_noted(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        sf = _make_source_file("shader.hlsl", "line0")
        self._setup_with_debug_info(ctx, files=[sf])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps", "file_index": 99})
        assert "note" in result

    def test_no_source_files_returns_empty_list(self):
        pytest.importorskip("renderdoc")
        gui, ctx = _make_gui()
        self._setup_with_debug_info(ctx, has_source=False, files=[])
        result = gui.inspect("get_shader_debug_info", {"stage": "ps"})
        assert "error" not in result
        assert result["source_file_count"] == 0
        assert result["source_files"] == []


# ---------------------------------------------------------------------------
# GUIContext.inspect() dispatch for Phase 10 operations
# ---------------------------------------------------------------------------


class TestGUIContextPhase10Dispatch:
    def test_all_phase10_ops_in_supported_list(self):
        gui, ctx = _make_gui()
        ctx.CurPipelineState = MagicMock(side_effect=Exception("unavailable"))
        # Trigger the "unsupported_operation" path
        result = gui.inspect("nonexistent_xyz_phase10", {})
        supported = result.get("supported", [])
        for op in ("list_shaders", "get_shader_info", "get_shader_reflection",
                   "get_shader_bindings", "get_shader_disassembly", "get_shader_debug_info"):
            assert op in supported, f"{op!r} not in supported list"

    def test_no_capture_loaded_for_all_ops(self):
        gui, ctx = _make_gui()
        ctx.IsCaptureLoaded = MagicMock(return_value=False)
        ctx.IsCaptureLoading = MagicMock(return_value=False)
        for op in ("list_shaders", "get_shader_info", "get_shader_reflection",
                   "get_shader_bindings", "get_shader_disassembly", "get_shader_debug_info"):
            result = gui.inspect(op, {"stage": "vs"})
            assert result["error"] == "no_capture_loaded", f"{op} returned wrong error: {result}"

    def test_capture_loading_for_all_ops(self):
        gui, ctx = _make_gui()
        ctx.IsCaptureLoaded = MagicMock(return_value=False)
        ctx.IsCaptureLoading = MagicMock(return_value=True)
        for op in ("list_shaders", "get_shader_info", "get_shader_reflection",
                   "get_shader_bindings", "get_shader_disassembly", "get_shader_debug_info"):
            result = gui.inspect(op, {"stage": "vs"})
            assert result["error"] == "capture_loading", f"{op} returned wrong error: {result}"


# ---------------------------------------------------------------------------
# ToolExecutor Phase 10 tool wrappers
# ---------------------------------------------------------------------------


def _make_executor_with_mock_inspection(return_value: dict):
    mgr = _make_manager()
    conn_id = _register(mgr, "inst-1")
    mgr.update_gui_state(conn_id, 1, True, "D:/test.rdc", "loaded")

    async def fake_inspection(cid, operation, params, timeout=30.0):
        return return_value

    mgr.request_capture_inspection = AsyncMock(side_effect=fake_inspection)
    return _make_executor(conn_manager=mgr)


@pytest.mark.asyncio
async def test_tool_list_shaders_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("list_shaders", {})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_list_shaders_success():
    expected = {"shaders": [{"stage": "Vertex", "shader_id": "s1"}], "shader_count": 1}
    executor = _make_executor_with_mock_inspection(expected)
    result = await executor.execute("list_shaders", {})
    assert result == expected


@pytest.mark.asyncio
async def test_tool_get_shader_info_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("get_shader_info", {"stage": "Vertex"})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_get_shader_info_success():
    expected = {"stage": "Vertex", "shader_id": "s1", "has_reflection": True}
    executor = _make_executor_with_mock_inspection(expected)
    result = await executor.execute("get_shader_info", {"stage": "Vertex"})
    assert result == expected


@pytest.mark.asyncio
async def test_tool_get_shader_info_passes_stage():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    mgr.update_gui_state(conn_id, 1, True, "D:/t.rdc", "loaded")
    received = {}

    async def capture(cid, operation, params, timeout=30.0):
        received.update(params)
        return {}

    mgr.request_capture_inspection = AsyncMock(side_effect=capture)
    executor = _make_executor(conn_manager=mgr)
    await executor.execute("get_shader_info", {"stage": "Pixel"})
    assert received["stage"] == "Pixel"


@pytest.mark.asyncio
async def test_tool_get_shader_reflection_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("get_shader_reflection", {"stage": "Vertex"})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_get_shader_reflection_passes_params():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    mgr.update_gui_state(conn_id, 1, True, "D:/t.rdc", "loaded")
    received = {}

    async def capture(cid, operation, params, timeout=30.0):
        received.update(params)
        return {}

    mgr.request_capture_inspection = AsyncMock(side_effect=capture)
    executor = _make_executor(conn_manager=mgr)
    await executor.execute("get_shader_reflection", {"stage": "vs", "section": "cbuffers"})
    assert received["stage"] == "vs"
    assert received["section"] == "cbuffers"


@pytest.mark.asyncio
async def test_tool_get_shader_bindings_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("get_shader_bindings", {"stage": "pixel"})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_get_shader_bindings_success():
    expected = {"bindings": [], "binding_count": 0, "stage": "Pixel"}
    executor = _make_executor_with_mock_inspection(expected)
    result = await executor.execute("get_shader_bindings", {"stage": "pixel"})
    assert result == expected


@pytest.mark.asyncio
async def test_tool_get_shader_disassembly_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("get_shader_disassembly", {"stage": "vs"})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_get_shader_disassembly_passes_all_params():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    mgr.update_gui_state(conn_id, 1, True, "D:/t.rdc", "loaded")
    received = {}

    async def capture(cid, operation, params, timeout=30.0):
        received.update(params)
        return {}

    mgr.request_capture_inspection = AsyncMock(side_effect=capture)
    executor = _make_executor(conn_manager=mgr)
    await executor.execute("get_shader_disassembly", {
        "stage": "vs", "target": "DXBC", "offset": 10, "limit": 50, "search": "mov"
    })
    assert received["stage"] == "vs"
    assert received["target"] == "DXBC"
    assert received["offset"] == 10
    assert received["limit"] == 50
    assert received["search"] == "mov"


@pytest.mark.asyncio
async def test_tool_get_shader_debug_info_no_manager():
    executor = _make_executor(conn_manager=None)
    result = await executor.execute("get_shader_debug_info", {"stage": "ps"})
    assert result.get("status") == "no_renderdoc_connected"


@pytest.mark.asyncio
async def test_tool_get_shader_debug_info_passes_all_params():
    mgr = _make_manager()
    conn_id = _register(mgr, "i1")
    mgr.update_gui_state(conn_id, 1, True, "D:/t.rdc", "loaded")
    received = {}

    async def capture(cid, operation, params, timeout=30.0):
        received.update(params)
        return {}

    mgr.request_capture_inspection = AsyncMock(side_effect=capture)
    executor = _make_executor(conn_manager=mgr)
    await executor.execute("get_shader_debug_info", {
        "stage": "ps", "file_index": 2, "start_line": 10, "max_lines": 50
    })
    assert received["stage"] == "ps"
    assert received["file_index"] == 2
    assert received["start_line"] == 10
    assert received["max_lines"] == 50


@pytest.mark.asyncio
async def test_all_phase10_tools_reachable_via_execute():
    """All 6 Phase 10 tools are registered in _dispatch."""
    expected = {"ok": True}
    executor = _make_executor_with_mock_inspection(expected)
    tools = [
        ("list_shaders", {}),
        ("get_shader_info", {"stage": "vs"}),
        ("get_shader_reflection", {"stage": "vs"}),
        ("get_shader_bindings", {"stage": "vs"}),
        ("get_shader_disassembly", {"stage": "vs"}),
        ("get_shader_debug_info", {"stage": "vs"}),
    ]
    for tool_name, args in tools:
        result = await executor.execute(tool_name, args)
        assert result == expected, f"Tool {tool_name!r} returned {result}"


@pytest.mark.asyncio
async def test_tool_ambiguous_session():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    mgr.update_gui_state(c1, 1, True, "D:/a.rdc", "loaded")
    mgr.update_gui_state(c2, 1, True, "D:/b.rdc", "loaded")
    executor = _make_executor(conn_manager=mgr)
    result = await executor.execute("list_shaders", {})
    assert result.get("status") == "ambiguous"


@pytest.mark.asyncio
async def test_tool_specific_instance_id_routes_correctly():
    mgr = _make_manager()
    c1 = _register(mgr, "i1", 1)
    c2 = _register(mgr, "i2", 2)
    mgr.update_gui_state(c1, 1, True, "D:/a.rdc", "loaded")
    mgr.update_gui_state(c2, 1, True, "D:/b.rdc", "loaded")
    used = []

    async def track(cid, operation, params, timeout=30.0):
        used.append(cid)
        return {}

    mgr.request_capture_inspection = AsyncMock(side_effect=track)
    executor = _make_executor(conn_manager=mgr)
    await executor.execute("list_shaders", {"instance_id": "i1"})
    assert used == [c1]
