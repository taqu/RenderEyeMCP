[English](expensive-drawcalls.md) | [日本語](../../ja/examples/expensive-drawcalls.md)

# Scenario P1 — Find the ten most expensive draw calls

## Problem

You want to know which draw calls consume the most GPU time in the captured frame, and
then inspect the pipeline configuration of the single most expensive one to understand
why it is expensive.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm with `get_current_capture`.

## Example prompt

> Find the ten most expensive draw calls in this capture and inspect the pipeline
> configuration, shaders, and render targets of the most expensive one.

---

## Investigation workflow

### 1. Confirm the capture is loaded

```json
{ "tool": "get_current_capture" }
```

Expected response (illustrative):

```json
{
  "status": "loaded",
  "path": "C:/captures/game_frame_0042.rdc",
  "api": "D3D12",
  "frame_number": 42
}
```

### 2. List available GPU counters and find timing counters

```json
{ "tool": "list_gpu_counters" }
```

Scan the response for counters whose `unit` is `seconds` or `nanoseconds`, or whose
`category` is `timing`. Note their `counter_id` values.

Example response excerpt (illustrative):

```json
{
  "counters": [
    { "counter_id": 1, "name": "GPU Duration", "unit": "seconds", "category": "timing",
      "description": "Time the GPU spent processing this event." },
    { "counter_id": 2, "name": "VS Invocations", "unit": "count", "category": "pipeline" },
    { "counter_id": 3, "name": "PS Invocations", "unit": "count", "category": "pipeline" }
  ]
}
```

Here `counter_id: 1` is the GPU duration counter. Record it.

### 3. Collect GPU timing counters

```json
{
  "tool": "collect_gpu_counters",
  "counter_ids": [1],
  "repeats": 2
}
```

Using `repeats: 2` reduces noise from thermal throttling with minimal extra cost.

Response (illustrative):

```json
{ "measurement_id": "meas_7f3a2b" }
```

### 4. Check measurement status

```json
{
  "tool": "get_gpu_measurement_status",
  "measurement_id": "meas_7f3a2b"
}
```

Poll until status is `ready`:

```json
{ "measurement_id": "meas_7f3a2b", "status": "ready", "event_count": 533 }
```

### 5. Get performance summary — top 10

```json
{
  "tool": "get_performance_summary",
  "measurement_id": "meas_7f3a2b",
  "top_n": 10
}
```

Example response (illustrative):

```json
{
  "total_measured_seconds": 0.01482,
  "top_events": [
    { "event_id": 1042, "event_name": "DrawIndexedInstanced() — terrain_patch_00",
      "duration_seconds": 0.00341, "percent_of_total": 23.0 },
    { "event_id": 876,  "event_name": "DrawIndexedInstanced() — vegetation_lod0",
      "duration_seconds": 0.00198, "percent_of_total": 13.4 },
    { "event_id": 1198, "event_name": "DrawIndexedInstanced() — characters_batch",
      "duration_seconds": 0.00145, "percent_of_total": 9.8 },
    ...
  ]
}
```

Event 1042 (`terrain_patch_00`) is the clear outlier at 23 % of measured GPU time.

### 6. Inspect the most expensive draw call

Select event 1042 in the RenderDoc GUI, then gather:

**Pipeline state:**

```json
{ "tool": "get_pipeline_state", "event_id": 1042 }
```

Look for bound vertex/index buffers, rasterizer state (fill mode, cull mode), depth
stencil settings, blend state, and the number of render targets.

**Shaders:**

```json
{ "tool": "get_current_shaders", "event_id": 1042 }
```

Note vertex shader and pixel shader entry points and their resource bind counts.
Optionally fetch disassembly for the pixel shader if instruction count is available.

**Render targets:**

```json
{ "tool": "get_render_targets", "event_id": 1042 }
```

Note output resolution and format — high-resolution HDR targets with MSAA multiply PS
invocation cost significantly.

### 7. Interpret the results

Combine the findings:

- `percent_of_total: 23.0` — terrain is the dominant GPU consumer.
- If the pixel shader invocation count (from `get_pipeline_statistics`) is very high
  relative to visible pixel count, overdraw or a large triangle count pushing many
  off-screen pixels is likely.
- A high-resolution render target with 4x MSAA quadruples pixel shader work compared to
  1x.
- A complex pixel shader (many texture samples, lighting iterations) on a high-invocation
  draw is a classic bottleneck; check the shader disassembly for instruction count.

---

## Expected observations

- One or two events account for a disproportionate share of GPU time (typical for games
  with terrain or dense vegetation).
- The most expensive event is usually in a G-buffer or shadow pass, not post-processing.
- Render target resolution and MSAA sample count often explain a large fraction of the
  cost without any shader analysis.

---

## Limitations

- GPU duration is replay-based; thermal state during capture and during replay may
  differ, so absolute millisecond values can vary slightly from what the live application
  measured.
- If `get_performance_summary` returns fewer than 10 events, some events were not
  captured by the counter (missing counter values are absent, not zero).

## Related tools

`get_current_capture`, `list_gpu_counters`, `collect_gpu_counters`,
`get_gpu_measurement_status`, `get_performance_summary`, `get_pipeline_state`,
`get_current_shaders`, `get_render_targets`, `get_pipeline_statistics` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
