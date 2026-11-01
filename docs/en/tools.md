[English](tools.md) | [日本語](../ja/tools.md)

# MCP tool reference

RenderEyeMCP registers **58 tools**. You normally do not call tools yourself; the agent
does. Knowing them helps you write precise prompts and read the agent's transcript.

- [Conventions](#conventions)
- [Session and capture](#session-and-capture)
- [Events](#events)
- [Pipeline state](#pipeline-state)
- [Resources and buffers](#resources-and-buffers)
- [Shaders and reflection](#shaders-and-reflection)
- [Render targets, textures and pixels](#render-targets-textures-and-pixels)
- [GPU performance analysis](#gpu-performance-analysis)
- [Geometry and mesh inspection](#geometry-and-mesh-inspection)
- [Advanced debugging (Pixel History & Shader Debug)](#advanced-debugging-pixel-history--shader-debug)
- [Capture files and managed windows](#capture-files-and-managed-windows)
- [Diagnostics](#diagnostics)
- [Examples](#examples)

## Conventions

**Read-only.** Every tool in this reference is read-only except the five marked
*changes GUI state*. Inspection tools never change the event selected in RenderDoc.

**Selected event.** Inspection tools work on the event currently **selected in the
RenderDoc GUI**. `get_pipeline_state` accepts `event_id` only to confirm it equals the
selected event (otherwise `error: event_not_selected`). `get_capture_event` can describe
any event without selecting it.

**`instance_id` (optional, default `""`).** Every inspection tool accepts it. When empty,
RenderEyeMCP picks the only connected RenderDoc session, or the only one with a capture
loaded. If several qualify you get `status: ambiguous` with a `sessions` list; repeat
the call with one of their `instance_id` values. Get IDs from `list_renderdoc_sessions`.

**Identifiers.** Resource IDs are strings such as `ResourceId::805`; event IDs are the
EIDs shown in RenderDoc. Both are only meaningful for the capture currently loaded.
The values in this page are examples, not IDs that exist in your capture.

**Every inspection result** includes `_capture_path`, the capture it was read from.

**Common results**

| Result | Meaning |
|--------|---------|
| `status: no_renderdoc_connected` | No RenderDoc window with the extension is connected |
| `status: ambiguous` | Several sessions qualify; pass `instance_id` |
| `error: no_capture_loaded` / `capture_loading` | Connected, but no capture is ready yet |
| `error: resource_not_found` | The resource ID does not exist in the loaded capture |
| `error: shader_not_bound` | No shader at that stage for the selected event |
| `error: timeout` | The extension did not answer within 30 s (RenderDoc busy or blocked by a dialog) |
| `error: extension_error` | RenderDoc raised an error; `message` has the details |
| `error: result_too_large` | The answer exceeded the 16 MiB IPC message limit; request less data |

## Session and capture

| Tool | Parameters | Returns |
|------|-----------|---------|
| `list_renderdoc_sessions` | — | `sessions[]`: `instance_id`, `process_id`, `connection_state` (`connected`/`disconnected`/`unknown`), `renderdoc_version`, `capture` (`state`, `path`), `last_known_capture` for disconnected sessions |
| `get_renderdoc_session_state` | `instance_id` (required) | One session as above; `error: session_not_found` if unknown |
| `get_current_capture` | `instance_id` | `status`: `loaded`, `no_capture_loaded`, `capture_loading`, `ambiguous`, `session_not_found`, `session_disconnected`, `no_renderdoc_connected`; with `capture_path`, `instance_id` when loaded |
| `get_current_capture_info` | `instance_id` | `api` (`D3D11`/`D3D12`/`OpenGL`/`Vulkan`), `vendor`, `frame_number`, `degraded`, `statistics` (`total_events`, `draw_calls`, `dispatches`), `resource_count` |

These work with captures opened any way — manually, by Unity, by Unreal Engine.

## Events

| Tool | Parameters | Returns / limits |
|------|-----------|------------------|
| `list_capture_events` | `limit` (50, **max 200**), `offset` (0), `include_markers` (true), `flags_filter` (`""`, `drawcall`, `dispatch`), `parent_event_id` (0 = top level) | `events[]` (`event_id`, `name`, `action_type`, `flags`, `num_indices`, `num_instances`, `dispatch_dimension`, `child_count`), `total`, `has_more` |
| `get_capture_event` | `event_id` (required) | The event and its `children`; does not select it |
| `get_selected_event` | — | `selected_event_id`, `current_event_id`, `selected_action` (name such as `ID3D12GraphicsCommandList::DrawIndexedInstanced()`) |

With `flags_filter` set, the list is flattened across the whole frame.

## Pipeline state

`get_pipeline_state` — `section` (default `summary`), `event_id` (0 = selected event).

| `section` | Contents |
|-----------|----------|
| `summary` | `pipeline_type` (`graphics`/`compute`), `topology`, bound stages and entry points, `render_target_count`, `has_depth_target` |
| `input_assembly` | `topology`, `index_buffer` (`resource_id`, `offset`, `stride`), `vertex_buffers[]` |
| `shaders` | Bound shader per stage |
| `rasterizer` | `viewports[]`, `scissors[]` (all slots; unused slots are zero-sized) |
| `depth_stencil` | **A note only.** Depth/stencil state is not exposed by RenderDoc's API-neutral interface |
| `output_merger` | `render_targets[]` (`resource_id`, `format`), `depth_target` |
| `resources` | `bindings[]`: stage, `binding_type` (`cbuffer`/`texture`/`uav`), `resource_id` |

Not available: cull mode, fill mode, depth function/write, stencil, blend state,
vertex input layout attributes (use the vertex shader's input signature instead).

## Resources and buffers

| Tool | Parameters | Returns / limits |
|------|-----------|------------------|
| `list_resources` | `resource_type` (`all`/`texture`/`buffer`), `name_filter` (substring), `limit` (50, **max 500**), `offset` | `resources[]` (`resource_id`, `name`, `category`), `total`, `has_more` |
| `get_resource_info` | `resource_id` (required) | Name, category and texture- or buffer-specific details |
| `get_texture_info` | `resource_id` (required) | `width`, `height`, `depth`, `array_size`, `mip_levels`, `sample_count`, `format`, `texture_type`, `usage`, `byte_size` |
| `get_buffer_info` | `resource_id` (required) | `byte_size`, `usage`, `gpu_address` |
| `read_buffer_data` | `resource_id` (required), `offset` (0), `length` (256, **max 16384 bytes**), `output_format` (`hex`/`base64`/`bytes`), `decode_layout` (optional) | `data`, `buffer_byte_size`; with `decode_layout` also `decoded.elements[]` |

`decode_layout` = `{"stride": N, "element_count": N (max 100), "fields": [{"name", "type", "offset", "components" (1–16)}]}`.
Field types: `float16`, `float32`, `float64`, `int8`/`16`/`32`/`64`, `uint8`/`16`/`32`/`64`.

Buffer contents are read at the selected event. For a constant buffer, use the
`byte_offset` reported by `get_shader_bindings` as `offset` — many engines sub-allocate
constant buffers from one large buffer.

## Shaders and reflection

`stage` accepts `Vertex`/`vs`, `Hull`/`hs`, `Domain`/`ds`, `Geometry`/`gs`,
`Pixel`/`ps`/`fragment`, `Compute`/`cs` (case-insensitive).

| Tool | Parameters | Returns / limits |
|------|-----------|------------------|
| `list_shaders` | — | Bound shaders for the selected event: `stage`, `shader_id`, `entry_point`, reflection counts, `has_debug_info` |
| `get_shader_info` | `stage` (required) | IDs, entry point, resource counts, `encoding` (e.g. `DXIL`), `disassembly_targets`, `source_file_count` |
| `get_shader_reflection` | `stage` (required), `section` (`all`/`input`/`output`/`cbuffers`/`resources`/`samplers`) | Signatures; constant buffers with variables (`name`, `byte_offset`, `type`); read-only and read-write resource declarations. Max 100 variables per list |
| `get_shader_bindings` | `stage` (required) | Each declared cbuffer / texture / UAV with `bound`, `resource_id` (null if unbound), `byte_offset`, `byte_size` |
| `get_shader_disassembly` | `stage` (required), `target` (`""` = default), `offset`, `limit` (**max 200 lines**), `search` | `lines[]`, `total_lines`, `has_more`, `available_targets` |
| `get_shader_debug_info` | `stage` (required), `file_index` (0), `start_line` (0), `max_lines` (100, **max 500**) | Embedded source files and a line range, when the shader was compiled with them |

Shader debugging (stepping, variable values per invocation) is not implemented.

## Render targets, textures and pixels

| Tool | Parameters | Returns / limits |
|------|-----------|------------------|
| `get_render_targets` | — | `color_targets[]` (`index`, `resource_id`, `bound`, `width`, `height`, `format`, `mip`, `slice`), `depth_target`, `has_depth` |
| `get_texture_image` | `resource_id` (required), `mip` (0), `array_slice` (0), `max_dim` (1024) | An MCP **image** (PNG) plus metadata. If the mip is larger than `max_dim`: `error: image_too_large` with `suggested_mip` (or null) and `required_max_dim` |
| `get_pixel_value` | `resource_id` (required), `x`, `y`, `mip`, `array_slice`, `sample`, `coords` (list of `{x, y}`, **max 16**) | Raw typed values `float[]`, `uint[]`, `sint[]` (top-left origin); with `coords`, `pixels[]`. `error: out_of_bounds` outside the mip |
| `get_texture_statistics` | `resource_id` (required), `mip`, `array_slice`, `include_histogram` (false), `hist_min` (0.0), `hist_max` (1.0) | Per-channel `min` and `max`; optional `histogram` (up to 256 bins) |

Texture contents are those at the selected event. The PNG preview is a display
conversion (RenderDoc's own save path); pixel values are the exact stored data — use
them, not the image, for numeric conclusions. `get_texture_image` sends the whole PNG in
one message; very large textures may need a smaller mip.

## Capture files and managed windows

These tools predate the active-GUI workflow. They manage `.rdc` files on disk and
RenderDoc windows that RenderEyeMCP launches itself. They are covered by automated tests
but were **not validated live** for this release; window focus/close use Windows APIs.

| Tool | Purpose | GUI state |
|------|---------|-----------|
| `capture_list`, `capture_get`, `capture_latest` | Query the capture registry (`.rdc` files in `RENDEREYE_CAPTURE_DIRS`) | read-only |
| `capture_rescan` | Rescan watched folders now | read-only (updates the registry) |
| `capture_registry_status` | Watcher state and counts | read-only |
| `capture_open` | Open a registered capture in RenderDoc (`open_mode`: `new_window`, `reuse`, `replace`) | **changes GUI state** |
| `operation_get` | Status of a `capture_open` operation | read-only |
| `instance_list`, `instance_gui_state` | RenderDoc processes/windows and their reported state | read-only |
| `session_list`, `session_get` | Sessions created by `capture_open` | read-only |
| `session_focus` | Bring a session window to the front | **changes GUI state** |
| `session_close` | Close a managed, unprotected session window | **changes GUI state** |
| `session_protect` | Protect a session from close/replace | changes session record |

Windows opened by you (or by an engine) are never closed or replaced by these tools.

## Diagnostics

| Tool | Returns |
|------|---------|
| `server_status` | Server name and version, OS, Python, whether RenderDoc was detected, IPC listener state, extension connection and session counts |

## Examples

The values below are illustrative.

Default session resolution — no `instance_id`:

```json
{"tool": "get_current_capture", "arguments": {}}
```

Explicit session when two RenderDoc windows are open:

```json
{"tool": "get_selected_event", "arguments": {"instance_id": "591ad434-1100-4c5c-ba03-3aa0b1361258"}}
```

Describe an event without selecting it:

```json
{"tool": "get_capture_event", "arguments": {"event_id": 1039}}
```

Use a resource ID from `get_render_targets`:

```json
{"tool": "get_texture_info", "arguments": {"resource_id": "ResourceId::805"}}
```

Bounded buffer read decoded as `float4` values (a constant buffer at offset 0):

```json
{"tool": "read_buffer_data", "arguments": {
  "resource_id": "ResourceId::1401", "offset": 0, "length": 48,
  "decode_layout": {"stride": 16, "element_count": 3,
                    "fields": [{"name": "v", "type": "float32", "offset": 0, "components": 4}]}}}
```

Texture preview and pixels:

```json
{"tool": "get_texture_image", "arguments": {"resource_id": "ResourceId::805", "max_dim": 1280}}
{"tool": "get_pixel_value", "arguments": {"resource_id": "ResourceId::815", "coords": [{"x": 640, "y": 360}, {"x": 10, "y": 10}]}}
```

## GPU performance analysis

GPU performance tools work in two steps: **measurement** (calls the GPU) then
**analysis** (operates on stored results, no GPU work). Always call
`list_gpu_counters` → `collect_gpu_counters` before calling analysis tools.

### `list_gpu_counters`

Enumerate GPU performance counters available for the loaded capture.
Returns `counter_id`, `name`, `unit`, and `result_type` for each counter.
Counter availability depends on GPU, driver, graphics API, and RenderDoc version.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `instance_id` | `""` | Optional session ID |

### `collect_gpu_counters`

Collect GPU counter values for all events in the loaded capture.
Runs `FetchCounters()` which performs GPU replay — **not read-only**.
Returns a `measurement_id` for subsequent analysis calls.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `counter_ids` | required | List of integer IDs from `list_gpu_counters` |
| `instance_id` | `""` | Optional session ID |
| `repeats` | `1` | Collection runs, 1–5; multiple runs are averaged |

### `get_gpu_measurement_status`

Check the status of a stored measurement.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `measurement_id` | required | ID from `collect_gpu_counters` |

### `get_gpu_timings`

Retrieve event-level counter values from a completed measurement. Does not re-run the GPU.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `measurement_id` | required | — |
| `counter_id` | auto | Defaults to the first timing/duration counter |
| `min_value` | none | Minimum value filter |
| `sort_by` | `value_desc` | `value_desc`, `value_asc`, `event_id`, `event_id_desc` |
| `limit` / `offset` | `100` / `0` | Pagination |

### `get_performance_summary`

Rank the most expensive GPU events by counter value descending.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `measurement_id` | required | — |
| `counter_id` | auto | — |
| `top_n` | `20` | Max 100 |

### `get_render_pass_performance`

Aggregate counter results by debug marker hierarchy (render passes).
`aggregated_duration` is the **sum of leaf event values** — not the GPU wall-clock elapsed time.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `measurement_id` | required | — |
| `counter_id` | auto | — |
| `instance_id` | `""` | Needed for event hierarchy lookup |

### `get_pipeline_statistics`

Filter measurement results to pipeline statistics counters
(vertex invocations, primitive counts, pixel shader invocations, etc.).

| Parameter | Default | Notes |
|-----------|---------|-------|
| `measurement_id` | required | — |
| `event_id` | none | Filter to a single draw call |
| `limit` / `offset` | `100` / `0` | Pagination |

## Geometry and mesh inspection

All geometry tools operate on the event currently **selected in the RenderDoc GUI**. Pass `event_id` only to verify the correct event is selected (otherwise `error: event_not_selected`). `get_post_vs_geometry` executes replay work and is **not read-only**.

| Tool | Parameters | Returns / limits |
|------|-----------|------------------|
| `get_draw_geometry_info` | `event_id` (0), `instance_id` | `is_indexed`, `is_instanced`, `is_indirect`, `num_indices`, `num_instances`, draw offsets (`index_offset`, `base_vertex`, `instance_offset`), `topology`, `vertex_buffers[]`, `index_buffer` |
| `get_vertex_input_layout` | `event_id` (0), `instance_id` | `attributes[]` (name, format, `component_type`, `component_count`, `component_byte_width`, `vertex_buffer` slot, `byte_offset`, `per_instance`), `vertex_buffers[]`, `index_buffer`, `vs_input_signature[]` |
| `get_mesh_indices` | `event_id` (0), `first_index` (0), `count` (100, **max 1000**), `instance_id` | `indices[]` (`position`, `raw_index`, `vertex_ref`), `index_byte_stride`, `base_vertex` |
| `get_mesh_vertices` | `event_id` (0), `first_vertex` (0), `count` (10, **max 100**), `attributes` (list, optional), `instance_id` | `vertices[]` (`vertex_id`, `attributes{}`) — per-vertex only; per-instance attributes excluded |
| `get_post_vs_geometry` | `event_id` (0), `instance` (0), `view` (0), `stage` (`vs_out`/`vs_in`/`gs_out`), `max_vertices` (50, **max 100**), `instance_id` | `vertices[]` with `SV_Position_clip` (XYZW), `SV_Position_ndc` (X/W, Y/W, Z/W), other VS outputs; `output_signature[]`, `topology`, `num_indices` — **changes replay state** |
| `get_mesh_statistics` | `event_id` (0), `max_vertices` (200, **max 500**), `instance_id` | `position_analysis`: `bounding_box` (object-space min/max XYZ), `valid_vertex_count`, `nan_component_count`, `inf_component_count`, `vertices_analyzed`; `sampled` flag |

`get_post_vs_geometry` positions are clip-space (before perspective divide). `SV_Position_ndc` = `{x/w, y/w, z/w}` and is omitted when `w` is zero or near-zero. `get_mesh_statistics` bounding box reflects vertex buffer input, not transformed clip-space positions.

## Advanced debugging (Pixel History & Shader Debug)

Seven tools for pixel-level and shader-level GPU debugging using RenderDoc's Pixel History
and Shader Debug Trace APIs.

| Tool | Description |
|---|---|
| `get_pixel_history` | Retrieve modifications affecting a selected pixel (replay-based) |
| `debug_pixel_shader` | Collect a bounded pixel shader debug trace |
| `debug_vertex_shader` | Collect a bounded vertex shader debug trace |
| `debug_compute_shader` | Collect a bounded compute shader debug trace |
| `get_shader_debug_trace` | Retrieve bounded steps from a stored debug trace |
| `get_shader_debug_variables` | Reconstruct variable state at a specific trace step |
| `get_shader_debug_status` | Check debug trace status and list stored traces |

