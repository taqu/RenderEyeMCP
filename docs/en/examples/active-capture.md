[English](active-capture.md) | [日本語](../../ja/examples/active-capture.md)

# Scenario A — Inspect an already-open capture

## Problem

You captured a frame from your engine (or Unity/Unreal) and it is open in RenderDoc.
You want the agent to work with *that* capture without reopening anything.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. The capture is open. Select any event in the Event Browser.

## Example prompts

**Quick investigation:**
> Inspect the capture currently open in RenderDoc. Tell me which graphics API it uses,
> what frame is captured, and which event is selected.

**Detailed investigation:**
> Inspect the capture open in RenderDoc and give me a full overview. Identify the
> graphics API, GPU, frame number, total event count, draw call count, and dispatch
> count. Also tell me the name and event ID of the currently selected event.

## What the agent should investigate

- Which RenderDoc windows are connected and which capture each one has loaded
- The graphics API, GPU vendor, frame number, and summary statistics (total events, draw calls, dispatches) for the loaded capture
- The event ID and API call name of the event currently selected in the Event Browser

## Expected results

- The path of the loaded `.rdc` file with a loaded status
- API such as `D3D12`, a frame number, and statistics such as `{"total_events": 2370, "draw_calls": 533, "dispatches": 17}`
- The selected event ID matching the EID highlighted in RenderDoc, with a name like `ID3D12GraphicsCommandList::DrawIndexedInstanced()`

## How to interpret the results

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
