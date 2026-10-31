[English](geometry-performance.md) | [日本語](../../ja/examples/geometry-performance.md)

# Scenario G4 — Geometry performance

## Problem

A draw call has been identified as expensive through GPU performance analysis.
You want to investigate whether the high cost is related to excessive geometry — too many
vertices, indices, or instances — or whether it stems from shader complexity or
rasterization work.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open.
3. GPU timing counters have already been collected. If not, ask the agent to measure
   GPU time for all events first.

## Example prompts

**Quick investigation:**
> Analyze the geometry processed by this expensive draw call. Compare its index count,
> instance count, vertex shader invocations, and available GPU timing measurements.
> Identify potential inefficiencies.

**Detailed investigation:**
> Event 880 (foliage_batch) takes 4.2 ms — 35% of GPU time. Analyze its geometry: how
> many instances and indices does it draw, what are the vertex buffer layouts, and how
> does the instance count relate to the GPU cost? Also check whether any vertices are
> off-screen after transformation, and report the object-space bounding box and
> degenerate primitive count.

## What the agent should investigate

- The draw call geometry configuration: draw type (indexed/non-indexed), index count, instance count, vertex buffer strides and slots
- Pipeline statistics if available: vertex shader invocations, pixel shader invocations, primitives entering and surviving clipping
- The object-space bounding box and count of NaN/Inf positions and degenerate triangles
- Post-vertex-shader positions for a sample of vertices: whether any instances fall outside the NDC visible region, suggesting off-screen work that could be culled

## Expected results

For a foliage batch with 250 instances and 18,000 indices per mesh, the total index reads are 4.5 million. Pipeline statistics showing 80% primitive survival after clipping indicates broad frustum or dense placement — instance culling could reduce VS invocations significantly. Degenerate triangles (e.g. 12 out of 6,000) are negligible.

## How to interpret the results

| Observation | Possible explanation |
|---|---|
| High instance count × high index count | Consider merging or impostor reduction for distant instances |
| Degenerate triangles | Minor; negligible performance impact |
| High primitive survival after clipping | Instance culling not in use; consider CPU or compute-based culling |
| Large per-instance vertex buffer slot | Normal for 4×4 transform matrix |
| Many post-VS vertices with NDC outside [-1,1] | Instances entirely off-screen; instance culling would remove VS work |

Vertex processing accounts for ~2.6 VS invocations per PS invocation — if this ratio is high, the bottleneck is most likely VS throughput or rasterization (primitive count), not the pixel shader.

## Limitations

- GPU duration is replay-based and may differ from live capture; thermal state changes
  can affect the measurement.
- Geometry statistics sample at most `max_vertices` vertices for the bounding box.
  The degenerate primitive count covers the full index buffer.
- Post-VS geometry retrieval has its own replay cost; use it only when VS output
  inspection is specifically needed.

## Related tools

`get_current_capture`, `list_gpu_counters`, `collect_gpu_counters`,
`get_gpu_measurement_status`, `get_performance_summary`, `get_pipeline_statistics`,
`get_draw_geometry_info`, `get_vertex_input_layout`, `get_mesh_statistics`,
`get_post_vs_geometry` — see the [geometry guide](../geometry.md),
[GPU performance guide](../performance.md), and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
