# Phase 9 — GPU Resource Metadata & Buffer Inspection

## Objective

Extend RenderEyeMCP with GPU resource discovery, metadata inspection, and bounded buffer-data access for captures already loaded in the RenderDoc GUI.

Phase 9 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 7 — RenderDoc GUI state discovery and synchronization.
- Phase 8 — Active capture, event, and pipeline-state inspection.

The primary goal is to enable AI coding agents to investigate GPU resources associated with draw calls and compute dispatches without reopening captures or interfering with the developer's RenderDoc session.

The implementation should provide:

1. GPU resource enumeration and discovery.
2. Texture metadata inspection.
3. Buffer metadata inspection.
4. Bounded raw buffer-data retrieval.
5. Basic structured buffer interpretation.
6. Constant buffer inspection where supported.
7. Integration with existing event and pipeline resource bindings.

**Prioritize reliable information retrieval over implementing a comprehensive resource viewer.**

Texture image extraction, pixel inspection, and advanced shader debugging are outside this phase.

---

## 1. Investigate the Existing Implementation

Before modifying the repository, inspect the current implementation.

Identify:

- The RenderDoc extension.
- The existing RenderDoc API integration.
- Phase 6 Shared IPC Service.
- Phase 7 capture and session state management.
- Phase 8 capture and pipeline inspection tools.
- Existing resource enumeration functionality.
- Existing buffer inspection functionality.
- Existing shader reflection support.
- Resource identifier serialization.
- Replay-thread scheduling mechanisms.
- Existing MCP tool conventions.
- Existing tests and documentation.

Determine whether the project already contains functionality equivalent to any proposed Phase 9 tools.

Reuse existing functionality and extend existing abstractions wherever practical.

Do not introduce duplicate implementations.

### 1.1 Verify Phase 8 Integration

Confirm that Phase 8 can provide:

- Current capture identity.
- GUI session identity.
- Current or explicitly selected event.
- Pipeline state.
- Bound resource references.

Phase 9 should use these capabilities to investigate resources associated with the selected event.

Do not create a separate capture-selection or event-selection mechanism.

### 1.2 Inspect RenderDoc API Capabilities

Investigate the available RenderDoc APIs for:

- Resource enumeration.
- Texture descriptions.
- Buffer descriptions.
- Resource naming.
- Resource identifiers.
- Buffer data retrieval.
- Buffer format interpretation.
- Shader reflection.
- Constant buffer variable extraction.
- Resource binding information.

Relevant API concepts may include:

- `ResourceId`
- `TextureDescription`
- `BufferDescription`
- `ResourceDescription`
- `ReplayController`
- `PipeState`
- `ShaderReflection`

These are investigation targets, not guaranteed API names or functionality.

Verify actual signatures, data structures, version compatibility, and threading requirements against the installed RenderDoc version.

Do not assume every feature is supported by every graphics API.

---

## 2. Resource Identity and Capture Scope

Every GPU resource belongs to a particular capture context.

A resource identifier must not be treated as globally unique across captures.

### 2.1 Resource Identity

Resource inspection requests must be associated with:

- RenderDoc GUI session.
- Loaded capture identity.
- Resource identifier.

Event-scoped queries should additionally identify the relevant event.

Use the existing capture identity mechanism introduced by previous phases.

Do not introduce a second independent capture registry.

### 2.2 Capture Changes

Handle the following scenario:

1. The agent identifies Resource A in Capture X.
2. The developer loads Capture Y.
3. The agent requests details about Resource A.
4. RenderEyeMCP must not silently resolve that identifier against Capture Y.

Return a structured capture-changed or stale-resource result.

Never silently reuse resource identifiers across different capture generations.

### 2.3 Resource Lifetime

Investigate how RenderDoc represents resources that:

- Exist throughout a capture.
- Are created or destroyed during execution.
- Are aliased or share memory.
- Are referenced by individual replay events.

Do not assume resource enumeration implies that every resource is valid or bound at every event.

Distinguish capture-wide resource metadata from event-specific binding state.

---

## 3. Resource Enumeration

Implement the ability to enumerate GPU resources in the currently loaded capture.

Suggested MCP tool:

`list_resources`

Reuse or extend an existing tool if equivalent functionality already exists.

### 3.1 Required Information

Return available information such as:

- Resource identifier.
- Resource name.
- Resource category.
- Resource type.
- Relevant dimensions or size.
- Format, where applicable.

Resource categories should at least distinguish:

- Textures.
- Buffers.
- Other resources, where supported.

Do not force every RenderDoc resource into a texture or buffer category.

### 3.2 Filtering

Support practical filters where feasible:

- Resource category.
- Resource name.
- Resource identifier.
- Resource type.

Name filtering should be useful for finding resources such as:

- Scene depth.
- Shadow maps.
- G-buffers.
- Material textures.
- Vertex buffers.
- Index buffers.
- Constant buffers.
- Compute output buffers.

Resource names may be unavailable or generated automatically.

Do not depend on meaningful debug names being present.

### 3.3 Bounded Results

Large captures may contain thousands of resources.

Implement bounded enumeration.

Support:

- Configurable result limits.
- Pagination or cursor-based navigation.
- Total result counts when practical.
- Indication of additional results.

Apply documented maximum limits.

Do not return the complete resource inventory by default.

### 3.4 Example Response

Illustrative schema:

```json
{
  "capture_id": "capture-1234",
  "total": 3,
  "resources": [
    {
      "resource_id": "resource-101",
      "name": "SceneDepth",
      "type": "texture"
    },
    {
      "resource_id": "resource-102",
      "name": "SceneColor",
      "type": "texture"
    },
    {
      "resource_id": "resource-103",
      "name": "MaterialConstants",
      "type": "buffer"
    }
  ],
  "has_more": false
}
```

Adapt the schema to the existing codebase.

Preserve the actual resource identifier representation used by RenderDoc.

---

## 4. General Resource Metadata

Implement a common resource inspection mechanism.

Suggested MCP tool:

`get_resource_info`

It should accept a resource identifier and optional session information.

### 4.1 Common Metadata

Retrieve available information such as:

- Resource ID.
- Resource name.
- Resource category.
- Resource type.
- Allocation or logical size, where available.
- Usage information.
- Relevant graphics API metadata.

Use the actual RenderDoc resource descriptions.

Do not invent memory allocation details or usage flags when the API does not expose them.

### 4.2 Resource-Specific Information

For textures, return texture-specific metadata.

For buffers, return buffer-specific metadata.

A general resource query may either include the appropriate type-specific description or refer the agent to a specialized inspection tool.

Avoid unnecessary duplication.

### 4.3 Unsupported Resources

Other resource categories should not cause internal failures.

Return whatever supported metadata is available.

If a resource category does not support detailed inspection, return a clear unsupported result.

---

## 5. Texture Metadata Inspection

Implement metadata inspection for GPU textures.

Suggested MCP tool:

`get_texture_info`

This phase does not require image extraction.

### 5.1 Required Texture Properties

Retrieve available information such as:

- Resource ID.
- Resource name.
- Texture dimension/type.
- Width.
- Height.
- Depth.
- Array size.
- Mip level count.
- Sample count.
- Format.
- Component type.
- Texture usage information.

Where supported, identify relevant properties such as:

- Render target usage.
- Depth/stencil usage.
- Shader resource usage.
- Storage/UAV usage.
- Multisampling.

Only expose properties actually available from the RenderDoc API.

Do not infer resource usage solely from resource names.

### 5.2 Format Representation

Preserve enough information to distinguish formats such as:

- UNORM.
- SNORM.
- UINT.
- SINT.
- FLOAT.
- Depth/stencil formats.
- Compressed formats.
- Typeless formats, where applicable.

Prefer RenderDoc's normalized format representation where possible.

Avoid implementing large, graphics-API-specific format conversion tables unnecessarily.

### 5.3 Example Response

```json
{
  "resource_id": "resource-101",
  "name": "SceneDepth",
  "type": "texture",
  "dimension": "2D",
  "width": 1920,
  "height": 1080,
  "depth": 1,
  "array_size": 1,
  "mip_levels": 1,
  "sample_count": 1,
  "format": "D32_FLOAT"
}
```

This is an illustrative response, not a mandatory format.

### 5.4 Scope Limitation

Do not implement:

- Texture image extraction.
- Thumbnail generation.
- Pixel value sampling.
- Texture histogram analysis.
- Texture comparison.
- Depth visualization.
- Mip image export.

These belong to a later phase.

---

## 6. Buffer Metadata Inspection

Implement detailed metadata inspection for GPU buffers.

Suggested MCP tool:

`get_buffer_info`

### 6.1 Required Information

Retrieve available properties such as:

- Resource ID.
- Resource name.
- Buffer size in bytes.
- Structure stride, when available.
- Element count, when reliably derivable.
- Buffer usage.
- Relevant buffer flags.

Potential usage classifications include:

- Vertex buffer.
- Index buffer.
- Constant/uniform buffer.
- Structured buffer.
- Raw/byte-address buffer.
- Storage buffer.
- Indirect argument buffer.

A single buffer may have multiple uses.

Do not assume that a buffer has one permanent usage classification.

### 6.2 Metadata vs Binding State

Distinguish resource metadata from event-specific bindings.

For example:

A resource may be used as a vertex buffer at one event and not be bound at another.

Do not report a buffer as currently bound merely because its description supports a particular usage.

Use the Phase 8 pipeline binding information for event-specific inspection.

### 6.3 Example Response

```json
{
  "resource_id": "resource-203",
  "name": "InstanceData",
  "type": "buffer",
  "byte_size": 65536,
  "structure_stride": 64,
  "element_count": 1024
}
```

Only calculate element counts when the underlying layout supports the calculation.

---

## 7. Bounded Raw Buffer Reading

This is a core requirement of Phase 9.

Implement the ability to read a specified byte range from a captured buffer.

Suggested MCP tool:

`read_buffer_data`

### 7.1 Request Parameters

Support:

- Resource identifier.
- Byte offset.
- Byte length.
- Output representation.
- Optional GUI session identifier.
- Capture identity validation.

Do not read an entire large buffer by default.

A request without an explicit range should use a small, documented default limit or require a range, consistent with existing project conventions.

### 7.2 Range Validation

Validate all requested ranges.

Required checks:

- Offset must be non-negative.
- Length must be positive.
- Offset must be within buffer bounds.
- Offset plus length must not overflow.
- Requested data must not extend beyond the buffer.
- Requested length must respect a maximum limit.

Use overflow-safe range validation.

Decide whether out-of-bounds requests are rejected or explicitly truncated.

Do not silently return an incomplete range without indicating that truncation occurred.

### 7.3 Data Size Limits

Introduce a conservative maximum read size.

For example, an initial limit of 64 KiB per request may be appropriate, subject to existing IPC limits and actual testing.

The exact limit should be justified and configurable only if necessary.

Remember that encoded data can be substantially larger than the original binary data.

The tool must protect:

- RenderDoc GUI responsiveness.
- IPC message size.
- MCP response size.
- AI agent context usage.
- Memory consumption.

### 7.4 Output Formats

Support practical representations such as:

- Hexadecimal.
- Base64.
- Numeric arrays, for small requests.

For binary inspection, hexadecimal output is useful for debugging.

Base64 is useful for lossless transport but is less suitable for direct LLM interpretation.

Do not default to an enormous hexadecimal dump.

Include:

- Requested offset.
- Actual returned byte count.
- Output encoding.
- Truncation status, if applicable.

### 7.5 Binary Correctness

Preserve the exact returned bytes.

Do not:

- Interpret arbitrary bytes as UTF-8 automatically.
- Perform endian conversions implicitly.
- Normalize binary data.
- Remove padding.
- Replace invalid values.

Binary interpretation must be explicit.

### 7.6 Replay Thread Safety

Use the supported RenderDoc replay API to retrieve buffer contents.

Verify the replay-thread requirements.

Do not perform replay-controller calls directly from arbitrary IPC worker threads.

Avoid holding shared service locks while waiting for GPU data retrieval.

---

## 8. Structured Buffer Interpretation

Add a lightweight mechanism for interpreting buffer bytes as structured values.

Prefer extending `read_buffer_data` with an explicit interpretation option rather than creating many separate MCP tools.

### 8.1 Supported Primitive Types

Support a focused set of basic types where practical:

- Signed integers.
- Unsigned integers.
- 16-bit and 32-bit floating-point values.
- 64-bit values where appropriate.
- Simple vectors.
- Repeated fixed-stride elements.

Support standard byte widths and specify byte order.

Do not attempt to automatically infer arbitrary C/C++ structures from raw bytes.

### 8.2 Explicit Layout

Allow the caller to provide a simple interpretation layout.

Example:

```json
{
  "resource_id": "resource-203",
  "offset": 0,
  "element_count": 4,
  "stride": 16,
  "fields": [
    {
      "name": "position",
      "offset": 0,
      "type": "float32",
      "components": 3
    },
    {
      "name": "flags",
      "offset": 12,
      "type": "uint32"
    }
  ]
}
```

This is a conceptual request format.

The implementation may use the project's existing buffer-format model instead.

### 8.3 Required Validation

Validate:

- Field offsets.
- Element stride.
- Component counts.
- Field sizes.
- Buffer bounds.
- Maximum decoded element count.

Avoid arbitrary allocation based on user-supplied sizes.

Do not execute code or evaluate expressions supplied as part of a layout.

### 8.4 Structured Output

Return compact structured values.

Example:

```json
{
  "resource_id": "resource-203",
  "elements": [
    {
      "position": [1.0, 2.0, 3.0],
      "flags": 1
    },
    {
      "position": [4.0, 5.0, 6.0],
      "flags": 0
    }
  ]
}
```

Use a bounded element count.

Avoid returning thousands of decoded structures in one response.

### 8.5 Numeric Representation

Preserve numeric accuracy where possible.

Special floating-point values such as NaN and infinity must not be silently converted to ordinary JSON numbers.

Use an explicit, documented representation.

---

## 9. Constant Buffer Inspection

Support inspection of constant/uniform buffer values using available RenderDoc functionality.

This is particularly important for debugging:

- Transformation matrices.
- Camera parameters.
- Material constants.
- Lighting parameters.
- Shader feature flags.
- Compute dispatch parameters.

### 9.1 Integration with Shader Reflection

Investigate whether the existing RenderDoc replay APIs provide reflected constant buffer layouts or decoded variable values.

Use RenderDoc's existing reflection and variable decoding facilities where available.

Do not implement a complete shader reflection engine in Phase 9.

### 9.2 Event-Specific Inspection

Constant buffer values must be associated with:

- Capture.
- Event.
- Shader stage.
- Relevant binding or descriptor location.
- Buffer/resource identity, when available.

Do not assume that constant buffers are bound identically across events.

### 9.3 Decoded Variables

Where reflection metadata is available, expose:

- Variable name.
- Type.
- Value.
- Array information, where applicable.
- Structure hierarchy, where applicable.

Support nested variables without producing unbounded output.

### 9.4 Fallback Behavior

When automatic decoding is unavailable:

1. Return the available buffer and binding metadata.
2. Allow bounded raw buffer reads.
3. Permit explicit-layout interpretation.
4. Clearly report that reflected decoding is unavailable.

Do not guess variable layouts from buffer contents.

### 9.5 Phase Boundary

Phase 9 may consume existing shader reflection information.

Advanced shader reflection, shader disassembly, and detailed shader analysis belong to Phase 10.

---

## 10. Integration with Pipeline Resource Bindings

Connect resource inspection to the Phase 8 event and pipeline inspection functionality.

The agent should be able to:

1. Identify the currently selected event.
2. Retrieve relevant pipeline bindings.
3. Identify a bound texture or buffer.
4. Retrieve the resource metadata.
5. Read buffer contents when appropriate.

### 10.1 Example Workflow

A developer asks:

"Inspect the constant buffer bound to the selected draw call."

Expected behavior:

1. Resolve the currently loaded capture.
2. Resolve the selected event.
3. Retrieve its shader resource bindings.
4. Identify the relevant constant buffer.
5. Retrieve buffer metadata.
6. Decode reflected variables if supported.
7. Otherwise provide bounded raw-data access.

Do not require the developer to manually enter internal resource identifiers when the agent can obtain them through the existing binding information.

### 10.2 Binding Identity

Preserve the relevant binding context.

For example:

- Shader stage.
- Binding slot or descriptor location.
- Resource ID.
- Buffer offset and range, when applicable.
- Array binding index, when applicable.

Do not confuse the entire backing buffer with the subrange bound to a shader.

### 10.3 Bound Buffer Ranges

Some graphics APIs permit binding only a portion of a buffer.

Ensure inspection distinguishes:

- Physical/logical buffer bounds.
- The region bound to the current event.
- The requested read range.

Do not implicitly expose unrelated buffer regions when an event-specific binding is intended.

---

## 11. Shared IPC and Multi-Agent Compatibility

Integrate Phase 9 with the existing Shared IPC Service.

Preserve the architecture introduced in Phase 6.

### 11.1 Request Routing

Resource queries must be routed to the correct RenderDoc GUI session.

The service should validate:

- Session availability.
- Capture identity.
- Resource identity.
- Request bounds.

The RenderDoc extension remains responsible for safe replay API interaction.

### 11.2 Binary Data Transfer

Investigate the existing IPC serialization format before introducing buffer-data transport.

Avoid unnecessary Base64 conversion inside the IPC layer if binary payloads are already supported.

It is acceptable to encode data at the MCP response boundary where the selected representation requires it.

Do not unnecessarily encode and decode binary data multiple times.

### 11.3 Concurrent Agents

Multiple agents must be able to query resources without corrupting shared state.

Example:

```text
Claude Code
    |
    | Read Buffer A
    |
    v
Shared IPC Service
    |
    |---------------- RenderDoc Extension
    |                         |
    |                         v
    |                  Replay Controller
    |                         ^
    |-------------------------|
    ^
    |
    | Get Texture B Metadata
    |
Codex
```

Ensure:

- Requests are independently tracked.
- Responses correspond to the correct requests.
- Replay operations are scheduled safely.
- Large reads cannot indefinitely block unrelated requests.
- One agent disconnecting does not invalidate another agent's work.

### 11.4 Timeout and Failure Handling

Handle:

- GUI shutdown.
- Capture unload.
- IPC disconnection.
- Replay controller unavailability.
- Invalid resource identifiers.
- Read failures.
- Timeouts.

Do not return stale buffer contents as current data after the capture changes.

---

## 12. Performance and Safety

Resource inspection must be suitable for interactive use.

### 12.1 Avoid Unnecessary GPU Work

Metadata queries should remain lightweight.

Do not trigger full resource downloads or expensive replay operations when only metadata is requested.

### 12.2 Memory Limits

Enforce limits on:

- Raw buffer reads.
- Decoded element counts.
- Resource enumeration.
- Structured output sizes.
- IPC message sizes, where applicable.

Avoid allocating memory based solely on unvalidated user parameters.

### 12.3 Large Resource Handling

A capture may contain resources exceeding hundreds of megabytes.

Do not read an entire resource as a convenience operation.

Use bounded reads and explicit ranges.

### 12.4 Non-Interference

Read-only inspection must not unexpectedly change:

- Current GUI selection.
- Current replay event.
- Loaded capture.
- Pipeline state.
- Resource contents.

If a RenderDoc API requires a replay-state transition, investigate the consequences before using it.

Prefer APIs that inspect the existing replay state without modifying developer-visible state.

---

## 13. MCP Tool Design

Prefer a small, coherent set of tools.

Suggested tool surface:

| Tool | Responsibility |
|---|---|
| `list_resources` | Discover resources in the active capture |
| `get_resource_info` | Retrieve general resource metadata |
| `get_texture_info` | Retrieve detailed texture metadata |
| `get_buffer_info` | Retrieve detailed buffer metadata |
| `read_buffer_data` | Read bounded buffer data with optional interpretation |

The existing Phase 8 pipeline binding tools should provide event-specific resource references.

Do not duplicate their behavior.

If specialized metadata can be returned through `get_resource_info`, separate texture/buffer tools may be unnecessary.

Choose the interface that best fits the current repository.

### 13.1 Tool Parameter Consistency

Use consistent parameter names and types for:

- Session IDs.
- Capture IDs or generations.
- Resource IDs.
- Event IDs.
- Offsets.
- Sizes.
- Result limits.

Preserve existing conventions.

### 13.2 Tool Discoverability

Tool descriptions must explain:

- What the tool retrieves.
- Whether it uses the current capture.
- Whether it requires a resource ID.
- Whether it changes GUI state.
- What limits apply.

Make it clear how an agent moves from event inspection to resource inspection.

---

## 14. Error Handling

Provide meaningful structured errors for:

- No RenderDoc session.
- No loaded capture.
- Capture changed.
- Invalid resource ID.
- Resource not found.
- Unsupported resource type.
- Invalid buffer range.
- Requested read exceeds limit.
- Buffer data unavailable.
- Unsupported data interpretation.
- Shader reflection unavailable.
- Replay controller unavailable.
- IPC timeout.
- GUI disconnected.

Do not treat normal missing metadata as an unexpected exception.

Use consistent error codes and response conventions.

Do not fabricate values when the API cannot provide them.

---

## 15. Testing

Implement automated tests and real RenderDoc integration tests where possible.

### 15.1 Unit Tests

Cover:

- Resource identity validation.
- Capture generation validation.
- Resource enumeration filtering.
- Pagination.
- Texture metadata serialization.
- Buffer metadata serialization.
- Offset and size validation.
- Integer overflow protection.
- Maximum read limits.
- Raw byte encoding.
- Structured data decoding.
- Floating-point special values.
- Constant buffer layout handling.
- Unsupported resource types.
- Error responses.

### 15.2 Buffer Decoding Tests

Use deterministic test buffers containing known values.

Verify:

- Signed and unsigned integers.
- Floating-point values.
- Vectors.
- Element strides.
- Padding.
- Field offsets.
- Array elements.
- Boundary conditions.
- Invalid layouts.

Compare decoded results against expected values.

Do not rely only on visual inspection of hexadecimal output.

### 15.3 Integration Tests

Verify:

1. Resources can be enumerated from a loaded capture.
2. Resource names and IDs match RenderDoc.
3. Texture metadata matches the RenderDoc UI.
4. Buffer metadata matches the RenderDoc UI.
5. A small buffer range can be read correctly.
6. Nonzero-offset reads return the correct bytes.
7. Out-of-bounds reads are rejected or explicitly bounded.
8. Structured buffer values decode correctly.
9. Constant buffer variables are available where supported.
10. Resource bindings correspond to the selected event.
11. Capture changes invalidate previous resource identities.
12. Two agents can inspect resources concurrently.

### 15.4 Manual Debugging Workflows

Test representative real-world scenarios.

**Scenario A — Vertex Buffer**

1. Open a capture containing indexed geometry.
2. Select a draw call.
3. Identify its vertex buffer binding.
4. Retrieve buffer metadata.
5. Read a small range of vertex data.
6. Verify the result against RenderDoc.

**Scenario B — Constant Buffer**

1. Select a draw call with constant buffer bindings.
2. Identify the relevant buffer.
3. Retrieve its metadata.
4. Decode available variables.
5. Verify values against RenderDoc's buffer viewer.

**Scenario C — Compute Output Buffer**

1. Select a compute dispatch.
2. Identify its output/storage buffer.
3. Retrieve buffer metadata.
4. Read a bounded range.
5. Validate the returned data against RenderDoc.

**Scenario D — Texture Metadata**

1. Select an event with a render target or shader texture.
2. Identify the texture resource.
3. Retrieve width, height, format, mip count, and sample count.
4. Verify against RenderDoc.

**Scenario E — Multi-Agent Inspection**

1. Connect Claude Code and Codex.
2. Load a capture in RenderDoc.
3. Query different resources concurrently.
4. Verify both agents receive correct results.
5. Change the capture and verify stale IDs are rejected.

### 15.5 Regression Tests

Ensure:

- Phase 6 multi-agent IPC remains functional.
- Phase 7 GUI state synchronization remains functional.
- Phase 8 event and pipeline inspection remains functional.
- Existing tools retain backward compatibility.
- RenderDoc GUI startup and shutdown remain stable.

Do not claim tests passed unless they were actually executed.

---

## 16. Documentation

Update the README and relevant technical documentation.

Include:

- Resource inspection overview.
- Supported resource categories.
- Resource ID and capture identity rules.
- Resource enumeration examples.
- Texture metadata examples.
- Buffer metadata examples.
- Bounded buffer reading examples.
- Supported output encodings.
- Structured buffer layout examples.
- Constant buffer inspection examples.
- Data size limits.
- Supported RenderDoc versions and graphics APIs.
- Known limitations.

### Example Workflow — Inspect a Bound Constant Buffer

```text
Developer:
"Inspect the constant buffer used by the
currently selected draw call."

Agent:
1. Resolves the selected event.
2. Queries pipeline resource bindings.
3. Identifies the constant buffer.
4. Retrieves buffer metadata.
5. Retrieves reflected values when supported.
6. Reports the values relevant to the draw call.
```

### Example Workflow — Investigate Compute Output

```text
Developer:
"Check the first 16 elements of the output
buffer bound to this compute dispatch."

Agent:
1. Resolves the selected dispatch.
2. Finds the output/storage buffer.
3. Retrieves its metadata.
4. Reads the required byte range.
5. Decodes the elements using a known layout.
6. Reports the decoded values.
```

### Example Workflow — Inspect Render Target Metadata

```text
Developer:
"What is the format and resolution of the
render target used by this draw call?"

Agent:
1. Resolves the selected event.
2. Retrieves the output attachment binding.
3. Identifies the texture resource.
4. Retrieves texture metadata.
5. Reports its dimensions and format.
```

---

## 17. Out of Scope

Do not implement the following in Phase 9:

- Texture pixel extraction.
- Texture image export.
- Thumbnail generation.
- Texture comparison.
- Pixel History.
- Shader debugging.
- Shader disassembly.
- Advanced shader reflection analysis.
- Mesh visualization.
- Full vertex processing visualization.
- GPU performance profiling.
- Automated rendering issue diagnosis.
- Capture opening or closing.
- GUI event-selection manipulation.
- Arbitrary replay-state modification.
- Major Shared IPC Service redesign.

Keep Phase 9 focused on resource metadata and bounded buffer inspection.

---

## 18. Implementation Principles

**Reuse existing infrastructure.**

Build on the Phase 6–8 architecture.

**Respect the active GUI capture.**

Do not create duplicate replay sessions unnecessarily.

**Preserve resource identity.**

Resource IDs are capture-scoped.

**Keep metadata queries lightweight.**

Do not download resource contents when only metadata is required.

**Bound all binary reads.**

Never allow unbounded resource transfers through MCP.

**Prefer explicit interpretation.**

Do not guess binary structures or numeric formats.

**Use available reflection.**

Do not rebuild shader reflection functionality unnecessarily.

**Maintain read-only behavior.**

Do not interfere with the developer's RenderDoc GUI.

**Keep the MCP interface compact.**

Avoid excessive specialized tools.

**Validate with real captures.**

Tool functionality must be useful for actual graphics debugging.

---

## 19. Deliverables

When implementation is complete, provide:

### Implementation Summary

- Modified components.
- Added or extended MCP tools.
- Resource enumeration implementation.
- Texture and buffer metadata handling.
- Buffer read and decoding implementation.
- Constant buffer inspection integration.

### RenderDoc API Findings

- APIs used.
- Supported resource metadata.
- Buffer read behavior.
- Replay-thread requirements.
- Shader reflection availability.
- API-dependent limitations.

### Performance and Safety

- Maximum buffer read size.
- Maximum decoded element count.
- IPC binary transport behavior.
- Memory allocation safeguards.
- Concurrency behavior.

### Test Report

- Unit tests executed.
- Integration tests executed.
- Manual GUI tests executed.
- Graphics APIs tested.
- Multi-agent test results.
- Known failures or unverified scenarios.

### Documentation

- Updated README.
- Tool reference documentation.
- Usage examples.
- Known limitations.

---

## 20. Acceptance Criteria

Phase 9 is complete when:

- [ ] Agents can enumerate GPU resources from the currently loaded capture.
- [ ] Resource enumeration supports bounded results and practical filtering.
- [ ] Resource IDs are associated with the correct capture.
- [ ] Texture dimensions, format, mip levels, and other available metadata can be retrieved.
- [ ] Buffer size, stride, and other available metadata can be retrieved.
- [ ] Agents can read explicitly bounded ranges of buffer data.
- [ ] Buffer reads enforce validated size and offset limits.
- [ ] Raw buffer data can be returned without corruption.
- [ ] Basic structured buffer values can be decoded using explicit layouts.
- [ ] Constant buffer values can be retrieved using RenderDoc reflection where supported.
- [ ] Missing reflection metadata has a safe fallback.
- [ ] Resource inspection integrates with Phase 8 pipeline bindings.
- [ ] Capture changes invalidate old resource references.
- [ ] Resource queries do not unexpectedly modify GUI selection or replay state.
- [ ] Multiple MCP clients can inspect resources concurrently.
- [ ] Large resources cannot cause unbounded MCP responses or memory allocations.
- [ ] Existing Phase 6–8 functionality continues working.
- [ ] Automated tests cover the core resource and buffer functionality.
- [ ] Real capture tests validate metadata and buffer contents.
- [ ] Documentation and known limitations are updated.

If an acceptance criterion depends on an unsupported RenderDoc API, document the limitation and mark the criterion as incomplete or partially implemented.

Do not silently substitute fabricated data.

---

## Final Goal

After Phase 9, an AI coding agent should be able to inspect GPU resources associated with the draw call or compute dispatch currently selected in RenderDoc.

For example, a developer should be able to ask:

**"Inspect the constant buffer bound to this draw call and show me the transformation matrix values."**

Or:

**"Find the structured buffer written by this compute dispatch and inspect its first 16 elements."**

The agent should use the existing RenderDoc GUI capture and RenderEyeMCP tools to identify the correct resource, retrieve relevant metadata, and read only the required data.

The developer should not need to reopen the capture, manually export buffers, or perform additional GUI operations.

Phase 9 should establish a reliable resource-inspection foundation for subsequent shader, texture, geometry, and advanced GPU debugging capabilities.
