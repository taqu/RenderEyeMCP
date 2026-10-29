[English](render-pass-performance.md) | [日本語](../../ja/examples/render-pass-performance.md)

# Scenario P2 — Compare the GPU cost of render passes

## Problem

Your frame has named render passes (shadow map, G-buffer, lighting, post-processing).
You want to know which pass consumes the most GPU time and then drill into the individual
events within the most expensive pass.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Debug markers (`BeginEvent`/`EndEvent` or equivalent API calls)
   must be present in the capture for pass-level grouping to work. Confirm with
   `list_capture_events` and look for marker entries.

## Example prompt

> Compare the GPU cost of the shadow, G-buffer, lighting, and post-processing passes.
> Identify the most expensive pass and show me the individual event timings inside it.

---

## Investigation workflow

### 1. Collect GPU duration

```json
{
  "tool": "collect_gpu_counters",
  "counter_ids": [1],
  "repeats": 2
}
```

Counter ID 1 is the GPU Duration counter (verify with `list_gpu_counters` first; the ID
may differ on your GPU/driver). `repeats: 2` averages two replay runs to reduce noise.

Response (illustrative):

```json
{ "measurement_id": "meas_c91e4d" }
```

Wait for `get_gpu_measurement_status` to return `status: "ready"` before continuing.

### 2. Get render pass performance

```json
{
  "tool": "get_render_pass_performance",
  "measurement_id": "meas_c91e4d"
}
```

Example response (illustrative):

```json
{
  "passes": [
    {
      "pass_name": "ShadowMap",
      "aggregated_duration_seconds": 0.00112,
      "event_count": 87,
      "percent_of_total": 7.6
    },
    {
      "pass_name": "GBuffer",
      "aggregated_duration_seconds": 0.00489,
      "event_count": 214,
      "percent_of_total": 33.0
    },
    {
      "pass_name": "Lighting",
      "aggregated_duration_seconds": 0.00631,
      "event_count": 12,
      "percent_of_total": 42.6
    },
    {
      "pass_name": "PostProcessing",
      "aggregated_duration_seconds": 0.00218,
      "event_count": 31,
      "percent_of_total": 14.7
    }
  ],
  "total_measured_seconds": 0.01482
}
```

### 3. Interpret pass hierarchy results

`aggregated_duration` is the **sum of leaf event durations** within the pass group — it
is not the GPU wall-clock elapsed time for the pass. The distinction matters in two
cases:

- **Overlapping events**: on tiled or async-capable GPUs, events inside a pass may
  overlap in hardware; summing them overcounts actual elapsed time.
- **Missing counter values**: if some events inside the pass did not produce a counter
  result, those events are absent (not zero). The aggregate will undercount in that
  case.

For most desktop GPU captures on D3D12 or Vulkan without async compute, the sum-of-
leaves approximation is close to elapsed time.

### 4. Identify the expensive pass

From the example above, `Lighting` at 42.6 % is the dominant cost, followed by
`GBuffer` at 33.0 %. Focus on `Lighting` first.

Note the `event_count: 12` — the lighting pass has very few events, so each one is
individually expensive.

### 5. Drill into events within the pass

```json
{
  "tool": "get_gpu_timings",
  "measurement_id": "meas_c91e4d",
  "pass_name": "Lighting",
  "sort_by": "duration_desc",
  "page": 0,
  "page_size": 50
}
```

Example response excerpt (illustrative):

```json
{
  "events": [
    { "event_id": 2801, "event_name": "Dispatch() — deferred_lighting_cs",
      "duration_seconds": 0.00448, "percent_of_pass": 71.0 },
    { "event_id": 2810, "event_name": "DrawIndexedInstanced() — sky_atmosphere",
      "duration_seconds": 0.00093, "percent_of_pass": 14.7 },
    { "event_id": 2815, "event_name": "Dispatch() — reflection_probes_cs",
      "duration_seconds": 0.00071, "percent_of_pass": 11.2 }
  ]
}
```

The deferred lighting compute dispatch (event 2801) accounts for 71 % of the Lighting
pass cost. This is the next investigation target — see
[Scenario P3](compute-performance.md) for how to inspect compute dispatches.

---

## Expected observations

- Lighting and G-buffer passes typically dominate deferred renderers.
- A single compute dispatch often accounts for the majority of the lighting pass cost.
- Post-processing passes are usually fast unless they include full-resolution blur chains
  or ray tracing.
- Shadow passes are fast if cascades are culled aggressively; they can spike if the
  scene has many shadow-casting lights.

---

## Limitations

- Pass grouping depends on debug markers in the capture. If the application does not
  emit `BeginEvent`/`EndEvent`, all events appear at the top level and
  `get_render_pass_performance` returns a flat list.
- `aggregated_duration` is not wall-clock pass elapsed time (see above).
- Passes with zero measured events (e.g. a pass that ran but all its events lacked
  counter data) will not appear in the result.

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_render_pass_performance`, `get_gpu_timings` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
