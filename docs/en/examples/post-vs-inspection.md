[English](post-vs-inspection.md) | [日本語](../../ja/examples/post-vs-inspection.md)

# Scenario G3 — Vertex transformation

## Problem

An object appears in the wrong position, is distorted after transformation, or partially
clips through the view frustum in an unexpected way. You want to inspect both the input
positions (object space) and the post-vertex-shader positions (clip space) to trace the
transformation.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open.
3. Select the draw call in RenderDoc.

## Example prompts

**Quick investigation:**
> Inspect the input and post-VS positions of this mesh. Check whether the transformed
> vertices fall outside the visible clip-space region, and examine the relevant
> transformation constants.

**Detailed investigation:**
> The selected mesh appears at the wrong position on screen. Read the first 10 vertex
> positions in object space and the first 10 post-VS positions in clip space. Report
> whether the NDC values are within [-1, 1] and whether w is positive. If the object is
> off-screen, identify which axis shows an extreme value and check the constant buffer
> containing the MVP matrix for unexpected values.

## What the agent should investigate

- The geometry configuration: draw type, index count, vertex count
- A sample of input vertex positions in object space — the raw positions before any transformation
- Post-vertex-shader positions for those same vertices: clip space (x, y, z, w) and derived NDC coordinates
- Whether any vertices have w ≤ 0 (behind camera or degenerate projection)
- Whether NDC x/y are outside [-1, 1] (off-screen) and by how much
- The vertex shader's constant buffer containing the MVP or view-projection matrix, if off-screen positions are found

## Expected results

Valid on-screen triangles should have:
- `w > 0` for all vertices
- NDC `x` and `y` within `[-1, 1]`
- NDC `z` within `[0, 1]` (D3D) or `[-1, 1]` (GL/Vulkan)

| NDC observation | Likely cause |
|---|---|
| All values much greater than 1 or less than -1 | Missing or incorrect projection matrix |
| All values near 0 | Object at origin after transform; view matrix wrong |
| `w ≤ 0` for all vertices | Object behind camera; view or model transform incorrect |
| One axis wrong, others OK | Row/column order wrong in matrix upload |
| Different instances off-screen | Per-instance transform buffer not updated |

## How to interpret the results

- Object-space positions within a reasonable range combined with extreme NDC values point to a wrong view/projection matrix rather than corrupt vertex data.
- NDC `x` = 300 means the model is positioned hundreds of clip units from center — likely the MVP was not updated to follow the camera (was set once at initialization and never updated).
- A cluster of vertices with `w ≈ 0` indicates the camera near plane is incorrectly configured, or a perspective matrix has a degenerate value.
- Post-VS geometry retrieval triggers a draw replay. Keep `max_vertices` small (10–20) for diagnosis — a representative sample is enough.

## Limitations

- Post-VS geometry retrieval triggers a draw replay. Keep `max_vertices` small (10–20)
  when investigating — you only need a representative sample to diagnose the transform.
- Only VS output stage (`vs_out`) is shown here. `gs_out` is available if the
  draw uses a geometry shader.
- `ndc_pos` is derived by the tool: `[x/w, y/w, z/w]`. It is not provided by RenderDoc
  directly; verify using the clip values if the projection matrix is non-standard.

## Related tools

`get_current_capture`, `get_draw_geometry_info`, `get_mesh_vertices`,
`get_post_vs_geometry`, `get_mesh_statistics`, `get_current_shaders` — see the
[geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
