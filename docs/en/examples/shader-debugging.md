[English](shader-debugging.md) | [日本語](../../ja/examples/shader-debugging.md)

# Scenario D2 — Pixel Shader Debugging

## Problem

A draw call produces unexpected colors on screen but pixel history shows only one
fragment touching the pixel. The bug is inside the pixel shader itself — an incorrect
texture sample, wrong lighting formula, or an uninitialized variable.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded.
3. Pixel History has identified the event_id responsible for the bad pixel (see
   [Scenario D1](pixel-history.md)).

## Example prompts

**Quick investigation:**
> Event 244 is the only draw touching pixel (640, 400) but the output color is
> (0.0, 0.0, 0.0). Step through the pixel shader to find where the black color comes
> from.

**Detailed investigation:**
> Event 244 is the only draw touching pixel (640, 400) but produces black (0.0, 0.0, 0.0)
> instead of the expected lit color. Debug the pixel shader at this coordinate. Scan all
> execution steps for any NaN/Inf generation. Find the step where the final color
> variable first becomes black or zero. At that step, show the values of all relevant
> variables — particularly the texture sample color, any lighting term like n_dot_l, and
> the output color — and explain what caused the value to become zero.

## What the agent should investigate

- Collect a pixel shader debug trace for the specified pixel coordinate and event
- Scan all execution steps for NaN/Inf generation
- Find the step where the final output first becomes incorrect (black, zero, or wrong value)
- At that step, inspect the variable values, particularly inputs to any multiplication or division that produced zero output
- Identify whether the problem is a zero lighting term, a discarded fragment, a wrong texture sample, or an uninitialized variable

## Expected results

The debug trace will show variable changes at each shader step. A typical finding: the texture sample at step 18 returns a reasonable color `(0.72, 0.45, 0.21)`, but at step 35 the `diffuse` variable becomes `(0.0, 0.0, 0.0, 1.0)` because `n_dot_l` (dot product of normal and light direction) is `0.0`. The diffuse lighting term is `sampled_color * n_dot_l` = zero.

## How to interpret the results

| Step | Variable | Value | Observation |
|---|---|---|---|
| 18 | `sampled_color` | (0.72, 0.45, 0.21, 1.0) | Texture sample is correct |
| 35 | `n_dot_l`       | 0.0                     | Light is perpendicular to surface |
| 35 | `diffuse`       | (0.0, 0.0, 0.0, 1.0)   | Color zeroed by zero n_dot_l |

`n_dot_l = 0` can mean:
- The surface normal vector is a zero vector (not normalized on upload).
- The light direction is perpendicular to the normal at this exact pixel (unlikely to
  affect the entire surface uniformly — more likely a broken normal).
- The wrong normal attribute is being read (UV instead of normal, or wrong semantic).

Next step: inspect the normal vector in the vertex data and compare with the Post-VS output.

## Limitations

- Shader debugging requires GPU support. Returns `error: debug_pixel_unsupported` when
  not available.
- Traces are capped at `max_steps` (default 200, max 500). Check `truncated: true`.
- Without shader debug info in the capture, variable names will be register names
  (`r0`, `v1`, etc.) rather than source-level names.
- The `DebugStore` retains at most 10 traces. Collect a new trace after eviction.

## Related tools

`get_pixel_history`, `debug_pixel_shader`, `get_shader_debug_trace`,
`get_shader_debug_variables`, `get_shader_debug_status`, `get_mesh_vertices`,
`get_post_vs_geometry` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
