[English](vertex-debugging.md) | [日本語](../../ja/examples/vertex-debugging.md)

# Scenario D4 — Vertex Shader Debugging

## Problem

Mesh vertices appear at wrong positions after transformation. You want to step through
the vertex shader for a specific vertex to see the MVP matrix multiplication result and
find where the transformation goes wrong.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded.
3. A draw call with the mispositioned mesh is selected or known.

## Example prompts

**Quick investigation:**
> Vertex 0 of draw event 310 is ending up at the wrong clip-space position. Step
> through the vertex shader to find where the transformation breaks down.

**Detailed investigation:**
> The mesh in draw event 310 appears at the wrong position on screen. First check the
> object-space position of vertex 0 and the post-VS position to confirm the scale of
> the problem. Then debug the vertex shader for vertex 0. Find the step where the
> world-space position first shows an extreme or incorrect value. At that step, inspect
> the model matrix and the world-space position variable to identify the incorrect
> matrix component.

## What the agent should investigate

- The object-space position of the affected vertex (pre-transformation)
- The post-vertex-shader position to confirm the vertex is off-screen and by how much
- A vertex shader debug trace for vertex 0 (or another representative vertex)
- The execution step where world-space position first becomes incorrect
- The model matrix value at that step, particularly looking for an unexpected scale or translation component

## Expected results

A complete investigation should identify the specific matrix component causing the issue. For example: post-VS NDC y = 200 (far outside [-1, 1]), vertex shader step 8 shows `pos_ws.y = 1000.0` after the model-to-world transform, and `model_matrix[1][1] = 1000.0` confirms the Y scale in the model matrix is 1000 instead of 1.

| Step | Finding |
|---|---|
| Post-VS clip: NDC y = 200 | Vertex is 200× too far in Y |
| Vertex shader step 8: `pos_ws.y = 1000` | Model-to-world transform scales Y by 1000 |
| `model_matrix[1][1] = 1000.0` | Confirmed: wrong scale in model matrix upload |

## How to interpret the results

The model-to-world transform is usually the first matrix applied in the vertex shader. If the world-space position is already incorrect after step 8, the model matrix itself is wrong — check where it is computed or uploaded in the application.

If the world-space position is correct but the clip-space position is wrong, the view-projection matrix is the culprit. Look for a matrix that was set once at initialization and never updated to follow the camera.

## Limitations

- Vertex shader debugging debugs a single vertex invocation. Other vertices may have
  different values; repeat for additional vertices if needed.
- For indexed draws, pass the index buffer value as `idx`. For non-indexed draws,
  `idx = vert_id + base_vertex`.
- Returns `error: debug_vertex_unsupported` if the API or driver does not support
  vertex shader debugging.

## Related tools

`get_draw_geometry_info`, `get_mesh_vertices`, `get_post_vs_geometry`,
`debug_vertex_shader`, `get_shader_debug_trace`, `get_shader_debug_variables` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
