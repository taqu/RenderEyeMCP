[English](quickstart.md) | [日本語](../ja/quickstart.md)

# Quick start: inspect the capture open in RenderDoc

This walkthrough takes about five minutes once RenderEyeMCP is installed. It uses the
main workflow: you open a capture in RenderDoc the way you normally do, and the agent
inspects it. The agent does not open or reopen the capture.

## 1. Install and connect an agent

Follow [Installation](installation.md) and [Configuration](configuration.md). You should
have:

- `rendereye-mcp doctor` without `✗` lines,
- the RenderEyeMCP extension enabled in RenderDoc (**Tools → Manage Extensions**,
  *Always Load*),
- Claude Code or Codex configured and restarted.

## 2. Start RenderDoc and open a capture

Any of these work:

- *File → Open Capture* and pick an `.rdc` file;
- capture a frame from Unity, Unreal Engine or your own application and open it in
  RenderDoc;
- double-click an `.rdc` file.

## 3. Select a draw call

In RenderDoc's **Event Browser**, click a draw call (for example a
`DrawIndexedInstanced` that renders the object you are interested in). Check the
*Pipeline State* or *Texture Viewer* panel updates to that event.

RenderEyeMCP always inspects **the event selected in the GUI**. The agent cannot change
the selection, so to look at another event, select it in RenderDoc and ask again.

## 4. Ask the agent

> Inspect the capture currently open in RenderDoc. Identify the selected draw call and
> summarize its pipeline state.

## 5. What the agent should do

A typical agent run looks like this (tool names are shown for reference; you do not
need to type them):

| Step | Tool | You should see |
|------|------|----------------|
| Find the RenderDoc session and its capture | `get_current_capture` | `status: loaded`, the `.rdc` path |
| Capture metadata | `get_current_capture_info` | API (e.g. `D3D12`), frame number, numbers of events, draws and dispatches |
| The selected event | `get_selected_event` | `selected_event_id` and the API call name, e.g. `DrawIndexedInstanced()` |
| Pipeline overview | `get_pipeline_state` (`section: summary`) | topology, bound shader stages, render target count, depth target |
| Details as needed | `get_pipeline_state` (`input_assembly`, `rasterizer`, `output_merger`, `resources`), `list_shaders`, `get_render_targets` | buffers, viewports, targets, bindings |

The agent then summarizes. A good summary separates what was **observed** (values
returned by the tools) from **hypotheses** about what they mean.

## 6. Understand the results

- **Resource IDs** look like `ResourceId::805`. They are valid for the capture that is
  currently open; reopening or switching captures can change them.
- **Event IDs** (EIDs) match the numbers in RenderDoc's Event Browser.
- `depth_stencil` returns a note instead of state: depth function and depth-write flags
  are not available through RenderDoc's API-neutral interface. The bound depth *target*
  is available via `output_merger` and `get_render_targets`.
- Viewport and scissor arrays list every slot; unused slots have zero size.

## Next steps

- Work through the [debugging scenarios](examples/README.md).
- Copy prompts from [Prompt examples](prompts.md).
- Look up parameters in the [MCP tool reference](tools.md).

## Validation

This flow was run against a D3D12 capture in RenderDoc 1.46 on Windows 11 through the
MCP stdio server (38 tools discovered; `get_current_capture`, `get_current_capture_info`,
`get_selected_event`, all `get_pipeline_state` sections, `list_shaders` and
`get_render_targets` returned data for a selected draw call). The event was selected
through RenderDoc's Python API. In one earlier manual session the extension kept
reporting the post-load event after a draw was clicked in the GUI; that observation is
still being investigated (see [release readiness](../release_readiness.md)). If the agent
reports a different event than the one you selected, see
[Troubleshooting](troubleshooting.md#the-agent-reports-a-different-event-than-the-one-i-selected).
