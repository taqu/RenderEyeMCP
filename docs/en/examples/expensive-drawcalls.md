[English](expensive-drawcalls.md) | [日本語](../../ja/examples/expensive-drawcalls.md)

# Scenario P1 — Find the ten most expensive draw calls

## Problem

You want to know which draw calls consume the most GPU time in the captured frame, and
then inspect the pipeline configuration of the single most expensive one to understand
why it is expensive.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open.

## Example prompts

**Quick investigation:**
> Find the ten most expensive draw calls in this capture and inspect the pipeline
> configuration, shaders, and render targets of the most expensive one.

**Detailed investigation:**
> Measure GPU time for all events in this capture and list the ten most expensive draw
> calls with their event IDs, names, durations, and percentage of total GPU time. For
> the single most expensive draw call, collect pipeline statistics, identify the vertex
> and pixel shaders, inspect the render targets (format, resolution, sample count), and
> list the pixel shader's texture bindings. Separate confirmed facts from hypotheses
> about why it is expensive.

## What the agent should investigate

- Measure GPU duration for all events and rank them to find the top 10 by cost
- For the most expensive draw call, examine its pipeline state: draw count, topology, rasterizer settings
- Identify the bound vertex and pixel shaders and their entry points
- Check the render targets bound during this draw: format, resolution, and MSAA sample count
- Collect pipeline statistics if available: vertex invocations, pixel shader invocations, primitives rasterized

## Expected results

Typically one or two events account for a disproportionate share of GPU time — in open-world or outdoor scenes this is often terrain, dense vegetation, or a character batch. The most expensive event is usually in a G-buffer or shadow pass. Render target resolution and MSAA sample count often explain a large fraction of the cost without any shader analysis.

## How to interpret the results

- `percent_of_total: 23.0` on a terrain draw means terrain is the dominant GPU consumer.
- If pixel shader invocations are much higher than the visible pixel count, overdraw or large triangle counts pushing many off-screen pixels are likely.
- A high-resolution render target with 4× MSAA quadruples pixel shader work compared to 1×.
- A complex pixel shader (many texture samples, lighting iterations) on a high-invocation draw is a classic bottleneck; check the shader disassembly for instruction count.
- GPU duration is replay-based; thermal state during capture and during replay may differ, so absolute millisecond values can vary slightly from what the live application measured.
- If performance summary returns fewer than 10 events, some events were not captured by the counter (missing counter values are absent, not zero).

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
