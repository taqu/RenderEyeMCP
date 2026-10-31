[English](compute-dispatch.md) | [日本語](../../ja/examples/compute-dispatch.md)

# Scenario F — Wrong compute shader output

## Problem

A compute shader writes unexpected results (zeros, garbage, a partially filled buffer).

## Preparation

Select the dispatch in RenderDoc. To find it, ask the agent:
*"List the dispatches in this capture with their group counts."*

## Example prompts

**Quick investigation:**
> Inspect the selected compute dispatch. Check its dispatch dimensions, shader resource
> bindings, constant buffers, and output storage buffers. Examine the first few elements
> of the output.

**Detailed investigation:**
> The selected compute dispatch is producing unexpected output. Investigate the thread
> group dimensions and how they relate to the data size. Check all resource bindings to
> confirm the input and output buffers are correctly bound. Read the constant buffer
> values and report any that look incorrect. Then read the first elements of the output
> buffer and describe what they contain.

**Follow-up investigation (optional):**
> Look at the compute shader disassembly to find the numthreads declaration and check
> whether the thread group count is large enough to process all elements.

## What the agent should investigate

- The dispatch dimensions (thread group counts on X, Y, Z axes) and whether they are sufficient to process the intended data size
- Which compute shader is bound and what its entry point and thread group size declaration are
- All resource bindings: which slots have read-only inputs, which have read-write outputs (UAVs), and whether any expected slots are unbound
- Constant buffer contents, especially counts, strides, and time values that could cause early exits
- The first elements of the output buffer or texture UAV to observe whether data was written correctly

## Expected results

- Dispatch dimensions such as `[16, 8, 16]`
- Bindings like `cbuffer Params → ResourceId::1401`, `InputData → ResourceId::503`, `OutputData (UAV) → ResourceId::505`
- Decoded constant values and the first elements of the output

## How to interpret the results

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
