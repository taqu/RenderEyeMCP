[English](missing-mesh.md) | [日本語](../../ja/examples/missing-mesh.md)

# Scenario G1 — Missing geometry

## Problem

An object is not visible in the rendered output, but a draw call for it exists in the
capture. You want to determine whether the geometry is incorrect, the vertex data is
invalid, or the transformed positions place the mesh outside the view frustum.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm with `get_current_capture`.
3. Select (or identify) the draw call for the missing object.

## Example prompt

> Inspect the geometry used by the currently selected draw call. Check its vertex and
> index buffers, input layout, and post-vertex-shader positions. Identify any suspicious
> values that could explain why the object is not visible.

---

## Investigation workflow

### 1. Confirm the capture is loaded

```json
{ "tool": "get_current_capture" }
```

Expected response (illustrative):

```json
{
  "status": "loaded",
  "path": "C:/captures/game_frame_0123.rdc",
  "api": "D3D12",
  "frame_number": 123
}
```

### 2. Get draw call geometry configuration

```json
{ "tool": "get_draw_geometry_info" }
```

Check:
- Is `draw_type` `indexed` or `non_indexed`? If `indirect`, the agent can only read
  metadata.
- Is `index_count` or `vertex_count` non-zero? A zero count means no geometry is
  submitted and the object cannot appear.
- Are `vertex_buffers` bound? An unbound VB slot means vertices cannot be fetched.
- Is an `index_buffer` present for an indexed draw?

Example response (illustrative):

```json
{
  "event_id": 712,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 2400,
  "instance_count": 1,
  "first_index": 0,
  "base_vertex": 0,
  "first_instance": 0,
  "vertex_buffers": [
    { "slot": 0, "resource_id": "0x0000a3f1", "byte_offset": 0, "byte_stride": 32 }
  ],
  "index_buffer": { "resource_id": "0x0000a3f2", "byte_offset": 0, "format": "uint16" }
}
```

### 3. Inspect the vertex input layout

```json
{ "tool": "get_vertex_input_layout" }
```

Check:
- Is `POSITION` present and bound to a valid VB slot?
- Are the component type and count correct (typically `Float`, 3 components)?
- Does the `byte_offset` of each attribute look plausible given the stride (32 bytes)?

Example response excerpt (illustrative):

```json
{
  "attributes": [
    { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 0,  "per_instance": false },
    { "name": "NORMAL",   "location": 1, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 12, "per_instance": false },
    { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 24, "per_instance": false }
  ]
}
```

POSITION starts at offset 0, NORMAL at 12 (3 × 4 bytes), TEXCOORD at 24 (6 × 4 bytes).
Total stride: 32 bytes — consistent with the VB stride above. No issues.

### 4. Read a sample of vertex positions

```json
{
  "tool": "get_mesh_vertices",
  "first_vertex": 0,
  "count": 10,
  "attributes": ["POSITION"]
}
```

Examine the first ten positions. Look for:
- NaN or infinity in any component.
- All-zero positions (object not initialized?).
- Positions on a plausible scale (a character mesh at world scale should be ~1–2 m tall,
  not at 0.001 or 10 000).

Example response excerpt (illustrative — suspicious case):

```json
{
  "vertices": [
    { "vertex_id": 0, "attributes": { "POSITION": [0.0, 0.0, 0.0] } },
    { "vertex_id": 1, "attributes": { "POSITION": [0.0, 0.0, 0.0] } },
    { "vertex_id": 2, "attributes": { "POSITION": [0.0, 0.0, 0.0] } }
  ]
}
```

All-zero positions before the vertex shader indicate the VB was not uploaded or was
cleared. This is a strong signal for a resource initialization bug.

### 5. Check geometry statistics

```json
{
  "tool": "get_mesh_statistics",
  "max_vertices": 200
}
```

Example response (illustrative — NaN positions):

```json
{
  "vertex_count": 2400,
  "index_count": 2400,
  "instance_count": 1,
  "topology": "triangle_list",
  "sampled": true,
  "bounding_box": null,
  "nan_inf_count": 2400,
  "degenerate_primitives": null
}
```

`nan_inf_count: 2400` means every sampled component is NaN or infinity — the vertex
buffer contains garbage. `bounding_box: null` is expected when no finite values exist.

### 6. Retrieve post-VS geometry

If vertex buffer data looks plausible but the object is still missing, the vertex shader
transformation may be wrong:

```json
{
  "tool": "get_post_vs_geometry",
  "stage": "vs_out",
  "max_vertices": 20
}
```

Check `clip_pos` and `ndc_pos` in the response. Valid on-screen triangles should have:
- `w > 0`
- NDC `x` and `y` within `[-1, 1]`
- NDC `z` within `[0, 1]` (D3D) or `[-1, 1]` (GL/Vulkan)

Example response (illustrative — off-screen):

```json
{
  "vertices": [
    { "vertex_id": 0, "clip_pos": [1500.2, 200.1, 0.5, 1.0],
      "ndc_pos":  [1500.2, 200.1, 0.5] },
    { "vertex_id": 1, "clip_pos": [1502.8, 201.5, 0.5, 1.0],
      "ndc_pos":  [1502.8, 201.5, 0.5] }
  ]
}
```

NDC `x` values of 1500 are far outside `[-1, 1]`. The geometry is transformed correctly
in object space but the view/projection matrix is wrong, placing the mesh hundreds of
clip units from the center.

### 7. Correlate with shader constants

Use `get_current_shaders` and constant buffer inspection to verify the view-projection
matrix bound to the vertex shader:

```json
{ "tool": "get_current_shaders", "event_id": 712 }
```

If the MVP matrix contains unexpected values (identity when a non-identity was expected,
or a matrix from a previous frame), that explains the off-screen NDC positions.

---

## Diagnostic decision tree

```
get_draw_geometry_info
├── index_count == 0 or vertex_count == 0  →  Draw submits no geometry (CPU-side bug)
├── vertex_buffers unbound               →  VB not set before draw call
└── otherwise → check vertex data

get_mesh_vertices (POSITION)
├── all zeros                            →  VB not uploaded / cleared
├── NaN or infinity                      →  VB contains invalid data
└── plausible values → check post-VS

get_post_vs_geometry
├── ndc_pos outside [-1,1]²              →  Wrong transform matrix
├── w ≤ 0                                →  Behind camera or degenerate projection
└── ndc_pos within bounds               →  Geometry visible; check rasterizer/culling
```

---

## Expected observations

- The most common causes of missing meshes are: zero vertex count, unbound vertex
  buffer, invalid (NaN/Inf/zero) vertex data, and incorrect transformation matrices.
- `get_mesh_statistics` quickly surfaces NaN/Inf without reading every vertex.
- Comparing vertex-buffer positions (object space) with post-VS clip positions makes
  the transformation chain observable without shader stepping.

---

## Limitations

- `get_post_vs_geometry` replays the draw call. For very large meshes set
  `max_vertices` to a small number (10–20) to limit cost.
- Vertex buffer values read by `get_mesh_vertices` are pre-transformation (object
  space). Do not compare them directly with clip-space post-VS positions.
- Indirect draws report metadata but the actual vertex count is determined at draw
  time; NaN detection will still work if the buffer is readable.

## Related tools

`get_current_capture`, `get_draw_geometry_info`, `get_vertex_input_layout`,
`get_mesh_vertices`, `get_mesh_statistics`, `get_post_vs_geometry`,
`get_current_shaders` — see the [geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
