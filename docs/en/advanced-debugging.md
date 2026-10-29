[English](advanced-debugging.md) | [日本語](../ja/advanced-debugging.md)

# Advanced Debugging (Pixel History & Shader Debug Trace)

## Introduction

RenderEyeMCP exposes RenderDoc's Pixel History and Shader Debugging APIs through seven
structured MCP tools. These tools allow AI coding agents to investigate rendering
problems that cannot be explained through static pipeline and resource inspection alone.

The workflow is designed around two complementary approaches:

- **Pixel History** — "Which draw calls touched this pixel and what were the results?"
- **Shader Debug Trace** — "What did the shader actually compute, step by step?"

Both require replay work on the RenderDoc GPU backend. They are explicit operations; the
server never triggers them automatically.

---

## Prerequisites

- RenderDoc is running with the RenderEyeMCP extension enabled.
- A capture (`.rdc` file) is open in the RenderDoc GUI.
- Verify readiness with `get_current_capture`.
- **Graphics API support**: Pixel History and Shader Debugging are not available on all
  graphics APIs and not for all shader types. Unsupported operations return explicit
  error codes rather than fabricated results.

---

## Available tools

| Tool | Purpose | Read-only |
|---|---|---|
| `get_pixel_history` | Retrieve all modifications affecting a pixel | No† |
| `debug_pixel_shader` | Collect a bounded pixel shader debug trace | No† |
| `debug_vertex_shader` | Collect a bounded vertex shader debug trace | No† |
| `debug_compute_shader` | Collect a bounded compute shader debug trace | No† |
| `get_shader_debug_trace` | Retrieve bounded steps from a stored trace | Yes |
| `get_shader_debug_variables` | Inspect variable state at a specific step | Yes |
| `get_shader_debug_status` | Check stored trace status and list trace IDs | Yes |

† Performs GPU replay. Does not modify the loaded capture or the GUI-selected event.

---

## Pixel History

### `get_pixel_history`

Retrieves the complete history of modifications to a single pixel across the current
frame, up to `max_modifications` entries.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `resource_id` | string | — | ResourceId of the target texture |
| `x`, `y` | int | — | Pixel coordinates |
| `mip` | int | `0` | Mip level |
| `slice` | int | `0` | Array slice |
| `sample` | int | `0` | MSAA sample index |
| `max_modifications` | int | `50` | Maximum to return (max 200) |
| `event_id` | int | `0` | Unused (reserved for future event scoping) |

**Key response fields per modification**

| Field | Meaning |
|---|---|
| `event_id` | The draw call that produced this fragment |
| `passed` | `true` if the fragment modified the pixel |
| `rejection_reason` | `depth_test`, `stencil_test`, `shader_discard`, `backface_cull`, `scissor`, `sample_mask`, or `unknown` |
| `pre_mod` | Pixel value before this draw |
| `shader_out` | Raw shader output |
| `post_mod` | Final pixel value after blend/write-mask |
| `prim_id` | Primitive (triangle) index |
| `frag_index` | Fragment index within the draw |
| `depth_test_failed` | `true` if rejected by depth test |
| `shader_discarded` | `true` if the pixel shader called discard |

**`summary` field** additionally reports:
- `passed_fragments` / `rejected_fragments` counts
- `last_modifying_event`: event_id of the last fragment that actually wrote the pixel

### Pixel History workflow

```text
get_current_capture → confirm capture
       ↓
get_render_targets → find the texture resource_id
       ↓
get_pixel_history (resource_id, x, y) → list of modifications
       ↓
examine rejection_reason and test flags
       ↓
optionally: debug_pixel_shader for the relevant event
```

---

## Shader Debug Traces

### Trace lifecycle

Shader debugging is a two-phase operation:

1. **Collection** (`debug_pixel_shader` / `debug_vertex_shader` / `debug_compute_shader`)
   — performs GPU replay, collects instruction steps and variable changes, stores the
   result in the server's `DebugStore`, and returns a `debug_id`.

2. **Inspection** (`get_shader_debug_trace`, `get_shader_debug_variables`,
   `get_shader_debug_status`) — reads stored data without further GPU work.

```text
debug_pixel_shader(x, y, event_id) → { debug_id, step_count }
              ↓
get_shader_debug_trace(debug_id, first_step=0, count=50) → steps
              ↓
get_shader_debug_variables(debug_id, step=N) → variable state at step N
```

The `DebugStore` retains up to 10 traces on a least-recently-used basis.

### `debug_pixel_shader`

Starts a pixel shader debug trace for a specific pixel coordinate.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `x`, `y` | int | — | Pixel to debug |
| `event_id` | int | `0` | Draw event (0 = current GUI selection) |
| `sample` | int | `0` | MSAA sample index |
| `primitive` | int | `-1` | Primitive ID (-1 = auto-select) |
| `view` | int | `0` | Multi-view index |
| `max_steps` | int | `200` | Maximum trace steps (max 500) |

Returns: `debug_id`, `stage`, `event_id`, `step_count`, `truncated`.

### `debug_vertex_shader`

Starts a vertex shader debug trace for a specific vertex invocation.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `vert_id` | int | `0` | Vertex index to debug |
| `inst_id` | int | `0` | Instance index |
| `idx` | int | `0` | Index buffer value (for indexed draws) |
| `view` | int | `0` | Multi-view index |
| `event_id` | int | `0` | Draw event (0 = current) |
| `max_steps` | int | `200` | Maximum steps (max 500) |

### `debug_compute_shader`

Starts a compute shader debug trace for a specific thread.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `group_x/y/z` | int | `0` | Workgroup indices |
| `thread_x/y/z` | int | `0` | Thread within the workgroup |
| `event_id` | int | `0` | Dispatch event (0 = current) |
| `max_steps` | int | `200` | Maximum steps (max 500) |

**Note**: Only the single requested thread is debugged. Cross-thread behavior
(shared memory, barriers, wave operations) is not observable from this view.

### `get_shader_debug_trace`

Retrieves bounded steps from a stored trace.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `debug_id` | string | — | ID from a debug tool |
| `first_step` | int | `0` | Starting step index |
| `count` | int | `50` | Steps to return (max 500) |

Each step includes:
- `step`: step index
- `next_instruction`: instruction offset about to execute
- `flags`: bitmask; bit 0x2 = `generated_nan_or_inf`
- `generated_nan_or_inf`: `true` when a NaN or Inf was generated
- `changes`: list of `{ before: ShaderVariable, after: ShaderVariable }` for each
  variable that changed at this step

### `get_shader_debug_variables`

Reconstructs the full variable state at a specific step by accumulating all change
deltas from the initial state up to and including `step`.

**Parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `debug_id` | string | — | ID from a debug tool |
| `step` | int | `0` | Step to reconstruct (clamped to valid range) |
| `variable_names` | list[string] | `null` | Filter; null = return all |

Returns a `variables` object mapping variable name → `{ name, rows, columns, type, value }`.

### `get_shader_debug_status`

Check a trace's status or list all stored trace IDs.

- With `debug_id`: returns `status` (`ready`/`failed`/`invalidated`), `stage`, `event_id`,
  `step_count`, and all metadata.
- Without `debug_id`: lists all stored `debug_ids`.

---

## ShaderVariable format

Each variable in trace steps and initial_vars has:

| Field | Meaning |
|---|---|
| `name` | Variable or register name |
| `rows`, `columns` | Matrix dimensions (1×1 for scalars) |
| `type` | Type string from RenderDoc reflection |
| `value` | Scalar, list, or nested for vectors/matrices |
| `members` | Nested variables (structs/arrays) |

---

## Recommended debugging workflows

### Find why a pixel has the wrong color

```text
get_render_targets → identify the render target resource_id
get_pixel_history(resource_id, x, y) → find the last modifying event
debug_pixel_shader(x, y, event_id) → collect trace
get_shader_debug_trace(debug_id) → inspect steps with NaN flags
get_shader_debug_variables(debug_id, step=N) → inspect variables at key step
```

### Find where a shader first produces NaN

```text
debug_pixel_shader / debug_vertex_shader / debug_compute_shader → collect trace
get_shader_debug_trace(debug_id, count=500) → scan flags for generated_nan_or_inf
  → note first step with generated_nan_or_inf: true
get_shader_debug_variables(debug_id, step=first_nan_step) → identify the variable
```

### Trace a vertex transformation

```text
get_draw_geometry_info → find vert_id and idx
debug_vertex_shader(vert_id, inst_id, idx) → collect trace
get_shader_debug_trace(debug_id) → step through position transformation
get_shader_debug_variables(debug_id, step=N) → inspect mvp multiplication result
```

---

## Replay effects and GUI safety

All four collection tools perform GPU replay work via RenderDoc's internal replay
controller. They do not:
- Change the loaded capture.
- Change the GUI-selected event.
- Modify the Shader Debugger UI state visible to the developer.

However, RenderDoc's internal replay position may change during collection. This
internal state is restored by RenderDoc automatically.

---

## Graphics API and shader support

Debugging support depends on RenderDoc's API and driver integration. Typical
availability:

| Feature | D3D11 | D3D12 | Vulkan | OpenGL |
|---|---|---|---|---|
| Pixel History | Yes | Yes | Yes | Yes |
| Pixel shader debug | Usually | Usually | Driver-dependent | Usually |
| Vertex shader debug | Yes | Yes | Driver-dependent | Yes |
| Compute shader debug | Usually | Usually | Driver-dependent | Limited |

Shaders compiled without debug information produce instruction-level traces only;
source-level variable names are not available.

Returns `error: debug_pixel_unsupported` (or `vertex`/`compute`) when the API or
shader does not support the requested debugging operation.

---

## Known limitations

- **No source-level debugging** without debug info in the capture; only instruction-level
  steps and register names.
- **Single-thread compute**: cross-thread dependencies (barriers, atomics, shared memory)
  are not reflected.
- **Primitive ambiguity**: when a pixel is covered by multiple fragments in one draw,
  `primitive: -1` selects one automatically; use Pixel History to identify the correct
  `prim_id` first.
- **Step limit**: traces are capped at `max_steps` (default 200, max 500). Large shaders
  may be truncated; check the `truncated` field.
- **DebugStore capacity**: the server retains at most 10 traces; oldest are evicted on
  overflow.
- **Replay cost**: each collection call has GPU cost comparable to one GPU counter
  measurement pass. Avoid calling in a tight loop.

---

## Related documentation

- [Tool reference](tools.md#advanced-debugging-pixel-history--shader-debug)
- [Scenario D1 — Incorrect pixel color](examples/pixel-history.md)
- [Scenario D2 — Pixel shader debugging](examples/shader-debugging.md)
- [Scenario D3 — Depth test rejection](examples/depth-rejection.md)
- [Scenario D4 — Vertex shader debugging](examples/vertex-debugging.md)
- [Scenario D5 — Compute shader NaN](examples/compute-debugging.md)
- [Geometry & mesh inspection](geometry.md)
- [GPU performance analysis](performance.md)
