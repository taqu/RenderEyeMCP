# Phase 8 — Active Capture Inspection & Pipeline State Analysis

## Objective

Extend RenderEyeMCP so AI coding agents can inspect captures that are already loaded in the RenderDoc GUI, without opening, reloading, or taking ownership of those captures.

Phase 7 introduced RenderDoc GUI state discovery and synchronization. Phase 8 builds on that foundation to expose useful capture information, draw calls, events, and graphics/compute pipeline state through MCP tools.

The primary use case is a developer debugging a game engine rendering issue.

Example workflow:

1. The developer captures a frame using Unity, Unreal Engine, or another application.
2. The capture is opened in RenderDoc.
3. The developer selects a suspicious draw call in the RenderDoc GUI.
4. The developer asks a coding agent:

   "Inspect the currently selected draw call and its pipeline state."

5. The agent queries RenderEyeMCP.
6. RenderEyeMCP retrieves information from the already-loaded capture.
7. The agent analyzes the results without modifying the RenderDoc GUI.

**The central requirement is to inspect the capture and event currently being examined by the developer.**

Do not require the agent to open the `.rdc` file again.

Do not create a separate replay session when the existing RenderDoc GUI replay context can safely provide the required information.

---

## 1. Inspect Existing Implementation

Before implementing Phase 8, investigate the current repository.

Identify:

- RenderDoc extension implementation.
- RenderDoc Extension API integration.
- Phase 6 Shared IPC Service.
- Phase 7 GUI state discovery and synchronization.
- Session and capture identity mechanisms.
- Existing capture information retrieval.
- Existing event and draw-call inspection tools.
- Existing pipeline-state inspection tools.
- Existing replay controller integration, if any.
- Existing MCP tool schemas.
- Existing tests and documentation.

Determine which inspection features already exist and whether they work with captures opened externally.

Reuse and extend existing functionality.

Do not introduce duplicate inspection APIs when existing tools can support the required behavior.

### Phase 7 Dependency

Verify that the implementation can:

1. Discover a connected RenderDoc GUI.
2. Identify its loaded capture.
3. Distinguish GUI sessions.
4. Detect capture changes.
5. Recover current state after IPC reconnection.

If Phase 7 is incomplete, document the missing dependencies and implement only the minimum integration necessary for Phase 8.

Do not redesign the Phase 7 architecture.

---

## 2. Investigate RenderDoc Replay and Extension APIs

Investigate the installed RenderDoc version and its supported APIs.

Determine how the extension can access capture information through the existing GUI context.

Relevant concepts may include:

- CaptureContext
- ReplayController
- ActionDescription
- APIProperties
- PipeState / PipelineState
- Shader reflection
- Resource descriptions
- Current event selection

These are investigation targets, not assumptions about specific API availability or naming.

Inspect the actual RenderDoc headers, Python bindings, extension interfaces, and repository code before selecting implementation approaches.

### 2.1 Replay Controller Access

Determine whether the extension can safely access the replay controller already associated with the RenderDoc GUI.

Prefer supported APIs that operate on the existing GUI replay context.

Do not create a second replay controller or reopen the capture simply to obtain inspection information unless absolutely necessary.

If independent replay is required for a specific operation, document why the GUI context is insufficient and keep that operation outside the default inspection path.

### 2.2 Threading Requirements

RenderDoc replay APIs may require execution on specific threads.

Investigate:

- GUI thread requirements.
- Replay thread requirements.
- Replay controller ownership.
- Supported asynchronous invocation mechanisms.
- Capture unload and replay shutdown behavior.

All replay-related operations must execute in the correct context.

Do not invoke replay APIs directly from arbitrary IPC worker threads.

Avoid blocking the RenderDoc GUI while performing IPC communication or expensive serialization.

### 2.3 API Compatibility

Do not assume all RenderDoc versions expose identical APIs.

Prefer the APIs supported by the project's existing RenderDoc compatibility requirements.

When an API is unavailable, return an explicit unsupported result rather than guessing.

Avoid undocumented internal interfaces and process-memory inspection.

---

## 3. Active Capture Resolution

Implement a common mechanism for resolving the capture that an MCP inspection request should target.

The default inspection target should be an existing loaded capture.

### 3.1 Resolution Rules

Apply the following rules:

1. If the request specifies a GUI session, use that session.
2. If an existing explicit session selection is available, honor it.
3. If exactly one eligible GUI session has a loaded capture, use it.
4. If multiple possible sessions exist, return an ambiguity result with the available sessions.
5. If no capture is loaded, return a structured no-capture result.
6. If the target GUI is disconnected, report the connection issue.

Do not automatically choose the newest capture, most recently registered GUI, or most recently opened file unless an explicit existing policy defines that behavior.

### 3.2 Capture Identity

Associate inspection requests with:

- GUI session identity.
- Capture identity.
- Capture state version or generation, when available.

A capture path alone may not uniquely identify a loaded capture instance.

If the capture changes while an inspection is running, do not silently combine information from the old and new captures.

Either:

- Complete the request against a validated capture snapshot, or
- Return a capture-changed result and allow the agent to retry.

### 3.3 No Implicit Capture Opening

Read-only inspection requests must never:

- Open an `.rdc` file.
- Reload the current capture.
- Launch another RenderDoc GUI.
- Close an existing capture.
- Change the active GUI session.

These actions belong to separate explicit operations.

---

## 4. Capture Information Inspection

Expose useful metadata for the currently loaded capture.

Suggested MCP tool:

`get_current_capture_info`

Reuse an existing tool if equivalent functionality already exists.

### 4.1 Information to Retrieve

Retrieve available information such as:

- GUI session identifier.
- Capture path.
- Capture identity.
- Replay API type (D3D11, D3D12, Vulkan, OpenGL, etc.).
- Captured application or executable name.
- Capture timestamp.
- Frame number, when available.
- Capture dimensions, when reliably available.
- Driver or API information.
- Total event count.
- Draw-call count.
- Dispatch count.
- Available resource counts.

Do not assume all metadata is exposed by the RenderDoc API.

Only include fields that can be derived reliably.

Distinguish unavailable values from zero values.

### 4.2 Suggested Response

Conceptual example:

```json
{
  "session_id": "renderdoc-session-1234",
  "capture": {
    "path": "D:/Captures/frame_001.rdc",
    "api": "D3D12",
    "application": "Game.exe",
    "frame_number": 125
  },
  "statistics": {
    "events": 2300,
    "draw_calls": 780,
    "dispatches": 120
  }
}
```

This example illustrates the desired structure and does not imply that every field is supported by every RenderDoc version.

Prefer existing repository response conventions.

Avoid returning large resource lists as part of basic capture information.

---

## 5. Draw Call and Event Inspection

Implement inspection of draw calls, compute dispatches, and relevant RenderDoc events.

The agent must be able to understand the event structure of the currently loaded capture.

### 5.1 Event Hierarchy

RenderDoc captures may contain hierarchical event structures, including:

- Debug markers.
- Render passes.
- Draw calls.
- Compute dispatches.
- Copy operations.
- Clears.
- Barriers.
- Other GPU commands.

Preserve the hierarchy where possible.

Do not flatten all events into an unstructured list if doing so loses meaningful context.

### 5.2 List Events

Suggested MCP tool:

`list_capture_events`

Support:

- Session targeting.
- Pagination or bounded result counts.
- Event ID lookup.
- Event type filtering, where practical.
- Optional hierarchical representation.
- Optional event name filtering.

Do not return thousands of events by default.

Use a bounded response format that is appropriate for LLM context windows.

For large captures, provide counts and allow the agent to request smaller ranges.

### 5.3 Event Information

Each event should expose available information such as:

- Event ID.
- Event name.
- Event/action type.
- Parent event or marker.
- Hierarchy depth.
- Draw, dispatch, or copy classification.
- Associated flags.
- Draw parameters where applicable.
- Dispatch dimensions where applicable.

For graphics draws, useful parameters may include:

- Vertex count.
- Index count.
- Instance count.
- First vertex/index.
- Base vertex.
- First instance.
- Primitive topology, when available.

For compute dispatches:

- Dispatch group counts.
- Relevant compute shader information, when available.

Do not confuse command events, draw-call actions, and marker events.

Use RenderDoc's actual event/action model.

### 5.4 Inspect Individual Event

Suggested MCP tool:

`get_capture_event`

Accept a session identifier and event ID.

Return detailed information for the requested event.

Use existing RenderDoc event identifiers rather than introducing artificial renumbering.

Validate that the event belongs to the currently loaded capture.

An invalid or obsolete event ID must produce a meaningful error.

---

## 6. Current GUI Event Selection

This is a high-priority feature of Phase 8.

The AI agent must be able to determine which event the developer is currently inspecting in the RenderDoc GUI.

Suggested MCP tool:

`get_selected_event`

### 6.1 Requirements

Retrieve, where supported:

- Currently selected event ID.
- Current replay event ID, if distinct.
- Selected event name.
- Selected event type.
- Associated capture identity.
- GUI session identifier.

RenderDoc may distinguish the selected event from the event currently being replayed or displayed.

Investigate the actual API semantics and preserve this distinction.

Do not assume the two IDs are always identical.

### 6.2 Selection Behavior

Example workflow:

1. A developer loads a capture.
2. The developer selects DrawCall 450.
3. The agent calls `get_selected_event`.
4. RenderEyeMCP returns DrawCall 450.
5. The developer selects DrawCall 625.
6. The next query returns DrawCall 625.

This must work without any agent-initiated selection command.

### 6.3 No GUI Selection Available

If no event is selected, return an explicit result.

If selection state is not exposed by the installed RenderDoc API, investigate supported alternatives and document the limitation.

Do not infer selected events from the last event inspected by an MCP client.

### 6.4 Read-Only Operation

The tool must not change the selected event.

Do not automatically navigate to another draw call.

Event selection manipulation is outside the scope of Phase 8.

---

## 7. Graphics Pipeline State Inspection

Implement retrieval of the graphics pipeline state for a specific event.

Suggested MCP tool:

`get_pipeline_state`

The tool should support:

- An explicit event ID.
- The currently selected GUI event.

An omitted event ID may use the currently selected event if its identity can be resolved unambiguously.

### 7.1 Pipeline Stages

For supported graphics APIs, retrieve the relevant pipeline state.

Potential categories include:

**Input Assembly**

- Primitive topology.
- Vertex buffers.
- Index buffer.
- Input attributes.
- Input layouts.

**Shaders**

- Vertex shader.
- Hull/tessellation control shader.
- Domain/tessellation evaluation shader.
- Geometry shader.
- Pixel/fragment shader.
- Other applicable graphics shader stages.

**Rasterizer**

- Cull mode.
- Fill mode.
- Front-face configuration.
- Depth bias.
- Viewports.
- Scissors.

**Depth and Stencil**

- Depth testing.
- Depth write state.
- Depth comparison function.
- Stencil testing and operations.

**Output Merger / Framebuffer**

- Render targets.
- Depth/stencil target.
- Blend configuration.
- Color write masks.
- Multisampling state where available.

**Resource Bindings**

- Constant/uniform buffers.
- Shader resource views.
- Textures.
- Samplers.
- Unordered access/storage resources.
- Descriptor bindings where applicable.

These categories are conceptual.

Use RenderDoc's API-independent pipeline abstractions where available, and do not force D3D-specific terminology onto Vulkan or OpenGL.

### 7.2 Efficient Responses

Pipeline state can be very large.

Do not return the entire pipeline state indiscriminately for every request.

Support inspection by section, such as:

- `summary`
- `input_assembly`
- `shaders`
- `rasterizer`
- `depth_stencil`
- `output_merger`
- `resources`

The default response should be a compact summary.

Allow targeted detailed queries for individual sections.

Follow existing tool conventions for naming and parameter formats.

### 7.3 State Correctness

A pipeline state belongs to a specific replay event.

Ensure the returned pipeline state actually corresponds to the requested event.

Do not assume that the current replay controller state matches an explicitly requested event ID.

Investigate whether RenderDoc can query an arbitrary event's pipeline state without changing the GUI's current replay position.

**If an explicit event inspection requires changing the GUI replay position, do not silently perform that operation.**

Prefer read-only access to the currently selected event.

For unsupported arbitrary-event inspection, report the limitation clearly.

Do not implement a temporary GUI selection change followed by restoration without explicit authorization and robust guarantees.

### 7.4 Shader Information

Return available shader information such as:

- Shader stage.
- Shader resource identifier.
- Entry point.
- Shader name or debug name.
- Bound resource counts.
- Shader reflection summary.

Do not automatically dump full shader bytecode, disassembly, or source code.

Detailed shader inspection can be provided through existing tools or a separate future phase.

---

## 8. Compute Pipeline Inspection

Extend pipeline inspection to compute dispatches.

For a selected compute event, retrieve available information such as:

- Compute shader identity.
- Dispatch group dimensions.
- Bound constant/uniform buffers.
- Shader resource bindings.
- UAV/storage resource bindings.
- Samplers.
- Relevant pipeline configuration.

Do not force compute events into a graphics pipeline representation.

Return an appropriate pipeline type:

```json
{
  "event_id": 625,
  "pipeline_type": "compute",
  "dispatch": {
    "groups_x": 32,
    "groups_y": 18,
    "groups_z": 1
  }
}
```

This is an illustrative schema.

Unsupported shader or resource information should remain explicitly unavailable.

---

## 9. Resource References

Pipeline inspection should expose resource references in a form that can be inspected later.

Useful information includes:

- RenderDoc resource identifier.
- Resource name.
- Resource type.
- Relevant format.
- Dimensions when available.
- Binding location.
- Shader stage.
- Access classification, when reliably available.

Do not copy entire texture contents, buffers, or binary data into MCP responses.

### 9.1 Resource Identity

Resource identifiers must be treated as capture-scoped.

A resource ID from Capture A must not be reused against Capture B.

Validate resource requests against the active capture identity.

### 9.2 Resource Inspection Scope

For this phase, focus on:

- Listing resources referenced by pipeline state.
- Basic resource metadata.
- Binding information.

Full texture extraction, buffer decoding, mesh visualization, and resource-content analysis are outside the core scope of Phase 8.

Reuse existing inspection tools if these capabilities already exist.

---

## 10. Shared IPC Integration

Expose capture inspection through the Phase 6 Shared IPC Service.

The RenderDoc extension is responsible for interacting safely with the RenderDoc GUI and its replay APIs.

The Shared IPC Service should:

1. Route requests to the correct GUI session.
2. Validate session availability.
3. Preserve capture identity.
4. Forward inspection requests.
5. Return structured results.
6. Handle timeouts and disconnections.
7. Support concurrent MCP clients.

### 10.1 Avoid Duplicated Replay State

Do not create a separate replay controller for each AI agent.

Do not independently load the capture in each MCP process.

All agents should be able to inspect the same existing GUI capture through the shared architecture.

### 10.2 Concurrency

Multiple agents may issue requests simultaneously.

Examples:

- Agent A requests capture metadata.
- Agent B requests the selected event.
- Agent A requests pipeline state.
- The developer changes the selected event.

Ensure requests do not corrupt shared state or interfere with the RenderDoc GUI.

Use request-local snapshots and explicit capture/event identity where necessary.

If replay APIs require serialized access, perform serialization at the appropriate shared execution boundary.

Do not hold IPC locks while waiting on replay-thread operations.

### 10.3 Timeouts and Cancellation

Inspection requests must not hang indefinitely when:

- The GUI closes.
- A capture unloads.
- Replay initialization is incomplete.
- The IPC connection is interrupted.

Use bounded waits and meaningful error responses.

Do not attempt unsafe cancellation of RenderDoc replay operations.

---

## 11. State Consistency and Race Conditions

This phase must account for the fact that the developer can interact with the GUI while an agent is inspecting it.

### 11.1 Capture Changes

Example:

1. Agent requests pipeline information from Capture A.
2. Developer loads Capture B.
3. Capture A becomes invalid.
4. The inspection request must not return data mislabeled as Capture B.

Associate results with the capture identity used during inspection.

If the capture changes and the result cannot be validated, return an appropriate stale-state or capture-changed result.

### 11.2 Event Selection Changes

Example:

1. Agent queries the currently selected event.
2. Developer changes the selection.
3. Agent requests pipeline state.

The two requests may refer to different events.

Support an explicit event ID to preserve the intended inspection target.

Where reliable arbitrary-event inspection is unavailable, report that the selection has changed rather than silently inspecting another event.

### 11.3 Inspection Result Identity

Detailed inspection responses should include enough context to identify:

- GUI session.
- Capture.
- Event ID.
- Relevant state generation, if available.

Do not combine information from incompatible capture or event snapshots.

---

## 12. MCP Response Design

Optimize the returned information for coding agents.

Responses should be:

- Structured.
- Compact by default.
- Deterministic where practical.
- Easy to interpret.
- Explicit about missing information.
- Consistent across supported graphics APIs.

Prefer JSON-compatible structured data.

Avoid sending large RenderDoc internal objects directly through IPC.

### 12.1 Bounded Output

Add appropriate limits for:

- Event enumeration.
- Resource lists.
- Shader binding lists.
- Pipeline sections.

Use pagination, filtering, or targeted queries.

Do not introduce arbitrary truncation without indicating that the response is incomplete.

### 12.2 Errors

Distinguish:

- No RenderDoc GUI connected.
- No capture loaded.
- Capture is loading.
- Multiple candidate GUI sessions.
- Invalid event ID.
- Event no longer valid.
- Selected event unavailable.
- Unsupported pipeline type.
- Replay state unavailable.
- Capture changed during inspection.
- RenderDoc API limitation.
- IPC timeout or disconnection.

Normal absence of a capture or event should not be represented as an unexpected internal exception.

---

## 13. Suggested MCP Tool Surface

Use these names only if suitable functionality does not already exist.

| Tool | Purpose |
|---|---|
| `get_current_capture_info` | Get metadata of the loaded capture |
| `list_capture_events` | Enumerate draw calls, dispatches, and other events |
| `get_capture_event` | Inspect an individual event |
| `get_selected_event` | Get the event selected in RenderDoc GUI |
| `get_pipeline_state` | Inspect graphics or compute pipeline state |
| `get_pipeline_resources` | Inspect resources bound to an event's pipeline |

Avoid an unnecessarily large number of tools.

If an existing tool already provides equivalent functionality, extend it to support active GUI capture resolution.

Where appropriate, make session IDs optional using the resolution rules described earlier.

Ensure all existing MCP tools remain backward-compatible.

---

## 14. Testing

Add unit tests and integration tests where practical.

### 14.1 Unit Tests

Cover:

- Active session resolution.
- Capture identity validation.
- Event ID validation.
- Event hierarchy representation.
- Pagination.
- Pipeline section filtering.
- Selection state handling.
- Capture changes during inspection.
- Concurrent inspection requests.
- IPC error propagation.
- Result serialization.
- Unsupported API handling.

### 14.2 Integration Tests

Verify:

1. Capture metadata is available through the GUI extension.
2. Event enumeration matches the loaded capture.
3. Explicit event lookup returns the intended event.
4. GUI-selected event retrieval works.
5. Graphics pipeline state is correctly associated with its event.
6. Compute pipeline state is correctly associated with its dispatch.
7. Resource references belong to the correct capture.
8. Two MCP clients can inspect the same GUI session.
9. Capture unload is handled safely.
10. IPC disconnection does not cause indefinite blocking.

### 14.3 Manual Validation

Test with a real RenderDoc GUI and a representative capture.

| Test | Expected result |
|---|---|
| Open D3D11 capture | Capture information available |
| Open D3D12 capture | Capture information available |
| Open Vulkan capture | Capture information available |
| Select graphics draw | Correct event information |
| Change selected draw | Updated selected event |
| Inspect graphics pipeline | Correct state for selected draw |
| Select compute dispatch | Correct compute information |
| Inspect resource bindings | Correct resource identifiers |
| Close capture during query | Graceful failure or validated result |
| Open different capture | Old event IDs not silently reused |
| Query using two agents | Consistent inspection results |
| Query without loaded capture | Explicit no-capture result |

Run tests only for graphics APIs available in the development environment.

Document unavailable or untested APIs.

Do not claim full cross-API compatibility without validation.

### 14.4 GUI Non-Interference Test

Record the GUI's current selected event and replay event before read-only inspection.

Perform supported Phase 8 inspection operations.

Verify that the operation does not unexpectedly modify:

- Selected event.
- Replay event.
- Loaded capture.
- GUI session.
- Relevant visible GUI state.

This test is particularly important for explicit event pipeline queries.

---

## 15. Documentation

Update the relevant README and technical documentation.

Include:

- Active capture inspection overview.
- Requirements for a connected RenderDoc GUI.
- Supported inspection tools.
- Active session resolution rules.
- Event selection behavior.
- Pipeline-state inspection examples.
- Resource identifier scope.
- Supported graphics APIs.
- Limitations of read-only replay inspection.
- Multi-agent behavior.

### Example Workflow A — Capture Information

```text
Developer:
"What capture is currently open in RenderDoc?"

Agent:
Calls get_current_capture_info.

RenderEyeMCP:
Returns metadata for the loaded capture.
```

### Example Workflow B — Selected Draw Call

```text
Developer:
"Inspect the draw call currently selected in RenderDoc."

Agent:
Calls get_selected_event.

Agent:
Calls get_capture_event for the selected event.

RenderEyeMCP:
Returns the selected draw's properties.
```

### Example Workflow C — Pipeline State

```text
Developer:
"Check the depth test and blend state of the
currently selected draw call."

Agent:
Resolves the selected event.

Agent:
Requests the depth_stencil and output_merger
pipeline sections for that event.

RenderEyeMCP:
Returns the relevant pipeline state.
```

### Example Workflow D — Compute Dispatch

```text
Developer:
"Inspect the compute dispatch selected in RenderDoc."

Agent:
Resolves the selected dispatch event.

Agent:
Requests compute pipeline state.

RenderEyeMCP:
Returns dispatch dimensions, shader information,
and available resource bindings.
```

---

## 16. Out of Scope

Do not implement the following in Phase 8:

- Opening captures automatically.
- Closing or replacing captures.
- Changing GUI event selection.
- Changing replay position as an implicit side effect.
- GPU pixel history analysis.
- Shader debugging.
- Texture image extraction.
- Full buffer content extraction.
- Mesh visualization.
- GPU performance profiling.
- Automated rendering issue diagnosis.
- Automated shader modifications.
- GUI window focus management.
- Major IPC redesign.
- General-purpose replay scripting.

These may be considered for later phases.

Phase 8 should establish a reliable read-only inspection foundation first.

---

## 17. Implementation Principles

**Use the existing GUI replay context.**

Avoid loading the same capture through a separate replay instance.

**Respect RenderDoc thread ownership.**

Use supported GUI/replay execution mechanisms.

**Do not disturb developer interaction.**

Read-only inspection must not unexpectedly change what the developer is viewing.

**Prioritize the selected event.**

The developer's GUI selection is an important context signal.

**Maintain capture identity.**

Never mix events, resources, or pipeline state from different captures.

**Reuse existing MCP tools.**

Avoid unnecessary API surface expansion.

**Keep results bounded.**

Large captures must remain practical for LLM-based analysis.

**Preserve Phase 6 and Phase 7 behavior.**

Multi-agent IPC and GUI state synchronization must continue functioning.

**Report limitations explicitly.**

Do not invent capabilities unsupported by RenderDoc.

---

## 18. Deliverables

Provide the following after implementation:

### Implementation Summary

- Modified components.
- New or extended MCP tools.
- Capture resolution strategy.
- Event enumeration approach.
- Pipeline inspection implementation.
- GUI selection integration.

### RenderDoc API Findings

- APIs used for capture metadata.
- APIs used for event enumeration.
- APIs used for selected-event retrieval.
- APIs used for pipeline state.
- Threading and replay restrictions.
- Unsupported or version-dependent functionality.

### Test Report

- Automated tests executed.
- Real RenderDoc GUI tests executed.
- Tested graphics APIs.
- Multi-agent test results.
- Known failures or limitations.

### Documentation

- Updated README.
- Updated tool documentation.
- Usage examples.
- Known limitations.

---

## 19. Acceptance Criteria

Phase 8 is complete when:

- [ ] Agents can retrieve information about an already-loaded capture.
- [ ] No MCP-initiated capture-open operation is required.
- [ ] Capture metadata comes from the actual RenderDoc session.
- [ ] Draw calls and relevant events can be enumerated.
- [ ] Individual events can be inspected by event ID.
- [ ] The currently selected GUI event can be identified when supported by RenderDoc.
- [ ] Selection and replay event semantics are handled correctly.
- [ ] Graphics pipeline state can be inspected for supported events.
- [ ] Compute pipeline state can be inspected for supported dispatches.
- [ ] Bound resources can be identified without extracting their full contents.
- [ ] Inspection results include sufficient capture and event identity.
- [ ] Large result sets are bounded and navigable.
- [ ] Read-only inspection does not unexpectedly change GUI selection or replay state.
- [ ] Capture changes during inspection are handled safely.
- [ ] Multiple MCP clients can inspect the same GUI.
- [ ] Existing Phase 6 and Phase 7 behavior remains functional.
- [ ] Automated tests cover the core inspection functionality.
- [ ] Real GUI validation is performed for available graphics APIs.
- [ ] Documentation and known limitations are updated.

If specific RenderDoc API limitations prevent individual criteria from being implemented, document those limitations and report the affected criteria as incomplete rather than silently substituting behavior.

---

## Final Goal

After Phase 8, a developer should be able to debug rendering issues using the following natural workflow:

1. Capture a frame from a game engine.
2. Open the frame in RenderDoc.
3. Select a suspicious draw call or dispatch.
4. Ask an AI coding agent to inspect it.

For example:

**"Look at the draw call I've selected in RenderDoc. Check its shaders, depth state, render targets, and bound resources."**

The agent should obtain the relevant information through RenderEyeMCP without reopening the capture, changing the GUI selection, or taking control of the developer's RenderDoc session.

The implementation should make the existing RenderDoc GUI a reliable, read-only source of rendering context for AI-assisted debugging.
