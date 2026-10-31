[English](compute-performance.md) | [日本語](../../ja/examples/compute-performance.md)

# Scenario P3 — Find the most expensive compute dispatches

## Problem

Your frame contains several compute passes. You want to know which dispatches consume
the most GPU time and then inspect the shader code and resource bindings of the top
offender.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open and contains compute dispatches. Confirm by checking the dispatch
   count in the capture statistics.

## Example prompts

**Quick investigation:**
> Find the most expensive compute dispatches in this frame. For the top one, show me
> the compute shader, its thread group dimensions, and what buffers and textures it reads
> and writes.

**Detailed investigation:**
> Measure GPU time for all events in this capture and identify the top 5 most expensive
> compute dispatches. For the most expensive one, report: the event ID and name, the
> measured GPU time and percentage of total, the compute shader entry point, the thread
> group count and size, all bound input textures and output UAVs with their formats and
> dimensions, and any observations about potential bottlenecks such as large textures,
> high thread counts, or heavy bandwidth.

## What the agent should investigate

- Measure GPU duration for all events and filter the results to find the most expensive dispatches
- For the top dispatch, collect the thread group count and thread group size (numthreads) to estimate total threads
- Identify the compute shader entry point and check its instruction count if available
- List all bound input resources (SRVs) and output resources (UAVs) with their formats and sizes
- Note any particularly large textures bound as inputs, which can create texture cache pressure

## Expected results

In a deferred renderer, findings might look like: the deferred lighting dispatch takes 4.48 ms (30.2% of total GPU time), dispatches ~2 million threads, and reads from four full-resolution G-buffer textures plus a large 4096×4096 shadow atlas. The large shadow atlas is a candidate for cache pressure because it is 32 MB and GPU L2 texture caches are typically 2–8 MB.

## How to interpret the results

- Shader instruction counts are estimates from disassembly; actual GPU cycles depend on
  ILP and memory latency, not instruction count alone.
- In deferred renderers, the deferred lighting dispatch is typically the most expensive
  single dispatch, often 20–40 % of GPU frame time.
- SSAO and bloom are usually cheaper but can spike with naive full-resolution
  implementations.
- Large read-only resources (shadow atlases, environment maps, GI caches) are common
  cache-pressure sources.
- Combine the thread count, instruction count, and texture size observations to form a
  hypothesis, but label any bandwidth/ALU bottleneck conclusions as hypotheses requiring
  dedicated counter data to confirm.

## Limitations

- Shader instruction counts are estimates from disassembly; actual GPU cycles depend on
  ILP and memory latency, not instruction count alone.
- Cache-miss counters are available on some GPUs (AMD, Intel) but not on all
  NVIDIA/D3D12 configurations.
- Bound resources are reported, not access patterns — a bound texture that is rarely
  sampled still appears in the list.

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_performance_summary`, `get_pipeline_state`, `get_current_shaders`,
`get_shader_bindings` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
