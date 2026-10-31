[English](vertex-layout.md) | [日本語](../../ja/examples/vertex-layout.md)

# Scenario G2 — Incorrect vertex format

## Problem

Rendered geometry appears distorted, garbled, or incorrectly colored. You suspect that
the vertex buffer layout in the pipeline state does not match what the vertex shader
expects — a classic mismatched input layout bug.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Confirm with `get_current_capture`.
3. Select the draw call with the suspected layout mismatch.

## Example prompt

> Compare the selected draw call's vertex input layout with the vertex shader input
> signature. Check whether attribute formats, offsets, and bindings are consistent.

---

## Investigation workflow

### 1. Retrieve the vertex input layout

```json
{ "tool": "get_vertex_input_layout" }
```

This returns the attributes as declared in the pipeline state: name, location, component
type, component count, byte offset, and which VB slot each attribute reads from.

Example response (illustrative):

```json
{
  "event_id": 340,
  "attributes": [
    { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 0,  "per_instance": false },
    { "name": "COLOR",    "location": 1, "comp_type": "UNorm", "comp_count": 4,
      "comp_byte_width": 1, "vertex_buffer": 0, "byte_offset": 12, "per_instance": false },
    { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 16, "per_instance": false }
  ]
}
```

Computed stride: `0 + 3×4 + 4×1 + 2×4 = 12 + 4 + 8 = 24 bytes`.

### 2. Retrieve the vertex shader input signature

```json
{ "tool": "get_current_shaders" }
```

This returns the active shaders. Look for the vertex shader's input signature in the
response. (Use `get_shader_reflection` for the full signature if needed.)

Example vertex shader signature (illustrative):

```json
{
  "vertex_shader": {
    "entry_point": "VSMain",
    "input_signature": [
      { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3 },
      { "name": "COLOR",    "location": 1, "comp_type": "Float", "comp_count": 4 },
      { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2 }
    ]
  }
}
```

### 3. Compare layout vs. shader signature

Line up the two attribute lists by location:

| Location | Layout type | Shader expects | Match? |
|---|---|---|---|
| 0 (POSITION) | `Float ×3` | `Float ×3` | ✓ |
| 1 (COLOR) | `UNorm ×4 ×1 byte` | `Float ×4` | **✗** |
| 2 (TEXCOORD) | `Float ×2` | `Float ×2` | ✓ |

Location 1 is the mismatch. The pipeline declares `COLOR` as `UNorm8 × 4` (packed
4-byte color, values 0–255 normalized to 0.0–1.0), but the vertex shader reads it as
`float4` expecting 32-bit floats. The hardware interprets the 4 bytes as a single
`float32`, producing a nonsensical floating-point value.

### 4. Verify with decoded vertex data

Decode the first few vertices to confirm the corruption:

```json
{
  "tool": "get_mesh_vertices",
  "first_vertex": 0,
  "count": 5,
  "attributes": ["COLOR"]
}
```

With the mismatch, the decoded COLOR values (read as Float by the tool, following the
layout) would show valid 0–1 range values:

```json
{
  "vertices": [
    { "vertex_id": 0, "attributes": { "COLOR": [1.0, 0.5, 0.25, 1.0] } },
    { "vertex_id": 1, "attributes": { "COLOR": [0.0, 1.0, 0.0,  1.0] } }
  ]
}
```

These look correct because `get_mesh_vertices` applies the layout's declared format
(UNorm8×4). The vertex shader, however, reads the underlying bytes as `float4`
components, producing garbage values.

### 5. Check the draw call geometry configuration

Confirm the VB stride matches the computed layout size:

```json
{ "tool": "get_draw_geometry_info" }
```

```json
{
  "vertex_buffers": [
    { "slot": 0, "byte_stride": 32 }
  ]
}
```

Stride is 32, but the computed layout sum is 24. This 8-byte discrepancy means either
there is padding between attributes, or the layout declaration is wrong and is reading
attributes at incorrect offsets. Adjust `byte_offset` values and recompute.

### 6. Geometry statistics sanity check

```json
{ "tool": "get_mesh_statistics" }
```

```json
{
  "vertex_count": 1200,
  "index_count": 1800,
  "topology": "triangle_list",
  "bounding_box": { "min": [-1.0, 0.0, -1.0], "max": [1.0, 2.0, 1.0] },
  "nan_inf_count": 0,
  "degenerate_primitives": 0
}
```

No NaN, no degenerates. The problem is purely a format mismatch — the geometry itself is
valid.

---

## Common mismatch patterns

| Pattern | Symptom | Diagnosis |
|---|---|---|
| `UNorm8` declared, shader reads `float` | Colors wrong or extreme | Format type mismatch at COLOR/TANGENT/BONEWEIGHT attributes |
| Offset off by 4 or 8 bytes | Positions sheared or skewed | Wrong `byte_offset` in layout for one attribute |
| Wrong binding slot | One attribute always zero | Attribute references unbound VB slot |
| Stride too small | Garbled after first vertex | Computed layout larger than declared stride |
| Per-instance flag wrong | Object uses wrong transform | Attribute marked `per_instance` when it should be per-vertex |

---

## Expected observations

- Format mismatches appear most often on packed color or normal attributes
  (UNorm/SNorm 8-bit) when the shader was compiled expecting 32-bit floats.
- Offset errors produce visible shearing and are easy to find once you list all offsets
  in a table and check monotonic increase.
- Stride errors compound — every vertex after the first reads from the wrong offset.

---

## Limitations

- `get_mesh_vertices` decodes using the layout's declared format. Discrepancies between
  the layout and the shader are visible only by comparing the two responses manually.
- Component byte width is reported for individual components; total attribute size is
  `comp_count × comp_byte_width`.

## Related tools

`get_current_capture`, `get_vertex_input_layout`, `get_current_shaders`,
`get_mesh_vertices`, `get_draw_geometry_info`, `get_mesh_statistics` — see the
[geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
