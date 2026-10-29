# Phase 10 — Shader Inspection & Reflection

## Objective

Extend RenderEyeMCP with comprehensive, read-only shader inspection capabilities for captures already loaded in the RenderDoc GUI.

Phase 10 builds on:

- Phase 6 — Shared IPC Service and multi-agent compatibility.
- Phase 7 — RenderDoc GUI state discovery and synchronization.
- Phase 8 — Active capture, event, and pipeline-state inspection.
- Phase 9 — GPU resource metadata, buffer inspection, and basic constant buffer decoding.

The goal is to enable AI coding agents to understand the shaders used by a draw call or compute dispatch, inspect their interfaces and resource requirements, examine constant buffer layouts and values, and retrieve available shader disassembly or source-level debugging information.

The implementation must work with the existing RenderDoc GUI capture without requiring the agent to reopen the capture or create an independent replay session.

**Prioritize shader reflection and resource correlation over complex shader debugging functionality.**

Shader execution tracing, breakpoint control, and instruction-by-instruction debugging are reserved for a later phase.

---

## 1. Investigate the Existing Implementation

Before making changes, inspect the repository and identify:

1. RenderDoc extension implementation and supported APIs.
2. Existing replay-controller integration.
3. Phase 6 Shared IPC Service.
4. Phase 7 capture and session identity management.
5. Phase 8 pipeline-state inspection.
6. Phase 9 resource and buffer inspection.
7. Existing shader inspection or reflection functionality.
8. Existing constant buffer decoding logic.
9. Existing event and resource identifier representations.
10. Existing MCP tool schemas, tests, and documentation.

Determine which capabilities are already available.

Do not create duplicate shader metadata, binding, or reflection implementations.

Extend existing abstractions where practical.

### 1.1 Phase 8 Integration

Confirm how Phase 8 identifies shaders bound to a selected event.

The existing pipeline inspection functionality should provide the starting point for shader inspection.

Phase 10 should support:

- Currently selected GUI event.
- Explicit event ID.
- Explicit shader stage.
- Explicit shader resource identifier, where appropriate.

Use the existing capture and event resolution mechanisms.

### 1.2 Phase 9 Integration

Inspect how Phase 9 handles:

- Constant buffer metadata.
- Raw buffer reads.
- Structured buffer decoding.
- Resource IDs.
- Binding offsets and ranges.
- Existing reflection-derived values.

Phase 10 must enhance these capabilities rather than replace them.

In particular, shader reflection should provide layouts that can be reused by Phase 9 buffer inspection.

---

## 2. Investigate RenderDoc Shader APIs

Investigate the actual RenderDoc APIs available in the installed version.

Relevant API concepts may include:

- `ReplayController`
- `PipeState`
- `ShaderReflection`
- `ShaderResource`
- `ShaderConstant`
- `ShaderVariable`
- `ShaderBindpointMapping`
- `ShaderDebugInfo`
- Shader disassembly APIs
- Shader source/debug information APIs

These names are investigation targets, not assumptions about available methods or structures.

Inspect the real API signatures and data models before implementing functionality.

### 2.1 Required API Investigation

Determine how to retrieve:

- Bound shader identifiers.
- Shader stages.
- Shader entry points.
- Shader reflection.
- Input and output signatures.
- Resource binding declarations.
- Constant buffer declarations.
- Constant buffer variable layouts.
- Shader debug names.
- Shader disassembly.
- Available source-level debug information.

Also investigate whether the APIs expose:

- Shader model or version.
- Original shader encoding or intermediate representation.
- Compilation-related metadata.
- Shader source file names.
- Source locations.
- Supported disassembly targets.

Only expose fields supported by reliable API data.

### 2.2 Graphics API Compatibility

Investigate differences between:

- D3D11.
- D3D12.
- Vulkan.
- OpenGL.
- Other APIs supported by the existing project.

Relevant shader representations may include:

- DXBC.
- DXIL.
- SPIR-V.
- GLSL-related representations.
- Other supported intermediate representations.

Do not assume that all graphics APIs provide the same shader metadata.

Prefer RenderDoc's common reflection abstractions where available.

Preserve API-specific information when it cannot be represented accurately by a common model.

### 2.3 Threading and Replay Ownership

Determine the correct execution context for shader inspection calls.

Requirements:

- Respect RenderDoc replay-thread ownership.
- Do not invoke replay APIs from arbitrary IPC worker threads.
- Do not block the GUI thread with expensive serialization.
- Avoid deadlocks between GUI callbacks, replay operations, and IPC processing.
- Ensure capture unloading invalidates pending shader requests safely.

Do not introduce another replay controller unless a documented limitation makes it unavoidable.

---

## 3. Shader Identity and Event Context

Shader inspection must preserve the relationship between:

- RenderDoc GUI session.
- Loaded capture.
- Event ID.
- Pipeline type.
- Shader stage.
- Shader resource ID.

### 3.1 Shader Identity

A shader resource identifier is scoped to its capture.

Do not treat shader IDs as globally unique across captures.

Validate capture identity before inspecting a shader.

### 3.2 Event-Specific Shader Bindings

A shader can exist in a capture without being bound at the currently selected event.

Distinguish:

1. Shader resources present in the capture.
2. Shaders bound to a specific pipeline event.

Do not report an existing shader as currently bound unless the pipeline state confirms the binding.

### 3.3 Capture Changes

If the developer changes the loaded capture while a shader request is running:

- Do not mix shader data from different captures.
- Validate capture identity before returning results.
- Return a structured capture-changed result when necessary.

### 3.4 Event Changes

If the developer changes the selected event while inspection is running, preserve the event identity associated with the request.

Do not silently inspect a different shader because the GUI selection changed.

Use the Phase 8 event selection and consistency mechanisms.

---

## 4. Shader Discovery

Implement the ability to discover shaders used by the active capture and selected event.

Suggested MCP tool:

`list_shaders`

Reuse an existing tool if equivalent functionality already exists.

### 4.1 Capture-Wide Shader Enumeration

Where supported, enumerate shader resources present in the capture.

Return available information such as:

- Shader resource ID.
- Debug name.
- Shader stage, when known.
- Entry point, when available.
- Shader representation.
- Available reflection or debug information.

A shader resource may not uniquely correspond to a single pipeline stage or entry point.

Do not invent stage assignments when the available API only identifies a shader module or resource.

### 4.2 Event-Specific Shader Discovery

Support querying shaders bound to an event.

Use the Phase 8 pipeline state information.

For example:

```json
{
  "event_id": 450,
  "pipeline_type": "graphics",
  "shaders": [
    {
      "stage": "vertex",
      "shader_id": "shader-101",
      "entry_point": "VSMain"
    },
    {
      "stage": "pixel",
      "shader_id": "shader-102",
      "entry_point": "PSMain"
    }
  ]
}
```

This response is illustrative.

Use the existing resource ID and shader stage conventions.

### 4.3 Shader Stages

Support the relevant stages exposed by RenderDoc, potentially including:

- Vertex.
- Hull / Tessellation Control.
- Domain / Tessellation Evaluation.
- Geometry.
- Pixel / Fragment.
- Compute.
- Mesh.
- Amplification / Task.

Do not require unsupported or unbound stages to appear as valid shaders.

For newer shader stages, report support according to the actual RenderDoc API and graphics backend.

### 4.4 Bounded Enumeration

Capture-wide shader enumeration must support bounded results.

Allow practical filtering by:

- Shader stage, when known.
- Shader name.
- Shader ID.
- Available shader representation.

Do not return all reflection or disassembly information during enumeration.

---

## 5. Shader Metadata Inspection

Implement detailed inspection of an individual shader.

Suggested MCP tool:

`get_shader_info`

### 5.1 Information to Retrieve

Return available information such as:

- Shader resource ID.
- Shader debug name.
- Shader stage.
- Entry point.
- Graphics API.
- Shader representation.
- Shader model or version.
- Reflection availability.
- Disassembly availability.
- Source debug information availability.
- Input signature count.
- Output signature count.
- Declared resource count.
- Constant buffer count.

Only report metadata that can be reliably obtained.

### 5.2 Shader Context

Support inspection through:

1. Explicit shader ID and relevant stage/entry-point context.
2. Explicit event and shader stage.
3. Currently selected event and shader stage.

When the shader identity is ambiguous, return the available candidates rather than guessing.

### 5.3 Compact Responses

The default metadata response should not include:

- Full disassembly.
- Full source code.
- Entire reflection trees.
- All constant buffer values.

These should be requested separately.

---

## 6. Shader Reflection

This is a core requirement of Phase 10.

Suggested MCP tool:

`get_shader_reflection`

Prefer extending an existing reflection tool if one is already available.

### 6.1 Reflection Sections

Support targeted retrieval of:

- Input signatures.
- Output signatures.
- Constant buffers.
- Shader resource declarations.
- Sampler declarations.
- Read/write resource declarations.
- Other reflected interfaces supported by RenderDoc.

The default response should be a compact summary.

Allow the agent to request individual sections.

### 6.2 Input Signatures

Retrieve available input signature information.

Potential fields include:

- Semantic name.
- Semantic index.
- Register or location.
- Component type.
- Component count or mask.
- System-value classification.
- Interpolation mode, where applicable.

Preserve graphics API semantics.

Do not assume that Vulkan shader inputs use D3D-style semantic names.

### 6.3 Output Signatures

Retrieve corresponding output signature information.

Useful examples include:

- Vertex shader outputs.
- Pixel shader render-target outputs.
- Compute shader interface metadata, where applicable.

Do not force compute shader interfaces into a graphics input/output signature model.

### 6.4 Resource Declarations

Return reflected resource declarations, including available information such as:

- Resource name.
- Resource type.
- Shader stage.
- Binding location.
- Descriptor set or register space.
- Array size.
- Read-only or read/write classification.
- Expected resource dimension.
- Expected format or component type, when available.

Do not assume that declaration bindings are identical to runtime pipeline bindings.

### 6.5 Declared vs Bound Resources

This distinction is mandatory.

**Shader reflection describes what the shader declares or expects. Pipeline state describes what is actually bound at a specific event.**

Preserve these as separate concepts.

For example, a shader may declare a texture binding that is unbound for a particular event.

Do not claim that a declared resource is actually bound without verifying the event-specific pipeline state.

### 6.6 Unavailable Reflection

Some shaders may lack complete reflection or debug metadata.

When reflection is unavailable:

- Return available shader metadata.
- Report which reflection sections are unavailable.
- Allow disassembly inspection where supported.
- Do not fabricate variable names or binding declarations.

---

## 7. Constant Buffer Layout Inspection

Integrate shader reflection with the Phase 9 constant buffer inspection functionality.

Suggested MCP capability:

`get_constant_buffer_layout`

This may be implemented as a section of `get_shader_reflection` rather than a separate MCP tool.

### 7.1 Layout Information

Retrieve available information such as:

- Constant buffer name.
- Declared size.
- Binding location.
- Variable names.
- Variable types.
- Byte offsets.
- Element sizes.
- Array lengths.
- Array strides.
- Matrix dimensions.
- Matrix layout information.
- Nested structure fields.

Preserve enough information to accurately interpret buffer contents.

### 7.2 Structured Types

Support reflected structures, including:

- Scalars.
- Vectors.
- Matrices.
- Arrays.
- Nested structures.

Do not flatten complex structures if doing so loses required layout information.

### 7.3 Layout Accuracy

Be careful with:

- Alignment.
- Padding.
- Matrix row-major vs column-major representation.
- Array strides.
- Structure strides.
- Explicit offsets.
- Graphics API-specific layout conventions.

Prefer offsets and strides reported by RenderDoc reflection.

Do not attempt to reconstruct layout solely from variable types when reliable reflection information is available.

### 7.4 Reflection and Phase 9 Decoder Integration

Reuse the Phase 9 buffer decoding infrastructure.

The desired flow is:

```text
Shader Reflection
        |
        v
Constant Buffer Layout
        |
        v
Event-Specific Buffer Binding
        |
        v
Phase 9 Bounded Buffer Reading
        |
        v
Decoded Shader Variables
```

Do not implement an independent raw buffer reader inside the shader inspection subsystem.

### 7.5 Actual Constant Buffer Values

Support obtaining the actual values used by a selected draw call or compute dispatch where RenderDoc provides sufficient information.

Possible implementation approaches include:

1. RenderDoc's supported reflected constant-buffer decoding APIs.
2. Existing Phase 9 decoding using reflection-derived layouts.

Investigate the exact semantics of any RenderDoc API that returns decoded constant values.

Ensure the values correspond to the intended event and binding.

Handle event-specific binding offsets and sizes correctly.

### 7.6 Example Response

```json
{
  "event_id": 450,
  "shader_stage": "vertex",
  "constant_buffer": "PerObject",
  "variables": [
    {
      "name": "WorldMatrix",
      "type": "float4x4",
      "offset": 0,
      "value": [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]
      ]
    },
    {
      "name": "ObjectId",
      "type": "uint",
      "offset": 64,
      "value": 42
    }
  ]
}
```

The example is conceptual.

Specify matrix layout conventions in actual responses.

Do not fabricate variable names or values when reflection or buffer access is unavailable.

---

## 8. Shader Resource Binding Correlation

Provide a way to correlate reflected shader declarations with the actual resources bound to an event.

This is another high-priority Phase 10 capability.

Suggested MCP tool:

`get_shader_bindings`

Reuse the Phase 8 resource-binding tools if they already expose equivalent functionality.

### 8.1 Required Correlation

For each reflected shader resource declaration, identify:

- Shader stage.
- Declaration name.
- Declaration resource type.
- Binding location.
- Actual bound resource ID, if present.
- Actual bound resource name, if available.
- Resource metadata reference.
- Whether the binding is populated.
- Applicable bound offset and range.

Use RenderDoc's actual bindpoint mapping and pipeline state data.

Do not assume declaration indices directly correspond to runtime binding slots.

### 8.2 Graphics API Differences

Account for differences such as:

- D3D register spaces.
- Vulkan descriptor sets and bindings.
- Descriptor arrays.
- Descriptor tables.
- Combined image samplers.
- Root constants or push constants.
- Dynamic buffer offsets.

Use supported RenderDoc abstractions rather than implementing an unrelated descriptor model.

### 8.3 Example Response

```json
{
  "event_id": 450,
  "shader_stage": "pixel",
  "bindings": [
    {
      "name": "AlbedoTexture",
      "type": "sampled_texture",
      "binding": "t0",
      "bound": true,
      "resource_id": "resource-205",
      "resource_name": "CharacterAlbedo"
    },
    {
      "name": "NormalTexture",
      "type": "sampled_texture",
      "binding": "t1",
      "bound": false,
      "resource_id": null
    }
  ]
}
```

The binding representation should be adapted to the graphics API and existing project conventions.

### 8.4 Integration with Phase 9

The resulting resource IDs should be directly usable by existing Phase 9 inspection tools.

An agent should be able to:

1. Find a resource declared by a shader.
2. Determine which resource is actually bound.
3. Retrieve its metadata.
4. Read bounded buffer data where applicable.

Do not duplicate resource metadata inside every shader binding response.

---

## 9. Shader Disassembly

Implement retrieval of available shader disassembly.

Suggested MCP tool:

`get_shader_disassembly`

### 9.1 Supported Representations

Investigate which disassembly targets RenderDoc supports for the loaded shader and graphics API.

Potential representations include:

- DXBC disassembly.
- DXIL-related representations.
- SPIR-V disassembly.
- Other RenderDoc-supported representations.

Do not assume that every target is available for every shader.

### 9.2 Discover Available Targets

If RenderDoc exposes multiple disassembly targets, allow the agent to discover them.

Use supported target names returned by RenderDoc.

Do not invent disassembly target identifiers.

### 9.3 Bounded Output

Shader disassembly can be extremely large.

Support bounded retrieval using an appropriate mechanism such as:

- Line range.
- Offset and length.
- Chunked retrieval.
- Search within disassembly.

Prefer a stable, deterministic representation.

Do not return an entire large disassembly by default.

### 9.4 Search Capabilities

Where practical, allow searching for text or instructions in disassembly.

Useful searches may include:

- Resource accesses.
- Texture sampling.
- Branch instructions.
- Arithmetic operations.
- Atomic operations.
- Barriers.

Do not implement a complete shader language parser solely for search.

### 9.5 Shader Instruction Semantics

Disassembly is useful for inspection, but it does not necessarily represent the original source code.

Do not present disassembly as reconstructed HLSL, GLSL, or original shader source.

Preserve the actual representation returned by RenderDoc.

---

## 10. Shader Source and Debug Information

Retrieve available shader source-level information where supported.

Suggested MCP tool:

`get_shader_debug_info`

This may be integrated with shader metadata and source retrieval rather than implemented as a separate tool.

### 10.1 Available Debug Information

Investigate whether RenderDoc exposes:

- Source file names.
- Source file contents.
- Entry point names.
- Source line mappings.
- Compilation/debug metadata.
- Source-to-instruction relationships.

Only expose information actually embedded in or accessible through the capture and supported RenderDoc APIs.

### 10.2 Source Retrieval

If source code is available, support bounded source retrieval.

Potential parameters:

- Source file index or identifier.
- Starting line.
- Maximum lines.

Do not return every source file automatically.

### 10.3 Source Availability

A capture may contain compiled shaders without embedded source code.

In such cases:

- Report that source is unavailable.
- Continue to support reflection and disassembly.
- Do not synthesize original source code.
- Do not search arbitrary local files and assume they correspond to the captured shader.

### 10.4 No Automatic Compilation

Do not compile, modify, or replace shaders as part of source inspection.

Shader editing and replacement are outside this phase.

---

## 11. Shader Comparison

Shader comparison is a lower-priority capability.

Implement it only if the core inspection features are complete and existing abstractions make it straightforward.

### 11.1 Useful Comparison Targets

Potential comparisons include:

- Shader metadata.
- Input/output signatures.
- Resource declarations.
- Constant buffer layouts.
- Bound resources between two events.
- Disassembly when available.

### 11.2 Comparison Scope

Prefer comparison within the same capture.

Cross-capture shader matching requires additional identity and equivalence rules and is not a required Phase 10 feature.

### 11.3 Avoid Excessive Complexity

Do not implement semantic shader equivalence analysis.

Do not attempt to prove that two different shaders produce identical outputs.

Simple structural differences are sufficient.

If comparison would require substantial additional infrastructure, defer it to a later phase.

---

## 12. MCP Tool Surface

Keep the MCP interface compact and consistent with previous phases.

Suggested capabilities:

| Tool | Purpose |
|---|---|
| `list_shaders` | Enumerate shaders or retrieve shaders bound to an event |
| `get_shader_info` | Retrieve shader metadata |
| `get_shader_reflection` | Inspect signatures, resources, and constant buffer declarations |
| `get_shader_bindings` | Correlate shader declarations with actual bound resources |
| `get_shader_disassembly` | Retrieve bounded disassembly |
| `get_shader_debug_info` | Inspect available source/debug information |

Constant buffer layout and values may be exposed through existing Phase 9 tools or through targeted reflection sections.

Do not introduce separate tools for every shader stage or reflection category.

### 12.1 Parameter Consistency

Use existing conventions for:

- Session ID.
- Capture identity.
- Event ID.
- Shader stage.
- Shader resource ID.
- Resource ID.
- Result limits.
- Pagination.

### 12.2 Default Context

Where appropriate:

1. Use an explicitly supplied event.
2. Otherwise use the currently selected GUI event.
3. Resolve the relevant shader stage.
4. Return an ambiguity result if multiple valid shaders remain.

Do not silently select an arbitrary shader.

### 12.3 Read-Only Semantics

All Phase 10 tools must be read-only from the developer's perspective.

Do not change:

- Loaded capture.
- Selected event.
- Replay event.
- Shader bindings.
- Shader contents.
- GUI selection.
- Pipeline state.

---

## 13. Shared IPC and Multi-Agent Support

Preserve Phase 6 architecture.

The Shared IPC Service should route shader inspection requests to the appropriate RenderDoc GUI extension.

### 13.1 Request Routing

Validate:

- GUI session.
- Capture identity.
- Event ID.
- Shader identity.
- Shader stage.
- Request options.

Return structured results using existing IPC conventions.

### 13.2 Replay Thread Execution

Use the correct RenderDoc replay-thread execution mechanism.

Do not call replay APIs directly from arbitrary IPC threads.

### 13.3 Concurrent Agents

Support scenarios such as:

- Claude Code requests shader reflection.
- Codex requests constant buffer values.
- Both inspect the same GUI capture.
- The developer changes the selected event.

Requests must remain associated with their original capture and event identities.

Do not rely on mutable global "last inspected shader" state.

### 13.4 Large Data Transfers

Reflection trees, disassembly, and source files may produce large responses.

Enforce bounded output sizes.

Avoid excessive serialization and repeated copying.

Do not block unrelated MCP requests indefinitely while processing a large shader.

### 13.5 Cache Strategy

Shader reflection and disassembly may be suitable for caching within a capture.

If caching is introduced:

- Key cache entries by capture identity and relevant shader/entry-point context.
- Include disassembly target where applicable.
- Invalidate entries when the capture changes.
- Do not cache event-specific bound-resource values as if they were shader-global.
- Keep memory consumption bounded.

Do not add a complex caching subsystem unless actual measurements justify it.

---

## 14. Data Representation

Optimize MCP responses for AI coding agents.

### 14.1 Structured Reflection

Return structured data rather than dumping RenderDoc internal objects.

Use stable field names and documented types.

### 14.2 Preserve Important Semantics

Maintain distinctions between:

- Shader declaration and runtime binding.
- Shader module and pipeline-stage usage.
- Resource ID and binding location.
- Constant buffer layout and actual values.
- Shader source and disassembly.
- Shader metadata and event-specific pipeline state.

### 14.3 Numeric Accuracy

Preserve numeric values accurately.

Handle special floating-point values explicitly.

Do not silently convert NaN or infinity to invalid JSON numeric values.

### 14.4 Bounded Trees

Reflection may contain nested structures and arrays.

Apply limits to:

- Recursive depth.
- Number of returned variables.
- Array elements.
- Source lines.
- Disassembly lines.
- Total response size.

Indicate when output is partial or truncated.

---

## 15. Error Handling

Provide structured errors for:

- No RenderDoc GUI connected.
- No capture loaded.
- Capture changed.
- Invalid event ID.
- Shader not found.
- Shader not bound at event.
- Ambiguous shader selection.
- Unsupported shader stage.
- Reflection unavailable.
- Disassembly unavailable.
- Unsupported disassembly target.
- Source debug information unavailable.
- Constant buffer not bound.
- Buffer contents unavailable.
- Unsupported graphics API behavior.
- Replay controller unavailable.
- IPC timeout.
- GUI disconnected.

Do not turn normal absence of debug symbols or reflection metadata into unexpected exceptions.

Do not fabricate missing information.

---

## 16. Performance and Safety

Shader inspection should remain suitable for interactive use.

### 16.1 Metadata Queries

Basic shader metadata queries must be lightweight.

Do not automatically retrieve disassembly or source code.

### 16.2 Reflection

Reflection queries should avoid unnecessary repeated processing.

Use existing RenderDoc facilities rather than constructing custom reflection parsers.

### 16.3 Disassembly

Disassembly may be expensive.

Only generate it when requested.

Use bounded responses and supported replay APIs.

### 16.4 GUI Non-Interference

Inspection must not unexpectedly modify the developer's selected event or replay position.

If an inspection API requires a replay-state change, investigate whether it can be performed safely without affecting the GUI.

Do not silently manipulate the GUI to obtain shader information.

### 16.5 Resource Limits

Enforce appropriate limits on:

- Reflection tree size.
- Decoded variable count.
- Disassembly output.
- Source output.
- IPC payload size.
- Cached shader data.

---

## 17. Testing

Implement unit tests and real RenderDoc integration tests where possible.

### 17.1 Unit Tests

Cover:

- Shader identity validation.
- Capture identity validation.
- Stage normalization.
- Shader metadata serialization.
- Input/output reflection serialization.
- Resource declaration handling.
- Constant buffer layout serialization.
- Nested variable types.
- Array and matrix layouts.
- Declaration-to-binding correlation.
- Missing resource bindings.
- Disassembly pagination.
- Source retrieval bounds.
- Unsupported API behavior.
- Cache invalidation.
- Structured error responses.

### 17.2 Reflection Tests

Use deterministic reflection fixtures where possible.

Verify:

- Scalar variables.
- Vector variables.
- Matrix variables.
- Arrays.
- Nested structures.
- Explicit offsets.
- Array strides.
- Matrix layout conventions.
- Resource binding arrays.
- Descriptor spaces and sets.

Ensure serialized reflection preserves all information needed for Phase 9 buffer decoding.

### 17.3 Integration Tests

Verify:

1. Bound shaders can be identified for a selected draw call.
2. Bound compute shaders can be identified for a dispatch.
3. Shader metadata matches RenderDoc.
4. Input/output signatures can be retrieved where supported.
5. Reflected resource declarations are correct.
6. Actual bound resources can be correlated with declarations.
7. Constant buffer layouts match RenderDoc.
8. Decoded constant values match the selected event.
9. Available shader disassembly can be retrieved.
10. Source/debug information can be retrieved when embedded.
11. Missing debug information is handled correctly.
12. Capture changes invalidate shader references.
13. Concurrent MCP clients can inspect shaders safely.

### 17.4 Manual Debugging Workflows

**Scenario A — Vertex Shader Inputs**

1. Open a capture containing a graphics draw.
2. Select the draw call.
3. Identify its vertex shader.
4. Retrieve input signature information.
5. Compare the signature against the pipeline input layout.
6. Verify the information against RenderDoc.

**Scenario B — Pixel Shader Resources**

1. Select a draw call.
2. Identify the pixel shader.
3. Retrieve reflected texture and sampler declarations.
4. Resolve actual runtime resource bindings.
5. Retrieve texture metadata using Phase 9.
6. Verify the result against RenderDoc.

**Scenario C — Constant Buffer Values**

1. Select a draw call.
2. Identify a bound constant buffer.
3. Retrieve its reflected layout.
4. Decode its actual values.
5. Compare the results with RenderDoc's constant buffer viewer.

**Scenario D — Compute Shader**

1. Select a compute dispatch.
2. Identify the compute shader.
3. Retrieve shader reflection.
4. Inspect storage resource declarations.
5. Resolve bound UAV/storage buffers.
6. Inspect relevant buffers through Phase 9.

**Scenario E — Shader Disassembly**

1. Select a draw call.
2. Identify a bound shader.
3. Query available disassembly targets.
4. Retrieve a bounded disassembly section.
5. Verify the result against RenderDoc.

**Scenario F — Multi-Agent Inspection**

1. Connect Claude Code and Codex.
2. Open a capture in RenderDoc.
3. Have one agent inspect shader reflection.
4. Have the other inspect constant buffer values.
5. Verify both results correspond to the correct capture and event.
6. Change the capture and verify stale shader identities are rejected.

### 17.5 Regression Tests

Ensure:

- Phase 6 Shared IPC behavior remains functional.
- Phase 7 GUI state synchronization remains functional.
- Phase 8 event and pipeline inspection remains functional.
- Phase 9 resource and buffer inspection remains functional.
- Existing MCP tools retain backward compatibility.
- GUI startup, capture unload, and shutdown remain stable.

Do not report tests as passed unless they were actually executed.

---

## 18. Documentation

Update the README and technical documentation.

Include:

- Shader inspection overview.
- Supported shader stages.
- Shader identity and capture scope.
- Reflection capabilities.
- Declaration vs runtime binding semantics.
- Constant buffer layout inspection.
- Integration with Phase 9 buffer decoding.
- Disassembly retrieval.
- Source/debug information availability.
- Supported graphics APIs and shader representations.
- Response size limits.
- Known RenderDoc API limitations.

### Example Workflow A — Inspect a Pixel Shader

```text
Developer:
"Inspect the pixel shader used by this draw call."

Agent:
1. Resolves the selected event.
2. Finds the bound pixel shader.
3. Retrieves shader metadata.
4. Retrieves input/output signatures.
5. Retrieves declared resources.
6. Reports relevant shader information.
```

### Example Workflow B — Find Shader Resource Bindings

```text
Developer:
"Which textures does this shader actually use?"

Agent:
1. Identifies the shader.
2. Retrieves reflected texture declarations.
3. Queries runtime resource bindings.
4. Correlates declarations with bound resources.
5. Retrieves texture metadata from Phase 9.
6. Reports bound and unbound texture slots.
```

### Example Workflow C — Inspect Transformation Constants

```text
Developer:
"Check the world and projection matrices used
by the selected vertex shader."

Agent:
1. Finds the bound vertex shader.
2. Retrieves constant buffer reflection.
3. Identifies the relevant buffer binding.
4. Retrieves the buffer data.
5. Decodes the reflected matrix variables.
6. Reports values and matrix layout conventions.
```

### Example Workflow D — Inspect Shader Disassembly

```text
Developer:
"Show the disassembly around the texture sampling
instructions in the selected pixel shader."

Agent:
1. Resolves the selected pixel shader.
2. Determines available disassembly targets.
3. Requests the appropriate disassembly.
4. Searches for relevant instructions.
5. Retrieves a bounded section.
6. Reports the instructions and their context.
```

---

## 19. Out of Scope

Do not implement the following in Phase 10:

- Shader instruction-by-instruction debugging.
- Shader breakpoints.
- Shader variable stepping.
- Pixel shader execution traces.
- Compute shader execution traces.
- Shader editing or replacement.
- Shader compilation.
- Automated shader optimization.
- Shader source reconstruction.
- GPU performance profiling.
- Pixel History.
- Texture image extraction.
- Mesh visualization.
- Major replay architecture redesign.
- Major Shared IPC Service redesign.
- A general-purpose shader compiler or parser.

Phase 10 is focused on shader inspection and reflection.

Advanced shader debugging belongs to a later phase.

---

## 20. Implementation Principles

**Reuse the existing RenderDoc replay context.**

Do not load separate copies of the capture unnecessarily.

**Prefer RenderDoc's reflection APIs.**

Do not create a custom shader reflection implementation when RenderDoc already provides the necessary information.

**Separate declarations from runtime state.**

Reflected resources are not necessarily bound resources.

**Integrate with Phase 9.**

Reuse existing buffer readers and decoders for constant buffer inspection.

**Respect capture and event identity.**

Never mix shader information from different captures or events.

**Avoid GUI interference.**

Inspection must not unexpectedly change the developer's selected draw call or replay state.

**Keep results bounded.**

Large disassembly and reflection outputs must be manageable.

**Preserve API-specific semantics.**

Do not incorrectly normalize graphics API differences.

**Maintain multi-agent safety.**

Concurrent shader queries must remain reliable.

**Prefer practical debugging value.**

Prioritize information that helps diagnose real rendering problems.

---

## 21. Deliverables

When implementation is complete, provide the following.

### Implementation Summary

- Modified components.
- Added or extended MCP tools.
- Shader discovery implementation.
- Shader reflection implementation.
- Constant buffer layout integration.
- Resource binding correlation.
- Disassembly retrieval.
- Source/debug information support.

### RenderDoc API Findings

- APIs used for shader identification.
- Reflection APIs and supported fields.
- Constant buffer decoding APIs.
- Disassembly targets.
- Source/debug information availability.
- Graphics API limitations.
- Replay-thread restrictions.

### Integration Summary

- Phase 8 pipeline-state integration.
- Phase 9 buffer inspection integration.
- Phase 6 Shared IPC compatibility.
- Multi-agent behavior.

### Test Report

- Unit tests executed.
- Integration tests executed.
- Manual RenderDoc GUI tests executed.
- Graphics APIs tested.
- Shader representations tested.
- Known failures and unverified scenarios.

### Documentation

- Updated README.
- MCP tool reference.
- Shader inspection examples.
- Known limitations.

---

## 22. Acceptance Criteria

Phase 10 is complete when:

- [ ] Agents can identify shaders bound to the currently selected draw call or dispatch.
- [ ] Shader resource identifiers are associated with the correct capture.
- [ ] Basic shader metadata can be retrieved.
- [ ] Shader input signatures can be inspected where supported.
- [ ] Shader output signatures can be inspected where supported.
- [ ] Shader resource declarations can be retrieved through reflection.
- [ ] Constant buffer layouts can be retrieved with accurate offsets and strides.
- [ ] Reflected layouts integrate with Phase 9 buffer decoding.
- [ ] Event-specific constant buffer values can be retrieved where supported.
- [ ] Shader declarations can be correlated with actual runtime resource bindings.
- [ ] Unbound declarations are distinguishable from bound resources.
- [ ] Resource identifiers returned by shader inspection can be used by Phase 9 tools.
- [ ] Shader disassembly is available through bounded retrieval where supported.
- [ ] Shader source/debug information can be retrieved when available.
- [ ] Missing reflection or debug information is reported explicitly.
- [ ] Unsupported shader stages and representations are handled safely.
- [ ] Capture and event changes do not cause inconsistent inspection results.
- [ ] Read-only inspection does not unexpectedly modify GUI selection or replay state.
- [ ] Multiple MCP clients can inspect shaders concurrently.
- [ ] Large reflection or disassembly results are bounded.
- [ ] Existing Phase 6–9 functionality remains operational.
- [ ] Automated tests cover shader metadata, reflection, and binding correlation.
- [ ] Real RenderDoc captures are used to validate supported inspection paths.
- [ ] Documentation and known limitations are updated.

If an acceptance criterion depends on an unsupported RenderDoc API, document the limitation and report the criterion as incomplete or partially implemented.

Do not fabricate shader information or claim unsupported functionality is implemented.

---

## Final Goal

After Phase 10, an AI coding agent should be able to understand the shader configuration associated with the draw call or compute dispatch currently selected in RenderDoc.

For example:

**"Inspect the pixel shader used by this draw call. Check its texture bindings, constant buffers, and relevant shader instructions."**

The agent should be able to:

1. Identify the correct shader.
2. Retrieve its reflection information.
3. Examine declared shader resources.
4. Determine which resources are actually bound.
5. Inspect resource metadata through Phase 9.
6. Decode relevant constant buffer values.
7. Retrieve available shader disassembly or source information.
8. Report findings grounded in the actual capture state.

The workflow must not require reopening the capture, exporting shader files manually, or taking control of the RenderDoc GUI.

Phase 10 should establish the shader-inspection foundation needed for subsequent texture, pixel, geometry, and advanced GPU debugging capabilities.
