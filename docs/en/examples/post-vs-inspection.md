[English](post-vs-inspection.md) | [日本語](../../ja/examples/post-vs-inspection.md)

# Scenario G3 — Vertex transformation

## Problem

An object appears in the wrong position, is distorted after transformation, or partially
clips through the view frustum in an unexpected way. You want to inspect both the input
positions (object space) and the post-vertex-shader positions (clip space) to trace the
transformation.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm with `get_current_capture`.
3. Select the draw call in RenderDoc.

## Example prompt

> Inspect the input and post-VS positions of this mesh. Check whether the transformed
> vertices fall outside the visible clip-space region, and examine the relevant
> transformation constants.

---

## Investigation workflow

### 1. Confirm the capture is loaded

```json
{ "tool": "get_current_capture" }
```

### 2. Get geometry configuration

```json
{ "tool": "get_draw_geometry_info" }
```

Note `event_id`, `topology`, `index_count` / `vertex_count`, and `instance_count`.

Example (illustrative):

```json
{
  "event_id": 520,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 720,
  "instance_count": 1,
  "base_vertex": 0
}
```

### 3. Read input positions (object space)

```json
{
  "tool": "get_mesh_vertices",
  "first_vertex": 0,
  "count": 10,
  "attributes": ["POSITION"]
}
```

Example (illustrative — a unit sphere):

```json
{
  "vertices": [
    { "vertex_id": 0, "attributes": { "POSITION": [ 0.000,  1.000,  0.000] } },
    { "vertex_id": 1, "attributes": { "POSITION": [ 0.866,  0.500,  0.000] } },
    { "vertex_id": 2, "attributes": { "POSITION": [ 0.866, -0.500,  0.000] } },
    { "vertex_id": 3, "attributes": { "POSITION": [ 0.000, -1.000,  0.000] } }
  ]
}
```

A unit sphere with radius 1. The object is in model space; absolute values within
`[-1, 1]` are expected.

### 4. Retrieve post-VS geometry (clip space)

```json
{
  "tool": "get_post_vs_geometry",
  "stage": "vs_out",
  "max_vertices": 10
}
```

Example (illustrative — perspective projection at distance 5):

```json
{
  "vertices": [
    { "vertex_id": 0,
      "clip_pos": [ 0.000,  1.732,  4.900,  5.000],
      "ndc_pos":  [ 0.000,  0.346,  0.980],
      "outputs": {} },
    { "vertex_id": 1,
      "clip_pos": [ 1.500,  0.866,  4.900,  5.000],
      "ndc_pos":  [ 0.300,  0.173,  0.980],
      "outputs": {} },
    { "vertex_id": 2,
      "clip_pos": [ 1.500, -0.866,  4.900,  5.000],
      "ndc_pos":  [ 0.300, -0.173,  0.980],
      "outputs": {} },
    { "vertex_id": 3,
      "clip_pos": [ 0.000, -1.732,  4.900,  5.000],
      "ndc_pos":  [ 0.000, -0.346,  0.980],
      "outputs": {} }
  ]
}
```

All NDC values are within `[-1, 1]` and `w = 5.0 > 0`. The sphere is visible and
correctly projected.

### 5. Detect a wrong transformation (illustrative — suspicious case)

If instead the response shows:

```json
{
  "vertices": [
    { "vertex_id": 0, "clip_pos": [   0.0, 1732.0, 4900.0, 5000.0],
      "ndc_pos":      [   0.0,  346.4,  980.0] },
    { "vertex_id": 1, "clip_pos": [1500.0,  866.0, 4900.0, 5000.0],
      "ndc_pos":      [ 300.0,  173.2,  980.0] }
  ]
}
```

NDC `x` = 300 and `y` = 346 are orders of magnitude outside `[-1, 1]`. The object
exists in the scene (finite clip positions, `w > 0`) but is completely off-screen. This
means the model transform, view matrix, or projection matrix is incorrect.

### 6. Inspect the vertex shader constant buffers

```json
{ "tool": "get_current_shaders" }
```

Identify the vertex shader and the constant buffer slot containing the MVP matrix.

```json
{ "tool": "get_resource_info", "resource_id": "<cbuffer_resource_id>" }
```

Read the first 64 bytes of the constant buffer (4×4 float32 = 64 bytes) to examine the
matrix. A common mistake is an MVP matrix that was set once during initialization and not
updated to follow the camera.

### 7. Validate W handling

Pay special attention to vertices where `clip_pos[3]` (w) is near zero or negative:

```json
{ "vertex_id": 5, "clip_pos": [0.1, 0.2, 0.0, 0.0], "ndc_pos": null }
```

`ndc_pos: null` means `w ≈ 0`; the tool skips the perspective divide to avoid
division-by-zero. A cluster of vertices with `w ≈ 0` indicates the camera near plane
is incorrectly configured, or a perspective matrix has a degenerate value.

### 8. Geometry statistics on post-VS positions

Use `get_mesh_statistics` to get bounding box information in object space:

```json
{ "tool": "get_mesh_statistics", "max_vertices": 200 }
```

Compare the object-space bounding box with the expected world-space position of the
object. If the object should be at world position `(100, 0, 50)` but the POSITION
bounding box is `[-1, 1]` (unit sphere), the scale is in the vertex shader transform and
the object-space data is correct.

---

## Coordinate space summary

| Data source | Coordinate space | Expected range |
|---|---|---|
| `get_mesh_vertices` POSITION | Object / model space | Depends on mesh scale |
| `get_post_vs_geometry` `clip_pos` | Clip space (homogeneous) | Finite; `w > 0` for visible |
| `get_post_vs_geometry` `ndc_pos` | NDC (after perspective divide) | `[-1, 1]` per axis for on-screen |

---

## Common transformation bugs

| NDC observation | Likely cause |
|---|---|
| All values >> 1 or << -1 | Missing or incorrect projection matrix |
| All values ≈ 0 | Object at origin after transform; view matrix wrong |
| `w ≤ 0` for all vertices | Object behind camera; view or model transform incorrect |
| One axis wrong, others ok | Row/column order wrong in matrix upload |
| Different instances off-screen | Per-instance transform buffer not updated |

---

## Limitations

- `get_post_vs_geometry` triggers a draw replay. Keep `max_vertices` small (10–20)
  when investigating — you only need a representative sample to diagnose the transform.
- Only VS output stage (`vs_out`) is demonstrated here. `gs_out` is available if the
  draw uses a geometry shader.
- `ndc_pos` is derived by the tool: `[x/w, y/w, z/w]`. It is not provided by RenderDoc
  directly; verify using the clip values if the projection matrix is non-standard.

## Related tools

`get_current_capture`, `get_draw_geometry_info`, `get_mesh_vertices`,
`get_post_vs_geometry`, `get_mesh_statistics`, `get_current_shaders` — see the
[geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
