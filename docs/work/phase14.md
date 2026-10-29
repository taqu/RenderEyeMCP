# Phase 14 — Geometry & Mesh Inspection

## Objective

Extend RenderEyeMCP with comprehensive geometry and mesh inspection capabilities for draw calls in captures already loaded in the RenderDoc GUI.

Phase 14 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 7 — Active GUI capture discovery.
- Phase 8 — Draw call, event, and pipeline-state inspection.
- Phase 9 — GPU resource metadata and buffer inspection.
- Phase 10 — Shader reflection and input/output signatures.
- Phase 11 — Texture and pixel inspection.
- Phase 12 — Release preparation and bilingual documentation.
- Phase 13 — GPU performance analysis.
- Phase 13.1 — End-to-end performance analysis validation.

The primary goal is to allow AI coding agents to inspect the geometry supplied to a draw call and the geometry produced by vertex processing.

Typical developer questions include:

- "Why is the selected mesh not rendering?"
- "Inspect the vertex positions and indices used by this draw call."
- "Does the vertex buffer layout match the vertex shader inputs?"
- "Check whether the geometry contains invalid positions or normals."
- "Inspect the vertices produced by the vertex shader."
- "Are the triangle indices or winding orders incorrect?"
- "Why does this draw call process so many vertices?"
- "Compare the vertex shader inputs and outputs for this draw call."

**The central goal is to enable evidence-based geometry debugging using the existing RenderDoc capture and replay context.**

Prioritize accurate mesh data, input-layout validation, and Post-VS inspection over implementing a complete mesh visualization application.

---

## 1. Investigate the Existing Implementation

Before modifying the repository, inspect the current codebase.

Identify:

1. RenderDoc extension implementation.
2. Existing RenderDoc ReplayController access.
3. Replay-thread scheduling and ownership.
4. Phase 6 Shared IPC Service.
5. Phase 7 session and capture identity.
6. Phase 8 draw call and pipeline inspection.
7. Phase 9 buffer inspection and decoding.
8. Phase 10 shader reflection.
9. Phase 13 GPU counter integration.
10. Existing geometry or mesh-related tools.
11. Existing MCP response and pagination conventions.
12. Existing tests and documentation.

Do not create duplicate infrastructure.

### 1.1 Reuse Phase 9 Buffer Inspection

Phase 9 already provides bounded raw buffer access and structured buffer decoding.

Reuse these facilities for:

- Vertex buffer data.
- Index buffer data.
- Vertex attributes.
- Numeric conversion.

Do not implement a second general-purpose buffer reader.

### 1.2 Reuse Phase 10 Shader Reflection

Use existing shader reflection to identify:

- Vertex shader input signatures.
- Vertex shader output signatures.
- Attribute semantics or locations.
- Component types.
- Shader stage information.

Do not implement an independent shader reflection parser.

### 1.3 Reuse Phase 13 Performance Data

Where GPU performance measurements are available, allow geometry inspection results to be correlated with:

- GPU event duration.
- Input vertex counts.
- Input primitive counts.
- Vertex shader invocation counts.
- Other supported pipeline statistics.

Do not automatically trigger GPU performance measurements from geometry inspection tools.

---

## 2. Investigate RenderDoc Mesh APIs

Inspect the actual RenderDoc APIs supported by the installed version.

Relevant API concepts may include:

- `ReplayController`
- `PipeState`
- `ActionDescription`
- `MeshFormat`
- `MeshDataStage`
- `ShaderReflection`
- `GetVBuffers()`
- `GetIBuffer()`
- `GetVertexInputs()`
- `GetPostVSData()`
- `GetBufferData()`
- `GetPipelineState()`

These are investigation targets, not guaranteed signatures.

Use the installed API definitions as the authoritative reference.

### 2.1 Reference Implementation

Review RenderDoc's official Python example for decoding mesh data:

https://github.com/baldurk/renderdoc/blob/v1.x/docs/python_api/examples/renderdoc/decode_mesh.py

Study how the example:

- Retrieves vertex buffer bindings.
- Retrieves index buffer bindings.
- Resolves vertex input attributes.
- Decodes indexed geometry.
- Interprets component formats.
- Retrieves post-vertex-shader data.
- Uses shader reflection for output interpretation.

Use the example as a reference, but verify compatibility with the installed RenderDoc version.

Do not copy assumptions that only work for simple meshes.

### 2.2 Graphics API Compatibility

Investigate differences between:

- D3D11.
- D3D12.
- Vulkan.
- OpenGL.
- Other supported graphics APIs.

Prefer RenderDoc's API-independent pipeline abstractions.

Preserve API-specific semantics where necessary.

### 2.3 Supported Draw Types

Determine how to handle:

- Non-indexed draws.
- Indexed draws.
- Instanced draws.
- Indirect draws.
- Base vertex offsets.
- First vertex offsets.
- First instance offsets.
- Primitive restart.
- Different primitive topologies.

Do not assume every graphics draw is an indexed triangle list.

### 2.4 Advanced Pipeline Stages

Investigate support for:

- Tessellation.
- Geometry shaders.
- Mesh shaders.
- Task/amplification shaders.
- Multi-view rendering.

Only implement data access supported by the installed RenderDoc API.

Do not misrepresent Post-VS data as final geometry when later stages can modify it.

---

## 3. Geometry Inspection Context

Geometry inspection must preserve:

- GUI session identity.
- Capture identity.
- Event ID.
- Draw call identity.
- Instance index, where applicable.
- View index, where applicable.
- Geometry stage.

Use existing Phase 7 and Phase 8 context resolution.

### 3.1 Default Event

When no event is explicitly supplied, use the currently selected GUI event according to existing rules.

Verify that the selected event is a compatible graphics draw.

Do not silently select an unrelated draw call.

### 3.2 Explicit Event

Support explicit event targeting.

An agent should be able to inspect a draw call discovered through Phase 13 performance analysis without manually selecting it in RenderDoc.

If the requested inspection cannot be performed safely without changing GUI replay state, return an explicit limitation.

### 3.3 Capture Changes

Validate capture identity throughout inspection.

Do not reuse vertex/index buffer identifiers against a different capture.

### 3.4 Read-Only Behavior

Geometry inspection must not unexpectedly change:

- Loaded capture.
- Selected event.
- Current replay event.
- Existing Mesh Viewer configuration.
- Developer-visible GUI state.

---

## 4. Draw Call Geometry Information

Expose the basic geometry configuration of a draw call.

Suggested MCP capability:

`get_draw_geometry_info`

Reuse existing Phase 8 draw call inspection if appropriate.

### 4.1 Required Information

Retrieve available information such as:

- Event ID.
- Draw call type.
- Primitive topology.
- Indexed or non-indexed.
- Vertex/index count.
- Instance count.
- First vertex.
- First index.
- Base vertex.
- First instance.
- Indirect draw information, where supported.
- Vertex buffer bindings.
- Index buffer binding.

### 4.2 Example Response

```json
{
  "event_id": 450,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 3600,
  "instance_count": 4,
  "first_index": 0,
  "base_vertex": 0,
  "first_instance": 0
}
```

This is an illustrative response.

Use the actual RenderDoc action representation.

### 4.3 Draw Semantics

Distinguish:

- Vertex count.
- Index count.
- Unique referenced vertices.
- Vertex shader invocations.
- Primitive count.

Do not treat these as equivalent.

### 4.4 Unsupported Draws

For draw types that cannot be inspected, return available metadata and an explicit unsupported status.

Do not fabricate geometry.

---

## 5. Vertex Input Layout Inspection

Implement inspection of vertex input declarations and buffer bindings.

Suggested MCP tool:

`get_vertex_input_layout`

### 5.1 Vertex Buffer Bindings

Retrieve:

- Binding slot.
- Resource ID.
- Buffer offset.
- Vertex stride.
- Input rate.
- Instance step rate or divisor, where applicable.
- Buffer size, where available.

Reuse Phase 9 buffer metadata.

### 5.2 Vertex Attributes

Retrieve:

- Attribute name or semantic.
- Semantic index or location.
- Component format.
- Component count.
- Byte offset.
- Buffer binding slot.
- Per-vertex or per-instance classification.
- Normalization information.

### 5.3 Shader Input Correlation

Correlate input attributes with Phase 10 vertex shader reflection.

Identify potential mismatches such as:

- Missing shader inputs.
- Incompatible component types.
- Incorrect binding locations.
- Unbound vertex buffers.
- Unexpected input rates.

Distinguish confirmed mismatches from possible issues.

Do not assume that attribute names alone establish correspondence.

### 5.4 Example Response

```json
{
  "event_id": 450,
  "attributes": [
    {
      "name": "POSITION",
      "location": 0,
      "format": "R32G32B32_FLOAT",
      "offset": 0,
      "binding": 0
    },
    {
      "name": "NORMAL",
      "location": 1,
      "format": "R32G32B32_FLOAT",
      "offset": 12,
      "binding": 0
    },
    {
      "name": "TEXCOORD",
      "location": 2,
      "format": "R32G32_FLOAT",
      "offset": 24,
      "binding": 0
    }
  ]
}
```

Adapt the schema to existing conventions.

---

## 6. Index Buffer Inspection

Implement accurate index buffer decoding.

Suggested MCP tool:

`get_mesh_indices`

### 6.1 Supported Index Formats

Handle index formats supported by RenderDoc and the relevant graphics API, commonly including:

- 8-bit indices where supported.
- 16-bit indices.
- 32-bit indices.

Do not assume a fixed index width.

### 6.2 Index Range

Account for:

- Bound index buffer offset.
- First index.
- Index count.
- Index element size.
- Base vertex.
- Primitive restart values.

Validate all offset calculations.

### 6.3 Raw vs Effective Indices

Distinguish the index value stored in the buffer from the effective vertex reference used by the draw.

Do not apply base vertex offsets twice.

Preserve the original index when reporting decoded results.

### 6.4 Bounded Retrieval

Support:

- Starting index.
- Maximum index count.
- Optional primitive grouping.
- Instance context where relevant.

Do not return entire index buffers by default.

### 6.5 Invalid Indices

Detect:

- Out-of-bounds reads.
- Unsupported index formats.
- Invalid effective vertex references.
- Incomplete index data.

Treat primitive restart values according to the actual topology and draw semantics.

Do not label valid restart markers as corrupt indices.

---

## 7. Vertex Attribute Decoding

Implement bounded decoding of vertex input data.

Suggested MCP tool:

`get_mesh_vertices`

### 7.1 Supported Data

Retrieve selected vertex attributes such as:

- Position.
- Normal.
- Tangent.
- Texture coordinates.
- Vertex color.
- Skinning weights.
- Skinning indices.
- Custom attributes.

Do not hardcode attribute names or require conventional semantics.

### 7.2 Format Decoding

Support formats exposed through RenderDoc, including relevant:

- Floating-point formats.
- Signed integers.
- Unsigned integers.
- Normalized integer formats.
- Packed component formats.
- Half-precision floating-point formats.

Reuse existing format decoding when available.

Avoid inventing format conversions.

### 7.3 Vertex Addressing

Correctly apply:

- Buffer binding offset.
- Attribute byte offset.
- Vertex stride.
- Vertex index.
- Instance index.
- Instance input divisor.
- Draw starting offsets.

Use overflow-safe calculations.

### 7.4 Indexed Geometry

For indexed draws, support retrieving vertices referenced by a specified index range.

Preserve the relationship between:

- Index buffer position.
- Stored index value.
- Effective vertex reference.
- Decoded vertex attributes.

### 7.5 Example Response

```json
{
  "event_id": 450,
  "vertices": [
    {
      "vertex_id": 0,
      "attributes": {
        "POSITION": [0.0, 1.0, 0.0],
        "NORMAL": [0.0, 0.0, 1.0],
        "TEXCOORD": [0.5, 1.0]
      }
    },
    {
      "vertex_id": 1,
      "attributes": {
        "POSITION": [-1.0, -1.0, 0.0],
        "NORMAL": [0.0, 0.0, 1.0],
        "TEXCOORD": [0.0, 0.0]
      }
    }
  ]
}
```

Use the actual input layout and resource data.

### 7.6 Bounded Responses

Support:

- Vertex range.
- Index range.
- Attribute selection.
- Instance selection.
- Result limit.

Do not return thousands of vertices by default.

---

## 8. Post-Vertex-Shader Geometry Inspection

This is a core Phase 14 capability.

Suggested MCP tool:

`get_post_vs_geometry`

Investigate RenderDoc's supported post-vertex-processing APIs.

### 8.1 Supported Geometry Stages

Determine which stages can be inspected, such as:

- Vertex shader input.
- Vertex shader output.
- Geometry shader output.
- Other post-transform outputs exposed by RenderDoc.

Use the actual `MeshDataStage` semantics supported by the installed version.

Do not assume all stages are available for every draw.

### 8.2 Post-VS Data Acquisition

Investigate whether Post-VS data requires:

- Replay execution.
- Data capture or initialization.
- Temporary GPU resources.
- Additional synchronization.
- Internal caching.

Do not assume Post-VS extraction is a lightweight metadata query.

### 8.3 Explicit Extraction

If Post-VS data acquisition requires additional replay work, make the operation explicit.

Do not trigger expensive Post-VS extraction automatically from basic draw call information requests.

### 8.4 Replay Safety

Use supported RenderDoc replay mechanisms.

Do not call replay APIs from arbitrary IPC threads.

Coordinate extraction with Phase 13 GPU measurement operations when they share replay resources.

Do not modify GUI-visible replay state without an explicit, documented policy.

### 8.5 Post-VS Attributes

Retrieve available output attributes using shader reflection.

Potential data includes:

- Clip-space position.
- Other vertex shader outputs.
- Interpolated attributes before rasterization, where represented.
- Geometry shader outputs where supported.

Do not assume the first output attribute is always the position.

Identify system-value position using supported reflection metadata.

### 8.6 Position Coordinate Spaces

Clearly distinguish:

- Object/local space.
- World space.
- View space.
- Clip space.
- Normalized device coordinates.

Post-VS position is often clip-space position, but the exact semantics depend on the shader and pipeline.

Do not describe arbitrary shader outputs as world-space positions.

### 8.7 Perspective Division

For clip-space positions, optionally calculate:

```text
ndc.x = clip.x / clip.w
ndc.y = clip.y / clip.w
ndc.z = clip.z / clip.w
```

Only perform perspective division when meaningful and numerically valid.

Handle:

- Zero W.
- Near-zero W.
- NaN.
- Infinity.
- Invalid values.

Preserve original clip-space values.

Do not silently clamp NDC coordinates.

### 8.8 Instance and View Selection

Support explicit instance and view selection where required.

Do not assume all instances produce identical geometry.

### 8.9 Output Bounds

Post-VS output can be much larger than the original input geometry, particularly when later shader stages generate additional primitives.

Enforce bounded extraction and output.

---

## 9. Vertex Shader Input/Output Correlation

Enable comparison between pre-VS attributes and post-VS outputs.

This feature helps diagnose:

- Incorrect transformation matrices.
- Invalid positions.
- Unexpected clipping.
- Incorrect instance transforms.
- Broken vertex inputs.
- Unexpected shader-generated output.

### 9.1 Correlation Scope

Correlate values only when RenderDoc provides sufficient information to establish a meaningful relationship.

A vertex shader invocation may not correspond one-to-one with a unique original vertex buffer element because of:

- Index reuse.
- Instancing.
- Vertex shader invocation order.
- Primitive restart.
- GPU processing behavior.
- Geometry amplification.

### 9.2 Comparison Result

Where supported, provide:

- Input vertex reference.
- Instance index.
- Relevant input attributes.
- Post-VS output values.
- Clip-space position.
- Derived NDC position.

### 9.3 Avoid False Assumptions

Do not assume a Post-VS output's ordinal position always identifies the original vertex index.

Validate the actual RenderDoc mesh-data mapping.

If correspondence is unavailable, expose input and output data separately.

### 9.4 Example Debugging Workflow

A developer asks:

"Why is this mesh outside the view frustum?"

The agent should:

1. Inspect the draw call.
2. Retrieve vertex input positions.
3. Retrieve Post-VS clip-space positions.
4. Inspect relevant transformation constants from Phase 10.
5. Identify invalid or suspicious transformed coordinates.
6. Report evidence and possible explanations.

Do not claim that every object outside the frustum is necessarily a bug.

---

## 10. Mesh Topology and Geometry Statistics

Add lightweight geometry analysis using decoded data.

Suggested MCP tool:

`get_mesh_statistics`

### 10.1 Basic Statistics

Where meaningful, calculate:

- Referenced vertex count.
- Index count.
- Primitive count.
- Instance count.
- Unique referenced vertex count.
- Available position bounds.
- Invalid numeric value count.
- Degenerate primitive count.

Clearly identify whether statistics cover:

- The complete draw.
- A selected subset.
- A particular instance.
- A particular geometry stage.

### 10.2 Bounding Boxes

For position attributes, calculate an axis-aligned bounding box.

Report the coordinate space used.

Do not mix input object-space bounds with post-VS clip-space bounds.

For a partial vertex sample, do not describe its bounds as the complete mesh bounds.

### 10.3 Invalid Values

Detect values such as:

- NaN.
- Positive or negative infinity.
- Invalid decoded component representations.

Do not classify legitimate negative positions or values outside a conventional range as invalid.

### 10.4 Degenerate Primitives

For supported triangle topologies, identify degenerate triangles.

Possible checks include:

- Repeated vertex indices.
- Zero or near-zero triangle area.

Use explicit tolerances for geometric degeneracy.

Different coordinate spaces and numerical scales may affect the result.

### 10.5 Primitive Topology

Support the primitive topologies actually exposed by the selected draw.

Do not interpret:

- Lines as triangles.
- Triangle strips as triangle lists.
- Patches as ordinary triangles.
- Adjacency data as standalone primitives.

Handle primitive restart correctly.

### 10.6 Full vs Sampled Analysis

For large meshes, avoid unbounded CPU processing and memory allocation.

Support bounded sampling or explicitly requested full analysis with resource limits.

Report whether results are complete or sampled.

Do not estimate total degeneracy counts from a sample without clearly describing the estimation method.

---

## 11. Geometry and Performance Correlation

Integrate Phase 14 with Phase 13 performance analysis.

The purpose is to support questions such as:

- "Why does this draw call have so many vertex shader invocations?"
- "Does this draw call use excessive geometry?"
- "Is instancing configured as expected?"
- "Are the input vertex count and pipeline statistics consistent?"

### 11.1 Use Existing Measurements

Retrieve previously collected Phase 13 measurements when available.

Do not automatically run GPU counter collection.

### 11.2 Relevant Metrics

Correlate:

- Draw index/vertex counts.
- Instance counts.
- Primitive topology.
- Input vertex count.
- Vertex shader invocation count.
- Input primitive count.
- GPU duration.

### 11.3 Derived Observations

Potential derived observations include:

- Difference between declared draw counts and measured invocation counts.
- Unusually high instance counts.
- Large numbers of referenced indices.
- Geometry duplication.
- Unexpected input-rate configuration.

Do not assume an observed difference is necessarily a performance bug.

### 11.4 Vertex Processing Costs

A high vertex count or invocation count does not independently prove that the vertex shader is the GPU bottleneck.

Likewise, a high GPU duration cannot be attributed to geometry processing without sufficient supporting evidence.

Separate measurements from hypotheses.

---

## 12. Mesh Visualization

Mesh visualization is a lower-priority feature.

Implement it only if the core geometry inspection features are complete and existing RenderDoc APIs make it straightforward.

### 12.1 Possible Visualization

Potential outputs include:

- Wireframe preview.
- Mesh bounds.
- Selected triangle highlighting.
- Basic vertex position preview.

### 12.2 Prefer RenderDoc Facilities

Investigate whether RenderDoc exposes a safe mesh rendering or output mechanism.

Do not implement a new GPU mesh renderer solely for Phase 14.

### 12.3 Non-Interference

Do not alter the existing RenderDoc Mesh Viewer configuration.

If visualization requires a separate replay output, manage it independently and release resources correctly.

### 12.4 Deferral

If image generation requires significant new infrastructure, defer it.

Numerical geometry inspection is the main Phase 14 objective.

---

## 13. MCP Tool Design

Keep the MCP tool interface compact.

Suggested capabilities:

| Tool | Responsibility |
|---|---|
| `get_draw_geometry_info` | Inspect draw parameters and geometry configuration |
| `get_vertex_input_layout` | Inspect vertex attributes and buffer bindings |
| `get_mesh_indices` | Decode a bounded index range |
| `get_mesh_vertices` | Decode selected vertex attributes |
| `get_post_vs_geometry` | Retrieve post-vertex-processing geometry |
| `get_mesh_statistics` | Calculate geometry statistics |

Reuse existing Phase 8 and Phase 9 tools where possible.

### 13.1 Parameter Consistency

Use existing conventions for:

- Session ID.
- Capture identity.
- Event ID.
- Vertex range.
- Index range.
- Instance index.
- View index.
- Mesh stage.
- Output limit.

### 13.2 Default Behavior

Default to the currently selected GUI draw call when the request does not specify an event.

Return an explicit error if the selected event is not a compatible draw.

### 13.3 Bounded Output

Do not return an entire large mesh by default.

Support pagination, ranges, and attribute filtering.

### 13.4 Tool Descriptions

Clearly explain:

- Which stage is inspected.
- Whether the operation requires replay extraction.
- Whether the result represents a complete mesh or subset.
- Whether the tool modifies GUI state.
- What output limits apply.

---

## 14. Shared IPC and Multi-Agent Compatibility

Preserve the existing Shared IPC Service architecture.

### 14.1 Request Routing

Route geometry requests to the correct RenderDoc GUI session.

Validate capture and event identity.

### 14.2 Replay Thread Safety

All replay-dependent operations must execute in the correct RenderDoc context.

Do not directly invoke replay APIs from arbitrary IPC worker threads.

### 14.3 Large Data Transfer

Avoid transferring entire vertex or index buffers through IPC unnecessarily.

Prefer bounded decoded results.

Reuse existing binary transport where practical.

### 14.4 Concurrent Agents

Support scenarios such as:

- Claude Code inspecting vertex input.
- Codex inspecting Post-VS geometry.
- A Phase 13 measurement running or queued.
- The developer changing the selected event.

Coordinate replay-dependent operations safely.

### 14.5 Post-VS Extraction Coordination

If Post-VS extraction requires replay execution, coordinate it with GPU performance measurement and other replay-sensitive operations.

Do not allow two MCP clients to trigger conflicting replay operations.

### 14.6 Failure Handling

Handle:

- Capture unload.
- GUI disconnect.
- Replay shutdown.
- Invalid event.
- Invalid vertex or index range.
- Unsupported geometry stage.
- Post-VS extraction failure.
- IPC timeout.

Avoid stale results and indefinite blocking.

---

## 15. Performance and Memory Safety

Geometry datasets can be very large.

### 15.1 Limits

Enforce limits on:

- Vertex count per response.
- Index count per response.
- Attribute count.
- Post-VS output size.
- Geometry analysis workload.
- IPC payload size.
- Temporary memory allocations.

### 15.2 Integer Safety

Use overflow-safe arithmetic for:

- Buffer offsets.
- Strides.
- Index ranges.
- Instance addressing.
- Element sizes.
- Output allocation sizes.

### 15.3 Data Decoding

Do not allocate large buffers before validating requested ranges.

Avoid unnecessary copies of large GPU data.

### 15.4 Post-VS Processing

Post-VS extraction may involve replay work.

Measure its cost during testing.

Do not automatically perform expensive extraction for every geometry metadata request.

### 15.5 Temporary Resources

Release any temporary replay resources according to RenderDoc ownership rules.

Do not retain unbounded Post-VS caches.

---

## 16. Error Handling

Provide structured errors for:

- No RenderDoc GUI connected.
- No capture loaded.
- Capture changed.
- No event selected.
- Event is not a graphics draw.
- Unsupported draw type.
- Missing vertex buffer.
- Missing index buffer.
- Invalid buffer range.
- Unsupported vertex format.
- Invalid vertex or index reference.
- Unsupported geometry stage.
- Post-VS data unavailable.
- Replay extraction failed.
- Geometry analysis limit exceeded.
- Replay controller unavailable.
- IPC timeout.
- GUI disconnected.

Do not fabricate missing geometry data.

Distinguish unsupported geometry from an empty but valid draw.

---

## 17. Testing

Implement automated tests and real RenderDoc integration tests.

### 17.1 Unit Tests

Cover:

- Draw parameter serialization.
- Vertex buffer binding offsets.
- Index buffer decoding.
- Base vertex handling.
- First index handling.
- Vertex stride calculations.
- Attribute offsets.
- Per-instance input rates.
- Normalized integer decoding.
- Half-precision float decoding.
- Packed component formats.
- Bounds checking.
- Primitive restart.
- Triangle list decoding.
- Triangle strip decoding.
- Bounding box calculation.
- Degenerate triangle detection.
- Clip-space to NDC conversion.
- NaN and infinity handling.
- Bounded output.
- Capture identity validation.

### 17.2 Deterministic Geometry Fixtures

Use synthetic geometry fixtures containing known values.

Include:

- Non-indexed triangle.
- Indexed triangle.
- Indexed quad.
- Instanced geometry.
- Interleaved vertex attributes.
- Multiple vertex buffers.
- Per-instance attributes.
- Nonzero base vertex.
- Primitive restart.
- Degenerate triangles.
- Invalid numeric values.

Verify decoded values exactly where appropriate.

### 17.3 Integration Tests

Verify:

1. Vertex buffer bindings match RenderDoc.
2. Index buffer bindings match RenderDoc.
3. Input attributes match the pipeline state.
4. Vertex shader inputs can be correlated with attributes.
5. Indexed geometry decodes correctly.
6. Instancing is handled correctly.
7. Post-VS data can be retrieved where supported.
8. Post-VS output attributes match RenderDoc.
9. Position coordinate spaces are correctly identified.
10. Geometry statistics are accurate.
11. Capture changes invalidate stale references.
12. Multiple MCP clients can inspect geometry safely.

### 17.4 Manual Scenario A — Missing Mesh

1. Open a capture containing a missing or incorrectly rendered object.
2. Select its intended draw call.
3. Retrieve vertex input information.
4. Inspect indices and positions.
5. Retrieve Post-VS geometry.
6. Check transformed positions.
7. Compare results against the RenderDoc Mesh Viewer.

### 17.5 Manual Scenario B — Incorrect Vertex Layout

1. Select a draw call with multiple vertex attributes.
2. Retrieve input layout.
3. Retrieve vertex shader reflection.
4. Compare expected and actual attribute formats.
5. Inspect decoded vertex values.
6. Verify against RenderDoc.

### 17.6 Manual Scenario C — Instancing

1. Select an instanced draw.
2. Inspect instance count and instance input bindings.
3. Retrieve vertex attributes for different instances.
4. Verify per-instance values.
5. Inspect Post-VS data for selected instances where supported.

### 17.7 Manual Scenario D — GPU Performance

1. Open a capture with Phase 13 timing results.
2. Identify an expensive geometry-heavy draw.
3. Inspect draw counts and topology.
4. Retrieve relevant pipeline statistics.
5. Inspect vertex inputs and shader configuration.
6. Report measured findings and possible performance explanations.

### 17.8 Manual Scenario E — Multi-Agent

1. Connect Claude Code and Codex.
2. Open a capture in RenderDoc.
3. Have one agent inspect input geometry.
4. Have the other inspect Post-VS geometry.
5. Verify both results refer to the correct capture and draw.
6. Change the loaded capture.
7. Verify stale references are rejected.

### 17.9 GUI Non-Interference

Record:

- Selected event.
- Replay event.
- Loaded capture.
- Relevant Mesh Viewer state.

Run geometry inspection operations.

Verify that no unexpected GUI modifications occur.

If Post-VS extraction has observable side effects, document them.

### 17.10 Regression Tests

Ensure Phase 6–13.1 functionality remains operational.

Do not report tests as passed unless they were actually executed.

---

## 18. Bilingual Documentation

Update English and Japanese documentation.

Suggested files:

```text
docs/
  en/
    geometry.md
    examples/
      missing-mesh.md
      vertex-layout.md
      post-vs-inspection.md
      geometry-performance.md

  ja/
    geometry.md
    examples/
      missing-mesh.md
      vertex-layout.md
      post-vs-inspection.md
      geometry-performance.md
```

Adapt to the existing documentation organization.

### 18.1 Required Topics

Document:

- Geometry inspection overview.
- Supported draw types.
- Vertex input layouts.
- Index decoding.
- Vertex attribute decoding.
- Instancing behavior.
- Post-VS geometry.
- Coordinate space interpretation.
- Geometry statistics.
- GPU performance correlation.
- Known limitations.

### 18.2 Example — Missing Geometry

Developer prompt:

> Inspect the geometry used by the currently selected draw call. Check its vertex and index buffers, input layout, and post-vertex-shader positions. Identify any suspicious values that could explain why the object is not visible.

### 18.3 Example — Incorrect Vertex Format

Developer prompt:

> Compare the selected draw call's vertex input layout with the vertex shader input signature. Check whether attribute formats, offsets, and bindings are consistent.

### 18.4 Example — Vertex Transformation

Developer prompt:

> Inspect the input and post-VS positions of this mesh. Check whether the transformed vertices fall outside the visible clip-space region, and examine the relevant transformation constants.

### 18.5 Example — Geometry Performance

Developer prompt:

> Analyze the geometry processed by this expensive draw call. Compare its index count, instance count, vertex shader invocations, and available GPU timing measurements. Identify potential inefficiencies.

Ensure examples correspond to implemented capabilities.

---

## 19. Out of Scope

Do not implement:

- Full interactive 3D Mesh Viewer replacement.
- GPU mesh editing.
- Vertex buffer modification.
- Index buffer modification.
- Mesh export to arbitrary 3D formats.
- Shader execution tracing.
- Vertex shader step debugging.
- Pixel History.
- Automatic mesh repair.
- Automatic LOD generation.
- GPU geometry optimization.
- New GPU performance counter infrastructure.
- Major replay architecture redesign.
- Major Shared IPC Service redesign.

Mesh visualization may be added only as a lightweight optional feature using existing RenderDoc functionality.

---

## 20. Implementation Principles

**Use the existing RenderDoc capture.**

Do not reopen captures unnecessarily.

**Reuse buffer decoding.**

Phase 9 remains responsible for raw buffer access.

**Reuse shader reflection.**

Phase 10 remains responsible for shader interfaces.

**Preserve draw semantics.**

Indexed, non-indexed, instanced, and indirect draws require correct addressing.

**Distinguish coordinate spaces.**

Do not confuse input positions, clip-space positions, and NDC.

**Make Post-VS extraction explicit.**

Avoid unnecessary replay execution.

**Preserve GUI state.**

Do not unexpectedly change selected events or Mesh Viewer settings.

**Keep output bounded.**

Large meshes must be inspectable incrementally.

**Use measured performance data.**

Do not infer GPU bottlenecks from vertex counts alone.

**Maintain multi-agent safety.**

Replay-sensitive operations must be coordinated.

---

## 21. Deliverables

Provide:

### A. Implementation Summary

- Modified components.
- Added or extended MCP tools.
- Vertex input inspection.
- Index decoding.
- Vertex attribute decoding.
- Post-VS geometry retrieval.
- Geometry statistics.
- Performance integration.

### B. RenderDoc API Findings

- APIs used.
- Supported draw types.
- Supported mesh stages.
- Post-VS extraction behavior.
- Replay-thread requirements.
- Graphics API limitations.
- Unsupported geometry features.

### C. Validation Report

- Unit tests executed.
- Integration tests executed.
- Manual RenderDoc tests executed.
- Draw types tested.
- Graphics APIs tested.
- Multi-agent behavior.
- Known failures.

### D. Documentation

- English geometry documentation.
- Japanese geometry documentation.
- Practical debugging scenarios.
- Updated MCP tool reference.
- Known limitations.

---

## 22. Acceptance Criteria

Phase 14 is complete when:

- [ ] Agents can inspect geometry information for the selected graphics draw.
- [ ] Explicit event targeting works where supported.
- [ ] Vertex buffer bindings can be retrieved.
- [ ] Index buffer bindings can be retrieved.
- [ ] Vertex input attributes and formats can be retrieved.
- [ ] Vertex shader input signatures can be correlated with input layouts.
- [ ] Indexed geometry can be decoded correctly.
- [ ] Non-indexed geometry can be inspected.
- [ ] Base vertex and first index offsets are handled correctly.
- [ ] Instanced vertex input is handled correctly.
- [ ] Primitive restart is handled where supported.
- [ ] Vertex attribute values can be retrieved through bounded queries.
- [ ] Post-VS geometry can be retrieved for supported draw types.
- [ ] Post-VS output attributes are interpreted using reliable reflection information.
- [ ] Position coordinate spaces are identified correctly.
- [ ] Optional NDC conversion handles invalid W safely.
- [ ] Input and output geometry can be correlated where supported.
- [ ] Geometry bounds can be computed for supported position data.
- [ ] Invalid numeric values can be detected.
- [ ] Degenerate primitives can be identified for supported topologies.
- [ ] Analysis correctly identifies complete versus sampled results.
- [ ] Phase 13 performance results can be correlated with geometry information.
- [ ] Geometry inspection does not automatically trigger GPU counter collection.
- [ ] Post-VS extraction is coordinated with other replay-sensitive operations.
- [ ] Capture changes invalidate stale geometry references.
- [ ] GUI selection and replay state are not unexpectedly modified.
- [ ] Multiple MCP clients can inspect geometry safely.
- [ ] Output size and memory use are bounded.
- [ ] Existing Phase 6–13.1 functionality remains operational.
- [ ] Automated tests cover geometry decoding and addressing.
- [ ] Real RenderDoc captures are used for integration validation.
- [ ] English and Japanese documentation are updated.
- [ ] Known limitations are documented.

Unsupported RenderDoc features must be reported as unavailable or partially implemented.

Do not fabricate geometry data or claim unverified functionality is complete.

---

## Final Goal

After Phase 14, a developer should be able to select a draw call in RenderDoc and ask:

**"Inspect the geometry for this draw call. Check whether the vertex buffers, indices, input layout, and post-vertex-shader positions are correct."**

The coding agent should be able to:

1. Identify the selected draw call.
2. Retrieve its geometry configuration.
3. Inspect the vertex input layout.
4. Decode relevant vertex and index data.
5. Retrieve Post-VS geometry where supported.
6. Identify invalid or suspicious geometric data.
7. Correlate results with shader reflection.
8. Incorporate previously collected GPU performance measurements where relevant.
9. Explain findings based on actual capture data.

The workflow must not require manually exporting mesh data or reopening the capture.

**Phase 14 should make RenderEyeMCP capable of investigating geometry problems through structured, read-only mesh inspection while preserving the developer's existing RenderDoc debugging workflow.**
