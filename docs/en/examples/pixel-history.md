[English](pixel-history.md) | [日本語](../../ja/examples/pixel-history.md)

# Scenario D1 — Incorrect Pixel Color

## Problem

A pixel on screen shows the wrong color. You need to find which draw call last wrote
that pixel and why the result differs from what is expected.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded.
3. You know the approximate screen coordinates of the wrong pixel.

## Example prompts

**Quick investigation:**
> Pixel at (512, 384) appears dark red but should be white. Find which draw call is
> responsible and what color the shader produced.

**Detailed investigation:**
> Pixel (512, 384) shows dark red but should be white. Use pixel history to find every
> draw that touched this pixel. Show all modifications — which passed, which were
> rejected, what the shader produced, and what the pixel value was before and after each
> event. Identify which event last wrote the pixel and explain whether there is a
> subsequent event whose output would have produced the correct color but was rejected.

**Follow-up investigation (optional):**
> Debug the pixel shader for the event that last wrote the dark red color to understand
> why it produced that color rather than white.

## What the agent should investigate

- Retrieve pixel history at the specified coordinate: all modifications, which events passed or were rejected, and rejection reasons
- Identify the last event that successfully wrote the pixel and the color it wrote
- Check whether any later event produced the correct color but was rejected, and if so, why (depth test, stencil test, shader discard, etc.)
- If the rejection reason is depth-related, examine the pipeline depth state of both the rejected draw and the draw that wrote the wrong color
- Optionally step through the pixel shader of the draw that produced the wrong color to investigate its lighting/texture logic

## Expected results

Pixel history will list all modifications to the pixel in event order. A typical wrong-color bug looks like: event 88 wrote dark red and passed; event 120 produced white but was rejected by the depth test. The pixel shows dark red because the white fragment lost the depth competition.

## How to interpret the results

- The **last modifying event** is the draw whose output is currently visible on screen.
- If a correct output exists in pixel history but was rejected, the bug is in the depth/stencil state, draw order, or blending — not in the pixel shader logic.
- If the last modifying event itself produced the wrong color, investigate that shader directly.
- `rejection_reason: depth_test` combined with a correct shader output strongly suggests a depth state or draw-order bug.
- Pixel History performs GPU replay. Avoid calling it in a loop over many pixels.

## Limitations

- Pixel History performs GPU replay. Avoid calling it in a loop over many pixels.
- `max_modifications` caps at 200. For extremely overdraw-heavy scenes, increase it.
- Pixel History availability depends on the graphics API; see
  [Advanced Debugging](../advanced-debugging.md#graphics-api-and-shader-support).

## Related tools

`get_current_capture`, `get_render_targets`, `get_pixel_history`,
`debug_pixel_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`,
`get_pipeline_state` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
