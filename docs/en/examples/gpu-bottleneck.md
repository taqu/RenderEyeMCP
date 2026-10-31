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
   `get_performance_summary`). Its `event_id` is known.

## Example prompt

> Event 1042 (`terrain_patch_00`) takes 3.41 ms — 23 % of GPU frame time. Collect
> pipeline statistics, inspect its shaders and render targets, and tell me where the
> bottleneck likely is.

---

## Investigation workflow

### 1. Get measured GPU duration for the selected draw

If you have not already collected counters, do so now:

```json
{
  "tool": "collect_gpu_counters",
  "counter_ids": [1],
  "repeats": 3
}
```

`repeats: 3` is recommended for a single-event investigation because thermal noise has
more impact on one event than on an aggregate.

Retrieve the event's timing directly:

```json
{
  "tool": "get_gpu_timings",
  "measurement_id": "meas_7f3a2b",
  "event_id": 1042
}
```

Example response (illustrative):

```json
{
  "events": [
    { "event_id": 1042, "event_name": "DrawIndexedInstanced() — terrain_patch_00",
      "duration_seconds": 0.00341, "percent_of_total": 23.0 }
  ]
}
```

This is a **measured fact**: event 1042 consumed 3.41 ms of GPU time (averaged over 3
replays).

### 2. Get pipeline statistics for that event

```json
{
  "tool": "get_pipeline_statistics",
  "measurement_id": "meas_7f3a2b",
  "event_id": 1042
}
```

Collect timing and pipeline-statistics counters in the same measurement if your GPU
supports it, or run a second collection with just the pipeline-statistics counter IDs.

Example response (illustrative):

```json
{
  "event_id": 1042,
  "pipeline_statistics": {
    "input_assembler_vertices": 1048576,
    "input_assembler_primitives": 349525,
    "vertex_shader_invocations": 1048576,
    "geometry_shader_invocations": 0,
    "rasterized_primitives": 349525,
    "pixel_shader_invocations": 8847360,
    "compute_shader_invocations": 0
  }
}
```

Key ratio: PS invocations (8 847 360) / rasterized primitives (349 525) ≈ 25. This
means each triangle covers on average 25 pixels, which is moderate — not micro-triangle
territory, but also not a simple low-complexity mesh.

### 3. Inspect shader configuration and disassembly

**Bound shaders:**

```json
{ "tool": "get_current_shaders", "event_id": 1042 }
```

Example response (illustrative):

```json
{
  "vertex_shader": {
    "entry_point": "VS_Terrain",
    "source_file": "Shaders/Terrain/Terrain.hlsl"
  },
  "pixel_shader": {
    "entry_point": "PS_TerrainPBR",
    "source_file": "Shaders/Terrain/TerrainPBR.hlsl",
    "estimated_instruction_count": 487
  }
}
```

487 pixel shader instructions × 8 847 360 invocations = a very large ALU budget per
frame for one draw call.

**Shader bindings (pixel stage):**

```json
{ "tool": "get_shader_bindings", "event_id": 1042, "stage": "pixel" }
```

Example response excerpt (illustrative):

```json
{
  "srvs": [
    { "slot": 0, "name": "t_Albedo",       "format": "RGBA8_UNORM",  "size": "4096x4096" },
    { "slot": 1, "name": "t_Normal",       "format": "RGBA8_UNORM",  "size": "4096x4096" },
    { "slot": 2, "name": "t_Roughness",    "format": "R8_UNORM",     "size": "4096x4096" },
    { "slot": 3, "name": "t_HeightBlend",  "format": "RGBA8_UNORM",  "size": "4096x4096" },
    { "slot": 4, "name": "t_ShadowMap",    "format": "R32_FLOAT",    "size": "4096x4096" },
    { "slot": 5, "name": "t_Splat",        "format": "RGBA8_UNORM",  "size": "2048x2048" }
  ]
}
```

Six texture reads per pixel. At 4096×4096 each these are large textures — cache
pressure is likely significant.

### 4. Inspect render targets

```json
{ "tool": "get_render_targets", "event_id": 1042 }
```

Example response (illustrative):

```json
{
  "render_targets": [
    { "slot": 0, "name": "GBuffer_Albedo",   "format": "RGBA8_UNORM",  "size": "1920x1080", "samples": 1 },
    { "slot": 1, "name": "GBuffer_Normals",  "format": "RGBA16_FLOAT", "size": "1920x1080", "samples": 1 },
    { "slot": 2, "name": "GBuffer_Material", "format": "RG8_UNORM",    "size": "1920x1080", "samples": 1 }
  ],
  "depth_stencil": {
    "name": "DepthBuffer", "format": "D24_S8", "size": "1920x1080", "samples": 1
  }
}
```

Three G-buffer outputs at 1920×1080. Total output bandwidth per pixel: 1+2+0.5 = 3.5
bytes average (ignoring depth). Not extraordinary, but combined with 8.8 M PS
invocations the bandwidth adds up.

### 5. Inspect resource bindings (vertex stage)

```json
{ "tool": "get_shader_bindings", "event_id": 1042, "stage": "vertex" }
```

Check whether the vertex shader reads from a large structured buffer or accesses
heightmap data; these can serialize vertex processing if the buffer is not cached.

### 6. Structured findings

The following separates confirmed measurements from hypotheses and open questions.

#### Confirmed by measurement

| Fact | Source |
|---|---|
| 3.41 ms GPU duration (23 % of frame) | `get_gpu_timings`, averaged over 3 replays |
| 8 847 360 pixel shader invocations | `get_pipeline_statistics` |
| 487 estimated PS instructions per invocation | shader disassembly |
| 6 texture SRV slots bound in the pixel stage | `get_shader_bindings` |
| 1 048 576 vertex shader invocations (no vertex amplification) | `get_pipeline_statistics` |

#### Likely bottlenecks (hypothesis)

- **ALU-heavy pixel shader**: 487 instructions × 8.8 M invocations is a very large
  compute budget. If the GPU is ALU-bound, reducing the instruction count (baking some
  PBR terms, using a simpler BRDF for terrain) could give a proportional speedup.
- **Texture cache pressure**: six 4096×4096 textures sampled in the pixel shader. On
  a 1920×1080 target the terrain surface texels map at roughly 2:1 to screen pixels
  when close to the camera; the full 4096 mip level is likely not accessed, but the
  working set is still large for one draw call. Random-access patterns from a splat
  texture further reduce cache efficiency.

#### Requires further profiling

- **Bandwidth vs. ALU dominance**: without a memory-bandwidth counter or an occupancy
  counter, it is not possible to determine whether the shader stalls on memory latency
  or runs out of ALU throughput. Collect a cache-miss or bandwidth counter (if your GPU
  driver exposes one) to resolve this.
- **Overdraw**: the rasterized primitive count is 349 525 but it is not clear how many
  of those are backface-culled or early depth-killed. If depth prepass is not used,
  overdraw multiplies PS invocations. Confirm by checking depth test mode in the
  pipeline state.
- **VS performance**: 1 M vertex invocations is modest; the vertex stage is unlikely
  to be the bottleneck unless heightmap fetch is involved (check vertex SRV bindings).

---

## Expected observations

- Terrain draws are often the heaviest single draw call in open-world games due to
  their combination of large triangle counts, PBR materials with multiple texture
  layers, and large on-screen coverage.
- The ratio of PS invocations to rasterized primitives is a quick overdraw/coverage
  signal.
- Large textures in the pixel stage are a consistent cache-pressure indicator even when
  the GPU does not expose explicit cache-miss counters.

---

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
