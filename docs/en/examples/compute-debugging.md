[English](compute-debugging.md) | [日本語](../../ja/examples/compute-debugging.md)

# Scenario D5 — Compute Shader NaN

## Problem

A compute shader producing a post-processing result outputs NaN or Inf values, causing
corrupted pixels downstream. You need to find the exact instruction that first generates
the NaN and identify the variable responsible.

## Prerequisites

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded. Confirm with `get_current_capture`.
3. The dispatch event_id containing the compute shader is known or selected in the GUI.

## Example prompt

> The compute dispatch at event 550 is producing NaN in its output buffer. Step through
> thread (0,0,0) in workgroup (0,0,0) to find the first NaN-generating instruction.

---

## Investigation workflow

### 1. Verify the dispatch is selected

```json
{ "tool": "get_current_capture" }
```

### 2. Collect the compute shader debug trace

```json
{
  "tool": "debug_compute_shader",
  "event_id": 550,
  "group_x": 0, "group_y": 0, "group_z": 0,
  "thread_x": 0, "thread_y": 0, "thread_z": 0
}
```

Example response (illustrative):

```json
{
  "debug_id": "dbg_ff00aa11",
  "stage": "compute",
  "event_id": 550,
  "step_count": 112,
  "truncated": false
}
```

### 3. Scan all steps for NaN flags

Request a large batch to scan for the `generated_nan_or_inf` flag:

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_ff00aa11",
  "first_step": 0,
  "count": 200
}
```

Scan the returned steps for `"generated_nan_or_inf": true`. Example (illustrative):

```json
{
  "steps": [
    { "step": 0,  "generated_nan_or_inf": false, "changes": [] },
    { "step": 10, "generated_nan_or_inf": false, "changes": [
        { "after": { "name": "luminance", "value": [0.0] } }
    ]},
    { "step": 47, "generated_nan_or_inf": true,  "changes": [
        { "before": { "name": "log_lum", "value": [0.0] },
          "after":  { "name": "log_lum", "value": ["Inf"] } }
    ]},
    { "step": 48, "generated_nan_or_inf": true,  "changes": [
        { "before": { "name": "tone_factor", "value": [0.0] },
          "after":  { "name": "tone_factor", "value": ["NaN"] } }
    ]}
  ]
}
```

Step 47 is the **first** NaN/Inf. The variable `log_lum` becomes `Inf`.

### 4. Inspect variables at the NaN step

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_ff00aa11",
  "step": 47
}
```

Example response (illustrative):

```json
{
  "variables": {
    "luminance":  { "name": "luminance",  "value": [0.0] },
    "log_lum":    { "name": "log_lum",    "value": ["Inf"] },
    "epsilon":    { "name": "epsilon",    "value": [0.0] }
  }
}
```

`log_lum` is computed as `log(luminance + epsilon)`. Both `luminance` and `epsilon`
are `0.0`, so `log(0.0) = -Inf`. The subsequent arithmetic on `-Inf` produces `NaN`.

### 5. Inspect variables one step before

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_ff00aa11",
  "step": 46,
  "variable_names": ["luminance", "epsilon", "input_color"]
}
```

Example response (illustrative):

```json
{
  "variables": {
    "luminance":   { "value": [0.0] },
    "epsilon":     { "value": [0.0] },
    "input_color": { "value": [0.0, 0.0, 0.0, 1.0] }
  }
}
```

`input_color` is black (zero) for this thread — a black border pixel. `luminance` is
correctly zero for a black pixel. The bug is that `epsilon` should be a small non-zero
constant (e.g., `1e-6`) to guard against `log(0)`, but it reads as `0.0`.

### 6. Check other threads if needed

The NaN might be limited to specific threads. Debug a thread in the middle of the
dispatch to compare:

```json
{
  "tool": "debug_compute_shader",
  "event_id": 550,
  "group_x": 4, "group_y": 4, "group_z": 0,
  "thread_x": 8, "thread_y": 8, "thread_z": 0
}
```

If other threads show non-zero `luminance` and no NaN, the problem is isolated to
pixels where luminance is exactly zero (dark borders or empty regions).

### 7. Check debug store status

```json
{ "tool": "get_shader_debug_status" }
```

Example response:

```json
{
  "debug_ids": ["dbg_ff00aa11", "dbg_a1b2c300"]
}
```

```json
{
  "tool": "get_shader_debug_status",
  "debug_id": "dbg_ff00aa11"
}
```

```json
{
  "debug_id": "dbg_ff00aa11",
  "status": "ready",
  "stage": "compute",
  "event_id": 550,
  "step_count": 112,
  "truncated": false
}
```

---

## Root cause summary

| Step | Variable | Value | Observation |
|---|---|---|---|
| 10 | `luminance` | 0.0 | Correct for black pixel |
| 46 | `epsilon`   | 0.0 | Should be ~1e-6 but is zero |
| 47 | `log_lum`   | Inf | `log(0 + 0) = -Inf` |
| 48 | `tone_factor`| NaN | Downstream arithmetic on Inf |

Fix: ensure `epsilon` is initialized to a non-zero constant before the `log` call.
This is typically a constant buffer upload bug — the uniform was not set or was zeroed.

---

## Limitations

- Only the requested thread is debugged. Shared memory, barriers, and wave operations
  are not observable from a single-thread view.
- If NaN first appears beyond `max_steps` (default 200, max 500), increase `max_steps`
  or use a thread closer to the origin of the problem.
- Returns `error: debug_compute_unsupported` if the API or driver does not support
  compute shader debugging (common on older OpenGL drivers).
- The `DebugStore` retains at most 10 traces; the oldest is evicted on overflow.

## Related tools

`debug_compute_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`,
`get_shader_debug_status`, `get_bound_resources` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
