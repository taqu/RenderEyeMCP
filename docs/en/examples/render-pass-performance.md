[English](render-pass-performance.md) | [日本語](../../ja/examples/render-pass-performance.md)

# Scenario P2 — Compare the GPU cost of render passes

## Problem

Your frame has named render passes (shadow map, G-buffer, lighting, post-processing).
You want to know which pass consumes the most GPU time and then drill into the individual
events within the most expensive pass.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Debug markers (`BeginEvent`/`EndEvent` or equivalent API calls)
   must be present in the capture for pass-level grouping to work. Confirm by looking
   for marker entries in the event list.

## Example prompts

**Quick investigation:**
> Compare the GPU cost of the shadow, G-buffer, lighting, and post-processing passes.
> Identify the most expensive pass and show me the individual event timings inside it.

**Detailed investigation:**
> Measure GPU time for this capture and compare the cost of each named render pass.
> Report the aggregated GPU time and event count for each pass. Then for the most
> expensive pass, list the individual events inside it sorted by cost, and identify the
> single most expensive event within that pass.

## What the agent should investigate

- GPU timing for all events, then aggregated per render pass (using debug marker groups)
- For each pass: its name, total aggregated duration, event count, and percentage of total
- For the most expensive pass: individual event timings sorted by cost to find the dominant event within it

## Expected results

In a deferred renderer, typical findings are: Lighting 42.6%, G-buffer 33.0%, PostProcessing 14.7%, ShadowMap 7.6%. Within the Lighting pass, the deferred lighting compute dispatch alone may account for 71% of that pass's time.

## How to interpret the results

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

- Lighting and G-buffer passes typically dominate deferred renderers.
- A single compute dispatch often accounts for the majority of the lighting pass cost.
- Post-processing passes are usually fast unless they include full-resolution blur chains
  or ray tracing.
- Shadow passes are fast if cascades are culled aggressively; they can spike if the
  scene has many shadow-casting lights.

## Limitations

- Pass grouping depends on debug markers in the capture. If the application does not
  emit `BeginEvent`/`EndEvent`, all events appear at the top level and pass-level
  performance returns a flat list.
- `aggregated_duration` is not wall-clock pass elapsed time (see above).
- Passes with zero measured events (e.g. a pass that ran but all its events lacked
  counter data) will not appear in the result.

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_render_pass_performance`, `get_gpu_timings` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
