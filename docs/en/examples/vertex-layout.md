[English](vertex-layout.md) | [日本語](../../ja/examples/vertex-layout.md)

# Scenario G2 — Incorrect vertex format

## Problem

Rendered geometry appears distorted, garbled, or incorrectly colored. You suspect that
the vertex buffer layout in the pipeline state does not match what the vertex shader
expects — a classic mismatched input layout bug.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open.
3. Select the draw call with the suspected layout mismatch.

## Example prompts

**Quick investigation:**
> Compare the selected draw call's vertex input layout with the vertex shader input
> signature. Check whether attribute formats, offsets, and bindings are consistent.

**Detailed investigation:**
> The selected draw call produces distorted geometry. Compare the declared vertex input
> layout with the vertex shader's expected input signature. For each attribute, list its
> declared format, component type, byte offset, and the vertex buffer slot it reads from.
> Then compare this with what the vertex shader expects. Identify any mismatch in format
> type, component count, or byte offset that could explain the distortion. Also compare
> the computed layout stride with the actual vertex buffer stride.

## What the agent should investigate

- The vertex input layout declared in the pipeline state: attribute names, locations, component types, component counts, byte offsets, and which vertex buffer slot each attribute reads from
- The vertex shader's input signature: what attribute names, locations, and types the shader expects
- Whether each attribute's declared type in the layout matches what the shader expects (especially UNorm vs Float mismatches on color/normal attributes)
- Whether the byte offsets are consistent (monotonically increasing, summing to the declared stride)
- Whether the actual vertex buffer stride matches the total computed from the layout

## Expected results

A typical mismatch looks like:

| Location | Layout type | Shader expects | Match? |
|---|---|---|---|
| 0 (POSITION) | `Float ×3` | `Float ×3` | Yes |
| 1 (COLOR) | `UNorm8 ×4` | `Float ×4` | **No** |
| 2 (TEXCOORD) | `Float ×2` | `Float ×2` | Yes |

Location 1 is the mismatch: the pipeline declares COLOR as `UNorm8 × 4` (4-byte packed color, values 0–255 normalized to 0.0–1.0), but the vertex shader reads it as `float4` expecting 32-bit floats.

## How to interpret the results

| Pattern | Symptom | Diagnosis |
|---|---|---|
| `UNorm8` declared, shader reads `float` | Colors wrong or extreme | Format type mismatch at COLOR/TANGENT/BONEWEIGHT attributes |
| Offset off by 4 or 8 bytes | Positions sheared or skewed | Wrong `byte_offset` for one attribute |
| Wrong binding slot | One attribute always zero | Attribute references unbound VB slot |
| Stride too small | Garbled after first vertex | Computed layout larger than declared stride |
| Per-instance flag wrong | Object uses wrong transform | Attribute marked `per_instance` when it should be per-vertex |

- Format mismatches appear most often on packed color or normal attributes
  (UNorm/SNorm 8-bit) when the shader was compiled expecting 32-bit floats.
- Offset errors produce visible shearing and are easy to find once you list all offsets
  in a table and check monotonic increase.
- Stride errors compound — every vertex after the first reads from the wrong offset.

## Limitations

- Vertex data is decoded using the layout's declared format. Discrepancies between
  the layout and the shader are visible only by comparing the two responses manually.
- Component byte width is reported for individual components; total attribute size is
  `comp_count × comp_byte_width`.

## Related tools

`get_current_capture`, `get_vertex_input_layout`, `get_current_shaders`,
`get_mesh_vertices`, `get_draw_geometry_info`, `get_mesh_statistics` — see the
[geometry guide](../geometry.md) and the
[tool reference](../tools.md#geometry-and-mesh-inspection).
