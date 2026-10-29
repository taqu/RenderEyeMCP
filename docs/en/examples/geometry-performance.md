[English](geometry-performance.md) | [日本語](../../ja/examples/geometry-performance.md)

# Scenario G4 — Geometry performance

## Problem

A draw call has been identified as expensive through Phase 13 GPU performance analysis.
You want to investigate whether the high cost is related to excessive geometry — too many
vertices, indices, or instances — or whether it stems from shader complexity or
rasterization work.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm with `get_current_capture`.
3. Phase 13 timing and pipeline-statistics counters have already been collected.
   If not, use `collect_gpu_counters` first.

## Example prompt

> Analyze the geometry processed by this expensive draw call. Compare its index count,
> instance count, vertex shader invocations, and available GPU timing measurements.
> Identify potential inefficiencies.

---

## Investigation workflow

### 1. Identify the expensive draw call with Phase 13

If you have a measurement from a previous session, retrieve the top events:

```json
{
  "tool": "get_performance_summary",
  "measurement_id": "meas_9a2c1f",
  "top_n": 10
}
```

Example response (illustrative):

```json
{
  "total_measured_seconds": 0.012,
  "top_events": [
    { "event_id": 880, "event_name": "DrawIndexedInstanced() — foliage_batch",
      "duration_seconds": 0.0042, "percent_of_total": 35.0 },
    { "event_id": 440, "event_name": "DrawIndexed() — terrain_hi",
      "duration_seconds": 0.0021, "percent_of_total": 17.5 }
  ]
}
```

Event 880 (`foliage_batch`) is the clear outlier at 35 % of measured time.

### 2. Get draw call geometry configuration

```json
{
  "tool": "get_draw_geometry_info",
  "event_id": 880
}
```

Example response (illustrative):

```json
{
  "event_id": 880,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 18000,
  "instance_count": 250,
  "first_index": 0,
  "base_vertex": 0,
  "first_instance": 0,
  "vertex_buffers": [
    { "slot": 0, "byte_stride": 48, "resource_id": "0x0000b1a2" },
    { "slot": 1, "byte_stride": 64, "resource_id": "0x0000b1a3", "per_instance": true }
  ]
}
```

Key observations:
- 250 instances × 18 000 indices = **4 500 000 index reads**.
- Slot 1 is a per-instance buffer (transform, material).
- At 35 % GPU time, this draw is likely the dominant cost in the frame.

### 3. Get pipeline statistics (if available)

```json
{
  "tool": "get_pipeline_statistics",
  "measurement_id": "meas_9a2c1f",
  "event_id": 880
}
```

Example response (illustrative):

```json
{
  "event_id": 880,
  "vs_invocations": 3960000,
  "ps_invocations": 1500000,
  "ia_vertices": 4500000,
  "ia_primitives": 1500000,
  "clipping_invocations": 6000000,
  "clipping_primitives": 1200000
}
```

3 960 000 VS invocations for 4 500 000 index reads is close (some reuse from the post-T&L
cache). 1 200 000 clipping-output primitives from 1 500 000 input primitives means ~80 %
survive clipping — reasonable for foliage that partially exits the frustum.

### 4. Get geometry statistics for the mesh

```json
{
  "tool": "get_mesh_statistics",
  "event_id": 880,
  "max_vertices": 500
}
```

Example response (illustrative):

```json
{
  "vertex_count": 18000,
  "index_count": 18000,
  "instance_count": 250,
  "topology": "triangle_list",
  "sampled": false,
  "bounding_box": { "min": [-0.5, 0.0, -0.5], "max": [0.5, 2.0, 0.5] },
  "nan_inf_count": 0,
  "degenerate_primitives": 12
}
```

12 degenerate triangles in 6 000 primitives (18 000 / 3) is marginal. The bounding
box `[-0.5, 0.5] × [0, 2] × [-0.5, 0.5]` indicates a 1 m wide, 2 m tall foliage
card — consistent with a tree billboard mesh.

### 5. Check the vertex input layout

```json
{
  "tool": "get_vertex_input_layout",
  "event_id": 880
}
```

Verify the per-instance slot. If each instance carries a 64-byte transform (4×float4)
that is perfectly normal. Look for unexpectedly large per-instance data, or per-instance
attributes that could instead be encoded in a texture to reduce VB bandwidth.

### 6. Inspect a small vertex sample

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 880,
  "first_vertex": 0,
  "count": 10,
  "attributes": ["POSITION"]
}
```

Check that positions are reasonable. No NaN, no unexpectedly large values, plausible mesh
size.

### 7. Interpret results and identify inefficiencies

Combine findings:

| Observation | Possible explanation |
|---|---|
| 250 instances × 18 000 indices = 4.5M reads | High instance count for a single mesh; consider batching into a mesh with merged instances if they share the same material |
| 12 degenerate triangles | Minor; negligible performance impact |
| 80 % primitive survival after clipping | Broad frustum or dense foliage placement; consider instance culling |
| Per-instance 64-byte VB slot | Normal for a 4×4 transform matrix |

### 8. Optional — Compare VS input vs. output

```json
{
  "tool": "get_post_vs_geometry",
  "event_id": 880,
  "stage": "vs_out",
  "max_vertices": 20
}
```

If many post-VS vertices have `w ≤ 0` or NDC outside `[-1, 1]`, those instances are
entirely off-screen. Instance culling on the CPU or in a compute pass would reduce VS
invocations significantly.

---

## Performance correlation summary

| Metric | Source | Value (illustrative) |
|---|---|---|
| GPU duration | Phase 13 timing counter | 4.2 ms (35 % of frame) |
| VS invocations | Pipeline statistics | 3 960 000 |
| PS invocations | Pipeline statistics | 1 500 000 |
| Index reads | `get_draw_geometry_info` | 4 500 000 |
| Instance count | `get_draw_geometry_info` | 250 |
| Degenerate primitives | `get_mesh_statistics` | 12 / 6 000 |
| Post-clipping survival | Pipeline statistics | 80 % |

Vertex processing accounts for ~2.6 VS invocations per PS invocation — the bottleneck
is most likely VS throughput or rasterization (primitive count), not the pixel shader.

---

## Limitations

- GPU duration is replay-based and may differ from live capture; thermal state changes
  can affect the measurement.
- `get_mesh_statistics` samples at most `max_vertices` vertices for the bounding box.
  The degenerate primitive count is over the full index buffer (up to `_MAX_INDEX_READ`
  indices).
- `get_post_vs_geometry` has its own replay cost; call it only when VS output inspection
  is specifically needed.

## Related tools

`get_current_capture`, `list_gpu_counters`, `collect_gpu_counters`,
`get_gpu_measurement_status`, `get_performance_summary`, `get_pipeline_statistics`,
`get_draw_geometry_info`, `get_vertex_input_layout`, `get_mesh_statistics`,
`get_post_vs_geometry` — see the [geometry guide](../geometry.md),
[GPU performance guide](../performance.md), and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
