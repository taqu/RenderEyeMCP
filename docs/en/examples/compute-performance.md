[English](compute-performance.md) | [日本語](../../ja/examples/compute-performance.md)

# Scenario P3 — Find the most expensive compute dispatches

## Problem

Your frame contains several compute passes. You want to know which dispatches consume
the most GPU time and then inspect the shader code and resource bindings of the top
offender.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm dispatch count with `get_current_capture_info` and look
   for a non-zero `dispatches` value in `statistics`.

## Example prompt

> Find the most expensive compute dispatches in this frame. For the top one, show me
> the compute shader, its thread group dimensions, and what buffers and textures it reads
> and writes.

---

## Investigation workflow

### 1. Collect GPU timing counters

```json
{
  "tool": "collect_gpu_counters",
  "counter_ids": [1],
  "repeats": 2
}
```

Counter ID 1 is GPU Duration (verify with `list_gpu_counters` for your GPU/driver).

Response (illustrative):

```json
{ "measurement_id": "meas_d04f9a" }
```

Wait for `status: "ready"` from `get_gpu_measurement_status`.

### 2. Get performance summary filtered to compute dispatches

```json
{
  "tool": "get_performance_summary",
  "measurement_id": "meas_d04f9a",
  "top_n": 20
}
```

From the full ranking, identify entries whose `event_name` contains `Dispatch`. Most
command-list APIs name compute work `Dispatch()` or `DispatchIndirect()`.

Example response excerpt (illustrative):

```json
{
  "total_measured_seconds": 0.01482,
  "top_events": [
    { "event_id": 2801, "event_name": "Dispatch() — deferred_lighting_cs",
      "duration_seconds": 0.00448, "percent_of_total": 30.2 },
    { "event_id": 3105, "event_name": "Dispatch() — ssao_cs",
      "duration_seconds": 0.00187, "percent_of_total": 12.6 },
    { "event_id": 3210, "event_name": "Dispatch() — bloom_downsample_cs",
      "duration_seconds": 0.00049, "percent_of_total": 3.3 },
    ...
  ]
}
```

Event 2801 (`deferred_lighting_cs`) is the most expensive dispatch at 30.2 % of total
GPU time.

### 3. Inspect the top dispatch — pipeline state

Select event 2801 in the RenderDoc GUI, then:

```json
{ "tool": "get_pipeline_state", "event_id": 2801 }
```

From the compute section, note:

- **Thread group dimensions** (`dispatch_x`, `dispatch_y`, `dispatch_z`): multiply
  by the shader's `[numthreads(x, y, z)]` to get total thread count.
- **Root signature / descriptor layout**: how many descriptor tables or root constants
  are bound.

Example pipeline state excerpt (illustrative):

```json
{
  "stage": "compute",
  "dispatch": { "x": 120, "y": 68, "z": 1 },
  "thread_group_size": { "x": 16, "y": 16, "z": 1 }
}
```

Total threads: 120 × 68 × 16 × 16 = 2 088 960. For a 1920×1080 output that is
reasonable (one thread per pixel with slight rounding), but suggests the shader runs
full-resolution work — check if a half-resolution path would be acceptable.

### 4. Inspect the compute shader

```json
{ "tool": "get_current_shaders", "event_id": 2801 }
```

Note the shader entry point and source file (if debug info is present). If disassembly
is available, look for:

- Many texture sample instructions (bandwidth-bound)
- Long dependency chains (latency-bound)
- Divergent branches (warp efficiency loss)

Example response excerpt (illustrative):

```json
{
  "compute_shader": {
    "entry_point": "CS_DeferredLighting",
    "source_file": "Shaders/Lighting/DeferredLighting.hlsl",
    "estimated_instruction_count": 312
  }
}
```

312 instructions × ~2 million threads = significant ALU work per frame. Compare with
simpler dispatches to calibrate.

### 5. Inspect resource bindings

```json
{ "tool": "get_shader_bindings", "event_id": 2801, "stage": "compute" }
```

List the bound SRVs (read resources) and UAVs (read-write resources):

Example response excerpt (illustrative):

```json
{
  "srvs": [
    { "slot": 0, "name": "t_GBufferAlbedo",    "format": "RGBA8_UNORM",  "size": "1920x1080" },
    { "slot": 1, "name": "t_GBufferNormals",   "format": "RGBA16_FLOAT", "size": "1920x1080" },
    { "slot": 2, "name": "t_GBufferDepth",     "format": "R32_FLOAT",    "size": "1920x1080" },
    { "slot": 3, "name": "t_ShadowAtlas",      "format": "R16_UNORM",    "size": "4096x4096" }
  ],
  "uavs": [
    { "slot": 0, "name": "u_LightingOutput",   "format": "RGBA16_FLOAT", "size": "1920x1080" }
  ]
}
```

Observations from this binding set:

- Four full-resolution texture reads per thread plus one large shadow atlas read.
- The shadow atlas at 4096×4096 R16 is 32 MB; random-access reads from it will stress
  the texture cache.
- Output is RGBA16_FLOAT (8 bytes/pixel × ~2M pixels = 16 MB write bandwidth per
  dispatch invocation).

### 6. Report findings

A complete finding for event 2801:

- **Measured cost**: 4.48 ms (30.2 % of total GPU time). This is confirmed by the
  counter.
- **Compute load**: ~2M threads, 312 instructions each — heavy but proportionate for
  deferred lighting.
- **Likely bottleneck** (hypothesis, not measured directly): random shadow-atlas
  reads breaking texture cache locality. The atlas is 32 MB; L2 texture cache on
  most GPUs is 2–8 MB.
- **Suggested further profiling**: collect a cache-miss counter (if the GPU exposes one)
  and compare cost with a reduced shadow atlas size or tighter shadow cascade layout.

---

## Expected observations

- In deferred renderers, the deferred lighting dispatch is typically the most expensive
  single dispatch, often 20–40 % of GPU frame time.
- SSAO and bloom are usually cheaper but can spike with naive full-resolution
  implementations.
- Large read-only resources (shadow atlases, environment maps, GI caches) are common
  cache-pressure sources.

---

## Limitations

- Shader instruction counts are estimates from disassembly; actual GPU cycles depend on
  ILP and memory latency, not instruction count alone.
- Cache-miss counters are available on some GPUs (AMD, Intel) but not on all
  NVIDIA/D3D12 configurations.
- `get_shader_bindings` reports bound resources, not access patterns — a bound texture
  that is rarely sampled still appears in the list.

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_performance_summary`, `get_pipeline_state`, `get_current_shaders`,
`get_shader_bindings` —
see the [GPU performance guide](../performance.md) and the
[tool reference](../tools.md#gpu-performance-analysis).
