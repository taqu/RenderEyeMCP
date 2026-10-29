[English](active-capture.md) | [日本語](../../ja/examples/active-capture.md)

# Scenario A — Inspect an already-open capture

## Problem

You captured a frame from your engine (or Unity/Unreal) and it is open in RenderDoc.
You want the agent to work with *that* capture without reopening anything.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Select any event in the Event Browser.

## Example prompt

> Inspect the capture currently open in RenderDoc. Tell me which graphics API it uses,
> what frame is captured, and which event is selected.

## Investigation workflow

1. **GUI session discovery** — `list_renderdoc_sessions` / `get_current_capture`: which
   RenderDoc windows are connected and which capture each one has loaded.
2. **Capture identification** — `get_current_capture_info`: API, GPU vendor, frame
   number, event/draw/dispatch counts.
3. **Event selection** — `get_selected_event`: the EID and the API call you selected.
4. Optionally `list_capture_events` with `flags_filter: drawcall` to give an overview.

## Expected observations

- `status: loaded` with the path of the `.rdc` file.
- `api` such as `D3D12`, a `frame_number`, and `statistics` such as
  `{"total_events": 2370, "draw_calls": 533, "dispatches": 17}`.
- `selected_event_id` matching the EID highlighted in RenderDoc, with a name like
  `ID3D12GraphicsCommandList::DrawIndexedInstanced()`.

## Interpretation

This confirms the whole chain works: agent → MCP server → shared service → extension →
your RenderDoc window. If the selected event is a marker or `Present`, later scenarios
will report "no shader bound" — select a draw call before going on.

## Limitations

- If several RenderDoc windows are connected, the agent must choose one
  (`status: ambiguous`). Say which capture you mean.
- `capture_time` may be `0` for some captures.

## Related tools

`list_renderdoc_sessions`, `get_renderdoc_session_state`, `get_current_capture`,
`get_current_capture_info`, `get_selected_event`, `list_capture_events` —
see the [tool reference](../tools.md#session-and-capture).
