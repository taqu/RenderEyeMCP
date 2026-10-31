[English](depth-debugging.md) | [日本語](../../ja/examples/depth-debugging.md)

# Scenario E — Depth testing problems

## Problem

An object disappears behind something it should be in front of, flickers (z-fighting),
or vanishes only in some views.

## Preparation

Select the draw call of the object that is wrongly hidden.

## Example prompts

**Quick investigation:**
> Inspect the depth state of the selected draw call and the associated depth texture.
> Check the depth comparison function, depth writes, and relevant depth pixel values.

The agent will find that the comparison function and depth writes are **not available**
(see Limitations) and should say so; the remaining checks still give useful evidence.

**Detailed investigation:**
> The selected object is not appearing when it should be in front of other geometry.
> Inspect the bound depth render target: its format, size, and whether it matches the
> color target and viewport. Read the viewport depth range. Then sample depth values at
> several pixel coordinates on the object and around it, and describe whether the values
> are consistent with reversed-Z or standard depth convention. Identify any abnormality
> that could explain why the object is being rejected.

## What the agent should investigate

- The bound depth render target: resource ID, format (such as D32_FLOAT or R32_TYPELESS), and whether its dimensions match the color target and viewport
- The viewport depth range (min_depth and max_depth)
- Overall depth statistics across the target — the minimum and maximum depth values present
- Sampled depth values at specific pixel coordinates on and around the object

## Expected results

- A bound depth target whose size matches the color target and viewport, or a mismatch
- Viewport depth range, usually `0.0 – 1.0`
- Depth statistics, e.g. `min 0.0, max 0.025` — a tight range typical of reversed-Z
- Depth values at specific pixels, e.g. `0.00107` at the object's center

## How to interpret the results

- **No depth target bound** while the object relies on depth testing → wrong pass setup.
- **Size mismatch** between depth target and color target/viewport → depth tests
  against the wrong area.
- **Viewport depth range** not `0..1` (e.g. `0..0`) → everything lands on one depth.
- **Depth values vs. convention:** with reversed-Z (near = 1, far = 0) most of the
  scene is close to 0. If the values at the object are on the "wrong" side of the
  occluder's values for your convention, the comparison function or projection is a
  likely cause — confirm the comparison function in RenderDoc's Pipeline State panel.
- Depth values read at the selected event already include earlier draws; to see what
  this draw would test against, select the event just before it.

Determining exactly why a particular fragment failed needs Pixel History or shader
debugging, which RenderEyeMCP does not provide. Use RenderDoc's Pixel History for that
final step.

## Limitations

- Depth compare function, depth-write enable, stencil and depth-bounds state are not
  exposed (RenderDoc's API-neutral interface does not provide them).
- Pixel History is not implemented.
- Typeless depth formats (`R32_TYPELESS`) are reported as stored; the `float` channel
  holds the depth value for 32-bit float depth.

## Related tools

`get_pipeline_state`, `get_render_targets`, `get_texture_info`,
`get_texture_statistics`, `get_pixel_value` — see the [tool reference](../tools.md).
