[English](shader-debugging.md) | [日本語](../../ja/examples/shader-debugging.md)

# Scenario D2 — Pixel Shader Debugging

## Problem

A draw call produces unexpected colors on screen but pixel history shows only one
fragment touching the pixel. The bug is inside the pixel shader itself — an incorrect
texture sample, wrong lighting formula, or an uninitialized variable.

## Prerequisites

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded. Confirm with `get_current_capture`.
3. Pixel History has identified the event_id responsible for the bad pixel (see
   [Scenario D1](pixel-history.md)).

## Example prompt

> Event 244 is the only draw touching pixel (640, 400) but the output color is
> (0.0, 0.0, 0.0). Step through the pixel shader to find where the black color comes
> from.

---

## Investigation workflow

### 1. Collect the pixel shader debug trace

```json
{
  "tool": "debug_pixel_shader",
  "x": 640,
  "y": 400,
  "event_id": 244
}
```

Example response (illustrative):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "stage": "pixel",
  "event_id": 244,
  "step_count": 67,
  "truncated": false
}
```

The trace is stored server-side. Use `debug_id` for all subsequent calls.

### 2. Retrieve the first batch of steps

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_7c3e1f00",
  "first_step": 0,
  "count": 50
}
```

Example response (illustrative — steps abbreviated):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "first_step": 0,
  "count": 50,
  "total_steps": 67,
  "steps": [
    { "step": 0, "next_instruction": 0, "flags": 0, "generated_nan_or_inf": false,
      "changes": [] },
    { "step": 5, "next_instruction": 12, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "v_texcoord", "rows": 1, "columns": 2,
                      "type": "float", "value": [0.0, 0.0] },
          "after":  { "name": "v_texcoord", "rows": 1, "columns": 2,
                      "type": "float", "value": [0.312, 0.748] } }
      ]
    },
    { "step": 18, "next_instruction": 31, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "sampled_color", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "sampled_color", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.72, 0.45, 0.21, 1.0] } }
      ]
    },
    { "step": 35, "next_instruction": 52, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "diffuse", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "diffuse", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 1.0] } }
      ]
    }
  ]
}
```

The texture sample at step 18 returns a reasonable color `(0.72, 0.45, 0.21)`.
But at step 35, the `diffuse` variable becomes `(0.0, 0.0, 0.0, 1.0)` — black with full
alpha. The lighting multiplication likely zeroed the color.

### 3. Inspect variable state at the critical step

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_7c3e1f00",
  "step": 35
}
```

Example response (illustrative):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "step": 35,
  "variables": {
    "sampled_color": { "name": "sampled_color", "rows": 1, "columns": 4,
                       "type": "float", "value": [0.72, 0.45, 0.21, 1.0] },
    "n_dot_l":       { "name": "n_dot_l",       "rows": 1, "columns": 1,
                       "type": "float", "value": [0.0] },
    "diffuse":       { "name": "diffuse",       "rows": 1, "columns": 4,
                       "type": "float", "value": [0.0, 0.0, 0.0, 1.0] }
  }
}
```

`n_dot_l` (dot product of normal and light direction) is `0.0`. The diffuse lighting
term is `sampled_color * n_dot_l`, which evaluates to zero — producing black output.

### 4. Check the remaining steps

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_7c3e1f00",
  "first_step": 50,
  "count": 50
}
```

Inspect the last steps to confirm the final output register value.

### 5. Filter variables by name

To focus on just the lighting-related variables without noise:

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_7c3e1f00",
  "step": 60,
  "variable_names": ["n_dot_l", "diffuse", "ambient", "final_color"]
}
```

---

## Root cause analysis

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

Next step: inspect the normal vector in the vertex data with `get_mesh_vertices` and
compare with the Post-VS output using `get_post_vs_geometry`.

---

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
