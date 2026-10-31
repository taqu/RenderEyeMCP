[English](depth-rejection.md) | [日本語](../../ja/examples/depth-rejection.md)

# Scenario D3 — Depth Test Rejection

## Problem

An object is invisible even though it should be in front of everything else. Pixel
History shows its fragments are present but consistently rejected by the depth test.

## Prerequisites

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded. Confirm with `get_current_capture`.
3. You know a pixel coordinate where the missing object should appear.

## Example prompt

> The UI overlay at pixel (960, 540) is not visible. Pixel History shows its draw call
> produces fragments but they are all rejected. Find out why.

---

## Investigation workflow

### 1. Run Pixel History on the affected pixel

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00014f00",
  "x": 960,
  "y": 540,
  "max_modifications": 50
}
```

Example response (illustrative):

```json
{
  "modification_count": 4,
  "modifications": [
    { "event_id": 5,   "passed": true,  "post_mod": { "r": 0.2, "g": 0.2, "b": 0.2, "a": 1.0 } },
    { "event_id": 180, "passed": true,  "post_mod": { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 } },
    { "event_id": 305, "passed": true,  "post_mod": { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 } },
    {
      "event_id": 420,
      "passed": false,
      "rejection_reason": "depth_test",
      "depth_test_failed": true,
      "shader_out": { "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 },
      "pre_mod":    { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 },
      "post_mod":   { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 }
    }
  ],
  "summary": {
    "passed_fragments": 3,
    "rejected_fragments": 1,
    "last_modifying_event": 305
  }
}
```

Event 420 (the UI overlay) is rejected by the depth test every time. The shader output
is correct (white), but the pixel value never changes.

### 2. Examine the pipeline state for event 420

```json
{ "tool": "get_pipeline_state", "event_id": 420 }
```

Examine the depth/stencil state:

```json
{
  "depth_stencil": {
    "depth_enable": true,
    "depth_write_enable": false,
    "depth_func": "LESS",
    "stencil_enable": false
  }
}
```

Depth test is `LESS`. The UI overlay renders at `z = 1.0` (far plane), but the scene
geometry already wrote `z = 0.82` at this pixel. Since `1.0` is not less than `0.82`,
the fragment fails.

### 3. Compare depth values

Confirm the depth values by examining the depth buffer before event 420:

```json
{ "tool": "get_bound_resources", "event_id": 420 }
```

Identify the depth buffer resource, then inspect the bound depth:

```json
{ "tool": "get_resource_info", "resource_id": "<depth_resource_id>" }
```

### 4. Check draw order and depth setup

The problem is that the UI overlay should render without depth testing (or with depth
always-pass), but the draw is using the scene depth state by mistake.

```json
{ "tool": "get_pipeline_state", "event_id": 305 }
```

Compare event 305 (last 3D object, depth write enabled) with event 420. If 420 should
be a UI pass, it should use `depth_func: ALWAYS` or have depth testing disabled
(`depth_enable: false`).

### 5. Verify with a second pixel

Check another pixel where the overlay should appear:

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00014f00",
  "x": 980,
  "y": 540,
  "max_modifications": 20
}
```

If the same pattern repeats (overlay fragment present, always depth-rejected), the
pipeline state error is confirmed.

---

## Rejection reason reference

| `rejection_reason` | Meaning | Common causes |
|---|---|---|
| `depth_test` | Depth comparison failed | Wrong depth function, incorrect z value, premature depth write |
| `stencil_test` | Stencil comparison failed | Stencil mask mismatch, wrong reference value |
| `shader_discard` | Shader called `discard` / `clip` | Alpha test, out-of-range UV, explicit culling |
| `backface_cull` | Back face removed | Wrong winding order, flipped normals |
| `scissor` | Outside scissor rectangle | Scissor rect misconfigured |
| `sample_mask` | Excluded by MSAA sample mask | MSAA configuration mismatch |
| `unknown` | Reason not determined | Check other pipeline stages |

---

## Root cause summary

| Finding | Implication |
|---|---|
| Event 420 fragments present but all depth-rejected | Pipeline depth state is wrong for UI rendering |
| `depth_func: LESS` on UI draw | UI should use `ALWAYS` or no depth test |
| Scene depth = 0.82; UI z = 1.0 | UI is behind all geometry in the depth buffer |

Fix: set `depth_enable = false` (or `depth_func = ALWAYS`) for the UI draw call pass.

---

## Limitations

- Pixel History is GPU-replay based; avoid calling it in a tight loop.
- If depth rejection is expected (e.g., correct occlusion), use `passed: true` to find
  the last fragment that actually wrote the pixel.

## Related tools

`get_pixel_history`, `get_pipeline_state`, `get_bound_resources`, `get_resource_info` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
