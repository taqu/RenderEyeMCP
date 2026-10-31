[English](missing-mesh.md) | [日本語](../../ja/examples/missing-mesh.md)

# Scenario G1 — Missing geometry

## Problem

An object is not visible in the rendered output, but a draw call for it exists in the
capture. You want to determine whether the geometry is incorrect, the vertex data is
invalid, or the transformed positions place the mesh outside the view frustum.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open.
3. Select (or identify) the draw call for the missing object.

## Example prompts

**Quick investigation:**
> Inspect the geometry used by the currently selected draw call. Check its vertex and
> index buffers, input layout, and post-vertex-shader positions. Identify any suspicious
> values that could explain why the object is not visible.

**Detailed investigation:**
> The draw call at event 712 produces no visible output. Investigate the geometry
> thoroughly: confirm the draw type and index/vertex counts are non-zero, verify the
> vertex buffer is bound, read the first 10 vertex positions and check for all-zero or
> NaN values, check geometry statistics for NaN/Inf across all vertices, and retrieve
> post-VS clip positions for the first 20 vertices. Identify the most likely cause from
> the evidence found.

## What the agent should investigate

- The draw type (indexed/non-indexed/indirect), index count, vertex count, and instance count — a zero count means no geometry is submitted
- Whether vertex buffers are bound, and whether an index buffer is present for indexed draws
- The vertex input layout: whether POSITION is present, bound to a valid slot, and the component type and byte offsets look consistent with the vertex buffer stride
- A sample of vertex positions in object space: whether they are all zero, contain NaN/Inf, or are at an implausible scale
- Geometry statistics across the mesh: NaN/Inf count and bounding box (null bounding box when all positions are NaN)
- Post-vertex-shader positions: clip space and NDC positions, particularly whether NDC x/y are within [-1, 1] and w > 0

## Expected results

The most common causes of missing meshes are:

- Zero vertex count → draw submits no geometry (CPU-side bug)
- Vertex buffer not bound → vertices cannot be fetched
- All-zero positions → VB not uploaded or cleared
- NaN or Inf positions → VB contains invalid data
- NDC positions outside [-1, 1] → wrong transformation matrix

## How to interpret the results

**Diagnostic decision tree:**

```
Vertex/index count zero → Draw submits no geometry (CPU-side bug)
Vertex buffer unbound  → VB not set before draw call

Vertex positions all zero → VB not uploaded / cleared
Vertex positions NaN/Inf  → VB contains invalid data
Vertex positions plausible → check post-VS

Post-VS NDC outside [-1,1] → Wrong transform matrix
Post-VS w ≤ 0              → Behind camera or degenerate projection
Post-VS NDC within bounds  → Geometry visible; check rasterizer/culling
```

Comparing vertex-buffer positions (object space) with post-VS clip positions makes
the transformation chain observable without shader stepping.

## Limitations

- Post-VS geometry retrieval replays the draw call. For very large meshes set
  `max_vertices` to a small number (10–20) to limit cost.
- Vertex buffer values are pre-transformation (object space). Do not compare them
  directly with clip-space post-VS positions.
- Indirect draws report metadata but the actual vertex count is determined at draw
  time; NaN detection will still work if the buffer is readable.

## Related tools

`get_current_capture`, `get_draw_geometry_info`, `get_vertex_input_layout`,
`get_mesh_vertices`, `get_mesh_statistics`, `get_post_vs_geometry`,
`get_current_shaders` — see the [geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
