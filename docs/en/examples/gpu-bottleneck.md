[English](gpu-bottleneck.md) | [日本語](../../ja/examples/gpu-bottleneck.md)

# Scenario P4 — Diagnose a GPU bottleneck in a single draw call

## Problem

A specific draw call takes a long time on the GPU. You want to collect pipeline
statistics, inspect shaders, check render targets, and examine resource bindings, then
produce a structured finding that distinguishes what the measurements confirm from what
is a hypothesis and what requires additional profiling.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open and the draw call of interest has been identified (e.g. from
   GPU timing analysis). Its event ID is known.

## Example prompts

**Quick investigation:**
> Event 1042 (`terrain_patch_00`) takes 3.41 ms — 23% of GPU frame time. Collect
> pipeline statistics, inspect its shaders and render targets, and tell me where the
> bottleneck likely is.

**Detailed investigation:**
> Event 1042 (`terrain_patch_00`) takes 3.41 ms (23% of GPU time). Investigate why it
> is expensive. Collect pipeline statistics for that event. Identify the pixel shader,
> list its bound textures with their formats and dimensions, and inspect the render
> targets. Then produce a structured analysis separating: (1) confirmed measurements,
> (2) likely bottleneck hypotheses based on those measurements, and (3) questions that
> require additional profiling to answer.

## What the agent should investigate

- GPU timing for this specific draw call to confirm the measured cost
- Pipeline statistics: vertex invocations, pixel shader invocations, primitives rasterized
- The pixel shader entry point and estimated instruction count from disassembly if available
- All texture bindings on the pixel stage: format, dimensions, and how many there are
- The render targets bound during this draw: format, resolution, and MSAA sample count
- Vertex stage bindings: whether the vertex shader reads from any large structured buffers

## Expected results

A complete finding separates what is measured from what is inferred:

**Confirmed by measurement:**
- 3.41 ms GPU duration (23% of frame), averaged over 3 replays
- 8,847,360 pixel shader invocations
- 487 estimated PS instructions per invocation
- 6 texture SRV slots bound in the pixel stage

**Likely bottlenecks (hypothesis):**
- ALU-heavy pixel shader: 487 instructions × 8.8M invocations is a very large compute budget
- Texture cache pressure: six 4096×4096 textures sampled in the pixel shader

**Requires further profiling:**
- Whether the shader is ALU-bound or memory-latency-bound requires a cache-miss or bandwidth counter

## How to interpret the results

- Terrain draws are often the heaviest single draw call in open-world games due to
  their combination of large triangle counts, PBR materials with multiple texture
  layers, and large on-screen coverage.
- The ratio of PS invocations to rasterized primitives is a quick overdraw/coverage
  signal.
- Large textures in the pixel stage are a consistent cache-pressure indicator even when
  the GPU does not expose explicit cache-miss counters.
- `estimated_instruction_count` from disassembly is an approximation; actual GPU cycles
  depend on dual-issue, predication, and memory latency hiding.
- Missing counter values are absent from results, not zero — if pipeline statistics
  returns no data for this event, the driver does not expose those counters for this API/GPU.

## Limitations

- Hypothesis-level conclusions require additional counter data to confirm; clearly label
  them as hypotheses in any report.
- `estimated_instruction_count` from disassembly is an approximation; actual GPU cycles
  depend on dual-issue, predication, and memory latency hiding.
- Missing counter values are absent from results, not zero — if
  `get_pipeline_statistics` returns no data for this event, the driver does not expose
  those counters for this API/GPU.

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_gpu_timings`, `get_pipeline_statistics`, `get_current_shaders`,
`get_shader_bindings`, `get_render_targets`, `get_pipeline_state` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
