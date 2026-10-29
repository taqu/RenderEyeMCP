[English](pixel-history.md) | [日本語](../../ja/examples/pixel-history.md)

# Scenario D1 — Incorrect Pixel Color

## Problem

A pixel on screen shows the wrong color. You need to find which draw call last wrote
that pixel and why the result differs from what is expected.

## Prerequisites

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded. Confirm with `get_current_capture`.
3. You know the approximate screen coordinates of the wrong pixel.

## Example prompt

> Pixel at (512, 384) appears dark red but should be white. Find which draw call is
> responsible and what color the shader produced.

---

## Investigation workflow

### 1. Confirm the capture is loaded

```json
{ "tool": "get_current_capture" }
```

Note the `capture_path` for reference.

### 2. Identify the render target resource ID

```json
{ "tool": "get_render_targets" }
```

Example response (illustrative):

```json
{
  "color_targets": [
    { "slot": 0, "resource_id": "0x00012abc", "format": "R8G8B8A8_UNORM",
      "width": 1920, "height": 1080 }
  ],
  "depth_target": { "resource_id": "0x00012abd", "format": "D24_UNORM_S8_UINT" }
}
```

Use `0x00012abc` as `resource_id`.

### 3. Retrieve pixel history

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00012abc",
  "x": 512,
  "y": 384,
  "max_modifications": 50
}
```

Example response (illustrative):

```json
{
  "resource_id": "0x00012abc",
  "x": 512, "y": 384,
  "modification_count": 3,
  "modifications": [
    {
      "event_id": 12,
      "passed": true,
      "pre_mod":   { "r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0 },
      "shader_out":{ "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "post_mod":  { "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "prim_id": 4, "frag_index": 0
    },
    {
      "event_id": 88,
      "passed": true,
      "pre_mod":   { "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "shader_out":{ "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "post_mod":  { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "prim_id": 211, "frag_index": 0
    },
    {
      "event_id": 120,
      "passed": false,
      "rejection_reason": "depth_test",
      "depth_test_failed": true,
      "pre_mod":   { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "shader_out":{ "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 },
      "post_mod":  { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 }
    }
  ],
  "summary": {
    "passed_fragments": 2,
    "rejected_fragments": 1,
    "last_modifying_event": 88
  }
}
```

Key observations:
- Event 88 was the last draw that **wrote** the pixel (dark red `0.8, 0.05, 0.05`).
- Event 120 produced the correct white (`1.0, 1.0, 1.0`) but failed the **depth test**,
  so its output was discarded.

### 4. Investigate event 120's depth failure

The expected white color came from event 120 but was rejected by the depth test. The
draw that wrote the red color (event 88) was rendered with a depth value that is closer
to the camera than event 120's geometry.

Options to investigate further:

```json
{ "tool": "get_pipeline_state", "event_id": 120 }
```

Check whether depth write is enabled and the depth comparison function is correct
(`LESS` vs `LESS_EQUAL` vs `GREATER` depending on the depth convention).

```json
{ "tool": "get_pipeline_state", "event_id": 88 }
```

Confirm event 88's depth state. If it writes depth and renders after event 120's
geometry should be in front, check the draw order or depth buffer initialization.

### 5. Optionally: debug the pixel shader for event 88

If the dark red color itself is suspicious (not just the draw order), collect a trace:

```json
{
  "tool": "debug_pixel_shader",
  "x": 512,
  "y": 384,
  "event_id": 88
}
```

Response:

```json
{ "debug_id": "dbg_3f1a2c00", "stage": "pixel", "event_id": 88,
  "step_count": 42, "truncated": false }
```

Then inspect the trace for incorrect lighting or texture reads:

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_3f1a2c00",
  "first_step": 0,
  "count": 50
}
```

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_3f1a2c00",
  "step": 30
}
```

---

## Summary

| Event | Passed | Shader output | Reason if rejected |
|---|---|---|---|
| 12  | Yes | (0.1, 0.1, 0.1) | — |
| 88  | Yes | (0.8, 0.05, 0.05) | — (last writer) |
| 120 | No  | (1.0, 1.0, 1.0) | depth_test |

The pixel displays the wrong color because a later draw that would have produced the
correct color was rejected by the depth test. The fix is to investigate the depth
buffer state or draw order so that event 120's fragment wins.

---

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
