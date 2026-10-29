# Phase 15 — Pixel History & Shader Debugging

## Objective

Extend RenderEyeMCP with advanced GPU debugging capabilities using RenderDoc's Pixel History and Shader Debugging APIs.

Phase 15 builds on the existing implementation:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 7 — Active RenderDoc GUI and capture discovery.
- Phase 8 — Draw call, event, and pipeline inspection.
- Phase 9 — GPU resource and buffer inspection.
- Phase 10 — Shader reflection and disassembly.
- Phase 11 — Render target, texture, and pixel inspection.
- Phase 12 — Release preparation and bilingual documentation.
- Phase 13 — GPU performance analysis.
- Phase 13.1 — End-to-end performance validation.
- Phase 14 — Geometry and mesh inspection.

The objective is to enable coding agents to investigate rendering problems that cannot be explained through static pipeline and resource inspection alone.

Typical questions include:

- "Why is this pixel black?"
- "Which draw call last modified this pixel?"
- "Why did this fragment fail the depth test?"
- "Which shader instruction produced the incorrect value?"
- "What values did the pixel shader variables contain?"
- "Why did the vertex shader produce an invalid position?"
- "Where does this compute shader produce NaN?"
- "Which fragment wrote the final color to this render target?"

**The primary goal is to expose reliable GPU execution evidence through structured, bounded MCP tools without replacing RenderDoc's existing shader debugger UI.**

Prioritize Pixel History, targeted Shader Debug Trace collection, and variable inspection.

Avoid implementing a general-purpose interactive debugger framework.

---

## 1. Initial Repository Investigation

Before modifying the repository, inspect the existing implementation.

Identify:

1. RenderDoc extension implementation.
2. ReplayController access and ownership.
3. Replay-thread scheduling.
4. Shared IPC Service.
5. Capture and session identity management.
6. Event and pipeline inspection.
7. Shader reflection and disassembly.
8. Texture and pixel inspection.
9. Geometry and vertex inspection.
10. GPU measurement lifecycle and replay coordination.
11. Existing debugging APIs, if any.
12. MCP request and response conventions.
13. Existing tests and documentation.

Determine whether any Pixel History or Shader Debugging functionality already exists.

Reuse existing infrastructure instead of introducing independent implementations.

### 1.1 Verify Dependencies

Confirm that RenderEyeMCP can:

- Identify the loaded capture.
- Resolve the selected event.
- Identify a render target or texture resource.
- Retrieve pixel values.
- Inspect shader metadata.
- Retrieve shader reflection.
- Access shader source/disassembly where available.
- Inspect vertex input data.
- Execute replay-dependent operations safely.

Do not duplicate these capabilities.

### 1.2 Establish Actual Supported Features

Review the installed RenderDoc version.

Determine which debugging operations are supported for each relevant graphics API and shader stage.

Do not assume that support is identical across D3D11, D3D12, Vulkan, and OpenGL.

Do not assume all shaders can be debugged even when their graphics API is generally supported.

---

## 2. Investigate RenderDoc Debugging APIs

Investigate the actual RenderDoc ReplayController APIs.

Relevant API concepts may include:

- `PixelHistory`
- `PixelModification`
- `PixelValue`
- `DebugPixel`
- `DebugVertex`
- `DebugThread`
- `DebugMeshThread`
- `DebugPixelInputs`
- `ShaderDebugTrace`
- `ShaderDebugState`
- `ShaderVariable`
- `ContinueDebug`
- `FreeTrace`
- `ShaderReflection`
- `ShaderDebugInfo`

These names are investigation targets.

Verify actual signatures, data structures, ownership requirements, and capabilities using the installed RenderDoc API definitions.

### 2.1 Pixel History

Investigate:

- How modification events are returned.
- How fragments within an event are represented.
- How previous and resulting pixel values are exposed.
- How depth and stencil tests are reported.
- Whether discarded fragments are represented.
- How multisampled textures are handled.
- How subresources are selected.
- Whether the operation performs additional replay work.

### 2.2 Shader Debugging

Investigate:

- How a debugging trace is created.
- How instructions are executed or recorded.
- How variable changes are represented.
- How traces are advanced.
- How source locations are associated with instructions.
- How traces must be released.
- Which shader stages are supported.
- How unsupported instructions are handled.

Do not assume that `DebugPixel()` or `DebugVertex()` returns a fully materialized instruction trace.

Inspect how the installed API uses the returned debugger and `ContinueDebug()`.

### 2.3 Official References

Consult the installed RenderDoc API headers and relevant upstream documentation.

Useful references include:

- https://github.com/baldurk/renderdoc/blob/v1.x/renderdoc/api/replay/renderdoc_replay.h
- https://github.com/baldurk/renderdoc/blob/v1.x/docs/how/how_inspect_pixel.rst
- https://github.com/baldurk/renderdoc/blob/v1.x/docs/how/how_debug_shader.rst
- https://github.com/baldurk/renderdoc/blob/v1.x/docs/python_api/renderdoc/analysis.rst

Use the installed version as the authoritative source.

Do not blindly implement APIs from a newer or older version.

### 2.4 Record API Findings

Document:

- Supported operations.
- Supported shader stages.
- Supported graphics APIs.
- Trace data availability.
- Replay requirements.
- Thread ownership.
- Resource cleanup requirements.
- Known limitations.

---

## 3. Debugging Architecture

Separate debugging execution from debugging result inspection.

### 3.1 Debugging Execution Layer

Responsible for:

- Starting Pixel History collection.
- Starting a Shader Debug Trace.
- Executing replay-dependent operations.
- Collecting trace states.
- Releasing RenderDoc debugger resources.
- Handling failures.
- Preserving capture and event identity.

### 3.2 Debugging Result Layer

Responsible for:

- Storing bounded debugging results.
- Enumerating pixel modifications.
- Retrieving trace steps.
- Inspecting variable values.
- Searching traces.
- Providing summary information.

The result layer should not need to repeat replay operations for every query.

### 3.3 Intended Workflow

```text
Active RenderDoc Capture
          |
          v
Select Event / Pixel / Shader Invocation
          |
          v
Explicit Debug Operation
          |
          +---- Pixel History
          |
          +---- Pixel Shader Trace
          |
          +---- Vertex Shader Trace
          |
          +---- Compute Shader Trace
          |
          v
Bounded Debug Result
          |
          +---- Inspect Events
          +---- Inspect Instructions
          +---- Inspect Variables
          +---- Search Changes
          +---- Generate Analysis
```

Do not add a second independent replay controller merely to implement the result layer.

---

## 4. Debugging Context and Identity

Every debugging result must preserve its original context.

### 4.1 Required Context

Associate results with:

- GUI session.
- Capture identity.
- Event ID.
- Shader stage.
- Shader identity.
- Debug operation ID.
- Relevant invocation coordinates or indices.

For Pixel History, additionally preserve:

- Texture resource ID.
- X/Y coordinates.
- Mip level.
- Array slice.
- Sample index.
- Component interpretation.

### 4.2 Capture Changes

If a different capture is loaded while debugging is running:

- Do not continue using invalid replay resources.
- Do not associate the old trace with the new capture.
- Safely terminate or invalidate the active operation as appropriate.

Completed trace data may remain available as historical results if it is self-contained and explicitly identified.

### 4.3 Event Changes

Do not silently switch the debugging target when the user changes the selected event.

Explicit event IDs must remain associated with the original request.

### 4.4 Debug Operation Identity

Use unique IDs for debugging operations.

Do not rely on mutable global state such as:

- Last debugged pixel.
- Last debugged shader.
- Last selected event.

This is especially important for multi-agent access.

---

## 5. Pixel History Inspection

Implement retrieval of Pixel History for a selected texture coordinate.

Suggested MCP tool:

`get_pixel_history`

Reuse existing tools if equivalent functionality is already implemented.

This is a core Phase 15 feature.

### 5.1 Required Parameters

Support:

- Texture resource ID.
- X coordinate.
- Y coordinate.
- Mip level.
- Array slice.
- Sample index where supported.
- Component interpretation.
- Optional GUI session identifier.

Use Phase 11 texture and coordinate validation.

### 5.2 Pixel Modification Events

Retrieve available information for each modification.

Potential information includes:

- Event ID.
- Event name.
- Primitive ID.
- Fragment identity.
- Fragment ordering information.
- Previous pixel value.
- Shader output value.
- Resulting pixel value.
- Depth-related values.
- Stencil-related values.
- Relevant test results.

Only return fields supported by the actual RenderDoc API.

### 5.3 Event Ordering

Preserve the ordering returned by RenderDoc.

Do not reorder modifications based solely on event IDs when the API provides more precise ordering.

Multiple fragments may affect the same pixel within one draw call.

Preserve their distinction.

### 5.4 Pixel Modification Classification

Where reliably available, distinguish:

- Fragments that modified the pixel.
- Fragments rejected by depth testing.
- Fragments rejected by stencil testing.
- Fragments discarded by the shader.
- Fragments affected by scissor or coverage tests.
- Blended output.
- Uncertain or unobservable modifications.

Do not infer an exact rejection reason solely from unchanged output color.

A fragment may pass relevant tests yet produce an unchanged value.

### 5.5 Previous and Resulting Values

Preserve the distinction between:

- Previous stored pixel value.
- Shader output value.
- Final stored pixel value after applicable operations.

These values may differ because of blending, write masks, or other pipeline behavior.

Do not label a shader output as the final render target value.

### 5.6 Example Response

Illustrative response:

```json
{
  "resource_id": "resource-201",
  "coordinate": {
    "x": 640,
    "y": 360
  },
  "modifications": [
    {
      "event_id": 450,
      "primitive_id": 12,
      "passed": true,
      "shader_output": [1.0, 0.0, 0.0, 1.0],
      "result": [1.0, 0.0, 0.0, 1.0]
    },
    {
      "event_id": 580,
      "primitive_id": 3,
      "passed": false,
      "failure_reason": "depth_test"
    }
  ]
}
```

This is conceptual.

Use actual RenderDoc data and established project schemas.

### 5.7 Bounded Results

Pixel History may contain many events and fragments.

Support:

- Maximum returned modifications.
- Pagination where practical.
- Event ID filtering.
- Relevant test-result filtering.
- Compact summaries.

Do not return an unbounded history by default.

### 5.8 Partial History Semantics

Investigate whether Pixel History is scoped to the current replay event.

Clearly report the range actually inspected.

Do not describe a partial history as the complete history of a frame.

### 5.9 Unsupported Pixel History

If the graphics API or texture configuration does not support Pixel History, return an explicit unsupported result.

Do not attempt to reconstruct exact fragment history from final texture values.

---

## 6. Pixel History Analysis

Provide useful, deterministic summaries based on collected Pixel History.

Prefer extending the existing history tool with a summary option rather than adding many specialized tools.

### 6.1 Useful Summaries

Where supported, summarize:

- Number of modifying events.
- Number of relevant fragments.
- Number of passed fragments.
- Number of rejected fragments.
- Last known modifying event.
- Available rejection reasons.
- Final observed value.
- Relevant uncertainty.

### 6.2 Root-Cause Investigation

Enable coding agents to answer questions such as:

"Why was this pixel not written by the selected draw?"

The agent should:

1. Retrieve Pixel History.
2. Identify the relevant event.
3. Inspect test results.
4. Retrieve the event's pipeline state.
5. Inspect depth/stencil configuration.
6. Report the actual observations.

Do not hardcode root-cause conclusions into RenderEyeMCP.

### 6.3 Missing Pixel Modifications

An empty history does not necessarily prove that no geometry covered the pixel.

Consider API limitations, selection scope, unsupported operations, and resource usage.

Return appropriate context.

---

## 7. Shader Debug Trace Management

Implement an internal lifecycle for shader debugging operations.

### 7.1 Trace Creation

A trace is created through a supported RenderDoc debugging operation.

Assign a RenderEyeMCP debug operation ID.

Associate it with the originating capture, event, shader, and invocation.

### 7.2 Trace Continuation

Investigate how the installed RenderDoc API advances debugging.

Use supported mechanisms such as `ContinueDebug()`.

Do not assume one call produces the entire trace.

### 7.3 Trace Collection Policy

Prefer collecting a bounded trace into an independently inspectable snapshot.

Do not retain live debugger objects indefinitely.

If incremental execution is necessary, ensure that debugger lifetime, ownership, expiration, and cleanup are explicitly managed.

### 7.4 Trace Resource Ownership

Verify the RenderDoc API's ownership requirements.

Release traces and debugger objects through the documented cleanup API.

Do not free RenderDoc-managed resources from the wrong thread.

### 7.5 Debugging Limits

Enforce limits on:

- Maximum instructions processed.
- Maximum retained trace states.
- Maximum trace size.
- Maximum debugger lifetime.
- Maximum concurrent debug operations.
- Total memory usage.

Do not allow unbounded instruction stepping.

### 7.6 Operation Status

Expose operation states where necessary:

- Pending.
- Running.
- Completed.
- Failed.
- Cancelled.
- Truncated.

Reuse Phase 13 job infrastructure when appropriate.

Do not create a separate general-purpose task scheduler without a concrete need.

---

## 8. Pixel Shader Debugging

Implement debugging of a selected pixel shader invocation.

Suggested MCP tool:

`debug_pixel_shader`

### 8.1 Required Context

Support:

- Event ID.
- Pixel X/Y coordinates.
- Sample index where supported.
- Primitive or fragment selection where supported.
- View index where relevant.
- Optional session identifier.

Use the actual `DebugPixelInputs` model supported by the installed RenderDoc version.

### 8.2 Fragment Selection

A single pixel may receive multiple fragments from the same draw call.

Do not assume a unique shader invocation exists for every pixel/event pair.

Where possible, use Pixel History to identify the relevant fragment or primitive.

### 8.3 Pixel History Integration

Support the workflow:

1. Retrieve Pixel History.
2. Identify a particular draw and fragment.
3. Resolve the necessary invocation parameters.
4. Start debugging the corresponding pixel shader invocation.
5. Retrieve trace information.

Do not claim exact fragment targeting unless RenderDoc supports the required selection semantics.

### 8.4 Shader Inputs

Retrieve available debugging inputs such as:

- Interpolated inputs.
- Relevant system values.
- Shader constants.
- Resource references.
- Invocation identifiers.

Do not invent missing interpolated values.

### 8.5 Expected Debugging Use Cases

Support investigations involving:

- Incorrect output colors.
- Unexpected conditional branches.
- Invalid texture coordinates.
- NaN propagation.
- Incorrect material parameters.
- Shader discards.
- Suspicious arithmetic operations.

Do not automatically execute shader instructions without an explicit debug request.

---

## 9. Vertex Shader Debugging

Implement targeted debugging of a vertex shader invocation.

Suggested MCP tool:

`debug_vertex_shader`

### 9.1 Required Parameters

Use the actual RenderDoc vertex debugging input semantics.

Potential inputs include:

- Event ID.
- Vertex invocation index.
- Instance index.
- Effective input index.
- View index.

Do not confuse index-buffer values with shader-visible vertex identifiers.

### 9.2 Phase 14 Integration

Reuse:

- Vertex input layout.
- Decoded vertex attributes.
- Index buffer information.
- Base vertex handling.
- Instancing information.
- Post-VS geometry.

### 9.3 Debugging Workflow

A developer asks:

"Why does this vertex end up outside the view frustum?"

The agent should:

1. Resolve the draw call.
2. Inspect the relevant vertex input.
3. Start vertex shader debugging.
4. Retrieve execution states.
5. Inspect transformation variables.
6. Identify the generated position.
7. Correlate the result with Phase 14 Post-VS output.

### 9.4 Coordinate Semantics

Clearly distinguish local, world, view, clip, and NDC coordinates.

Do not assume intermediate shader variables represent a particular coordinate space solely from their numeric values.

---

## 10. Compute Shader Debugging

Add compute shader debugging where supported.

Suggested MCP tool:

`debug_compute_shader`

Compute debugging is an advanced capability and must be treated as potentially limited or experimental.

### 10.1 Invocation Selection

Support:

- Event ID.
- Workgroup ID.
- Thread ID within the workgroup.
- Relevant view or dispatch context if required.

Validate requested indices against available dispatch information where possible.

### 10.2 Execution Trace

Retrieve available instruction and variable states for the selected invocation.

### 10.3 Synchronization Limitations

A compute thread may depend on:

- Other threads.
- Shared memory.
- Barriers.
- Atomics.
- Wave/subgroup operations.
- Inter-thread ordering.

Do not assume debugging one isolated thread reproduces all concurrent execution behavior.

Document the limitations of the installed RenderDoc implementation.

### 10.4 Unsupported Features

If the shader uses unsupported instructions or synchronization features, return a clear limitation.

Do not fabricate thread-local values.

### 10.5 Practical Scope

Prioritize simple compute shaders with deterministic inputs for initial validation.

Do not attempt to implement a full GPU parallel execution simulator.

---

## 11. Shader Trace Inspection

Provide bounded retrieval of captured shader execution states.

Suggested MCP tool:

`get_shader_debug_trace`

### 11.1 Trace Data

Expose available information such as:

- Debug operation ID.
- Shader stage.
- Event ID.
- Instruction index.
- Source location.
- Executed instruction.
- Variable changes.
- Register changes.
- Execution flags.
- Trace status.

Only include values supported by RenderDoc.

### 11.2 Compact Representation

Do not return the entire trace by default.

Support:

- Starting step.
- Maximum steps.
- Instruction range.
- Relevant variable filtering.
- Compact state changes.

### 11.3 Delta Representation

Where appropriate, return variable changes rather than repeating every variable at every instruction.

Reuse the actual change information provided by RenderDoc.

Do not incorrectly infer that a variable is unchanged merely because a value was not included in a partial response.

### 11.4 Initial State

Preserve the trace's initial variable and register state where available.

A sequence of deltas without a valid initial state may be insufficient to reconstruct values.

### 11.5 Example Response

```json
{
  "debug_id": "debug-001",
  "shader_stage": "pixel",
  "event_id": 450,
  "steps": [
    {
      "step": 0,
      "instruction": 12,
      "changes": [
        {
          "name": "r0",
          "value": [0.5, 0.2, 0.8, 1.0]
        }
      ]
    },
    {
      "step": 1,
      "instruction": 13,
      "changes": [
        {
          "name": "r1",
          "value": [0.25, 0.04, 0.64, 1.0]
        }
      ]
    }
  ],
  "has_more": true
}
```

This is illustrative.

Preserve the actual meaning of RenderDoc's debug states.

---

## 12. Shader Variable Inspection

Enable coding agents to inspect variables at selected execution steps.

Suggested MCP tool:

`get_shader_debug_variables`

### 12.1 Variable Categories

Where available, support:

- Shader inputs.
- Local variables.
- Temporary registers.
- Output variables.
- Constant values.
- Relevant system values.

### 12.2 Step-Specific Values

Allow querying variable values at a particular trace step.

If RenderDoc exposes only variable changes, reconstruct state carefully using the initial state and the ordered changes.

Do not invent values for variables that cannot be reconstructed.

### 12.3 Structured Values

Support:

- Scalars.
- Vectors.
- Matrices.
- Arrays.
- Structures.

Reuse existing Phase 9 and Phase 10 serialization conventions.

### 12.4 Variable Search

Support searching a trace for:

- Named variables.
- Register identifiers.
- NaN.
- Infinity.
- Selected numeric changes.
- Instruction locations.

Keep search bounded.

### 12.5 First Invalid Value

A useful debugging operation is identifying the first recorded step where a variable becomes NaN or infinity.

Implement this as a deterministic analysis over collected trace data when possible.

Do not assume an invalid value at one step proves that the corresponding instruction originally caused it unless the trace establishes that relationship.

---

## 13. Source and Disassembly Correlation

Integrate Phase 15 with Phase 10 shader source and disassembly inspection.

### 13.1 Instruction Mapping

Where available, associate trace steps with:

- Disassembly instruction.
- Source file.
- Source line.
- Source-level variable name.

### 13.2 Missing Debug Information

Shader source-level debugging may be unavailable when captures lack appropriate debug information.

Do not synthesize source mappings.

Continue to expose instruction-level debugging data where supported.

### 13.3 Multiple Source Instructions

Compiler optimizations may cause:

- Inlined functions.
- Reordered instructions.
- Removed variables.
- Combined operations.
- Multiple instructions associated with one source line.

Preserve RenderDoc's actual mappings.

Do not claim a one-to-one source/instruction relationship.

### 13.4 Agent Workflow

A developer asks:

"Find where this shader first produces NaN."

The agent should:

1. Obtain a targeted debug trace.
2. Search for invalid variable values.
3. Identify the earliest relevant recorded step.
4. Retrieve the corresponding instruction.
5. Resolve source information where available.
6. Report the evidence and any mapping uncertainty.

---

## 14. Pixel History and Shader Trace Correlation

This is an important Phase 15 integration feature.

The agent should be able to move naturally from an incorrect pixel value to the responsible shader execution.

### 14.1 Intended Workflow

```text
Incorrect Pixel
      |
      v
Pixel History
      |
      v
Relevant Modification / Fragment
      |
      v
Draw Call / Pipeline State
      |
      v
Pixel Shader Debug Trace
      |
      v
Instruction and Variable Inspection
      |
      v
Evidence-Based Explanation
```

### 14.2 Preserve Identity

Ensure the transition preserves:

- Capture.
- Event.
- Texture.
- Pixel coordinate.
- Sample.
- Primitive/fragment selection.
- Shader identity.

### 14.3 No Implicit Debugging

Pixel History retrieval must not automatically start shader debugging.

The agent should explicitly request a debug trace after identifying the relevant event or fragment.

### 14.4 Ambiguous Fragments

If several fragments may correspond to the requested pixel, expose the available candidates.

Do not silently choose the first fragment.

---

## 15. Replay Coordination and GUI Safety

Phase 15 contains operations that may perform additional replay work.

Treat these operations separately from ordinary read-only metadata queries.

### 15.1 Execution Ownership

Use the supported RenderDoc replay thread.

Do not invoke debugging APIs directly from arbitrary IPC threads.

### 15.2 Shared Replay Coordination

Coordinate debugging operations with:

- Phase 13 GPU counter collection.
- Phase 14 Post-VS extraction.
- Other replay-sensitive operations.

Prefer one active conflicting replay operation per affected GUI replay context.

### 15.3 GUI State

Do not unexpectedly change:

- Loaded capture.
- Selected event.
- Current GUI replay event.
- Developer-visible Shader Debugger state.
- Texture Viewer state.
- Mesh Viewer state.

### 15.4 Internal Replay Effects

Investigate whether RenderDoc debugging APIs internally replay events or restore replay state.

Do not assume that returning from an API guarantees complete GUI state preservation.

### 15.5 Non-Interference Testing

Measure actual GUI state before and after debugging.

If an operation cannot be performed without visible side effects, document the limitation.

Do not silently manipulate the GUI and attempt an unreliable restoration.

### 15.6 Cancellation and Failure

Do not interrupt RenderDoc replay internals unsafely.

Cancellation may stop future trace collection while permitting an in-progress API operation to finish safely.

Ensure debugger resources are released afterward.

---

## 16. Multi-Agent Support

Preserve Phase 6 Shared IPC compatibility.

### 16.1 Independent Operations

Each agent's debugging operation must have its own identity.

Example:

- Claude Code debugs a pixel shader.
- Codex requests Pixel History.
- Both target the same capture.

The Shared IPC Service must coordinate conflicting replay operations.

### 16.2 Shared Result Access

Completed, immutable debugging results may be shared across MCP clients where appropriate.

Do not share mutable live debugger handles directly between independent MCP processes.

### 16.3 Resource Ownership

Track:

- Which component owns the debugger.
- Which replay context created it.
- Whether it is still valid.
- When it must be destroyed.

### 16.4 Client Disconnection

If the requesting MCP client disconnects:

- Do not leak debugger resources.
- Do not leave replay operations blocked.
- Follow the defined job cancellation or completion policy.

### 16.5 Multiple Captures

Debugging operations against separate RenderDoc GUI sessions should not interfere unnecessarily.

Avoid a global debugging lock when per-session coordination is sufficient.

---

## 17. Performance and Resource Limits

Shader debugging can produce large traces.

### 17.1 Trace Limits

Enforce configurable or documented limits for:

- Maximum executed instruction steps.
- Maximum stored trace states.
- Maximum trace memory.
- Maximum response size.
- Maximum concurrent debug jobs.
- Maximum retained completed traces.

Use conservative defaults.

### 17.2 Pixel History Limits

Limit:

- Returned modifications.
- Returned fragments.
- Serialized per-fragment data.
- Total response size.

### 17.3 Lazy Inspection

Prefer:

1. Compact debugging summary.
2. Targeted trace range.
3. Selected variable inspection.
4. Detailed source/disassembly lookup.

Do not send every instruction and variable to the agent automatically.

### 17.4 GPU Work

Do not repeat expensive debugging operations for every trace query.

Reuse completed results where safe and practical.

### 17.5 Resource Cleanup

Ensure RenderDoc debugger resources are released after completion, failure, cancellation, and capture unload.

Avoid indefinite retention of active debugger objects.

---

## 18. MCP Tool Design

Prefer a compact tool interface.

Suggested capabilities:

| Tool | Purpose |
|---|---|
| `get_pixel_history` | Retrieve modifications affecting a selected pixel |
| `debug_pixel_shader` | Start a targeted pixel shader debug trace |
| `debug_vertex_shader` | Start a targeted vertex shader debug trace |
| `debug_compute_shader` | Start a supported compute shader debug trace |
| `get_shader_debug_trace` | Retrieve bounded trace steps |
| `get_shader_debug_variables` | Inspect variables at a particular step |
| `get_shader_debug_status` | Check operation status when execution is asynchronous |

Optional trace search may be integrated into `get_shader_debug_trace`.

Avoid creating individual MCP tools for every shader instruction, register, or variable type.

### 18.1 Tool Descriptions

Clearly state whether a tool:

- Performs replay work.
- Returns cached data.
- Requires an explicit event.
- Requires invocation parameters.
- Can be unavailable on some graphics APIs.
- Has resource or execution limits.

### 18.2 Tool Parameter Consistency

Reuse existing conventions for:

- Session ID.
- Capture identity.
- Event ID.
- Resource ID.
- Shader stage.
- Pixel coordinates.
- Vertex index.
- Instance index.
- Compute workgroup/thread IDs.
- Result limits.

### 18.3 Structured Errors

Distinguish:

- Unsupported graphics API.
- Unsupported shader stage.
- Unsupported shader instruction.
- Missing debug information.
- Ambiguous fragment.
- Invalid invocation.
- Replay unavailable.
- Debug initialization failure.
- Trace limit reached.
- Capture changed.
- Operation expired.
- IPC timeout.

Do not fabricate debugging results.

---

## 19. Testing

Implement automated and real RenderDoc integration tests.

### 19.1 Unit Tests

Cover:

- Pixel coordinate validation.
- Subresource selection.
- Pixel History serialization.
- Modification ordering.
- Fragment identification.
- Depth/stencil result handling.
- Debug operation identity.
- Shader trace serialization.
- Variable delta reconstruction.
- Trace pagination.
- NaN/infinity detection.
- Source mapping.
- Trace truncation.
- Result expiration.
- Resource cleanup.
- Error handling.

### 19.2 Deterministic Fixtures

Use synthetic debugging fixtures to verify:

- Multiple modifications to one pixel.
- Depth-rejected fragments.
- Passed fragments.
- Blended results.
- Variable changes across instructions.
- Branching execution paths.
- Invalid floating-point values.
- Partial traces.

Do not present synthetic results as real GPU debugging evidence.

### 19.3 Integration Tests

Verify:

1. Pixel History can be retrieved for a supported texture.
2. History events correspond to the correct capture.
3. Fragment information matches RenderDoc where available.
4. Pixel Shader Debugging works for a supported shader.
5. Vertex Shader Debugging works for a supported shader.
6. Compute debugging works where supported.
7. Trace states can be retrieved incrementally.
8. Variable values match RenderDoc's debugger.
9. Source mappings are correct when available.
10. Unsupported shaders fail gracefully.
11. Debugger resources are released correctly.
12. Capture changes invalidate live operations.
13. Multiple agents do not corrupt replay state.

### 19.4 Manual Scenario A — Incorrect Pixel Color

1. Open a capture containing a color rendering issue.
2. Identify the affected render target.
3. Select a pixel.
4. Retrieve Pixel History.
5. Identify the last relevant modification.
6. Start pixel shader debugging.
7. Inspect the output and preceding variable changes.
8. Compare findings against RenderDoc's Shader Debugger.

### 19.5 Manual Scenario B — Depth Test Failure

1. Select a pixel where an object is missing.
2. Retrieve Pixel History.
3. Locate relevant fragments.
4. Inspect depth/stencil results.
5. Inspect the draw call's depth state.
6. Explain the observed rejection behavior.

### 19.6 Manual Scenario C — Invalid Vertex Position

1. Select a draw call with suspicious geometry.
2. Identify a relevant vertex using Phase 14.
3. Retrieve vertex inputs.
4. Start vertex shader debugging.
5. Inspect transformation operations.
6. Compare the result with Post-VS geometry.

### 19.7 Manual Scenario D — Compute Shader NaN

1. Open a capture with a supported compute shader.
2. Select a dispatch.
3. Specify a workgroup and thread.
4. Start a debug trace.
5. Search for the first recorded invalid value.
6. Inspect relevant instructions.
7. Verify results against RenderDoc.

### 19.8 Manual Scenario E — Multi-Agent

1. Connect Claude Code and Codex.
2. Load a supported capture.
3. Have one agent retrieve Pixel History.
4. Have the other request a Shader Debug Trace.
5. Verify safe replay coordination.
6. Disconnect one agent during an operation.
7. Confirm resource cleanup and continued operation.

### 19.9 Regression Tests

Verify that Phase 6–14 functionality remains operational.

In particular:

- GPU counter collection.
- Post-VS geometry extraction.
- Active capture synchronization.
- Resource and shader inspection.
- Shared IPC concurrency.

Do not claim a test passed unless it was actually executed.

---

## 20. Bilingual Documentation

Update English and Japanese documentation.

Suggested files:

```text
docs/
  en/
    advanced-debugging.md
    examples/
      pixel-history.md
      shader-debugging.md
      depth-rejection.md
      vertex-debugging.md
      compute-debugging.md

  ja/
    advanced-debugging.md
    examples/
      pixel-history.md
      shader-debugging.md
      depth-rejection.md
      vertex-debugging.md
      compute-debugging.md
```

Adapt to the existing documentation structure.

### 20.1 Required Topics

Document:

- Pixel History.
- Pixel modification semantics.
- Depth/stencil rejection.
- Pixel shader debugging.
- Vertex shader debugging.
- Compute shader debugging.
- Instruction traces.
- Variable inspection.
- Source/disassembly mapping.
- Replay effects.
- Supported graphics APIs.
- Known debugging limitations.

### 20.2 Example — Pixel History

Developer prompt:

> Investigate pixel (640, 360) in the currently selected render target. Show which events modified it and identify any fragments rejected by depth or stencil testing.

### 20.3 Example — Pixel Shader Debugging

Developer prompt:

> Debug the pixel shader invocation responsible for this incorrect pixel color. Find where the output becomes incorrect and show the relevant variable changes.

### 20.4 Example — Vertex Shader Debugging

Developer prompt:

> Debug this vertex shader invocation and trace the position transformation. Check where the resulting clip-space position becomes invalid.

### 20.5 Example — Compute Shader Debugging

Developer prompt:

> Debug the selected compute shader thread and look for the first instruction that produces NaN or infinity.

### 20.6 Evidence and Limitations

Teach agents and users to distinguish:

- Recorded execution states.
- Derived observations.
- Suspected root causes.
- Unavailable debugging evidence.

Do not claim every shader is debuggable.

---

## 21. Out of Scope

Do not implement:

- A replacement for RenderDoc's interactive Shader Debugger UI.
- Full remote breakpoint management.
- Arbitrary interactive shader execution control.
- Shader source editing.
- Shader replacement.
- Shader recompilation.
- Automatic shader patching.
- GPU memory modification.
- Full GPU execution simulation.
- General-purpose thread scheduling simulation.
- CPU-side application debugging.
- Vendor-specific shader debugging tools.
- Automatic rendering bug repair.
- Major replay architecture redesign.
- Major Shared IPC Service redesign.

Keep Phase 15 focused on reliable Pixel History and Shader Debug Trace acquisition and inspection.

---

## 22. Implementation Principles

**Prefer RenderDoc's supported debugging APIs.**

Do not create a custom shader interpreter.

**Make expensive operations explicit.**

Ordinary metadata queries must not automatically trigger debugging replay.

**Preserve capture and event identity.**

Never combine debugging data from different captures or events.

**Distinguish fragments.**

Several fragments may affect the same pixel.

**Preserve trace semantics.**

Instruction states and variable changes must reflect actual RenderDoc data.

**Bound trace collection.**

Do not generate unlimited instruction histories.

**Manage debugger lifetime.**

Release debugger resources through supported APIs.

**Respect replay ownership.**

Coordinate debugging with performance measurement and Post-VS extraction.

**Avoid GUI interference.**

Do not unexpectedly alter developer-visible RenderDoc state.

**Maintain multi-agent compatibility.**

Concurrent agents must not corrupt replay or debugger state.

**Report unsupported behavior explicitly.**

Do not fabricate shader execution results.

---

## 23. Deliverables

Provide the following.

### A. Implementation Summary

- Modified components.
- Added or extended MCP tools.
- Pixel History implementation.
- Shader Debug Trace management.
- Variable inspection.
- Source/disassembly correlation.
- Replay coordination.
- Resource cleanup.

### B. RenderDoc API Findings

- Supported debugging APIs.
- Supported graphics APIs.
- Supported shader stages.
- Trace continuation semantics.
- Debugger ownership and cleanup.
- Known unsupported features.
- Replay side effects.

### C. Testing Report

- Unit tests executed.
- Integration tests executed.
- Manual RenderDoc GUI tests.
- Graphics APIs tested.
- Shader stages tested.
- Multi-agent tests.
- Known failures.
- Unverified scenarios.

### D. Documentation

- English advanced debugging documentation.
- Japanese advanced debugging documentation.
- Practical Pixel History examples.
- Shader debugging workflows.
- MCP tool reference updates.
- Known limitations.

---

## 24. Acceptance Criteria

Phase 15 is complete when:

- [ ] Pixel History can be retrieved for supported textures.
- [ ] History results preserve pixel, texture, event, and capture identity.
- [ ] Multiple modifications and fragments are represented correctly.
- [ ] Depth/stencil rejection information is exposed where supported.
- [ ] Pixel History output is bounded.
- [ ] Pixel shader debugging works for supported shaders.
- [ ] Vertex shader debugging works for supported shaders.
- [ ] Compute shader debugging works where supported.
- [ ] Debug traces can be collected safely.
- [ ] Trace steps can be inspected incrementally.
- [ ] Variable changes and values can be retrieved.
- [ ] Invalid numeric values can be identified.
- [ ] Source/disassembly locations can be correlated where available.
- [ ] Pixel History can be used to select a relevant shader debugging target where supported.
- [ ] Debug operation IDs preserve execution context.
- [ ] Debugger resources are released correctly.
- [ ] Trace sizes and memory usage are bounded.
- [ ] Capture changes invalidate live debugging operations safely.
- [ ] Replay-dependent operations are coordinated with Phase 13 and Phase 14.
- [ ] GUI state is preserved where supported, or side effects are explicitly documented.
- [ ] Multiple MCP clients can use advanced debugging safely.
- [ ] Unsupported APIs and shader features produce meaningful errors.
- [ ] Automated tests cover Pixel History and trace handling.
- [ ] Real RenderDoc captures validate supported debugging operations.
- [ ] Existing Phase 6–14 functionality remains operational.
- [ ] English and Japanese documentation are updated.
- [ ] Known limitations are clearly documented.

If RenderDoc cannot support a specific debugging capability, report it as unavailable or partially implemented.

Do not fabricate shader execution states or claim unsupported debugging functionality is complete.

---

## Final Goal

After Phase 15, a developer should be able to ask an AI coding agent:

**"This pixel is rendering incorrectly. Find the draw call responsible, inspect its pixel history, debug the shader invocation, and identify where the incorrect value originated."**

The agent should be able to:

1. Identify the active capture.
2. Identify the target texture and pixel.
3. Retrieve Pixel History.
4. Find relevant draw calls and fragments.
5. Inspect pipeline and shader state.
6. Start a targeted Shader Debug Trace where supported.
7. Inspect instruction execution and variable changes.
8. Correlate results with shader source or disassembly.
9. Report evidence and likely causes.

The developer should not need to manually export debugger traces, reopen the capture, or transfer data between separate tools.

**Phase 15 should establish a practical foundation for AI-assisted pixel-level and instruction-level GPU debugging while retaining RenderDoc as the authoritative debugging environment.**
