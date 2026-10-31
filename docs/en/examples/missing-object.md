[English](missing-object.md) | [日本語](../../ja/examples/missing-object.md)

# Scenario B — An object is not visible

## Problem

An object that should appear in the frame is missing.

## Preparation

1. Find the draw call that should render the object (search the Event Browser for its
   marker or mesh name; *Texture Viewer → Overlay → Highlight Drawcall* helps).
2. Select that draw call. If you cannot find any draw call for the object, the problem
   is upstream (culling or submission in the engine), not in this frame's pipeline.

## Example prompts

**Quick investigation:**
> This object is not appearing in the frame. Inspect the selected draw call and check its
> vertex input, shaders, rasterizer state, depth state, and render targets. Identify
> suspicious settings. Separate confirmed findings from possible causes.

**Detailed investigation:**
> The selected draw call should render a visible object but nothing appears. Systematically
> inspect each pipeline stage: confirm the draw submits a non-zero vertex/index count,
> check the vertex buffer bindings and stride, verify the viewport and scissor cover the
> expected screen area, list the bound render targets with their formats and sizes, and
> identify any shader reflection mismatches. For each suspicious finding, state whether
> it is confirmed or a possible cause.

## What the agent should investigate

- Whether the draw call submits any geometry at all (index count, vertex count, instance count)
- Vertex buffer and index buffer bindings: whether they are bound and their strides
- The vertex shader's expected input attributes compared to what is declared in the pipeline
- Viewport and scissor rectangles: whether they are non-zero and cover the area where the object should appear
- Render targets: what color and depth targets are bound, their sizes and formats

## Expected results

| Check | Suspicious values |
|-------|-------------------|
| `num_indices` / `num_instances` | 0 |
| Topology | Not what the mesh uses (e.g. `LineList` instead of `TriangleList`) |
| Vertex buffers | Missing, stride different from the vertex layout, unexpected offset |
| Viewport/scissor | Zero size, or not covering the area where the object should be |
| Render targets | Nothing bound, an unexpected target, or a size mismatch with the viewport |
| Decoded positions | All zeros, NaN, or huge values |

## How to interpret the results

- A zero-sized viewport or scissor, zero instances, or no bound render target explains a
  missing object directly — these are **confirmed findings**.
- A stride mismatch or unexpected topology is a strong **possible cause**; check the
  engine's vertex layout.
- If everything looks plausible, the cause is probably in state RenderEyeMCP cannot
  show (culling, depth test, blending) or in the transforms; continue with
  [Scenario E](depth-debugging.md) and inspect the constant buffers
  ([Scenario C](shader-resources.md)).

A single draw call rarely proves *why* something is missing. Treat the result as a list
of facts and leads, not a diagnosis.

## Limitations

- Cull mode, fill mode, depth/stencil state and blend state are **not** exposed. Check
  them in RenderDoc's Pipeline State panel.
- The vertex input layout (attribute formats and offsets) is not exposed; the vertex
  shader's input signature shows what the shader expects.
- Post-transform geometry (mesh viewer output) is not available.

## Related tools

`get_selected_event`, `get_pipeline_state`, `list_shaders`, `get_shader_reflection`,
`get_render_targets`, `read_buffer_data`, `get_texture_image` —
see the [tool reference](../tools.md).
