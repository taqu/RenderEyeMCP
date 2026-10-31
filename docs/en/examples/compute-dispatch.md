[English](compute-dispatch.md) | [日本語](../../ja/examples/compute-dispatch.md)

# Scenario F — Wrong compute shader output

## Problem

A compute shader writes unexpected results (zeros, garbage, a partially filled buffer).

## Preparation

Select the dispatch in RenderDoc. To find it, ask the agent:
*"List the dispatches in this capture with their group counts."*

## Example prompt

> Inspect the selected compute dispatch. Check its dispatch dimensions, shader resource
> bindings, constant buffers, and output storage buffers. Examine the first few elements
> of the output.

## Investigation workflow

1. `get_selected_event` — `dispatch_dimension` (thread-group counts X, Y, Z).
2. `list_shaders` / `get_shader_info` (`stage: Compute`) — which compute shader, entry
   point, encoding.
3. `get_shader_reflection` (`stage: Compute`, `section: all`) — declared inputs
   (read-only resources), outputs (read-write/UAV resources) and constant buffer layout.
4. `get_shader_bindings` (`stage: Compute`) — what is actually bound to each slot.
5. `read_buffer_data` on the constant buffer (from its `byte_offset`) decoded with the
   reflected layout.
6. Output: for a buffer UAV, `get_buffer_info` then `read_buffer_data` with a
   `decode_layout` matching the element struct; for a texture UAV, `get_texture_info`,
   `get_texture_statistics` and `get_pixel_value`.
7. Optional: `get_shader_disassembly` with `search` to find the thread-group size
   declaration (e.g. `numthreads`) or a specific instruction.

## Expected observations

- Dispatch dimensions such as `[16, 8, 16]`.
- Bindings like `cbuffer Params → ResourceId::1401 (byte_offset 0, byte_size 256)`,
  `InputData → ResourceId::503`, `OutputData (UAV) → ResourceId::505`.
- Decoded constants and the first elements of the output.

## Interpretation

- **Dispatch dimensions are thread-group counts, not threads.** The logical workload is
  `group count × numthreads` per axis. A buffer of 1000 elements processed with
  `numthreads(64,1,1)` needs at least 16 groups; 15 groups leave the tail unwritten.
  Find `numthreads` in the disassembly or source.
- **UAV not bound** or bound to an unexpected resource → output goes elsewhere.
- **Constants** (counts, strides, time) that are zero or stale often explain early-outs.
- Output is read **at the selected event** — that is, after this dispatch's position in
  the frame. If a later pass overwrote it, select the dispatch itself; if you need the
  state before the dispatch, select the preceding event.

## Limitations

- Individual invocations cannot be stepped or inspected (no shader debugging).
- Structured buffers need a `decode_layout` matching the element struct (max 100
  elements and 16384 bytes per read; page with `offset`).
- Indirect dispatch arguments are not decoded specially; read the argument buffer with
  `read_buffer_data` if needed.

## Related tools

`get_selected_event`, `list_capture_events`, `list_shaders`, `get_shader_info`,
`get_shader_reflection`, `get_shader_bindings`, `get_shader_disassembly`,
`get_buffer_info`, `read_buffer_data`, `get_texture_statistics`, `get_pixel_value` —
see the [tool reference](../tools.md).
