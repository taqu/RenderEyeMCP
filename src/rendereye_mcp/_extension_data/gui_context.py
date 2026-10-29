"""Access the supplied CaptureContext exclusively on its GUI thread."""

from __future__ import absolute_import

import os
import threading

# ActionFlags bit values (mirrors renderdoc.ActionFlags)
_FLAG_DRAWCALL = 2
_FLAG_DISPATCH = 4
_FLAG_PUSH_MARKER = 64
_FLAG_POP_MARKER = 128
_FLAG_POP_USER_DEFINED = 256
_FLAG_CLEAR = 512
_FLAG_COPY = 1024
_FLAG_RESOLVE = 2048
_FLAG_INDIRECT = 4096
_FLAG_INDEXED = 8192
_FLAG_INSTANCED = 16384
_FLAG_AUTO = 32768

_KNOWN_FLAGS = [
    (_FLAG_DRAWCALL, "Drawcall"),
    (_FLAG_DISPATCH, "Dispatch"),
    (_FLAG_PUSH_MARKER, "PushMarker"),
    (_FLAG_POP_MARKER, "PopMarker"),
    (_FLAG_POP_USER_DEFINED, "PopUserDefined"),
    (_FLAG_CLEAR, "Clear"),
    (_FLAG_COPY, "Copy"),
    (_FLAG_RESOLVE, "Resolve"),
    (_FLAG_INDIRECT, "Indirect"),
    (_FLAG_INDEXED, "Indexed"),
    (_FLAG_INSTANCED, "Instanced"),
    (_FLAG_AUTO, "Auto"),
]


def _flag_names(flags_int):
    return [name for bit, name in _KNOWN_FLAGS if flags_int & bit]


def _resource_id_str(rid):
    try:
        return str(rid)
    except Exception:
        return "invalid"


def _action_type(flags_int):
    if flags_int & _FLAG_DISPATCH:
        return "dispatch"
    if flags_int & _FLAG_DRAWCALL:
        return "drawcall"
    if flags_int & _FLAG_PUSH_MARKER:
        return "marker_begin"
    if flags_int & _FLAG_POP_MARKER:
        return "marker_end"
    if flags_int & _FLAG_POP_USER_DEFINED:
        return "marker_end"
    if flags_int & _FLAG_CLEAR:
        return "clear"
    if flags_int & _FLAG_COPY:
        return "copy"
    if flags_int & _FLAG_RESOLVE:
        return "resolve"
    return "other"


def _action_to_dict(action, depth=0, include_children=False, sdf=None):
    """Convert an ActionDescription to a serializable dict."""
    try:
        flags_int = int(action.flags)
    except Exception:
        flags_int = 0

    try:
        name = str(action.customName) if action.customName else ""
        if not name and sdf is not None:
            try:
                name = str(action.GetName(sdf))
            except Exception:
                pass
        if not name:
            name = "Event %d" % action.eventId
    except Exception:
        name = "Event %d" % getattr(action, "eventId", 0)

    d = {
        "event_id": int(action.eventId),
        "action_id": int(action.actionId),
        "name": name,
        "action_type": _action_type(flags_int),
        "flags": _flag_names(flags_int),
        "depth": depth,
    }

    try:
        d["num_instances"] = int(action.numInstances)
    except Exception:
        pass

    try:
        d["num_indices"] = int(action.numIndices)
    except Exception:
        pass

    try:
        dims = action.dispatchDimension
        if dims and any(dims):
            d["dispatch_dimension"] = [int(dims[0]), int(dims[1]), int(dims[2])]
    except Exception:
        pass

    if include_children:
        try:
            children = action.children
            if children:
                d["children"] = [_action_to_dict(c, depth + 1, True, sdf) for c in children]
            else:
                d["children"] = []
        except Exception:
            d["children"] = []
    else:
        try:
            d["child_count"] = len(action.children) if action.children else 0
        except Exception:
            d["child_count"] = 0

    return d


# Maximum bytes read per read_buffer_data call
_MAX_BUFFER_READ_BYTES = 16384  # 16 KiB
# Maximum decoded elements per structured decode
_MAX_DECODE_ELEMENTS = 100

# ResourceType int values (mirrors renderdoc.ResourceType)
_RESTYPE_TEXTURE = 4
_RESTYPE_BUFFER = 5
_RESTYPE_SWAPCHAIN = 8

# BufferCategory bit values (mirrors renderdoc.BufferCategory)
_BUFCAT_VERTEX = 1
_BUFCAT_INDEX = 2
_BUFCAT_CONSTANTS = 4
_BUFCAT_READWRITE = 8
_BUFCAT_INDIRECT = 16

_KNOWN_BUFCAT = [
    (_BUFCAT_VERTEX, "Vertex"),
    (_BUFCAT_INDEX, "Index"),
    (_BUFCAT_CONSTANTS, "Constants"),
    (_BUFCAT_READWRITE, "ReadWrite"),
    (_BUFCAT_INDIRECT, "Indirect"),
]

# TextureCategory bit values (mirrors renderdoc.TextureCategory)
_TEXCAT_SHADER_READ = 1
_TEXCAT_COLOR_TARGET = 2
_TEXCAT_DEPTH_TARGET = 4
_TEXCAT_SHADER_RW = 8
_TEXCAT_SWAP = 16

_KNOWN_TEXCAT = [
    (_TEXCAT_SHADER_READ, "ShaderRead"),
    (_TEXCAT_COLOR_TARGET, "ColorTarget"),
    (_TEXCAT_DEPTH_TARGET, "DepthTarget"),
    (_TEXCAT_SHADER_RW, "ShaderReadWrite"),
    (_TEXCAT_SWAP, "SwapBuffer"),
]

_TYPE_TO_STRUCT = {
    "float16": ("e", 2),
    "float32": ("f", 4),
    "float64": ("d", 8),
    "uint8":   ("B", 1),
    "uint16":  ("H", 2),
    "uint32":  ("I", 4),
    "uint64":  ("Q", 8),
    "int8":    ("b", 1),
    "int16":   ("h", 2),
    "int32":   ("i", 4),
    "int64":   ("q", 8),
}


def _buf_cat_names(flags_int):
    return [name for bit, name in _KNOWN_BUFCAT if flags_int & bit]


def _tex_cat_names(flags_int):
    return [name for bit, name in _KNOWN_TEXCAT if flags_int & bit]


def _resource_category(type_int):
    if type_int in (_RESTYPE_TEXTURE, _RESTYPE_SWAPCHAIN):
        return "texture"
    if type_int == _RESTYPE_BUFFER:
        return "buffer"
    return "other"


def _find_resource_id_obj(ctx, resource_id_str):
    """Return the ResourceId object whose string representation matches resource_id_str."""
    try:
        for r in ctx.GetResources():
            try:
                if str(r.resourceId) == resource_id_str:
                    return r.resourceId
            except Exception:
                pass
    except Exception:
        pass
    return None


def _json_safe_float(v):
    import math
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
    return v


def _decode_structured(data, decode_layout):
    """Decode binary data using a caller-supplied structured layout. Returns a dict."""
    import struct as _struct
    stride = int(decode_layout.get("stride", 0))
    element_count = int(decode_layout.get("element_count", 1))
    fields = decode_layout.get("fields", [])

    if not fields:
        return {"error": "decode_layout.fields is empty"}
    if stride <= 0:
        return {"error": "decode_layout.stride must be > 0"}
    if element_count <= 0:
        return {"error": "decode_layout.element_count must be > 0"}

    element_count = min(element_count, _MAX_DECODE_ELEMENTS)

    for fld in fields:
        ftype = str(fld.get("type", ""))
        if ftype not in _TYPE_TO_STRUCT:
            return {
                "error": "unsupported field type: " + ftype,
                "valid_types": list(_TYPE_TO_STRUCT.keys()),
            }
        foff = int(fld.get("offset", 0))
        comps = int(fld.get("components", 1))
        if foff < 0:
            return {"error": "field offset must be >= 0"}
        if comps < 1 or comps > 16:
            return {"error": "components must be 1-16"}
        _, bw = _TYPE_TO_STRUCT[ftype]
        if foff + comps * bw > stride:
            return {"error": "field '%s' extends beyond stride" % fld.get("name", "?")}

    available = len(data) // stride
    if available == 0:
        return {"error": "insufficient data", "byte_size": len(data), "stride": stride}
    element_count = min(element_count, available)

    is_float_type = {"float16", "float32", "float64"}
    elements = []
    for i in range(element_count):
        base = i * stride
        elem = {}
        for fld in fields:
            fname = str(fld.get("name", "field_%d" % len(elem)))
            ftype = str(fld.get("type", "uint8"))
            foff = int(fld.get("offset", 0))
            comps = int(fld.get("components", 1))
            fmt_char, bw = _TYPE_TO_STRUCT.get(ftype, ("B", 1))
            is_flt = ftype in is_float_type
            vals = []
            for c in range(comps):
                src = base + foff + c * bw
                raw = data[src: src + bw]
                if len(raw) < bw:
                    break
                val = _struct.unpack("<" + fmt_char, raw)[0]
                vals.append(_json_safe_float(val) if is_flt else val)
            elem[fname] = vals[0] if comps == 1 and len(vals) == 1 else vals
        elements.append(elem)

    return {
        "elements": elements,
        "element_count": len(elements),
        "stride": stride,
        "truncated": len(elements) < int(decode_layout.get("element_count", 1)),
    }


# Phase 10 Shader Inspection limits
_MAX_DISASM_LINES = 200
_MAX_REFL_VARS = 100
_MAX_SOURCE_LINES = 500

# Phase 11 Texture/Pixel inspection limits
_MAX_IMAGE_DIM = 1024      # default maximum output image dimension
_MAX_PIXEL_BATCH = 16      # maximum coordinates per batch pixel request
_MAX_HISTOGRAM_BINS = 256

# Phase 14 Geometry & Mesh inspection limits
_MAX_INDEX_READ = 1000         # max indices per get_mesh_indices
_MAX_VERTEX_READ = 100         # max vertices per get_mesh_vertices
_MAX_POST_VS_VERTICES = 100    # max vertices per get_post_vs_geometry
_MAX_GEOMETRY_STATS_VERTS = 500  # max vertex sample for mesh_statistics

# Phase 15 Pixel History & Shader Debugging limits
_MAX_PIXEL_HISTORY = 200       # max modifications per get_pixel_history
_MAX_TRACE_STEPS = 500         # max steps collected per debug trace
_MAX_TRACE_CHANGES = 100       # max variable changes returned per step
_MAX_SHADER_VARS = 50          # max variables returned per step inspection


def _comp_type_str(comp_type):
    """Return a plain-string name for a CompType enum value."""
    try:
        s = str(comp_type)
        return s.split(".")[-1] if "." in s else s
    except Exception:
        return "Unknown"


def _decode_vertex_attr(data, byte_offset, comp_type, comp_byte_width, num_comps):
    """Decode vertex attribute components from binary data.

    Returns a list of decoded scalar values, or None when data is insufficient.
    comp_type: plain string from _comp_type_str(), e.g. "Float", "UNorm", "UInt".
    """
    import struct as _vstruct
    if byte_offset + num_comps * comp_byte_width > len(data):
        return None
    values = []
    for c in range(num_comps):
        off = byte_offset + c * comp_byte_width
        raw = bytes(data[off: off + comp_byte_width])
        if len(raw) < comp_byte_width:
            return None
        try:
            if comp_type in ("Float", "Depth"):
                fmt = {2: "<e", 4: "<f", 8: "<d"}.get(comp_byte_width, "<f")
                values.append(_json_safe_float(_vstruct.unpack(fmt, raw)[0]))
            elif comp_type == "Double":
                values.append(_json_safe_float(_vstruct.unpack("<d", raw)[0]))
            elif comp_type in ("UInt", "UScaled"):
                fmt = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}.get(comp_byte_width, "<I")
                values.append(_vstruct.unpack(fmt, raw)[0])
            elif comp_type in ("SInt", "SScaled"):
                fmt = {1: "<b", 2: "<h", 4: "<i", 8: "<q"}.get(comp_byte_width, "<i")
                values.append(_vstruct.unpack(fmt, raw)[0])
            elif comp_type == "UNorm":
                max_v = {1: 255.0, 2: 65535.0, 4: 4294967295.0}.get(comp_byte_width, 255.0)
                fmt = {1: "<B", 2: "<H", 4: "<I"}.get(comp_byte_width, "<B")
                values.append(_json_safe_float(_vstruct.unpack(fmt, raw)[0] / max_v))
            elif comp_type == "SNorm":
                max_v = {1: 127.0, 2: 32767.0, 4: 2147483647.0}.get(comp_byte_width, 127.0)
                fmt = {1: "<b", 2: "<h", 4: "<i"}.get(comp_byte_width, "<b")
                values.append(_json_safe_float(max(-1.0, _vstruct.unpack(fmt, raw)[0] / max_v)))
            else:
                fmt = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}.get(comp_byte_width, "<B")
                values.append(_vstruct.unpack(fmt, raw)[0])
        except Exception:
            return None
    return values


def _shader_var_to_dict(v, depth=0):
    """Convert a ShaderVariable to a JSON-safe dict."""
    if depth > 3:
        return {"name": "...", "note": "max_depth"}
    d = {}
    try:
        d["name"] = str(v.name)
    except Exception:
        pass
    try:
        d["rows"] = int(v.rows)
        d["columns"] = int(v.columns)
    except Exception:
        pass
    try:
        vtype = v.type
        d["type"] = vtype.name if hasattr(vtype, "name") else str(vtype)
    except Exception:
        pass
    # value: try float array first, then uint, then int
    try:
        fv = list(v.value.f32v)
        ncomps = max(1, d.get("rows", 1) * d.get("columns", 1))
        fv = [_json_safe_float(x) for x in fv[:ncomps]]
        d["value"] = fv[0] if len(fv) == 1 else fv
    except Exception:
        try:
            uv = list(v.value.u32v)
            ncomps = max(1, d.get("rows", 1) * d.get("columns", 1))
            d["value"] = uv[:ncomps]
        except Exception:
            try:
                iv = list(v.value.s32v)
                ncomps = max(1, d.get("rows", 1) * d.get("columns", 1))
                d["value"] = iv[:ncomps]
            except Exception:
                pass
    # members (structs/arrays)
    try:
        members = list(v.members)
        if members:
            d["members"] = [_shader_var_to_dict(m, depth + 1) for m in members[:_MAX_SHADER_VARS]]
    except Exception:
        pass
    return d


def _debug_state_to_dict(state, max_changes=None):
    """Convert a ShaderDebugState to a JSON-safe dict."""
    if max_changes is None:
        max_changes = _MAX_TRACE_CHANGES
    d = {}
    try:
        d["step"] = int(state.stepIndex)
    except Exception:
        pass
    try:
        d["next_instruction"] = int(state.nextInstruction)
    except Exception:
        pass
    try:
        flags = state.flags
        flags_int = int(flags) if not isinstance(flags, int) else flags
        d["flags"] = flags_int
        # Check for NaN/Inf generation flag (0x2 from ShaderEvents)
        if flags_int & 0x2:
            d["generated_nan_or_inf"] = True
    except Exception:
        pass
    changes = []
    try:
        raw_changes = list(state.changes)
        for ch in raw_changes[:max_changes]:
            c = {}
            try:
                c["before"] = _shader_var_to_dict(ch.before)
            except Exception:
                pass
            try:
                c["after"] = _shader_var_to_dict(ch.after)
            except Exception:
                pass
            if c:
                changes.append(c)
    except Exception:
        pass
    d["changes"] = changes
    return d


def _pixel_value_to_dict(pv):
    """Convert a RenderDoc PixelValue to a JSON-safe dict."""
    d = {}
    try:
        d["float"] = [_json_safe_float(v) for v in list(pv.floatValue)]
    except Exception:
        pass
    try:
        d["uint"] = [int(v) for v in list(pv.uintValue)]
    except Exception:
        pass
    try:
        d["sint"] = [int(v) for v in list(pv.intValue)]
    except Exception:
        pass
    return d


# Stage name normalization map (lowercase aliases → canonical)
_STAGE_MAP = {
    "vertex": "Vertex", "vs": "Vertex",
    "hull": "Hull", "hs": "Hull",
    "domain": "Domain", "ds": "Domain",
    "geometry": "Geometry", "gs": "Geometry",
    "pixel": "Pixel", "ps": "Pixel", "fragment": "Pixel", "fs": "Pixel",
    "compute": "Compute", "cs": "Compute",
}


def _normalize_stage(s):
    """Normalize a user-supplied stage name to a canonical form, or None."""
    return _STAGE_MAP.get(str(s).lower().strip())


def _get_rd_stage(canonical_name):
    """Return rd.ShaderStage enum value for a canonical stage name, or None."""
    try:
        import renderdoc as rd
        _map = {
            "Vertex": rd.ShaderStage.Vertex,
            "Hull": rd.ShaderStage.Hull,
            "Domain": rd.ShaderStage.Domain,
            "Geometry": rd.ShaderStage.Geometry,
            "Pixel": rd.ShaderStage.Pixel,
            "Compute": rd.ShaderStage.Compute,
        }
        return _map.get(canonical_name)
    except Exception:
        return None


def _sig_param_to_dict(sp):
    """Convert a SigParameter to a serializable dict."""
    d = {}
    try:
        d["var_name"] = str(sp.varName)
    except Exception:
        pass
    try:
        d["semantic_name"] = str(sp.semanticName)
    except Exception:
        pass
    try:
        d["semantic_index"] = int(sp.semanticIndex)
    except Exception:
        pass
    try:
        d["reg_index"] = int(sp.regIndex)
    except Exception:
        pass
    try:
        sv = sp.systemValue
        d["system_value"] = sv.name if hasattr(sv, "name") else str(sv)
    except Exception:
        pass
    try:
        ct = sp.compType
        d["comp_type"] = ct.name if hasattr(ct, "name") else str(ct)
    except Exception:
        pass
    try:
        d["reg_channel_mask"] = int(sp.regChannelMask)
    except Exception:
        pass
    try:
        d["channel_used_mask"] = int(sp.channelUsedMask)
    except Exception:
        pass
    return d


def _const_type_to_dict(ctype, depth=0):
    """Recursively convert ShaderConstantType to a serializable dict."""
    if depth > 4:
        return {"note": "max_depth"}
    d = {}
    try:
        d["name"] = str(ctype.name)
    except Exception:
        pass
    try:
        bt = ctype.baseType
        d["base_type"] = bt.name if hasattr(bt, "name") else str(bt)
    except Exception:
        pass
    try:
        d["rows"] = int(ctype.rows)
        d["columns"] = int(ctype.columns)
    except Exception:
        pass
    try:
        elems = int(ctype.elements)
        if elems > 0:
            d["elements"] = elems
    except Exception:
        pass
    try:
        stride = int(ctype.arrayByteStride)
        if stride > 0:
            d["array_byte_stride"] = stride
    except Exception:
        pass
    try:
        mstride = int(ctype.matrixByteStride)
        if mstride > 0:
            d["matrix_byte_stride"] = mstride
    except Exception:
        pass
    try:
        members = list(ctype.members)
        if members:
            d["members"] = [_shader_const_to_dict(m, depth + 1) for m in members[:_MAX_REFL_VARS]]
    except Exception:
        pass
    return d


def _shader_const_to_dict(sc, depth=0):
    """Convert a ShaderConstant to a serializable dict."""
    d = {}
    try:
        d["name"] = str(sc.name)
    except Exception:
        pass
    try:
        d["byte_offset"] = int(sc.byteOffset)
    except Exception:
        pass
    try:
        d["type"] = _const_type_to_dict(sc.type, depth)
    except Exception:
        pass
    return d


def _cbuf_to_dict(cbuf):
    """Convert a ConstantBlock (reflected cbuffer declaration) to a dict."""
    d = {}
    try:
        d["name"] = str(cbuf.name)
    except Exception:
        pass
    try:
        d["buffer_backed"] = bool(cbuf.bufferBacked)
    except Exception:
        pass
    try:
        d["bind_number"] = int(cbuf.fixedBindNumber)
    except Exception:
        pass
    try:
        d["bind_set"] = int(cbuf.fixedBindSetOrSpace)
    except Exception:
        pass
    try:
        d["bind_array_size"] = int(cbuf.bindArraySize)
    except Exception:
        pass
    try:
        variables = list(cbuf.variables)
        d["variable_count"] = len(variables)
        d["variables"] = [_shader_const_to_dict(v) for v in variables[:_MAX_REFL_VARS]]
    except Exception:
        d["variable_count"] = 0
    return d


def _shader_res_to_dict(res):
    """Convert a ShaderResource (reflected SRV/UAV declaration) to a dict."""
    d = {}
    try:
        d["name"] = str(res.name)
    except Exception:
        pass
    try:
        rt = res.resType
        d["res_type"] = rt.name if hasattr(rt, "name") else str(rt)
    except Exception:
        pass
    try:
        d["bind_number"] = int(res.fixedBindNumber)
    except Exception:
        pass
    try:
        d["bind_set"] = int(res.fixedBindSetOrSpace)
    except Exception:
        pass
    try:
        d["bind_array_size"] = int(res.bindArraySize)
    except Exception:
        pass
    try:
        d["is_texture"] = bool(res.isTexture)
    except Exception:
        pass
    return d


def _sampler_to_dict(samp):
    """Convert a ShaderSampler to a dict."""
    d = {}
    try:
        d["name"] = str(samp.name)
    except Exception:
        pass
    try:
        d["bind_number"] = int(samp.fixedBindNumber)
    except Exception:
        pass
    try:
        d["bind_set"] = int(samp.fixedBindSetOrSpace)
    except Exception:
        pass
    try:
        d["bind_array_size"] = int(samp.bindArraySize)
    except Exception:
        pass
    return d


class GUIContext(object):
    def __init__(self, context, version):
        for name in ("IsCaptureLoaded", "IsCaptureLoading", "GetCaptureFilename", "Extensions"):
            if not callable(getattr(context, name, None)):
                raise RuntimeError("Required CaptureContext API unavailable: " + name)
        self.context = context
        self.version = version
        self.thread_id = None

    def _check_thread(self):
        if self.thread_id is None:
            self.thread_id = threading.get_ident()
        if threading.get_ident() != self.thread_id:
            raise RuntimeError("CaptureContext access requires the GUI thread")
        if self.context is None:
            raise RuntimeError("Extension has been unregistered")

    def snapshot(self):
        self._check_thread()
        loading = bool(self.context.IsCaptureLoading())
        loaded = bool(self.context.IsCaptureLoaded())
        path = str(self.context.GetCaptureFilename()) if loaded else None
        return path or None, loaded, loading

    def execute(self, command, params):
        self._check_thread()
        ctx = self.context
        if ctx.IsCaptureLoading():
            return False, "failed", "A capture is loading"
        if command not in ("open_capture", "close_capture"):
            return False, "unsupported", "Unsupported GUI command: " + command
        window = ctx.GetMainWindow()
        if command == "close_capture":
            ok = bool(window.PromptCloseCapture())
            return ok, "success" if ok else "failed", "" if ok else "Close cancelled"
        path = params.get("path", "")
        if not isinstance(path, str) or not os.path.isfile(path):
            return False, "failed", "Capture file does not exist"
        import renderdoc as rd

        if not callable(getattr(ctx, "LoadCapture", None)):
            return False, "unsupported", "LoadCapture API unavailable"
        if not window.PromptCloseCapture():
            return False, "failed", "Close cancelled"
        ctx.LoadCapture(path, rd.ReplayOptions(), path, False, True)
        ok = bool(ctx.IsCaptureLoaded()) and os.path.normcase(
            os.path.abspath(str(ctx.GetCaptureFilename()))
        ) == os.path.normcase(os.path.abspath(path))
        return ok, "success" if ok else "failed", "" if ok else "Capture did not load"

    def inspect(self, operation, params):
        """Run a capture inspection operation on the GUI thread."""
        self._check_thread()
        ctx = self.context

        capture_path = str(ctx.GetCaptureFilename()) if ctx.IsCaptureLoaded() else None

        if not ctx.IsCaptureLoaded():
            if ctx.IsCaptureLoading():
                return {
                    "error": "capture_loading",
                    "message": "A capture is currently loading",
                }
            return {
                "error": "no_capture_loaded",
                "message": "No capture is loaded in RenderDoc",
            }

        try:
            if operation == "capture_info":
                result = self._inspect_capture_info(ctx)
            elif operation == "selected_event":
                result = self._inspect_selected_event(ctx)
            elif operation == "list_events":
                result = self._inspect_list_events(ctx, params)
            elif operation == "get_event":
                result = self._inspect_get_event(ctx, params)
            elif operation == "pipeline_state":
                result = self._inspect_pipeline_state(ctx, params)
            elif operation == "list_resources":
                result = self._inspect_list_resources(ctx, params)
            elif operation == "get_resource_info":
                result = self._inspect_get_resource_info(ctx, params)
            elif operation == "get_texture_info":
                result = self._inspect_get_texture_info(ctx, params)
            elif operation == "get_buffer_info":
                result = self._inspect_get_buffer_info(ctx, params)
            elif operation == "read_buffer_data":
                result = self._inspect_read_buffer_data(ctx, params)
            elif operation == "list_shaders":
                result = self._inspect_list_shaders(ctx, params)
            elif operation == "get_shader_info":
                result = self._inspect_get_shader_info(ctx, params)
            elif operation == "get_shader_reflection":
                result = self._inspect_get_shader_reflection(ctx, params)
            elif operation == "get_shader_bindings":
                result = self._inspect_get_shader_bindings(ctx, params)
            elif operation == "get_shader_disassembly":
                result = self._inspect_get_shader_disassembly(ctx, params)
            elif operation == "get_shader_debug_info":
                result = self._inspect_get_shader_debug_info(ctx, params)
            elif operation == "get_render_targets":
                result = self._inspect_get_render_targets(ctx, params)
            elif operation == "get_texture_image":
                result = self._inspect_get_texture_image(ctx, params)
            elif operation == "get_pixel_value":
                result = self._inspect_get_pixel_value(ctx, params)
            elif operation == "get_texture_statistics":
                result = self._inspect_get_texture_statistics(ctx, params)
            elif operation == "list_gpu_counters":
                result = self._inspect_list_gpu_counters(ctx, params)
            elif operation == "fetch_gpu_counters":
                result = self._inspect_fetch_gpu_counters(ctx, params)
            elif operation == "draw_geometry_info":
                result = self._inspect_draw_geometry_info(ctx, params)
            elif operation == "vertex_input_layout":
                result = self._inspect_vertex_input_layout(ctx, params)
            elif operation == "mesh_indices":
                result = self._inspect_mesh_indices(ctx, params)
            elif operation == "mesh_vertices":
                result = self._inspect_mesh_vertices(ctx, params)
            elif operation == "post_vs_geometry":
                result = self._inspect_post_vs_geometry(ctx, params)
            elif operation == "mesh_statistics":
                result = self._inspect_mesh_statistics(ctx, params)
            elif operation == "pixel_history":
                result = self._inspect_pixel_history(ctx, params)
            elif operation == "debug_pixel":
                result = self._inspect_debug_pixel(ctx, params)
            elif operation == "debug_vertex":
                result = self._inspect_debug_vertex(ctx, params)
            elif operation == "debug_compute":
                result = self._inspect_debug_compute(ctx, params)
            else:
                result = {
                    "error": "unsupported_operation",
                    "operation": operation,
                    "supported": [
                        "capture_info", "selected_event", "list_events", "get_event",
                        "pipeline_state", "list_resources", "get_resource_info",
                        "get_texture_info", "get_buffer_info", "read_buffer_data",
                        "list_shaders", "get_shader_info", "get_shader_reflection",
                        "get_shader_bindings", "get_shader_disassembly", "get_shader_debug_info",
                        "get_render_targets", "get_texture_image", "get_pixel_value",
                        "get_texture_statistics", "list_gpu_counters", "fetch_gpu_counters",
                        "draw_geometry_info", "vertex_input_layout", "mesh_indices",
                        "mesh_vertices", "post_vs_geometry", "mesh_statistics",
                        "pixel_history", "debug_pixel", "debug_vertex", "debug_compute",
                    ],
                }
        except Exception as exc:
            result = {
                "error": "inspection_failed",
                "message": str(exc),
            }

        # Verify capture didn't change during inspection
        if capture_path is not None:
            current_path = str(ctx.GetCaptureFilename()) if ctx.IsCaptureLoaded() else None
            if current_path != capture_path:
                return {
                    "error": "capture_changed",
                    "message": "Capture changed during inspection",
                }

        if isinstance(result, dict) and "error" not in result:
            result["_capture_path"] = capture_path

        return result

    def _inspect_capture_info(self, ctx):
        result = {
            "capture_path": str(ctx.GetCaptureFilename()),
        }

        try:
            api_props = ctx.APIProps()
            if api_props is not None:
                try:
                    result["api"] = str(api_props.pipelineType.name)
                except Exception:
                    try:
                        result["api"] = str(api_props.pipelineType)
                    except Exception:
                        pass
                try:
                    result["vendor"] = str(api_props.vendor.name)
                except Exception:
                    pass
                try:
                    result["degraded"] = bool(api_props.degraded)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            frame_info = ctx.FrameInfo()
            if frame_info is not None:
                no_frame = 4294967295
                fn = int(frame_info.frameNumber)
                result["frame_number"] = fn if fn != no_frame else None
                try:
                    result["capture_time"] = float(frame_info.captureTime)
                except Exception:
                    pass
        except Exception:
            pass

        draw_count = [0]
        dispatch_count = [0]
        total_count = [0]

        def count_actions(actions):
            for a in actions:
                total_count[0] += 1
                try:
                    flags_int = int(a.flags)
                except Exception:
                    flags_int = 0
                if flags_int & _FLAG_DRAWCALL:
                    draw_count[0] += 1
                if flags_int & _FLAG_DISPATCH:
                    dispatch_count[0] += 1
                try:
                    if a.children:
                        count_actions(a.children)
                except Exception:
                    pass

        try:
            root_actions = ctx.CurRootActions()
            if root_actions is not None:
                count_actions(root_actions)
                result["statistics"] = {
                    "total_events": total_count[0],
                    "draw_calls": draw_count[0],
                    "dispatches": dispatch_count[0],
                }
        except Exception:
            pass

        try:
            resources = ctx.GetResources()
            if resources is not None:
                result["resource_count"] = len(resources)
        except Exception:
            pass

        return result

    def _inspect_selected_event(self, ctx):
        result = {}

        try:
            selected_id = int(ctx.CurSelectedEvent())
            result["selected_event_id"] = selected_id
        except Exception as exc:
            return {"error": "unsupported", "message": "CurSelectedEvent not available: " + str(exc)}

        try:
            current_id = int(ctx.CurEvent())
            result["current_event_id"] = current_id
        except Exception:
            result["current_event_id"] = None

        try:
            selected_action = ctx.CurSelectedAction()
            if selected_action is not None:
                sdf = None
                try:
                    sdf = ctx.GetStructuredFile()
                except Exception:
                    pass
                result["selected_action"] = _action_to_dict(selected_action, 0, False, sdf)
            else:
                result["selected_action"] = None
        except Exception:
            result["selected_action"] = None

        try:
            cur_action = ctx.CurAction()
            result["current_action_id"] = int(cur_action.eventId) if cur_action is not None else None
        except Exception:
            result["current_action_id"] = None

        return result

    def _collect_actions_flat(self, actions, depth, items, limit, offset, counter, include_markers, flags_filter):
        sdf = None
        for action in actions:
            try:
                flags_int = int(action.flags)
            except Exception:
                flags_int = 0

            is_marker = bool(flags_int & (_FLAG_PUSH_MARKER | _FLAG_POP_MARKER | _FLAG_POP_USER_DEFINED))
            if is_marker and not include_markers:
                try:
                    if action.children:
                        self._collect_actions_flat(
                            action.children, depth + 1, items, limit, offset,
                            counter, include_markers, flags_filter
                        )
                except Exception:
                    pass
                continue

            if flags_filter == "drawcall" and not (flags_int & _FLAG_DRAWCALL):
                try:
                    if action.children:
                        self._collect_actions_flat(
                            action.children, depth + 1, items, limit, offset,
                            counter, include_markers, flags_filter
                        )
                except Exception:
                    pass
                continue
            elif flags_filter == "dispatch" and not (flags_int & _FLAG_DISPATCH):
                try:
                    if action.children:
                        self._collect_actions_flat(
                            action.children, depth + 1, items, limit, offset,
                            counter, include_markers, flags_filter
                        )
                except Exception:
                    pass
                continue

            counter[0] += 1
            if counter[0] > offset and len(items) < limit:
                items.append(_action_to_dict(action, depth, False, sdf))

            try:
                if action.children:
                    self._collect_actions_flat(
                        action.children, depth + 1, items, limit, offset,
                        counter, include_markers, flags_filter
                    )
            except Exception:
                pass

    def _inspect_list_events(self, ctx, params):
        limit = min(int(params.get("limit", 50)), 200)
        offset = max(int(params.get("offset", 0)), 0)
        include_markers = bool(params.get("include_markers", True))
        flags_filter = str(params.get("flags_filter", ""))
        parent_event_id = int(params.get("parent_event_id", 0))

        try:
            root_actions = ctx.CurRootActions()
            if root_actions is None:
                return {"events": [], "total": 0, "limit": limit, "offset": offset}
        except Exception as exc:
            return {"error": "unsupported", "message": "CurRootActions not available: " + str(exc)}

        start_actions = root_actions
        if parent_event_id > 0:
            parent_action = None
            try:
                parent_action = ctx.GetAction(parent_event_id)
            except Exception:
                pass
            if parent_action is None:
                return {
                    "error": "event_not_found",
                    "event_id": parent_event_id,
                }
            try:
                start_actions = parent_action.children or []
            except Exception:
                start_actions = []

        items = []
        counter = [0]
        self._collect_actions_flat(
            start_actions, 0, items, limit, offset, counter,
            include_markers, flags_filter
        )

        return {
            "events": items,
            "total": counter[0],
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < counter[0],
        }

    def _inspect_get_event(self, ctx, params):
        event_id = int(params.get("event_id", 0))
        if event_id <= 0:
            return {"error": "invalid_event_id", "message": "event_id must be > 0"}

        try:
            action = ctx.GetAction(event_id)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetAction not available: " + str(exc)}

        if action is None:
            return {
                "error": "event_not_found",
                "event_id": event_id,
                "message": "No event found with the given ID",
            }

        sdf = None
        try:
            sdf = ctx.GetStructuredFile()
        except Exception:
            pass

        return _action_to_dict(action, 0, True, sdf)

    def _inspect_pipeline_state(self, ctx, params):
        section = str(params.get("section", "summary"))
        requested_event_id = int(params.get("event_id", 0))

        try:
            selected_id = int(ctx.CurSelectedEvent())
        except Exception as exc:
            return {"error": "unsupported", "message": "CurSelectedEvent not available: " + str(exc)}

        if requested_event_id > 0 and requested_event_id != selected_id:
            return {
                "error": "event_not_selected",
                "requested_event_id": requested_event_id,
                "selected_event_id": selected_id,
                "message": (
                    "Querying pipeline state for an event other than the currently selected "
                    "event would require changing the GUI replay position, which is not "
                    "permitted in read-only inspection mode. Select event %d in RenderDoc "
                    "first, or omit event_id to inspect the currently selected event."
                ) % requested_event_id,
            }

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": "CurPipelineState not available: " + str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable", "message": "No pipeline state available"}

        try:
            if not pipe.IsCaptureLoaded():
                return {"error": "no_capture_loaded"}
        except Exception:
            pass

        base = {"event_id": selected_id}

        api_name = "unknown"
        try:
            if pipe.IsCaptureD3D11():
                api_name = "D3D11"
            elif pipe.IsCaptureD3D12():
                api_name = "D3D12"
            elif pipe.IsCaptureGL():
                api_name = "OpenGL"
            elif pipe.IsCaptureVK():
                api_name = "Vulkan"
        except Exception:
            pass
        base["api"] = api_name

        pipeline_type = "graphics"
        try:
            cur_action = ctx.CurAction()
            if cur_action is not None:
                flags_int = int(cur_action.flags)
                if flags_int & _FLAG_DISPATCH:
                    pipeline_type = "compute"
        except Exception:
            pass
        base["pipeline_type"] = pipeline_type

        valid_sections = ("summary", "input_assembly", "shaders", "rasterizer",
                          "depth_stencil", "output_merger", "resources")
        if section not in valid_sections:
            return {
                "error": "invalid_section",
                "section": section,
                "valid_sections": list(valid_sections),
            }

        if section == "summary":
            return self._pipeline_summary(pipe, base)
        elif section == "input_assembly":
            return self._pipeline_input_assembly(pipe, base)
        elif section == "shaders":
            return self._pipeline_shaders(pipe, base)
        elif section == "rasterizer":
            return self._pipeline_rasterizer(pipe, base)
        elif section == "depth_stencil":
            return self._pipeline_depth_stencil(pipe, base)
        elif section == "output_merger":
            return self._pipeline_output_merger(pipe, base)
        elif section == "resources":
            return self._pipeline_resources(pipe, base)
        return base

    def _pipeline_summary(self, pipe, base):
        result = dict(base)
        result["section"] = "summary"

        try:
            topo = pipe.GetPrimitiveTopology()
            result["topology"] = topo.name if hasattr(topo, "name") else str(topo)
        except Exception:
            pass

        import renderdoc as rd
        shaders_present = []
        stages = []
        try:
            stages = [
                (rd.ShaderStage.Vertex, "VS"),
                (rd.ShaderStage.Hull, "HS"),
                (rd.ShaderStage.Domain, "DS"),
                (rd.ShaderStage.Geometry, "GS"),
                (rd.ShaderStage.Pixel, "PS"),
                (rd.ShaderStage.Compute, "CS"),
            ]
        except Exception:
            pass
        for stage, abbrev in stages:
            try:
                shader_id = pipe.GetShader(stage)
                null_id = rd.ResourceId.Null()
                if str(shader_id) != str(null_id):
                    entry_point = ""
                    try:
                        entry_point = str(pipe.GetShaderEntryPoint(stage))
                    except Exception:
                        pass
                    shaders_present.append({"stage": abbrev, "entry_point": entry_point})
            except Exception:
                pass
        if shaders_present:
            result["shaders"] = shaders_present

        try:
            targets = pipe.GetOutputTargets()
            result["render_target_count"] = len(targets) if targets else 0
        except Exception:
            pass

        try:
            depth = pipe.GetDepthTarget()
            if depth is not None and hasattr(depth, "resource"):
                null_id = rd.ResourceId.Null()
                rid_str = _resource_id_str(depth.resource)
                result["has_depth_target"] = rid_str != str(null_id)
            else:
                result["has_depth_target"] = False
        except Exception:
            pass

        return result

    def _pipeline_input_assembly(self, pipe, base):
        result = dict(base)
        result["section"] = "input_assembly"

        try:
            topo = pipe.GetPrimitiveTopology()
            result["topology"] = topo.name if hasattr(topo, "name") else str(topo)
        except Exception:
            pass

        try:
            ibuf = pipe.GetIBuffer()
            if ibuf is not None:
                result["index_buffer"] = {
                    "resource_id": _resource_id_str(ibuf.resourceId),
                    "offset": int(ibuf.byteOffset) if hasattr(ibuf, "byteOffset") else 0,
                    "stride": int(ibuf.byteStride) if hasattr(ibuf, "byteStride") else 0,
                }
        except Exception:
            pass

        try:
            vbufs = pipe.GetVBuffers()
            if vbufs:
                result["vertex_buffers"] = [
                    {
                        "resource_id": _resource_id_str(vb.resourceId),
                        "offset": int(vb.byteOffset) if hasattr(vb, "byteOffset") else 0,
                        "stride": int(vb.byteStride) if hasattr(vb, "byteStride") else 0,
                    }
                    for vb in vbufs[:16]
                ]
        except Exception:
            pass

        return result

    def _pipeline_shaders(self, pipe, base):
        result = dict(base)
        result["section"] = "shaders"

        import renderdoc as rd
        stages = []
        try:
            stages = [
                (rd.ShaderStage.Vertex, "Vertex"),
                (rd.ShaderStage.Hull, "Hull"),
                (rd.ShaderStage.Domain, "Domain"),
                (rd.ShaderStage.Geometry, "Geometry"),
                (rd.ShaderStage.Pixel, "Pixel"),
                (rd.ShaderStage.Compute, "Compute"),
            ]
        except Exception:
            pass

        shader_info = []
        for stage, name in stages:
            try:
                shader_id = pipe.GetShader(stage)
                null_id = rd.ResourceId.Null()
                if str(shader_id) == str(null_id):
                    continue
                info = {
                    "stage": name,
                    "resource_id": _resource_id_str(shader_id),
                }
                try:
                    ep = str(pipe.GetShaderEntryPoint(stage))
                    if ep:
                        info["entry_point"] = ep
                except Exception:
                    pass
                try:
                    refl = pipe.GetShaderReflection(stage)
                    if refl is not None:
                        try:
                            info["cbuffer_count"] = len(refl.constantBlocks) if hasattr(refl, "constantBlocks") else 0
                        except Exception:
                            pass
                        try:
                            info["texture_count"] = len(refl.readOnlyResources) if hasattr(refl, "readOnlyResources") else 0
                        except Exception:
                            pass
                        try:
                            info["uav_count"] = len(refl.readWriteResources) if hasattr(refl, "readWriteResources") else 0
                        except Exception:
                            pass
                except Exception:
                    pass
                shader_info.append(info)
            except Exception:
                pass

        result["stages"] = shader_info
        return result

    def _pipeline_rasterizer(self, pipe, base):
        result = dict(base)
        result["section"] = "rasterizer"

        viewports = []
        for i in range(16):
            try:
                vp = pipe.GetViewport(i)
                if vp is None:
                    break
                viewports.append({
                    "x": float(vp.x), "y": float(vp.y),
                    "width": float(vp.width), "height": float(vp.height),
                    "min_depth": float(vp.minDepth) if hasattr(vp, "minDepth") else 0.0,
                    "max_depth": float(vp.maxDepth) if hasattr(vp, "maxDepth") else 1.0,
                    "enabled": bool(vp.enabled) if hasattr(vp, "enabled") else True,
                })
            except Exception:
                break
        if viewports:
            result["viewports"] = viewports

        scissors = []
        for i in range(16):
            try:
                sc = pipe.GetScissor(i)
                if sc is None:
                    break
                scissors.append({
                    "x": int(sc.x), "y": int(sc.y),
                    "width": int(sc.width), "height": int(sc.height),
                    "enabled": bool(sc.enabled) if hasattr(sc, "enabled") else True,
                })
            except Exception:
                break
        if scissors:
            result["scissors"] = scissors

        return result

    def _pipeline_depth_stencil(self, pipe, base):
        result = dict(base)
        result["section"] = "depth_stencil"
        result["note"] = (
            "Cross-API depth/stencil state is not exposed by the abstract PipeState interface. "
            "Use section='output_merger' to see the bound depth/stencil target, or "
            "section='summary' for a compact overview."
        )
        return result

    def _pipeline_output_merger(self, pipe, base):
        result = dict(base)
        result["section"] = "output_merger"

        try:
            targets = pipe.GetOutputTargets()
            if targets:
                rt_list = []
                for t in targets[:16]:
                    rt = {}
                    try:
                        rt["resource_id"] = _resource_id_str(t.resource)
                    except Exception:
                        pass
                    try:
                        if hasattr(t, "format") and t.format is not None:
                            rt["format"] = str(t.format.Name())
                    except Exception:
                        pass
                    rt_list.append(rt)
                result["render_targets"] = rt_list
        except Exception:
            pass

        try:
            depth = pipe.GetDepthTarget()
            if depth is not None and hasattr(depth, "resource"):
                result["depth_target"] = {
                    "resource_id": _resource_id_str(depth.resource),
                }
        except Exception:
            pass

        return result

    def _pipeline_resources(self, pipe, base):
        result = dict(base)
        result["section"] = "resources"

        import renderdoc as rd
        stages = []
        try:
            stages = [
                (rd.ShaderStage.Vertex, "VS"),
                (rd.ShaderStage.Pixel, "PS"),
                (rd.ShaderStage.Compute, "CS"),
                (rd.ShaderStage.Geometry, "GS"),
                (rd.ShaderStage.Hull, "HS"),
                (rd.ShaderStage.Domain, "DS"),
            ]
        except Exception:
            pass

        resource_bindings = []
        for stage, abbrev in stages:
            try:
                cbuffers = pipe.GetConstantBlocks(stage, True)
                for cb in (cbuffers or [])[:8]:
                    binding = {"stage": abbrev, "binding_type": "cbuffer"}
                    try:
                        binding["resource_id"] = _resource_id_str(cb.descriptor.resource)
                    except Exception:
                        pass
                    resource_bindings.append(binding)
            except Exception:
                pass

            try:
                textures = pipe.GetReadOnlyResources(stage, True)
                for t in (textures or [])[:8]:
                    binding = {"stage": abbrev, "binding_type": "texture"}
                    try:
                        binding["resource_id"] = _resource_id_str(t.descriptor.resource)
                    except Exception:
                        pass
                    resource_bindings.append(binding)
            except Exception:
                pass

            try:
                uavs = pipe.GetReadWriteResources(stage, True)
                for u in (uavs or [])[:8]:
                    binding = {"stage": abbrev, "binding_type": "uav"}
                    try:
                        binding["resource_id"] = _resource_id_str(u.descriptor.resource)
                    except Exception:
                        pass
                    resource_bindings.append(binding)
            except Exception:
                pass

        result["bindings"] = resource_bindings[:64]
        result["total_bindings"] = len(resource_bindings)
        return result

    def _inspect_list_resources(self, ctx, params):
        """Enumerate resources in the loaded capture with filtering and pagination."""
        limit = min(int(params.get("limit", 50)), 500)
        offset = max(int(params.get("offset", 0)), 0)
        resource_type = str(params.get("resource_type", "all")).lower()
        name_filter = str(params.get("name_filter", "")).lower()

        try:
            all_resources = ctx.GetResources()
            if all_resources is None:
                return {"resources": [], "total": 0, "limit": limit, "offset": offset}
        except Exception as exc:
            return {"error": "unsupported", "message": "GetResources not available: " + str(exc)}

        items = []
        total = 0
        for r in all_resources:
            try:
                type_int = int(r.type)
            except Exception:
                type_int = 0
            category = _resource_category(type_int)

            if resource_type != "all" and category != resource_type:
                continue

            try:
                name = str(r.name)
            except Exception:
                name = ""

            if name_filter and name_filter not in name.lower():
                continue

            total += 1
            if total > offset and len(items) < limit:
                entry = {
                    "resource_id": _resource_id_str(r.resourceId),
                    "name": name,
                    "category": category,
                    "resource_type": type_int,
                }
                try:
                    entry["autogenerated_name"] = bool(r.autogeneratedName)
                except Exception:
                    pass
                items.append(entry)

        return {
            "resources": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    def _inspect_get_resource_info(self, ctx, params):
        """General resource metadata with type-specific details."""
        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        try:
            all_resources = ctx.GetResources()
        except Exception as exc:
            return {"error": "unsupported", "message": "GetResources not available: " + str(exc)}

        found = None
        for r in (all_resources or []):
            try:
                if str(r.resourceId) == resource_id_str:
                    found = r
                    break
            except Exception:
                pass

        if found is None:
            return {
                "error": "resource_not_found",
                "resource_id": resource_id_str,
                "message": "No resource with the given ID exists in the loaded capture",
            }

        try:
            type_int = int(found.type)
        except Exception:
            type_int = 0
        category = _resource_category(type_int)

        result = {
            "resource_id": resource_id_str,
            "name": str(found.name),
            "category": category,
            "resource_type": type_int,
        }
        try:
            result["autogenerated_name"] = bool(found.autogeneratedName)
        except Exception:
            pass

        rid_obj = found.resourceId

        if category == "texture":
            try:
                tex = ctx.GetTexture(rid_obj)
                if tex is not None:
                    result["texture"] = self._texture_desc_to_dict(tex)
            except Exception as exc:
                result["texture_error"] = str(exc)
        elif category == "buffer":
            try:
                buf = ctx.GetBuffer(rid_obj)
                if buf is not None:
                    result["buffer"] = self._buffer_desc_to_dict(buf)
            except Exception as exc:
                result["buffer_error"] = str(exc)

        return result

    def _inspect_get_texture_info(self, ctx, params):
        """Detailed texture metadata."""
        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {
                "error": "resource_not_found",
                "resource_id": resource_id_str,
            }

        try:
            tex = ctx.GetTexture(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetTexture not available: " + str(exc)}

        if tex is None:
            return {
                "error": "not_a_texture",
                "resource_id": resource_id_str,
                "message": "The resource is not a texture or could not be retrieved",
            }

        result = self._texture_desc_to_dict(tex)
        result["resource_id"] = resource_id_str
        return result

    def _inspect_get_buffer_info(self, ctx, params):
        """Detailed buffer metadata."""
        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {
                "error": "resource_not_found",
                "resource_id": resource_id_str,
            }

        try:
            buf = ctx.GetBuffer(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetBuffer not available: " + str(exc)}

        if buf is None:
            return {
                "error": "not_a_buffer",
                "resource_id": resource_id_str,
                "message": "The resource is not a buffer or could not be retrieved",
            }

        result = self._buffer_desc_to_dict(buf)
        result["resource_id"] = resource_id_str
        return result

    def _inspect_read_buffer_data(self, ctx, params):
        """Read a bounded byte range from a buffer, with optional structured decode."""
        import base64 as _base64

        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        offset = int(params.get("offset", 0))
        length = int(params.get("length", 256))
        output_format = str(params.get("output_format", "hex")).lower()
        decode_layout = params.get("decode_layout", None)

        if offset < 0:
            return {"error": "invalid_range", "message": "offset must be >= 0"}
        if length <= 0:
            return {"error": "invalid_range", "message": "length must be > 0"}
        if length > _MAX_BUFFER_READ_BYTES:
            return {
                "error": "range_too_large",
                "message": "length %d exceeds maximum %d bytes" % (length, _MAX_BUFFER_READ_BYTES),
                "max_length": _MAX_BUFFER_READ_BYTES,
            }
        if output_format not in ("hex", "base64", "bytes"):
            return {
                "error": "invalid_output_format",
                "valid_formats": ["hex", "base64", "bytes"],
            }

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {
                "error": "resource_not_found",
                "resource_id": resource_id_str,
            }

        # Validate bounds against buffer metadata
        byte_size = None
        try:
            buf = ctx.GetBuffer(rid_obj)
            if buf is not None:
                byte_size = int(buf.length)
        except Exception:
            pass

        if byte_size is not None:
            if offset >= byte_size:
                return {
                    "error": "out_of_bounds",
                    "message": "offset %d >= buffer size %d" % (offset, byte_size),
                    "buffer_byte_size": byte_size,
                }
            end = offset + length
            if end > byte_size:
                length = byte_size - offset

        # Read data via blocking replay controller
        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "GetBlockingController returned None"}
            data = controller.GetBufferData(rid_obj, offset, length)
        except Exception as exc:
            return {"error": "read_failed", "message": str(exc)}

        if data is None:
            return {"error": "read_failed", "message": "GetBufferData returned None"}

        actual_length = len(data)

        result = {
            "resource_id": resource_id_str,
            "offset": offset,
            "length": actual_length,
            "output_format": output_format,
        }

        if byte_size is not None:
            result["buffer_byte_size"] = byte_size

        if output_format == "hex":
            result["data"] = data.hex()
        elif output_format == "base64":
            result["data"] = _base64.b64encode(data).decode("ascii")
        else:  # bytes
            result["data"] = list(data[:1024])
            if actual_length > 1024:
                result["data_truncated"] = True
                result["data_note"] = "byte array limited to 1024 entries; use hex or base64 for full data"

        if decode_layout is not None:
            decode_result = _decode_structured(data, decode_layout)
            if "error" in decode_result:
                result["decode_error"] = decode_result["error"]
            else:
                result["decoded"] = decode_result

        return result

    def _texture_desc_to_dict(self, tex):
        """Convert TextureDescription to a serializable dict."""
        d = {}
        try:
            d["width"] = int(tex.width)
            d["height"] = int(tex.height)
            d["depth"] = int(tex.depth)
        except Exception:
            pass
        try:
            d["dimension"] = int(tex.dimension)
        except Exception:
            pass
        try:
            d["array_size"] = int(tex.arraysize)
        except Exception:
            pass
        try:
            d["mip_levels"] = int(tex.mips)
        except Exception:
            pass
        try:
            d["sample_count"] = int(tex.msSamp)
        except Exception:
            pass
        try:
            d["cubemap"] = bool(tex.cubemap)
        except Exception:
            pass
        try:
            d["byte_size"] = int(tex.byteSize)
        except Exception:
            pass
        try:
            ttype = tex.type
            d["texture_type"] = ttype.name if hasattr(ttype, "name") else str(ttype)
        except Exception:
            pass
        try:
            d["format"] = str(tex.format.Name())
        except Exception:
            pass
        try:
            flags_int = int(tex.creationFlags)
            d["usage"] = _tex_cat_names(flags_int)
        except Exception:
            pass
        return d

    def _buffer_desc_to_dict(self, buf):
        """Convert BufferDescription to a serializable dict."""
        d = {}
        try:
            d["byte_size"] = int(buf.length)
        except Exception:
            pass
        try:
            flags_int = int(buf.creationFlags)
            d["usage"] = _buf_cat_names(flags_int)
        except Exception:
            pass
        try:
            gpu_addr = int(buf.gpuAddress)
            if gpu_addr:
                d["gpu_address"] = "0x%x" % gpu_addr
        except Exception:
            pass
        return d

    def _inspect_list_shaders(self, ctx, params):
        """List shaders bound to the currently selected event."""
        import renderdoc as rd

        try:
            selected_id = int(ctx.CurSelectedEvent())
        except Exception as exc:
            return {"error": "unsupported", "message": "CurSelectedEvent not available: " + str(exc)}

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": "CurPipelineState not available: " + str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        null_id = str(rd.ResourceId.Null())

        stages = []
        try:
            stages = [
                (rd.ShaderStage.Vertex, "Vertex"),
                (rd.ShaderStage.Hull, "Hull"),
                (rd.ShaderStage.Domain, "Domain"),
                (rd.ShaderStage.Geometry, "Geometry"),
                (rd.ShaderStage.Pixel, "Pixel"),
                (rd.ShaderStage.Compute, "Compute"),
            ]
        except Exception as exc:
            return {"error": "unsupported", "message": "ShaderStage not available: " + str(exc)}

        shaders = []
        for stage_enum, stage_name in stages:
            try:
                shader_id = pipe.GetShader(stage_enum)
                if str(shader_id) == null_id:
                    continue
                entry = {
                    "stage": stage_name,
                    "shader_id": _resource_id_str(shader_id),
                }
                try:
                    ep = str(pipe.GetShaderEntryPoint(stage_enum))
                    if ep:
                        entry["entry_point"] = ep
                except Exception:
                    pass
                try:
                    refl = pipe.GetShaderReflection(stage_enum)
                    if refl is not None:
                        entry["has_reflection"] = True
                        try:
                            entry["cbuffer_count"] = len(list(refl.constantBlocks))
                        except Exception:
                            pass
                        try:
                            entry["input_sig_count"] = len(list(refl.inputSignature))
                        except Exception:
                            pass
                        try:
                            entry["output_sig_count"] = len(list(refl.outputSignature))
                        except Exception:
                            pass
                        try:
                            di = refl.debugInfo
                            entry["has_debug_info"] = bool(di.sourceDebugInformation) if di is not None else False
                        except Exception:
                            entry["has_debug_info"] = False
                    else:
                        entry["has_reflection"] = False
                except Exception as exc:
                    entry["has_reflection"] = False
                    entry["reflection_error"] = str(exc)
                shaders.append(entry)
            except Exception:
                pass

        pipeline_type = "graphics"
        try:
            cur_action = ctx.CurAction()
            if cur_action is not None and int(cur_action.flags) & _FLAG_DISPATCH:
                pipeline_type = "compute"
        except Exception:
            pass

        return {
            "event_id": selected_id,
            "pipeline_type": pipeline_type,
            "shaders": shaders,
            "shader_count": len(shaders),
        }

    def _inspect_get_shader_info(self, ctx, params):
        """Retrieve metadata for the shader bound at a specific stage."""
        stage_name = str(params.get("stage", ""))
        if not stage_name:
            return {"error": "stage is required", "valid_stages": sorted(set(_STAGE_MAP.values()))}
        canonical = _normalize_stage(stage_name)
        if canonical is None:
            return {"error": "invalid_stage", "stage": stage_name, "valid_stages": sorted(set(_STAGE_MAP.values()))}

        import renderdoc as rd

        stage_enum = _get_rd_stage(canonical)
        if stage_enum is None:
            return {"error": "unsupported_stage", "stage": canonical}

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        try:
            shader_id = pipe.GetShader(stage_enum)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetShader not available: " + str(exc)}

        null_id = str(rd.ResourceId.Null())
        if str(shader_id) == null_id:
            return {
                "error": "shader_not_bound",
                "stage": canonical,
                "message": "No %s shader is bound at the currently selected event" % canonical,
            }

        result = {"stage": canonical, "shader_id": _resource_id_str(shader_id)}

        try:
            ep = str(pipe.GetShaderEntryPoint(stage_enum))
            if ep:
                result["entry_point"] = ep
        except Exception:
            pass

        try:
            refl = pipe.GetShaderReflection(stage_enum)
            if refl is not None:
                result["has_reflection"] = True
                try:
                    result["input_sig_count"] = len(list(refl.inputSignature))
                except Exception:
                    pass
                try:
                    result["output_sig_count"] = len(list(refl.outputSignature))
                except Exception:
                    pass
                try:
                    result["cbuffer_count"] = len(list(refl.constantBlocks))
                except Exception:
                    pass
                try:
                    result["ro_resource_count"] = len(list(refl.readOnlyResources))
                except Exception:
                    pass
                try:
                    result["rw_resource_count"] = len(list(refl.readWriteResources))
                except Exception:
                    pass
                try:
                    result["sampler_count"] = len(list(refl.samplers))
                except Exception:
                    pass
                try:
                    di = refl.debugInfo
                    if di is not None:
                        result["has_debug_info"] = bool(di.sourceDebugInformation)
                        try:
                            result["source_file_count"] = len(list(di.files))
                        except Exception:
                            pass
                    else:
                        result["has_debug_info"] = False
                except Exception:
                    result["has_debug_info"] = False
                try:
                    enc = refl.encoding
                    result["encoding"] = enc.name if hasattr(enc, "name") else str(enc)
                except Exception:
                    pass
            else:
                result["has_reflection"] = False
        except Exception as exc:
            result["has_reflection"] = False
            result["reflection_error"] = str(exc)

        try:
            controller = ctx.GetBlockingController()
            if controller is not None:
                try:
                    targets = controller.GetDisassemblyTargets(True)
                except Exception:
                    try:
                        targets = controller.GetDisassemblyTargets()
                    except Exception:
                        targets = []
                result["disassembly_targets"] = [str(t) for t in (targets or [])]
        except Exception:
            pass

        return result

    def _inspect_get_shader_reflection(self, ctx, params):
        """Retrieve shader reflection data (signatures, cbuffers, resources, samplers)."""
        import renderdoc as rd

        stage_name = str(params.get("stage", ""))
        if not stage_name:
            return {"error": "stage is required"}
        canonical = _normalize_stage(stage_name)
        if canonical is None:
            return {"error": "invalid_stage", "stage": stage_name}
        stage_enum = _get_rd_stage(canonical)
        if stage_enum is None:
            return {"error": "unsupported_stage", "stage": canonical}

        section = str(params.get("section", "all")).lower()
        valid_sections = ("all", "input", "output", "cbuffers", "resources", "samplers")
        if section not in valid_sections:
            return {"error": "invalid_section", "section": section, "valid_sections": list(valid_sections)}

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        shader_id = pipe.GetShader(stage_enum)
        null_id = str(rd.ResourceId.Null())
        if str(shader_id) == null_id:
            return {"error": "shader_not_bound", "stage": canonical}

        try:
            refl = pipe.GetShaderReflection(stage_enum)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetShaderReflection not available: " + str(exc)}

        if refl is None:
            return {"error": "reflection_unavailable", "stage": canonical}

        try:
            selected_id = int(ctx.CurSelectedEvent())
        except Exception:
            selected_id = None

        result = {
            "stage": canonical,
            "shader_id": _resource_id_str(shader_id),
            "event_id": selected_id,
            "section": section,
        }

        try:
            ep = None
            try:
                ep = str(refl.entryPoint)
            except Exception:
                ep = str(pipe.GetShaderEntryPoint(stage_enum))
            if ep:
                result["entry_point"] = ep
        except Exception:
            pass

        if section in ("all", "input"):
            try:
                result["input_signature"] = [_sig_param_to_dict(s) for s in list(refl.inputSignature)]
            except Exception:
                result["input_signature"] = []

        if section in ("all", "output"):
            try:
                result["output_signature"] = [_sig_param_to_dict(s) for s in list(refl.outputSignature)]
            except Exception:
                result["output_signature"] = []

        if section in ("all", "cbuffers"):
            try:
                result["constant_buffers"] = [_cbuf_to_dict(cb) for cb in list(refl.constantBlocks)]
            except Exception:
                result["constant_buffers"] = []

        if section in ("all", "resources"):
            try:
                result["read_only_resources"] = [_shader_res_to_dict(r) for r in list(refl.readOnlyResources)]
            except Exception:
                result["read_only_resources"] = []
            try:
                result["read_write_resources"] = [_shader_res_to_dict(r) for r in list(refl.readWriteResources)]
            except Exception:
                result["read_write_resources"] = []

        if section in ("all", "samplers"):
            try:
                result["samplers"] = [_sampler_to_dict(s) for s in list(refl.samplers)]
            except Exception:
                result["samplers"] = []

        return result

    def _inspect_get_shader_bindings(self, ctx, params):
        """Correlate reflected shader declarations with actual runtime resource bindings."""
        import renderdoc as rd

        stage_name = str(params.get("stage", ""))
        if not stage_name:
            return {"error": "stage is required"}
        canonical = _normalize_stage(stage_name)
        if canonical is None:
            return {"error": "invalid_stage", "stage": stage_name}
        stage_enum = _get_rd_stage(canonical)
        if stage_enum is None:
            return {"error": "unsupported_stage", "stage": canonical}

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        shader_id = pipe.GetShader(stage_enum)
        null_id = str(rd.ResourceId.Null())
        if str(shader_id) == null_id:
            return {"error": "shader_not_bound", "stage": canonical}

        try:
            refl = pipe.GetShaderReflection(stage_enum)
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if refl is None:
            return {"error": "reflection_unavailable", "stage": canonical}

        try:
            selected_id = int(ctx.CurSelectedEvent())
        except Exception:
            selected_id = None

        mapping = None
        try:
            mapping = pipe.GetBindpointMapping(stage_enum)
        except Exception:
            pass

        bindings = []

        # Constant buffers
        try:
            bound_cbufs = pipe.GetConstantBlocks(stage_enum, False)
        except Exception:
            bound_cbufs = []

        try:
            for i, cbuf in enumerate(list(refl.constantBlocks)):
                b = {
                    "binding_type": "cbuffer",
                    "name": str(cbuf.name) if hasattr(cbuf, "name") else "",
                    "declared_bind": int(cbuf.fixedBindNumber) if hasattr(cbuf, "fixedBindNumber") else i,
                }
                actual_bind = int(cbuf.fixedBindNumber) if hasattr(cbuf, "fixedBindNumber") else i
                try:
                    if mapping is not None:
                        bp = list(mapping.constantBlocks)[i]
                        actual_bind = int(bp.bind)
                        b["bind_set"] = int(bp.bindset)
                except Exception:
                    pass
                b["actual_bind"] = actual_bind
                try:
                    desc = list(bound_cbufs)[actual_bind]
                    rid = desc.descriptor.resource
                    if str(rid) != null_id:
                        b["bound"] = True
                        b["resource_id"] = _resource_id_str(rid)
                        try:
                            b["byte_offset"] = int(desc.descriptor.byteOffset)
                        except Exception:
                            pass
                        try:
                            b["byte_size"] = int(desc.descriptor.byteSize)
                        except Exception:
                            pass
                    else:
                        b["bound"] = False
                        b["resource_id"] = None
                except Exception:
                    b["bound"] = False
                    b["resource_id"] = None
                bindings.append(b)
        except Exception:
            pass

        # Read-only resources (SRVs / textures)
        try:
            bound_ro = pipe.GetReadOnlyResources(stage_enum, False)
        except Exception:
            bound_ro = []

        try:
            for i, res in enumerate(list(refl.readOnlyResources)):
                b = {
                    "binding_type": "texture",
                    "name": str(res.name) if hasattr(res, "name") else "",
                    "declared_bind": int(res.fixedBindNumber) if hasattr(res, "fixedBindNumber") else i,
                }
                try:
                    rt = res.resType
                    b["res_type"] = rt.name if hasattr(rt, "name") else str(rt)
                except Exception:
                    pass
                actual_bind = int(res.fixedBindNumber) if hasattr(res, "fixedBindNumber") else i
                try:
                    if mapping is not None:
                        bp = list(mapping.readOnlyResources)[i]
                        actual_bind = int(bp.bind)
                        b["bind_set"] = int(bp.bindset)
                except Exception:
                    pass
                b["actual_bind"] = actual_bind
                try:
                    desc = list(bound_ro)[actual_bind]
                    rid = desc.descriptor.resource
                    if str(rid) != null_id:
                        b["bound"] = True
                        b["resource_id"] = _resource_id_str(rid)
                    else:
                        b["bound"] = False
                        b["resource_id"] = None
                except Exception:
                    b["bound"] = False
                    b["resource_id"] = None
                bindings.append(b)
        except Exception:
            pass

        # Read-write resources (UAVs)
        try:
            bound_rw = pipe.GetReadWriteResources(stage_enum, False)
        except Exception:
            bound_rw = []

        try:
            for i, res in enumerate(list(refl.readWriteResources)):
                b = {
                    "binding_type": "uav",
                    "name": str(res.name) if hasattr(res, "name") else "",
                    "declared_bind": int(res.fixedBindNumber) if hasattr(res, "fixedBindNumber") else i,
                }
                actual_bind = int(res.fixedBindNumber) if hasattr(res, "fixedBindNumber") else i
                try:
                    if mapping is not None:
                        bp = list(mapping.readWriteResources)[i]
                        actual_bind = int(bp.bind)
                        b["bind_set"] = int(bp.bindset)
                except Exception:
                    pass
                b["actual_bind"] = actual_bind
                try:
                    desc = list(bound_rw)[actual_bind]
                    rid = desc.descriptor.resource
                    if str(rid) != null_id:
                        b["bound"] = True
                        b["resource_id"] = _resource_id_str(rid)
                    else:
                        b["bound"] = False
                        b["resource_id"] = None
                except Exception:
                    b["bound"] = False
                    b["resource_id"] = None
                bindings.append(b)
        except Exception:
            pass

        return {
            "stage": canonical,
            "shader_id": _resource_id_str(shader_id),
            "event_id": selected_id,
            "bindings": bindings,
            "binding_count": len(bindings),
        }

    def _inspect_get_shader_disassembly(self, ctx, params):
        """Retrieve bounded shader disassembly with optional search."""
        import renderdoc as rd

        stage_name = str(params.get("stage", ""))
        if not stage_name:
            return {"error": "stage is required"}
        canonical = _normalize_stage(stage_name)
        if canonical is None:
            return {"error": "invalid_stage", "stage": stage_name}
        stage_enum = _get_rd_stage(canonical)
        if stage_enum is None:
            return {"error": "unsupported_stage", "stage": canonical}

        target = str(params.get("target", ""))
        offset = max(int(params.get("offset", 0)), 0)
        limit = min(int(params.get("limit", _MAX_DISASM_LINES)), _MAX_DISASM_LINES)
        search = str(params.get("search", "")).lower()

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        shader_id = pipe.GetShader(stage_enum)
        null_id = str(rd.ResourceId.Null())
        if str(shader_id) == null_id:
            return {"error": "shader_not_bound", "stage": canonical}

        try:
            refl = pipe.GetShaderReflection(stage_enum)
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if refl is None:
            return {"error": "reflection_unavailable", "stage": canonical}

        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "GetBlockingController returned None"}
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}

        available_targets = []
        try:
            targets_raw = None
            try:
                targets_raw = controller.GetDisassemblyTargets(True)
            except Exception:
                try:
                    targets_raw = controller.GetDisassemblyTargets()
                except Exception:
                    pass
            if targets_raw:
                available_targets = [str(t) for t in targets_raw]
        except Exception:
            pass

        if not target:
            if available_targets:
                target = available_targets[0]
        elif target not in available_targets and available_targets:
            return {
                "error": "invalid_disassembly_target",
                "target": target,
                "available_targets": available_targets,
            }

        pipeline_id = rd.ResourceId.Null()
        try:
            pipeline_id = pipe.GetCurrentPipelineObject()
        except Exception:
            pass

        try:
            disasm = controller.DisassembleShader(pipeline_id, refl, target)
        except Exception as exc:
            return {"error": "disassembly_failed", "message": str(exc)}

        if not disasm:
            return {"error": "disassembly_unavailable", "target": target, "stage": canonical}

        lines = str(disasm).splitlines()

        if search:
            context_size = 3
            matched_indices = set()
            for idx, line in enumerate(lines):
                if search in line.lower():
                    for ci in range(max(0, idx - context_size), min(len(lines), idx + context_size + 1)):
                        matched_indices.add(ci)
            filtered = []
            prev = None
            for ci in sorted(matched_indices):
                if prev is not None and ci > prev + 1:
                    filtered.append("...")
                filtered.append(lines[ci])
                prev = ci
            lines = filtered

        total = len(lines)
        page = lines[offset:offset + limit]

        return {
            "stage": canonical,
            "target": target,
            "available_targets": available_targets,
            "offset": offset,
            "limit": limit,
            "total_lines": total,
            "has_more": (offset + limit) < total,
            "lines": page,
            "search": search if search else None,
        }

    def _inspect_get_shader_debug_info(self, ctx, params):
        """Retrieve shader source/debug information where available."""
        import renderdoc as rd

        stage_name = str(params.get("stage", ""))
        if not stage_name:
            return {"error": "stage is required"}
        canonical = _normalize_stage(stage_name)
        if canonical is None:
            return {"error": "invalid_stage", "stage": stage_name}
        stage_enum = _get_rd_stage(canonical)
        if stage_enum is None:
            return {"error": "unsupported_stage", "stage": canonical}

        file_index = max(int(params.get("file_index", 0)), 0)
        start_line = max(int(params.get("start_line", 0)), 0)
        max_lines = min(int(params.get("max_lines", 100)), _MAX_SOURCE_LINES)

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        shader_id = pipe.GetShader(stage_enum)
        null_id = str(rd.ResourceId.Null())
        if str(shader_id) == null_id:
            return {"error": "shader_not_bound", "stage": canonical}

        try:
            refl = pipe.GetShaderReflection(stage_enum)
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}

        if refl is None:
            return {"error": "reflection_unavailable", "stage": canonical}

        try:
            di = refl.debugInfo
        except Exception as exc:
            return {"error": "debug_info_unavailable", "message": str(exc)}

        if di is None:
            return {
                "error": "debug_info_unavailable",
                "stage": canonical,
                "message": "No debug info attached to shader reflection",
            }

        result = {
            "stage": canonical,
            "shader_id": _resource_id_str(shader_id),
            "source_debug_information": False,
        }

        try:
            result["source_debug_information"] = bool(di.sourceDebugInformation)
        except Exception:
            pass

        all_files = []
        try:
            all_files = list(di.files)
        except Exception:
            pass

        files_meta = []
        for idx, f in enumerate(all_files):
            meta = {"index": idx}
            try:
                meta["filename"] = str(f.filename)
            except Exception:
                pass
            try:
                content = str(f.contents)
                meta["line_count"] = len(content.splitlines())
                meta["has_content"] = len(content) > 0
            except Exception:
                meta["has_content"] = False
            files_meta.append(meta)

        result["source_files"] = files_meta
        result["source_file_count"] = len(files_meta)

        if all_files and 0 <= file_index < len(all_files):
            try:
                f = all_files[file_index]
                content = str(f.contents)
                all_lines = content.splitlines()
                total_lines = len(all_lines)
                page_lines = all_lines[start_line:start_line + max_lines]
                result["source"] = {
                    "file_index": file_index,
                    "filename": str(f.filename) if hasattr(f, "filename") else "",
                    "start_line": start_line,
                    "lines": page_lines,
                    "total_lines": total_lines,
                    "has_more": (start_line + max_lines) < total_lines,
                }
            except Exception as exc:
                result["source_error"] = str(exc)
        elif all_files:
            result["note"] = "file_index %d out of range (0-%d)" % (file_index, len(all_files) - 1)

        try:
            cf = di.compileFlags
            if cf is not None:
                try:
                    result["compile_flags"] = [str(f) for f in list(cf.flags)]
                except Exception:
                    pass
        except Exception:
            pass

        return result

    def _inspect_get_render_targets(self, ctx, params):
        """List color render targets and depth/stencil attachment for the selected event."""
        import renderdoc as rd

        try:
            pipe = ctx.CurPipelineState()
        except Exception as exc:
            return {"error": "unsupported", "message": "CurPipelineState not available: " + str(exc)}
        if pipe is None:
            return {"error": "pipeline_state_unavailable"}

        null_id = str(rd.ResourceId.Null())

        event_id = None
        try:
            event_id = int(ctx.CurSelectedEvent())
        except Exception:
            pass

        color_targets = []
        try:
            targets = list(pipe.GetOutputTargets())
            for i, t in enumerate(targets[:16]):
                rt = {"index": i}
                rid_str = null_id
                try:
                    rid_str = _resource_id_str(t.resource)
                    rt["resource_id"] = rid_str
                except Exception:
                    rt["resource_id"] = null_id
                bound = rt["resource_id"] != null_id
                rt["bound"] = bound
                if bound:
                    try:
                        rt["mip"] = int(t.firstMip) if hasattr(t, "firstMip") else 0
                    except Exception:
                        pass
                    try:
                        rt["slice"] = int(t.firstSlice) if hasattr(t, "firstSlice") else 0
                    except Exception:
                        pass
                    try:
                        tex = ctx.GetTexture(t.resource)
                        if tex is not None:
                            td = self._texture_desc_to_dict(tex)
                            for k in ("width", "height", "format", "mip_levels",
                                      "sample_count", "array_size"):
                                if k in td:
                                    rt[k] = td[k]
                    except Exception:
                        pass
                color_targets.append(rt)
        except Exception as exc:
            return {"error": "output_targets_unavailable", "message": str(exc)}

        depth_target = None
        try:
            dt = pipe.GetDepthTarget()
            if dt is not None and hasattr(dt, "resource"):
                rid_str = _resource_id_str(dt.resource)
                if rid_str != null_id:
                    depth_target = {"resource_id": rid_str, "bound": True}
                    try:
                        depth_target["mip"] = int(dt.firstMip) if hasattr(dt, "firstMip") else 0
                    except Exception:
                        pass
                    try:
                        depth_target["slice"] = (
                            int(dt.firstSlice) if hasattr(dt, "firstSlice") else 0
                        )
                    except Exception:
                        pass
                    try:
                        tex = ctx.GetTexture(dt.resource)
                        if tex is not None:
                            td = self._texture_desc_to_dict(tex)
                            for k in ("width", "height", "format", "mip_levels", "sample_count"):
                                if k in td:
                                    depth_target[k] = td[k]
                    except Exception:
                        pass
        except Exception:
            pass

        result = {
            "color_targets": color_targets,
            "color_target_count": len([t for t in color_targets if t.get("bound")]),
            "depth_target": depth_target,
            "has_depth": depth_target is not None,
        }
        if event_id is not None:
            result["event_id"] = event_id
        return result

    def _inspect_get_texture_image(self, ctx, params):
        """Save a texture mip level as PNG and return it base64-encoded."""
        import base64 as _base64
        import os as _os
        import tempfile as _tempfile

        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        mip = int(params.get("mip", 0))
        if mip < 0:
            return {"error": "invalid_param", "message": "mip must be >= 0"}
        array_slice = int(params.get("array_slice", 0))
        if array_slice < 0:
            return {"error": "invalid_param", "message": "array_slice must be >= 0"}
        max_dim = int(params.get("max_dim", _MAX_IMAGE_DIM))
        if max_dim <= 0:
            max_dim = _MAX_IMAGE_DIM

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {"error": "resource_not_found", "resource_id": resource_id_str}

        try:
            tex = ctx.GetTexture(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetTexture not available: " + str(exc)}
        if tex is None:
            return {"error": "not_a_texture", "resource_id": resource_id_str}

        tex_w = int(tex.width)
        tex_h = int(tex.height)
        total_mips = 1
        try:
            total_mips = int(tex.mips)
        except Exception:
            pass

        if mip >= total_mips:
            return {
                "error": "invalid_mip",
                "mip": mip,
                "mip_levels": total_mips,
                "message": "mip %d out of range (texture has %d mip levels)" % (mip, total_mips),
            }

        mip_w = max(1, tex_w >> mip)
        mip_h = max(1, tex_h >> mip)

        if mip_w > max_dim or mip_h > max_dim:
            suggested_mip = None
            for m in range(total_mips):
                w = max(1, tex_w >> m)
                h = max(1, tex_h >> m)
                if w <= max_dim and h <= max_dim:
                    suggested_mip = m
                    break
            if suggested_mip is None:
                hint = "No mip level fits; set max_dim to at least %d." % max(mip_w, mip_h)
            else:
                hint = "Use mip=%d or set max_dim to at least %d." % (
                    suggested_mip, max(mip_w, mip_h))
            return {
                "error": "image_too_large",
                "mip": mip,
                "mip_width": mip_w,
                "mip_height": mip_h,
                "max_dim": max_dim,
                "suggested_mip": suggested_mip,
                "required_max_dim": max(mip_w, mip_h),
                "message": "Mip %d is %dx%d, exceeding max_dim=%d. %s" % (
                    mip, mip_w, mip_h, max_dim, hint),
            }

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}

        import renderdoc as rd

        tmp_path = None
        png_bytes = b""
        try:
            texsave = rd.TextureSave()
            texsave.resourceId = rid_obj
            texsave.mip = mip
            texsave.destType = rd.FileType.PNG
            texsave.alpha = rd.AlphaMapping.BlendToCheckerboard
            texsave.slice.sliceIndex = array_slice
            texsave.sample.sampleIndex = 0

            fd, tmp_path = _tempfile.mkstemp(suffix=".png", prefix="rendereye_")
            _os.close(fd)
            ok = controller.SaveTexture(texsave, tmp_path)
            if not ok:
                return {"error": "save_failed", "message": "SaveTexture returned False"}
            with open(tmp_path, "rb") as fh:
                png_bytes = fh.read()
        except Exception as exc:
            return {"error": "save_error", "message": str(exc)}
        finally:
            if tmp_path is not None:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass

        format_str = ""
        try:
            format_str = str(tex.format.Name())
        except Exception:
            pass

        return {
            "resource_id": resource_id_str,
            "mip": mip,
            "array_slice": array_slice,
            "width": mip_w,
            "height": mip_h,
            "format": format_str,
            "image_data": _base64.b64encode(png_bytes).decode("ascii"),
            "mime_type": "image/png",
            "encoding": "base64",
            "byte_size": len(png_bytes),
        }

    def _inspect_get_pixel_value(self, ctx, params):
        """Retrieve typed pixel component value(s) at given coordinate(s)."""
        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        mip = int(params.get("mip", 0))
        array_slice = int(params.get("array_slice", 0))
        sample = int(params.get("sample", 0))
        coords = params.get("coords", None)

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {"error": "resource_not_found", "resource_id": resource_id_str}

        try:
            tex = ctx.GetTexture(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetTexture not available: " + str(exc)}
        if tex is None:
            return {"error": "not_a_texture", "resource_id": resource_id_str}

        total_mips = 1
        try:
            total_mips = int(tex.mips)
        except Exception:
            pass
        if mip >= total_mips:
            return {"error": "invalid_mip", "mip": mip, "mip_levels": total_mips}

        mip_w = max(1, int(tex.width) >> mip)
        mip_h = max(1, int(tex.height) >> mip)

        format_str = ""
        try:
            format_str = str(tex.format.Name())
        except Exception:
            pass

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}

        import renderdoc as rd

        sub = rd.Subresource()
        sub.mip = mip
        sub.slice = array_slice
        sub.sample = sample

        def pick_one(px, py):
            if px < 0 or py < 0 or px >= mip_w or py >= mip_h:
                return {
                    "error": "out_of_bounds",
                    "x": px,
                    "y": py,
                    "mip_width": mip_w,
                    "mip_height": mip_h,
                }
            try:
                val = controller.PickPixel(rid_obj, px, py, sub, rd.CompType.Typeless)
                result = _pixel_value_to_dict(val)
                result["x"] = px
                result["y"] = py
                return result
            except Exception as exc:
                return {"error": "pick_failed", "x": px, "y": py, "message": str(exc)}

        meta = {
            "resource_id": resource_id_str,
            "mip": mip,
            "array_slice": array_slice,
            "sample": sample,
            "mip_width": mip_w,
            "mip_height": mip_h,
            "format": format_str,
        }

        if coords is not None:
            coord_list = list(coords)[:_MAX_PIXEL_BATCH]
            pixels = []
            for c in coord_list:
                px = int(c.get("x", 0))
                py = int(c.get("y", 0))
                pixels.append(pick_one(px, py))
            meta["pixels"] = pixels
            meta["pixel_count"] = len(pixels)
            return meta
        else:
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            pix = pick_one(x, y)
            meta.update(pix)
            return meta

    def _inspect_get_texture_statistics(self, ctx, params):
        """Retrieve min/max pixel values and optionally a histogram for a texture subresource."""
        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        mip = int(params.get("mip", 0))
        array_slice = int(params.get("array_slice", 0))
        include_histogram = bool(params.get("include_histogram", False))
        hist_min = float(params.get("hist_min", 0.0))
        hist_max = float(params.get("hist_max", 1.0))

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {"error": "resource_not_found", "resource_id": resource_id_str}

        try:
            tex = ctx.GetTexture(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": "GetTexture not available: " + str(exc)}
        if tex is None:
            return {"error": "not_a_texture", "resource_id": resource_id_str}

        format_str = ""
        try:
            format_str = str(tex.format.Name())
        except Exception:
            pass

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}

        import renderdoc as rd

        sub = rd.Subresource()
        sub.mip = mip
        sub.slice = array_slice
        sub.sample = 0

        result = {
            "resource_id": resource_id_str,
            "mip": mip,
            "array_slice": array_slice,
            "format": format_str,
        }

        try:
            mn, mx = controller.GetMinMax(rid_obj, sub, rd.CompType.Typeless)
            result["min"] = _pixel_value_to_dict(mn)
            result["max"] = _pixel_value_to_dict(mx)
        except Exception as exc:
            result["min_max_error"] = str(exc)

        if include_histogram:
            try:
                hist = controller.GetHistogram(
                    rid_obj, sub, rd.CompType.Typeless, hist_min, hist_max,
                    (True, True, True, True),
                )
                bins = [int(b) for b in list(hist)[:_MAX_HISTOGRAM_BINS]]
                result["histogram"] = bins
                result["histogram_bin_count"] = len(bins)
                result["histogram_range"] = [hist_min, hist_max]
            except Exception as exc:
                result["histogram_error"] = str(exc)

        return result

    def _inspect_list_gpu_counters(self, ctx, params):
        """Enumerate available GPU performance counters and their descriptions."""
        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "Replay controller not available"}
            counters = controller.EnumerateCounters()
            result_list = []
            for c in counters:
                try:
                    desc = controller.DescribeCounter(c)
                    unit_str = str(desc.unit)
                    rtype_str = str(desc.resultType)
                    entry = {
                        "counter_id": int(c),
                        "name": str(desc.name),
                        "description": str(desc.description),
                        "unit": unit_str.split(".")[-1] if "." in unit_str else unit_str,
                        "result_type": rtype_str.split(".")[-1] if "." in rtype_str else rtype_str,
                        "result_byte_width": int(desc.resultByteWidth),
                    }
                    if hasattr(desc, "uuid") and desc.uuid:
                        entry["uuid"] = str(desc.uuid)
                    result_list.append(entry)
                except Exception:
                    pass
            return {"counters": result_list, "count": len(result_list)}
        except Exception as exc:
            return {"error": "inspection_failed", "message": str(exc)}

    def _inspect_fetch_gpu_counters(self, ctx, params):
        """Collect GPU performance counter values for all events in the loaded capture.

        This operation runs FetchCounters() which may execute multiple replay passes
        and perform GPU work. It is not read-only.
        """
        counter_ids_raw = params.get("counter_ids")
        if not counter_ids_raw or not isinstance(counter_ids_raw, list):
            return {
                "error": "missing_counter_ids",
                "message": "counter_ids must be a non-empty list of integer counter IDs",
            }

        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "Replay controller not available"}
            import renderdoc as rd

            available_counters = controller.EnumerateCounters()
            available_set = set(int(c) for c in available_counters)

            requested = []
            invalid = []
            for cid in counter_ids_raw:
                try:
                    cid_int = int(cid)
                    if cid_int in available_set:
                        requested.append(cid_int)
                    else:
                        invalid.append(cid_int)
                except (ValueError, TypeError):
                    invalid.append(cid)

            if not requested:
                return {
                    "error": "no_valid_counters",
                    "message": (
                        "None of the requested counter IDs are available on this GPU/API/RenderDoc version"
                    ),
                    "invalid_counter_ids": invalid,
                }

            rd_counters = [rd.GPUCounter(c) for c in requested]

            # Build counter descriptions for serialization type info
            desc_map = {}
            counter_descriptions = []
            for c, cint in zip(rd_counters, requested):
                try:
                    d = controller.DescribeCounter(c)
                    unit_str = str(d.unit)
                    rtype_str = str(d.resultType)
                    unit = unit_str.split(".")[-1] if "." in unit_str else unit_str
                    rtype = rtype_str.split(".")[-1] if "." in rtype_str else rtype_str
                    desc_map[cint] = {
                        "name": str(d.name),
                        "unit": unit,
                        "result_type": rtype,
                        "result_byte_width": int(d.resultByteWidth),
                    }
                    counter_descriptions.append({
                        "counter_id": cint,
                        "name": str(d.name),
                        "unit": unit,
                        "result_type": rtype,
                        "result_byte_width": int(d.resultByteWidth),
                    })
                except Exception:
                    desc_map[cint] = {"result_type": "Float", "result_byte_width": 4, "unit": "Absolute", "name": ""}

            # Fetch counters (may require multiple GPU replay passes)
            raw_results = controller.FetchCounters(rd_counters)

            serialized = []
            for r in raw_results:
                cid_int = int(r.counter)
                desc = desc_map.get(cid_int, {"result_type": "Float", "result_byte_width": 4})
                rtype = desc.get("result_type", "Float")
                rbytes = desc.get("result_byte_width", 4)

                try:
                    if rtype == "Double" or (rtype == "Float" and rbytes == 8):
                        val = _json_safe_float(r.value.d)
                    elif rtype == "Float":
                        val = _json_safe_float(r.value.f)
                    elif rtype in ("UInt", "UnsignedInteger") and rbytes == 8:
                        val = int(r.value.u64)
                    elif rtype in ("UInt", "UnsignedInteger"):
                        val = int(r.value.u32)
                    elif rtype in ("SInt", "SignedInteger"):
                        val = int(r.value.i32)
                    else:
                        val = _json_safe_float(r.value.f)
                except Exception:
                    val = None

                serialized.append({
                    "event_id": int(r.eventId),
                    "counter_id": cid_int,
                    "value": val,
                })

            return {
                "results": serialized,
                "result_count": len(serialized),
                "counter_descriptions": counter_descriptions,
                "counters_fetched": requested,
                "counters_invalid": invalid,
            }
        except Exception as exc:
            return {"error": "inspection_failed", "message": str(exc)}

    # -----------------------------------------------------------------------
    # Phase 14: Geometry & Mesh Inspection
    # -----------------------------------------------------------------------

    def _inspect_draw_geometry_info(self, ctx, params):
        """Return draw parameters and geometry configuration for the current draw call."""
        event_id = int(params.get("event_id", 0))
        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d). "
                           "Select the event in RenderDoc first." % (event_id, current_event),
                "current_event_id": current_event,
            }

        action = ctx.CurAction()
        if action is None:
            return {"error": "no_action", "message": "No action at current replay event"}

        try:
            flags_int = int(action.flags)
        except Exception:
            flags_int = 0

        if not (flags_int & _FLAG_DRAWCALL):
            return {
                "error": "not_a_draw",
                "message": "Current event is not a draw call (action_type: %s)" % _action_type(flags_int),
                "action_type": _action_type(flags_int),
                "event_id": int(action.eventId),
            }

        result = {
            "event_id": int(action.eventId),
            "is_indexed": bool(flags_int & _FLAG_INDEXED),
            "is_instanced": bool(flags_int & _FLAG_INSTANCED),
            "is_indirect": bool(flags_int & _FLAG_INDIRECT),
        }

        sdf = None
        try:
            sdf = ctx.GetStructuredFile()
        except Exception:
            pass
        try:
            name = str(action.customName) if action.customName else ""
            if not name and sdf is not None:
                try:
                    name = str(action.GetName(sdf))
                except Exception:
                    pass
            result["name"] = name or ("Event %d" % result["event_id"])
        except Exception:
            result["name"] = "Event %d" % result["event_id"]

        for attr, key in [
            ("numIndices", "num_indices"),
            ("numInstances", "num_instances"),
            ("indexOffset", "index_offset"),
            ("baseVertex", "base_vertex"),
            ("instanceOffset", "instance_offset"),
        ]:
            try:
                result[key] = int(getattr(action, attr))
            except Exception:
                pass

        try:
            pipe = ctx.CurPipelineState()
            if pipe is not None:
                try:
                    topo = pipe.GetPrimitiveTopology()
                    result["topology"] = topo.name if hasattr(topo, "name") else str(topo)
                except Exception:
                    pass
                try:
                    vbufs = pipe.GetVBuffers()
                    if vbufs:
                        result["vertex_buffers"] = [
                            {
                                "slot": i,
                                "resource_id": _resource_id_str(vb.resourceId),
                                "byte_offset": int(vb.byteOffset) if hasattr(vb, "byteOffset") else 0,
                                "byte_stride": int(vb.byteStride) if hasattr(vb, "byteStride") else 0,
                            }
                            for i, vb in enumerate(vbufs[:16])
                        ]
                except Exception:
                    pass
                if flags_int & _FLAG_INDEXED:
                    try:
                        ibuf = pipe.GetIBuffer()
                        if ibuf is not None:
                            result["index_buffer"] = {
                                "resource_id": _resource_id_str(ibuf.resourceId),
                                "byte_offset": int(ibuf.byteOffset) if hasattr(ibuf, "byteOffset") else 0,
                                "byte_stride": int(ibuf.byteStride) if hasattr(ibuf, "byteStride") else 0,
                            }
                    except Exception:
                        pass
        except Exception:
            pass

        return result

    def _inspect_vertex_input_layout(self, ctx, params):
        """Return vertex input attributes and buffer bindings for the selected pipeline state."""
        event_id = int(params.get("event_id", 0))
        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d)." % (event_id, current_event),
                "current_event_id": current_event,
            }

        pipe = ctx.CurPipelineState()
        if pipe is None:
            return {"error": "no_pipeline_state", "message": "No pipeline state available"}

        result = {"event_id": current_event}

        try:
            vbufs = pipe.GetVBuffers()
            if vbufs is not None:
                result["vertex_buffers"] = [
                    {
                        "slot": i,
                        "resource_id": _resource_id_str(vb.resourceId),
                        "byte_offset": int(vb.byteOffset) if hasattr(vb, "byteOffset") else 0,
                        "byte_stride": int(vb.byteStride) if hasattr(vb, "byteStride") else 0,
                    }
                    for i, vb in enumerate(vbufs[:16])
                ]
        except Exception:
            result["vertex_buffers"] = []

        try:
            ibuf = pipe.GetIBuffer()
            if ibuf is not None:
                result["index_buffer"] = {
                    "resource_id": _resource_id_str(ibuf.resourceId),
                    "byte_offset": int(ibuf.byteOffset) if hasattr(ibuf, "byteOffset") else 0,
                    "byte_stride": int(ibuf.byteStride) if hasattr(ibuf, "byteStride") else 0,
                }
        except Exception:
            pass

        attrs = []
        try:
            inputs = pipe.GetVertexInputs()
            if inputs is not None:
                for inp in inputs:
                    try:
                        fmt = inp.format
                        ct = _comp_type_str(fmt.compType) if hasattr(fmt, "compType") else "Unknown"
                        entry = {
                            "name": str(inp.name) if hasattr(inp, "name") else "",
                            "location": int(inp.location) if hasattr(inp, "location") else 0,
                            "vertex_buffer": int(inp.vertexBuffer) if hasattr(inp, "vertexBuffer") else 0,
                            "byte_offset": int(inp.byteOffset) if hasattr(inp, "byteOffset") else 0,
                            "per_instance": bool(inp.perInstance) if hasattr(inp, "perInstance") else False,
                            "instance_rate": int(inp.instanceRate) if hasattr(inp, "instanceRate") else 1,
                            "component_type": ct,
                            "component_count": int(fmt.compCount) if hasattr(fmt, "compCount") else 0,
                            "component_byte_width": int(fmt.compByteWidth) if hasattr(fmt, "compByteWidth") else 0,
                        }
                        try:
                            fmt_type = fmt.type
                            entry["format"] = fmt_type.name if hasattr(fmt_type, "name") else str(fmt_type)
                        except Exception:
                            pass
                        attrs.append(entry)
                    except Exception:
                        pass
        except Exception:
            pass

        result["attributes"] = attrs
        result["attribute_count"] = len(attrs)

        vs_inputs = []
        try:
            import renderdoc as rd
            refl = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
            if refl is not None and hasattr(refl, "inputSignature") and refl.inputSignature:
                for sig in refl.inputSignature:
                    try:
                        ct_str = _comp_type_str(sig.compType) if hasattr(sig, "compType") else "Unknown"
                        sv_str = ""
                        try:
                            sv = sig.systemValue
                            sv_str = sv.name if hasattr(sv, "name") else str(sv)
                        except Exception:
                            pass
                        entry = {
                            "semantic_name": str(sig.semanticName) if hasattr(sig, "semanticName") else "",
                            "semantic_index": int(sig.semanticIndex) if hasattr(sig, "semanticIndex") else 0,
                            "location": int(sig.regIndex) if hasattr(sig, "regIndex") else 0,
                            "component_type": ct_str,
                            "used_components": int(sig.compMask) if hasattr(sig, "compMask") else 0,
                        }
                        if sv_str and sv_str not in ("None", "Undefined", "Invalid"):
                            entry["system_value"] = sv_str
                        vs_inputs.append(entry)
                    except Exception:
                        pass
        except Exception:
            pass

        if vs_inputs:
            result["vs_input_signature"] = vs_inputs

        return result

    def _inspect_mesh_indices(self, ctx, params):
        """Decode a bounded range of indices from the bound index buffer."""
        event_id = int(params.get("event_id", 0))
        first_index = max(0, int(params.get("first_index", 0)))
        count = min(max(1, int(params.get("count", 100))), _MAX_INDEX_READ)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d)." % (event_id, current_event),
                "current_event_id": current_event,
            }

        pipe = ctx.CurPipelineState()
        if pipe is None:
            return {"error": "no_pipeline_state", "message": "No pipeline state available"}

        try:
            ibuf = pipe.GetIBuffer()
        except Exception as exc:
            return {"error": "index_buffer_unavailable", "message": str(exc)}

        if ibuf is None:
            return {"error": "no_index_buffer", "message": "No index buffer is bound"}

        rid_str = _resource_id_str(ibuf.resourceId)
        buf_byte_offset = int(ibuf.byteOffset) if hasattr(ibuf, "byteOffset") else 0
        index_stride = int(ibuf.byteStride) if hasattr(ibuf, "byteStride") else 2
        if index_stride not in (1, 2, 4):
            index_stride = 2

        base_vertex = 0
        try:
            action = ctx.CurAction()
            if action is not None:
                try:
                    base_vertex = int(action.baseVertex)
                except Exception:
                    pass
        except Exception:
            pass

        byte_offset = buf_byte_offset + first_index * index_stride
        byte_count = count * index_stride

        rid_obj = _find_resource_id_obj(ctx, rid_str)
        if rid_obj is None:
            return {"error": "resource_not_found", "resource_id": rid_str}

        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "GetBlockingController returned None"}
            data = controller.GetBufferData(rid_obj, byte_offset, byte_count)
        except Exception as exc:
            return {"error": "read_failed", "message": str(exc)}

        if data is None:
            return {"error": "read_failed", "message": "GetBufferData returned None"}

        import struct as _istruct
        fmt = {1: "<B", 2: "<H", 4: "<I"}.get(index_stride, "<H")
        actual_count = len(data) // index_stride
        indices = []
        for i in range(actual_count):
            raw = bytes(data[i * index_stride: (i + 1) * index_stride])
            if len(raw) < index_stride:
                break
            raw_idx = _istruct.unpack(fmt, raw)[0]
            indices.append({
                "position": first_index + i,
                "raw_index": raw_idx,
                "vertex_ref": raw_idx + base_vertex,
            })

        return {
            "event_id": current_event,
            "first_index": first_index,
            "count": len(indices),
            "requested_count": count,
            "index_byte_stride": index_stride,
            "base_vertex": base_vertex,
            "indices": indices,
        }

    def _inspect_mesh_vertices(self, ctx, params):
        """Decode vertex attributes for a range of vertices from the bound vertex buffers."""
        event_id = int(params.get("event_id", 0))
        first_vertex = max(0, int(params.get("first_vertex", 0)))
        count = min(max(1, int(params.get("count", 10))), _MAX_VERTEX_READ)
        attr_filter = params.get("attributes")

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d)." % (event_id, current_event),
                "current_event_id": current_event,
            }

        pipe = ctx.CurPipelineState()
        if pipe is None:
            return {"error": "no_pipeline_state", "message": "No pipeline state available"}

        try:
            vbufs_raw = pipe.GetVBuffers()
        except Exception as exc:
            return {"error": "vbuffer_unavailable", "message": str(exc)}

        if not vbufs_raw:
            return {"error": "no_vertex_buffers", "message": "No vertex buffers are bound"}

        try:
            inputs = list(pipe.GetVertexInputs() or [])
        except Exception as exc:
            return {"error": "input_layout_unavailable", "message": str(exc)}

        if not inputs:
            return {"error": "no_vertex_attributes", "message": "No vertex input attributes defined"}

        if attr_filter and isinstance(attr_filter, list):
            af_set = set(a.upper() for a in attr_filter)
            inputs = [inp for inp in inputs
                      if hasattr(inp, "name") and str(inp.name).upper() in af_set]
            if not inputs:
                return {
                    "error": "no_matching_attributes",
                    "message": "None of the requested attributes exist in the input layout",
                    "requested": attr_filter,
                }

        inputs = inputs[:32]

        needed_slots = set()
        for inp in inputs:
            try:
                if not (bool(inp.perInstance) if hasattr(inp, "perInstance") else False):
                    needed_slots.add(int(inp.vertexBuffer) if hasattr(inp, "vertexBuffer") else 0)
            except Exception:
                pass

        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "GetBlockingController returned None"}
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}

        buffer_data = {}
        for slot in needed_slots:
            if slot >= len(vbufs_raw):
                continue
            vb = vbufs_raw[slot]
            try:
                rid_str = _resource_id_str(vb.resourceId)
                rid_obj = _find_resource_id_obj(ctx, rid_str)
                if rid_obj is None:
                    continue
                stride = int(vb.byteStride) if hasattr(vb, "byteStride") else 0
                if stride <= 0:
                    continue
                buf_off = int(vb.byteOffset) if hasattr(vb, "byteOffset") else 0
                byte_offset = buf_off + first_vertex * stride
                byte_count = min(count * stride, _MAX_BUFFER_READ_BYTES)
                data = controller.GetBufferData(rid_obj, byte_offset, byte_count)
                if data is not None:
                    buffer_data[slot] = (bytes(data), stride)
            except Exception:
                pass

        if not buffer_data:
            return {
                "error": "no_buffer_data",
                "message": "Could not read any vertex buffer data",
                "event_id": current_event,
            }

        vertices = []
        for vi in range(count):
            vertex = {"vertex_id": first_vertex + vi, "attributes": {}}
            for inp in inputs:
                try:
                    per_inst = bool(inp.perInstance) if hasattr(inp, "perInstance") else False
                    if per_inst:
                        continue
                    slot = int(inp.vertexBuffer) if hasattr(inp, "vertexBuffer") else 0
                    if slot not in buffer_data:
                        continue
                    data, stride = buffer_data[slot]
                    attr_off = vi * stride + (int(inp.byteOffset) if hasattr(inp, "byteOffset") else 0)
                    fmt = inp.format if hasattr(inp, "format") else None
                    if fmt is None:
                        continue
                    ct = _comp_type_str(fmt.compType) if hasattr(fmt, "compType") else "Unknown"
                    num_comps = int(fmt.compCount) if hasattr(fmt, "compCount") else 1
                    comp_bw = int(fmt.compByteWidth) if hasattr(fmt, "compByteWidth") else 4
                    vals = _decode_vertex_attr(data, attr_off, ct, comp_bw, num_comps)
                    name = str(inp.name) if hasattr(inp, "name") else "attr_%d" % len(vertex["attributes"])
                    vertex["attributes"][name] = (vals if len(vals) > 1 else vals[0]) if vals is not None else None
                except Exception:
                    pass
            vertices.append(vertex)

        return {
            "event_id": current_event,
            "first_vertex": first_vertex,
            "count": len(vertices),
            "vertices": vertices,
        }

    def _inspect_post_vs_geometry(self, ctx, params):
        """Retrieve post-vertex-shader geometry for the selected draw call."""
        event_id = int(params.get("event_id", 0))
        instance_index = max(0, int(params.get("instance", 0)))
        view_index = max(0, int(params.get("view", 0)))
        stage_str = str(params.get("stage", "vs_out")).lower()
        max_verts = min(max(1, int(params.get("max_vertices", 50))), _MAX_POST_VS_VERTICES)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d)." % (event_id, current_event),
                "current_event_id": current_event,
            }

        try:
            controller = ctx.GetBlockingController()
            if controller is None:
                return {"error": "replay_unavailable", "message": "GetBlockingController returned None"}
            import renderdoc as rd
            stage_map = {
                "vs_in":  rd.MeshDataStage.VSIn,
                "vs_out": rd.MeshDataStage.VSOut,
                "gs_out": rd.MeshDataStage.GSOut,
            }
            stage = stage_map.get(stage_str)
            if stage is None:
                return {
                    "error": "invalid_stage",
                    "message": "stage must be one of: vs_in, vs_out, gs_out",
                    "requested": stage_str,
                }
            mesh = controller.GetPostVSData(instance_index, view_index, stage)
        except Exception as exc:
            return {"error": "inspection_failed", "message": str(exc)}

        if mesh is None:
            return {
                "error": "post_vs_unavailable",
                "message": "GetPostVSData returned None for stage=%s instance=%d view=%d" % (
                    stage_str, instance_index, view_index),
            }

        try:
            null_rid = rd.ResourceId.Null()
            vid_str = _resource_id_str(mesh.vertexResourceId) if hasattr(mesh, "vertexResourceId") else ""
            if vid_str == str(null_rid):
                return {
                    "error": "no_post_vs_data",
                    "message": "No post-VS vertex data available for stage=%s. "
                               "This draw may not support post-VS inspection." % stage_str,
                }
        except Exception:
            pass

        result = {"stage": stage_str, "instance": instance_index, "view": view_index, "event_id": current_event}

        try:
            topo = mesh.topology
            result["topology"] = topo.name if hasattr(topo, "name") else str(topo)
        except Exception:
            pass

        num_indices = 0
        try:
            num_indices = int(mesh.numIndices) if hasattr(mesh, "numIndices") else 0
            result["num_indices"] = num_indices
        except Exception:
            pass

        vert_stride = 0
        try:
            vert_stride = int(mesh.vertexByteStride) if hasattr(mesh, "vertexByteStride") else 0
            result["vertex_byte_stride"] = vert_stride
        except Exception:
            pass

        vert_byte_offset = 0
        try:
            vert_byte_offset = int(mesh.vertexByteOffset) if hasattr(mesh, "vertexByteOffset") else 0
        except Exception:
            pass

        # VS output signature for attribute decoding
        output_sig = []
        pos_sig = None
        pipe = ctx.CurPipelineState()
        if pipe is not None:
            try:
                refl = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
                if refl is not None and hasattr(refl, "outputSignature") and refl.outputSignature:
                    for sig in refl.outputSignature:
                        try:
                            sv_str = ""
                            try:
                                sv = sig.systemValue
                                sv_str = sv.name if hasattr(sv, "name") else str(sv)
                            except Exception:
                                pass
                            sem_name = str(sig.semanticName) if hasattr(sig, "semanticName") else ""
                            is_pos = sv_str == "Position" or sem_name.upper() in ("SV_POSITION",)
                            comp_mask = int(sig.compMask) if hasattr(sig, "compMask") else 0xF
                            num_comps = bin(comp_mask).count("1") or 4
                            reg_idx = int(sig.regIndex) if hasattr(sig, "regIndex") else 0
                            ct = _comp_type_str(sig.compType) if hasattr(sig, "compType") else "Float"
                            sig_entry = {
                                "semantic_name": sem_name,
                                "semantic_index": int(sig.semanticIndex) if hasattr(sig, "semanticIndex") else 0,
                                "reg_index": reg_idx,
                                "component_type": ct,
                                "component_count": num_comps,
                                "byte_offset": reg_idx * 16,
                            }
                            if sv_str and sv_str not in ("None", "Undefined", "Invalid"):
                                sig_entry["system_value"] = sv_str
                            if is_pos:
                                sig_entry["is_position"] = True
                                if pos_sig is None:
                                    pos_sig = sig_entry
                            output_sig.append(sig_entry)
                        except Exception:
                            pass
            except Exception:
                pass

        if output_sig:
            result["output_signature"] = output_sig

        # Read and decode vertex data
        if vert_stride > 0 and num_indices > 0:
            num_verts_to_read = min(max_verts, num_indices)
            byte_count = min(num_verts_to_read * vert_stride, _MAX_BUFFER_READ_BYTES)
            try:
                data = controller.GetBufferData(mesh.vertexResourceId, vert_byte_offset, byte_count)
            except Exception as exc:
                result["vertex_read_error"] = str(exc)
                data = None

            if data is not None:
                actual_verts = len(data) // vert_stride
                vertices = []
                for vi in range(actual_verts):
                    base = vi * vert_stride
                    vertex = {"vertex_index": vi}
                    attrs = {}
                    for sig_entry in output_sig:
                        try:
                            byte_off = base + sig_entry["byte_offset"]
                            ct = sig_entry["component_type"]
                            num_comps = sig_entry["component_count"]
                            sem_name = sig_entry["semantic_name"]
                            sem_idx = sig_entry.get("semantic_index", 0)
                            attr_name = ("%s%d" % (sem_name, sem_idx)) if sem_idx else sem_name
                            vals = _decode_vertex_attr(data, byte_off, ct, 4, num_comps)
                            if vals is not None:
                                if sig_entry.get("is_position"):
                                    attrs["SV_Position_clip"] = vals
                                    if len(vals) == 4:
                                        try:
                                            w = vals[3]
                                            if isinstance(w, (int, float)) and abs(float(w)) > 1e-10:
                                                w = float(w)
                                                attrs["SV_Position_ndc"] = [
                                                    _json_safe_float(float(vals[0]) / w),
                                                    _json_safe_float(float(vals[1]) / w),
                                                    _json_safe_float(float(vals[2]) / w),
                                                ]
                                        except Exception:
                                            pass
                                else:
                                    attrs[attr_name] = vals if len(vals) > 1 else vals[0]
                        except Exception:
                            pass
                    if attrs:
                        vertex["attributes"] = attrs
                    vertices.append(vertex)
                result["vertices"] = vertices
                result["vertices_read"] = len(vertices)
                result["vertices_available"] = num_indices

        return result

    def _inspect_mesh_statistics(self, ctx, params):
        """Compute geometry statistics from a bounded vertex position sample."""
        event_id = int(params.get("event_id", 0))
        max_verts = min(max(1, int(params.get("max_vertices", 200))), _MAX_GEOMETRY_STATS_VERTS)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            current_event = 0

        if event_id != 0 and event_id != current_event:
            return {
                "error": "event_not_selected",
                "message": "event_id %d is not the current replay event (%d)." % (event_id, current_event),
                "current_event_id": current_event,
            }

        action = ctx.CurAction()
        if action is None:
            return {"error": "no_action", "message": "No action at current replay event"}

        try:
            flags_int = int(action.flags)
        except Exception:
            flags_int = 0

        if not (flags_int & _FLAG_DRAWCALL):
            return {"error": "not_a_draw", "message": "Current event is not a draw call"}

        pipe = ctx.CurPipelineState()
        if pipe is None:
            return {"error": "no_pipeline_state"}

        result = {"event_id": current_event, "sampled": False}

        try:
            result["num_indices"] = int(action.numIndices)
        except Exception:
            pass
        try:
            result["num_instances"] = int(action.numInstances)
        except Exception:
            pass
        try:
            topo = pipe.GetPrimitiveTopology()
            result["topology"] = topo.name if hasattr(topo, "name") else str(topo)
        except Exception:
            pass

        # Find position attribute
        pos_attr = None
        try:
            inputs = list(pipe.GetVertexInputs() or [])
            for inp in inputs:
                try:
                    name_up = str(inp.name).upper() if hasattr(inp, "name") else ""
                    if name_up in ("POSITION", "SV_POSITION", "POSITION0", "IN_POSITION", "INPOSITION"):
                        pos_attr = inp
                        break
                except Exception:
                    pass
            if pos_attr is None and inputs:
                pos_attr = inputs[0]
        except Exception:
            pass

        if pos_attr is None:
            result["position_analysis"] = {"error": "no_position_attribute"}
            return result

        try:
            slot = int(pos_attr.vertexBuffer) if hasattr(pos_attr, "vertexBuffer") else 0
            vbufs_raw = pipe.GetVBuffers()
            if not vbufs_raw or slot >= len(vbufs_raw):
                result["position_analysis"] = {"error": "vertex_buffer_not_bound"}
                return result

            vb = vbufs_raw[slot]
            stride = int(vb.byteStride) if hasattr(vb, "byteStride") else 0
            if stride <= 0:
                result["position_analysis"] = {"error": "zero_stride"}
                return result

            buf_off = int(vb.byteOffset) if hasattr(vb, "byteOffset") else 0
            attr_byte_off = int(pos_attr.byteOffset) if hasattr(pos_attr, "byteOffset") else 0
            fmt = pos_attr.format if hasattr(pos_attr, "format") else None
            if fmt is None:
                result["position_analysis"] = {"error": "no_format"}
                return result

            ct = _comp_type_str(fmt.compType) if hasattr(fmt, "compType") else "Float"
            num_comps = int(fmt.compCount) if hasattr(fmt, "compCount") else 3
            comp_bw = int(fmt.compByteWidth) if hasattr(fmt, "compByteWidth") else 4

            num_indices = result.get("num_indices", 0)
            actual_max = min(max_verts, max(num_indices, 1))
            byte_count = min(actual_max * stride, _MAX_BUFFER_READ_BYTES)

            controller = ctx.GetBlockingController()
            if controller is None:
                result["position_analysis"] = {"error": "replay_unavailable"}
                return result

            rid_str = _resource_id_str(vb.resourceId)
            rid_obj = _find_resource_id_obj(ctx, rid_str)
            if rid_obj is None:
                result["position_analysis"] = {"error": "resource_not_found"}
                return result

            data = controller.GetBufferData(rid_obj, buf_off, byte_count)
            if data is None:
                result["position_analysis"] = {"error": "read_failed"}
                return result

            actual_verts = len(data) // stride
            if actual_verts < num_indices:
                result["sampled"] = True
                result["sampled_vertex_count"] = actual_verts

            import math as _gmath
            mn = [float("inf")] * num_comps
            mx = [float("-inf")] * num_comps
            nan_count = 0
            inf_count = 0
            valid_count = 0

            for vi in range(actual_verts):
                off = vi * stride + attr_byte_off
                vals = _decode_vertex_attr(data, off, ct, comp_bw, num_comps)
                if vals is None:
                    continue
                bad = False
                for i, v in enumerate(vals):
                    if v == "nan":
                        nan_count += 1
                        bad = True
                    elif v in ("inf", "-inf"):
                        inf_count += 1
                        bad = True
                    elif isinstance(v, float) and (_gmath.isnan(v) or _gmath.isinf(v)):
                        nan_count += (1 if _gmath.isnan(v) else 0)
                        inf_count += (1 if _gmath.isinf(v) else 0)
                        bad = True
                    elif isinstance(v, (int, float)):
                        fv = float(v)
                        if i < num_comps:
                            mn[i] = min(mn[i], fv)
                            mx[i] = max(mx[i], fv)
                if not bad:
                    valid_count += 1

            attr_name = str(pos_attr.name) if hasattr(pos_attr, "name") else "position"
            pos_analysis = {
                "attribute_name": attr_name,
                "component_count": num_comps,
                "vertices_analyzed": actual_verts,
                "valid_vertex_count": valid_count,
                "nan_component_count": nan_count,
                "inf_component_count": inf_count,
            }

            if valid_count > 0 and num_comps >= 3:
                if all(v != float("inf") for v in mn[:3]) and all(v != float("-inf") for v in mx[:3]):
                    pos_analysis["bounding_box"] = {
                        "min": [_json_safe_float(v) for v in mn[:3]],
                        "max": [_json_safe_float(v) for v in mx[:3]],
                        "coordinate_space": "object_space (vertex_buffer_input)",
                    }

            result["position_analysis"] = pos_analysis

        except Exception as exc:
            result["position_analysis"] = {"error": str(exc)}

        return result

    # Phase 15: Pixel History & Shader Debugging

    def _inspect_pixel_history(self, ctx, params):
        """Retrieve Pixel History for a given resource and pixel coordinate."""
        import renderdoc as rd

        resource_id_str = str(params.get("resource_id", ""))
        if not resource_id_str:
            return {"error": "resource_id is required"}

        x = max(0, int(params.get("x", 0)))
        y = max(0, int(params.get("y", 0)))
        mip = max(0, int(params.get("mip", 0)))
        array_slice = max(0, int(params.get("slice", 0)))
        sample = max(0, int(params.get("sample", 0)))
        max_mods = min(max(1, int(params.get("max_modifications", 50))), _MAX_PIXEL_HISTORY)

        rid_obj = _find_resource_id_obj(ctx, resource_id_str)
        if rid_obj is None:
            return {"error": "resource_not_found", "resource_id": resource_id_str}

        try:
            tex = ctx.GetTexture(rid_obj)
        except Exception as exc:
            return {"error": "unsupported", "message": str(exc)}
        if tex is None:
            return {"error": "not_a_texture", "resource_id": resource_id_str}

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}
        if controller is None:
            return {"error": "replay_unavailable"}

        sub = rd.Subresource()
        sub.mip = mip
        sub.slice = array_slice
        sub.sample = sample

        _ = str(rd.ResourceId.Null())

        try:
            modifications = controller.PixelHistory([rid_obj], x, y, sub, rd.CompType.Typeless)
        except Exception as exc:
            return {
                "error": "pixel_history_failed",
                "message": str(exc),
                "note": "PixelHistory may be unsupported for this graphics API or texture format",
            }

        if modifications is None:
            return {"error": "pixel_history_unsupported", "resource_id": resource_id_str}

        all_mods = list(modifications)
        total = len(all_mods)
        mods = []
        for mod in all_mods[:max_mods]:
            m = {}
            try:
                m["event_id"] = int(mod.eventId)
            except Exception:
                pass
            try:
                m["passed"] = bool(mod.passed)
            except Exception:
                pass
            try:
                m["prim_id"] = int(mod.primitiveID)
            except Exception:
                pass
            try:
                m["frag_index"] = int(mod.fragIndex)
            except Exception:
                pass
            try:
                m["depth_clipped"] = bool(mod.depthClipped)
            except Exception:
                pass
            try:
                m["backface_culled"] = bool(mod.backfaceCulled)
            except Exception:
                pass
            try:
                m["sample_masked"] = bool(mod.sampleMasked)
            except Exception:
                pass
            try:
                m["shader_discarded"] = bool(mod.shaderDiscarded)
            except Exception:
                pass
            try:
                m["depth_test_failed"] = bool(mod.depthTestFailed)
            except Exception:
                pass
            try:
                m["stencil_test_failed"] = bool(mod.stencilTestFailed)
            except Exception:
                pass
            try:
                m["scissor_clipped"] = bool(mod.scissorClipped)
            except Exception:
                pass
            try:
                m["pre_mod"] = _pixel_value_to_dict(mod.preMod)
            except Exception:
                pass
            try:
                m["shader_out"] = _pixel_value_to_dict(mod.shaderOut)
            except Exception:
                pass
            try:
                m["post_mod"] = _pixel_value_to_dict(mod.postMod)
            except Exception:
                pass
            try:
                m["pre_depth"] = _json_safe_float(mod.preMod.depth) if hasattr(mod.preMod, "depth") else None
            except Exception:
                pass
            try:
                m["post_depth"] = _json_safe_float(mod.postMod.depth) if hasattr(mod.postMod, "depth") else None
            except Exception:
                pass
            # Classify rejection reason
            if not m.get("passed", True):
                if m.get("depth_test_failed"):
                    m["rejection_reason"] = "depth_test"
                elif m.get("stencil_test_failed"):
                    m["rejection_reason"] = "stencil_test"
                elif m.get("shader_discarded"):
                    m["rejection_reason"] = "shader_discard"
                elif m.get("backface_culled"):
                    m["rejection_reason"] = "backface_cull"
                elif m.get("depth_clipped"):
                    m["rejection_reason"] = "depth_clip"
                elif m.get("scissor_clipped"):
                    m["rejection_reason"] = "scissor"
                elif m.get("sample_masked"):
                    m["rejection_reason"] = "sample_mask"
                else:
                    m["rejection_reason"] = "unknown"
            mods.append(m)

        result = {
            "resource_id": resource_id_str,
            "x": x,
            "y": y,
            "mip": mip,
            "slice": array_slice,
            "sample": sample,
            "total_modifications": total,
            "returned_modifications": len(mods),
            "truncated": total > max_mods,
            "modifications": mods,
        }

        # Summary
        passed = sum(1 for m in mods if m.get("passed", False))
        failed = len(mods) - passed
        result["summary"] = {
            "passed_fragments": passed,
            "rejected_fragments": failed,
        }
        if mods:
            last = max((m for m in mods if m.get("passed")), key=lambda m: m.get("event_id", 0), default=None)
            if last:
                result["summary"]["last_modifying_event"] = last.get("event_id")

        return result

    def _collect_debug_trace(self, controller, trace, max_steps):
        """Run a ShaderDebugTrace to completion and collect steps. Returns (steps, initial_vars, error)."""
        steps = []
        initial_vars = {}
        error = None
        debugger = None
        try:
            # Collect initial variable state
            try:
                init_inputs = list(trace.inputs) if hasattr(trace, "inputs") else []
                for v in init_inputs[:_MAX_SHADER_VARS]:
                    try:
                        initial_vars[str(v.name)] = _shader_var_to_dict(v)
                    except Exception:
                        pass
            except Exception:
                pass

            # Begin debug session
            try:
                debugger = controller.BeginDebugTrace(trace, None)
            except Exception as exc:
                error = "BeginDebugTrace failed: " + str(exc)
                return steps, initial_vars, error

            if debugger is None:
                error = "BeginDebugTrace returned null"
                return steps, initial_vars, error

            # Collect steps
            for _ in range(max_steps):
                try:
                    state = controller.ContinueDebug(debugger)
                except Exception as exc:
                    error = "ContinueDebug failed: " + str(exc)
                    break
                if state is None:
                    break
                try:
                    steps.append(_debug_state_to_dict(state))
                except Exception:
                    break

        except Exception as exc:
            error = str(exc)
        finally:
            try:
                controller.FreeTrace(trace)
            except Exception:
                pass
        return steps, initial_vars, error

    def _inspect_debug_pixel(self, ctx, params):
        """Collect a pixel shader debug trace for the selected event."""
        import renderdoc as rd

        event_id_param = int(params.get("event_id", 0))
        x = max(0, int(params.get("x", 0)))
        y = max(0, int(params.get("y", 0)))
        sample = max(0, int(params.get("sample", 0)))
        primitive = int(params.get("primitive", -1))
        view = max(0, int(params.get("view", 0)))
        max_steps = min(max(1, int(params.get("max_steps", 200))), _MAX_TRACE_STEPS)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            return {"error": "no_event_selected"}

        event_id = event_id_param if event_id_param > 0 else current_event

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}
        if controller is None:
            return {"error": "replay_unavailable"}

        try:
            inputs = rd.DebugPixelInputs()
            inputs.sample = sample
            inputs.view = view
            if primitive >= 0:
                inputs.primitive = primitive
        except Exception as exc:
            return {"error": "debug_inputs_unavailable", "message": str(exc)}

        try:
            trace = controller.DebugPixel(event_id, x, y, inputs)
        except Exception as exc:
            return {
                "error": "debug_pixel_failed",
                "message": str(exc),
                "note": "DebugPixel may be unsupported for this graphics API or shader stage",
            }

        if trace is None:
            return {
                "error": "debug_pixel_unsupported",
                "note": "DebugPixel returned null — graphics API may not support pixel debugging",
            }

        steps, initial_vars, err = self._collect_debug_trace(controller, trace, max_steps)

        result = {
            "stage": "pixel",
            "event_id": event_id,
            "x": x,
            "y": y,
            "sample": sample,
            "step_count": len(steps),
            "truncated": len(steps) >= max_steps,
            "steps": steps,
            "initial_vars": initial_vars,
        }
        if err:
            result["collection_warning"] = err
        return result

    def _inspect_debug_vertex(self, ctx, params):
        """Collect a vertex shader debug trace for a specific vertex invocation."""

        event_id_param = int(params.get("event_id", 0))
        vert_id = max(0, int(params.get("vert_id", 0)))
        inst_id = max(0, int(params.get("inst_id", 0)))
        idx = max(0, int(params.get("idx", 0)))
        view = max(0, int(params.get("view", 0)))
        max_steps = min(max(1, int(params.get("max_steps", 200))), _MAX_TRACE_STEPS)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            return {"error": "no_event_selected"}

        event_id = event_id_param if event_id_param > 0 else current_event

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}
        if controller is None:
            return {"error": "replay_unavailable"}

        try:
            trace = controller.DebugVertex(event_id, vert_id, inst_id, idx, view)
        except Exception as exc:
            return {
                "error": "debug_vertex_failed",
                "message": str(exc),
                "note": "DebugVertex may be unsupported for this graphics API or shader stage",
            }

        if trace is None:
            return {
                "error": "debug_vertex_unsupported",
                "note": "DebugVertex returned null — graphics API may not support vertex debugging",
            }

        steps, initial_vars, err = self._collect_debug_trace(controller, trace, max_steps)

        result = {
            "stage": "vertex",
            "event_id": event_id,
            "vert_id": vert_id,
            "inst_id": inst_id,
            "idx": idx,
            "step_count": len(steps),
            "truncated": len(steps) >= max_steps,
            "steps": steps,
            "initial_vars": initial_vars,
        }
        if err:
            result["collection_warning"] = err
        return result

    def _inspect_debug_compute(self, ctx, params):
        """Collect a compute shader debug trace for a specific thread invocation."""

        event_id_param = int(params.get("event_id", 0))
        group_x = max(0, int(params.get("group_x", 0)))
        group_y = max(0, int(params.get("group_y", 0)))
        group_z = max(0, int(params.get("group_z", 0)))
        thread_x = max(0, int(params.get("thread_x", 0)))
        thread_y = max(0, int(params.get("thread_y", 0)))
        thread_z = max(0, int(params.get("thread_z", 0)))
        max_steps = min(max(1, int(params.get("max_steps", 200))), _MAX_TRACE_STEPS)

        try:
            current_event = int(ctx.CurEvent())
        except Exception:
            return {"error": "no_event_selected"}

        event_id = event_id_param if event_id_param > 0 else current_event

        try:
            controller = ctx.GetBlockingController()
        except Exception as exc:
            return {"error": "replay_unavailable", "message": str(exc)}
        if controller is None:
            return {"error": "replay_unavailable"}

        groupid = [group_x, group_y, group_z]
        threadid = [thread_x, thread_y, thread_z]

        try:
            trace = controller.DebugThread(event_id, groupid, threadid)
        except Exception as exc:
            return {
                "error": "debug_compute_failed",
                "message": str(exc),
                "note": "DebugThread may be unsupported for this graphics API or shader stage",
            }

        if trace is None:
            return {
                "error": "debug_compute_unsupported",
                "note": "DebugThread returned null — graphics API may not support compute debugging",
            }

        steps, initial_vars, err = self._collect_debug_trace(controller, trace, max_steps)

        result = {
            "stage": "compute",
            "event_id": event_id,
            "group": [group_x, group_y, group_z],
            "thread": [thread_x, thread_y, thread_z],
            "step_count": len(steps),
            "truncated": len(steps) >= max_steps,
            "steps": steps,
            "initial_vars": initial_vars,
        }
        if err:
            result["collection_warning"] = err
        return result

    def close(self):
        self.context = None
