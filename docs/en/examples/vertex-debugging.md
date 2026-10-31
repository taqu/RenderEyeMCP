[English](vertex-debugging.md) | [日本語](../../ja/examples/vertex-debugging.md)

# Scenario D4 — Vertex Shader Debugging

## Problem

Mesh vertices appear at wrong positions after transformation. You want to step through
the vertex shader for a specific vertex to see the MVP matrix multiplication result and
find where the transformation goes wrong.

## Prerequisites

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded. Confirm with `get_current_capture`.
3. A draw call with the mispositioned mesh is selected or known.

## Example prompt

> Vertex 0 of draw event 310 is ending up at the wrong clip-space position. Step
> through the vertex shader to find where the transformation breaks down.

---

## Investigation workflow

### 1. Get draw geometry info to find vertex indices

```json
{ "tool": "get_draw_geometry_info", "event_id": 310 }
```

Example response (illustrative):

```json
{
  "event_id": 310,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 360,
  "instance_count": 1,
  "first_index": 0,
  "base_vertex": 0
}
```

For an indexed draw, you need the `idx` (the raw index buffer value) for the vertex
you want to debug. Use `get_mesh_vertices` to cross-reference:

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 310,
  "first_vertex": 0,
  "count": 5,
  "attributes": ["POSITION"]
}
```

Note the first vertex has `vertex_id: 0`. For the vertex shader debugger, `vert_id`
is the vertex index within the draw (0-based), and `idx` is the index buffer value
(`base_vertex + vert_id` for non-indexed draws; same as index buffer value for indexed).

### 2. Check the input position

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 310,
  "first_vertex": 0,
  "count": 1,
  "attributes": ["POSITION", "NORMAL"]
}
```

Example response (illustrative):

```json
{
  "vertices": [
    { "vertex_id": 0,
      "attributes": {
        "POSITION": [0.0, 1.0, 0.0],
        "NORMAL":   [0.0, 1.0, 0.0]
      }
    }
  ]
}
```

Object-space position is `(0, 1, 0)` — the top of a unit object.

### 3. Check the post-VS position

```json
{
  "tool": "get_post_vs_geometry",
  "event_id": 310,
  "stage": "vs_out",
  "max_vertices": 5
}
```

Example response (illustrative — incorrect):

```json
{
  "vertices": [
    { "vertex_id": 0,
      "clip_pos": [0.0, 1000.0, 4.9, 5.0],
      "ndc_pos":  [0.0, 200.0, 0.98]
    }
  ]
}
```

NDC y = 200 is far outside `[-1, 1]`. The vertex is off-screen. The Y coordinate is
scaled by 1000 — a scale bug in the model matrix.

### 4. Collect a vertex shader debug trace

```json
{
  "tool": "debug_vertex_shader",
  "event_id": 310,
  "vert_id": 0,
  "inst_id": 0,
  "idx": 0
}
```

Example response (illustrative):

```json
{
  "debug_id": "dbg_a1b2c300",
  "stage": "vertex",
  "event_id": 310,
  "step_count": 38,
  "truncated": false
}
```

### 5. Step through the trace

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_a1b2c300",
  "first_step": 0,
  "count": 50
}
```

Example response (illustrative — key steps):

```json
{
  "steps": [
    { "step": 0,  "changes": [] },
    { "step": 8,  "changes": [
        { "before": { "name": "pos_ws", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "pos_ws", "value": [0.0, 1000.0, 0.0, 1.0] } }
    ]},
    { "step": 22, "changes": [
        { "before": { "name": "pos_cs", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "pos_cs", "value": [0.0, 1000.0, 4.9, 5.0] } }
    ]}
  ]
}
```

After the model-to-world transform (step 8), `pos_ws.y = 1000.0` — clearly wrong. The
model matrix has a scale factor of 1000 on the Y axis.

### 6. Inspect variables at step 8

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_a1b2c300",
  "step": 8,
  "variable_names": ["pos_ws", "model_matrix"]
}
```

Example response (illustrative):

```json
{
  "variables": {
    "model_matrix": {
      "name": "model_matrix",
      "rows": 4, "columns": 4,
      "type": "float",
      "value": [
        [1.0,    0.0,    0.0, 0.0],
        [0.0, 1000.0,    0.0, 0.0],
        [0.0,    0.0,    1.0, 0.0],
        [0.0,    0.0,    0.0, 1.0]
      ]
    },
    "pos_ws": { "name": "pos_ws", "value": [0.0, 1000.0, 0.0, 1.0] }
  }
}
```

`model_matrix[1][1] = 1000.0`. The Y scale in the model matrix is 1000 instead of 1.
The application is uploading the wrong scale value or computing the matrix incorrectly.

---

## Root cause summary

| Step | Finding |
|---|---|
| Post-VS clip: NDC y = 200 | Vertex is 200× too far in Y |
| Vertex shader step 8: `pos_ws.y = 1000` | Model-to-world transform scales Y by 1000 |
| `model_matrix[1][1] = 1000.0` | Confirmed: wrong scale in model matrix upload |

Fix: find where the model matrix is computed or uploaded and correct the Y scale.

---

## Limitations

- `debug_vertex_shader` debugs a single vertex invocation. Other vertices may have
  different values; repeat for additional vertices if needed.
- For indexed draws, pass the index buffer value as `idx`. For non-indexed draws,
  `idx = vert_id + base_vertex`.
- Returns `error: debug_vertex_unsupported` if the API or driver does not support
  vertex shader debugging.

## Related tools

`get_draw_geometry_info`, `get_mesh_vertices`, `get_post_vs_geometry`,
`debug_vertex_shader`, `get_shader_debug_trace`, `get_shader_debug_variables` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
