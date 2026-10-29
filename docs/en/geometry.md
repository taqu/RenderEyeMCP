[English](geometry.md) | [日本語](../ja/geometry.md)

# Geometry & Mesh Inspection

## Introduction

RenderEyeMCP provides six tools for inspecting the geometry consumed and produced by
graphics draw calls. Inspection is performed against the capture already loaded in the
RenderDoc GUI — no live application is required and no new capture is taken.

The tools are organized around two complementary views of a draw call:

- **Input geometry** — what the application supplied: vertex buffers, index buffer, input
  layout, and draw parameters.
- **Output geometry** — what the vertex shader produced: clip-space positions and shader
  outputs retrieved through RenderDoc's replay infrastructure.

Separating these two views makes it straightforward to answer questions such as:

- "Are the vertex positions in the buffer valid?"
- "Does the vertex buffer layout match the vertex shader input signature?"
- "Did the vertex shader transform the geometry correctly?"
- "How many primitives does this draw call process, and are any degenerate?"

---

## Prerequisites

- RenderDoc is running with the RenderEyeMCP extension enabled.
- A capture (`.rdc` file) is open in the RenderDoc GUI.
- The currently selected event (or an explicitly supplied `event_id`) must be a graphics
  draw call. Non-draw events (state changes, copies, computes) are not supported.
- Verify readiness with `get_current_capture` before calling any geometry tool.

---

## Available tools

| Tool | Responsibility | Read-only |
|---|---|---|
| `get_draw_geometry_info` | Draw parameters and geometry configuration | Yes |
| `get_vertex_input_layout` | Vertex attributes and buffer bindings | Yes |
| `get_mesh_indices` | Decode a bounded index range | Yes |
| `get_mesh_vertices` | Decode selected vertex attributes | Yes |
| `get_post_vs_geometry` | Post-vertex-shader positions and outputs | No† |
| `get_mesh_statistics` | Geometry statistics: bounds, degenerates, invalid values | Yes |

† `get_post_vs_geometry` triggers a replay pass to capture vertex shader outputs and is
therefore marked `readOnlyHint: false`. It does not modify the loaded capture or the
selected event visible in the RenderDoc GUI.

---

## Supported draw types

All tools support both indexed and non-indexed draws. Instanced draws are supported with
explicit `instance_id` / `instance` parameters where relevant.

| Draw type | Supported |
|---|---|
| Non-indexed (`Draw`) | Yes |
| Indexed (`DrawIndexed`) | Yes |
| Instanced (`DrawInstanced`, `DrawIndexedInstanced`) | Yes (bounded) |
| Indirect (`DrawIndirect`, `DrawIndexedIndirect`) | Metadata only |
| Compute, copy, blit | Not applicable |

For indirect draws the server returns available metadata (vertex/index counts as
reported by RenderDoc) but cannot expand the indirect argument buffer itself.

---

## Supported primitive topologies

Topology is reported as returned by RenderDoc:

`triangle_list`, `triangle_strip`, `triangle_fan`, `line_list`, `line_strip`,
`point_list`, `patch_list`, and adjacency variants.

Degenerate primitive detection (`get_mesh_statistics`) is implemented for `triangle_list`
only. Other topologies report `degenerate_primitives: null`.

---

## Tool reference

### `get_draw_geometry_info`

Returns the geometry configuration of the target draw call: draw type, topology, vertex
and index counts, instance count, draw offsets, vertex buffer bindings, and index buffer
binding.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `instance_id` | string | `""` | MCP instance identifier (multi-agent routing) |

**Key response fields**

| Field | Meaning |
|---|---|
| `draw_type` | `indexed`, `non_indexed`, or `indirect` |
| `topology` | Primitive topology string |
| `index_count` | Index elements processed (indexed draws) |
| `vertex_count` | Vertex count (non-indexed draws) |
| `instance_count` | Number of instances |
| `first_index` | Starting index in the index buffer |
| `base_vertex` | Signed offset added to each index |
| `first_instance` | First instance index |
| `vertex_buffers` | List of bound VB slots with resource ID, offset, stride |
| `index_buffer` | Bound IB resource ID, offset, format |

---

### `get_vertex_input_layout`

Returns the vertex input attributes declared by the pipeline and their buffer bindings.
Each attribute record matches a `VertexInputAttribute` from RenderDoc's pipeline state.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `instance_id` | string | `""` | MCP instance identifier |

**Key response fields per attribute**

| Field | Meaning |
|---|---|
| `name` | Attribute/semantic name (e.g. `POSITION`, `NORMAL`) |
| `location` | Shader input register location |
| `comp_type` | Component type: `Float`, `UNorm`, `SNorm`, `UInt`, `SInt`, … |
| `comp_count` | Number of components (1–4) |
| `comp_byte_width` | Bytes per component |
| `vertex_buffer` | VB binding slot |
| `byte_offset` | Byte offset within the vertex element |
| `per_instance` | `true` for per-instance attributes |
| `instance_rate` | Instance step rate or divisor |

---

### `get_mesh_indices`

Decodes a bounded range of index values from the bound index buffer. Returns raw index
values; `base_vertex` is reported separately and is not added to the decoded values.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `first_index` | int | `0` | Starting position within the index array |
| `count` | int | `100` | Number of indices to return (max 1 000) |
| `instance_id` | string | `""` | MCP instance identifier |

For non-indexed draws the tool returns an error explaining that the draw has no index
buffer.

---

### `get_mesh_vertices`

Decodes vertex attribute values from the bound vertex buffers for a range of vertices.
Per-instance attributes are skipped because the tool addresses by vertex index only.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `first_vertex` | int | `0` | Starting vertex index |
| `count` | int | `10` | Number of vertices to return (max 100) |
| `attributes` | list[string] | `null` | Attribute names to include; `null` returns all |
| `instance_id` | string | `""` | MCP instance identifier |

**Key response fields per vertex**

| Field | Meaning |
|---|---|
| `vertex_id` | Vertex index (equal to `first_vertex + n`) |
| `attributes` | Object mapping attribute name → decoded component list |

---

### `get_post_vs_geometry`

Retrieves post-vertex-shader geometry using RenderDoc's `GetPostVSData` API. The API
replays the draw call to record vertex shader outputs; this has a GPU and CPU cost
comparable to collecting one GPU performance counter.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `instance` | int | `0` | Instance index |
| `view` | int | `0` | View index (for multi-view rendering) |
| `stage` | string | `"vs_out"` | `vs_in`, `vs_out`, or `gs_out` |
| `max_vertices` | int | `50` | Maximum output vertices (max 100) |
| `instance_id` | string | `""` | MCP instance identifier |

**Key response fields per vertex**

| Field | Meaning |
|---|---|
| `vertex_id` | Output vertex index |
| `clip_pos` | Clip-space position `[x, y, z, w]` |
| `ndc_pos` | NDC position `[x/w, y/w, z/w]` (omitted if `w ≈ 0`) |
| `outputs` | Other shader output attributes (from VS output signature) |

Post-VS position is **clip space**, not world space. NDC conversion is provided for
convenience and assumes a standard perspective divide. Interpret it in the context of the
active projection matrix.

---

### `get_mesh_statistics`

Computes geometry statistics by reading up to `max_vertices` vertex positions and,
for indexed draws, a bounded set of indices.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `event_id` | int | `0` | `0` uses the currently selected GUI event |
| `max_vertices` | int | `200` | Vertices to sample for bounds and validity (max 500) |
| `instance_id` | string | `""` | MCP instance identifier |

**Key response fields**

| Field | Meaning |
|---|---|
| `vertex_count` | Total vertices declared by the draw |
| `index_count` | Total indices declared (indexed draws) |
| `instance_count` | Instance count |
| `topology` | Primitive topology |
| `sampled` | `true` when fewer vertices were read than the total count |
| `bounding_box` | `{min: [x,y,z], max: [x,y,z]}` over sampled POSITION values |
| `nan_inf_count` | Components with NaN or infinite values |
| `degenerate_primitives` | Degenerate triangle count (triangle_list only; else `null`) |

---

## Coordinate spaces

| Space | When encountered |
|---|---|
| Object / local space | Vertex buffer positions before transformation |
| View / world space | Intermediate shader computation (not directly observable) |
| Clip space | Post-VS `clip_pos` from `get_post_vs_geometry` |
| NDC | `ndc_pos` = clip / w, derived by the tool for convenience |

Do not treat vertex buffer positions and post-VS clip-space positions as equivalent.
They use different coordinate spaces and numerical scales.

---

## Instancing behavior

`get_draw_geometry_info` and `get_mesh_statistics` report aggregate counts (total
instances, total vertices). To inspect a specific instance:

- `get_post_vs_geometry`: use the `instance` parameter.
- `get_mesh_vertices`: per-instance attributes are currently skipped; only per-vertex
  attributes are decoded.
- `get_mesh_indices`: indices are shared across instances; no per-instance filtering.

---

## GPU performance correlation

Geometry inspection results can be combined with Phase 13 performance measurements.
Geometry tools never trigger GPU counter collection automatically.

Suggested workflow:

1. Collect timing and pipeline-statistics counters with `collect_gpu_counters`.
2. Retrieve results with `get_counter_values` or `get_pipeline_statistics`.
3. Identify expensive draw calls with `get_performance_summary`.
4. Use `get_draw_geometry_info` and `get_mesh_statistics` to examine the geometry of the
   expensive draw.
5. Use `get_post_vs_geometry` only if vertex transformation is suspect.

---

## Known limitations

- **Per-instance vertex attributes** — `get_mesh_vertices` skips per-instance attributes.
  Use `get_draw_geometry_info` to identify per-instance bindings and
  `get_vertex_input_layout` to find their offsets.
- **Indirect draws** — index and vertex counts for indirect draws are reported as
  exposed by RenderDoc; the tool cannot expand indirect argument buffers.
- **Geometry / mesh / task shaders** — stages beyond VS and GS are not addressed.
  `get_post_vs_geometry` with `stage: "gs_out"` requires a geometry shader to be active.
- **Degenerate detection** — supported for `triangle_list` only. Strip and fan topologies
  are reported as `null`.
- **Sampled statistics** — `get_mesh_statistics` reads at most `max_vertices` vertices.
  For large meshes, bounding box and invalid-value counts cover a sample, not the whole
  mesh.
- **Post-VS replay cost** — `get_post_vs_geometry` replays the draw; avoid calling it in
  a tight loop. For large meshes limit `max_vertices` to reduce data transfer.
- **Format support** — half-precision (float16) vertex attributes are not decoded;
  affected components are returned as `null`.

---

## Related documentation

- [GPU performance analysis](performance.md)
- [Tool reference](tools.md#geometry-and-mesh-inspection)
- [Scenario G1 — Missing geometry](examples/missing-mesh.md)
- [Scenario G2 — Incorrect vertex format](examples/vertex-layout.md)
- [Scenario G3 — Vertex transformation](examples/post-vs-inspection.md)
- [Scenario G4 — Geometry performance](examples/geometry-performance.md)
