# Phase 11 — Render Target & Pixel Inspection

## Objective

Extend RenderEyeMCP with read-only texture visualization, render target inspection, pixel-value retrieval, and depth/stencil inspection for captures already loaded in the RenderDoc GUI.

Phase 11 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 7 — RenderDoc GUI state discovery and synchronization.
- Phase 8 — Active capture, event, and pipeline-state inspection.
- Phase 9 — GPU resource metadata and buffer inspection.
- Phase 10 — Shader inspection, reflection, and resource binding correlation.

The goal is to allow AI coding agents to investigate the actual contents of GPU textures and render targets associated with a selected draw call or compute dispatch.

Typical debugging questions include:

- "What does the render target of this draw call look like?"
- "What is the pixel value at coordinate (640, 360)?"
- "Is this shadow map empty?"
- "What depth value is stored at this pixel?"
- "Which render target is bound to the selected draw call?"
- "Does this G-buffer contain valid normal values?"
- "Show the output texture written by this compute dispatch."

The agent must be able to answer these questions without requiring the developer to manually export textures or reopen the capture.

**Prioritize accurate pixel data, useful visual output, and integration with the existing active-capture workflow.**

Pixel History, shader execution debugging, and advanced GPU tracing are reserved for later phases.

---

## 1. Initial Repository Investigation

Before modifying the implementation, inspect the repository.

Identify:

1. RenderDoc extension implementation.
2. RenderDoc replay-controller integration.
3. Existing GUI and replay-thread scheduling.
4. Phase 6 Shared IPC Service.
5. Phase 7 capture identity and GUI state synchronization.
6. Phase 8 pipeline and render-target binding inspection.
7. Phase 9 texture metadata inspection.
8. Phase 10 shader resource binding correlation.
9. Existing texture and pixel inspection functionality.
10. Existing binary data transfer and MCP response mechanisms.
11. Existing tests and documentation.

Determine whether similar functionality already exists.

Reuse existing abstractions and tools wherever practical.

Do not introduce parallel resource identification, capture state, or replay-controller management mechanisms.

### 1.1 Verify Existing Dependencies

Confirm that the implementation can:

- Identify the currently loaded capture.
- Resolve the selected GUI event.
- Retrieve event-specific pipeline bindings.
- Identify texture resources.
- Retrieve texture metadata.
- Validate resource identity against the loaded capture.
- Schedule replay operations on the correct thread.

If a required earlier-phase capability is incomplete, document the limitation and implement only the minimum integration needed.

Avoid broad refactoring unrelated to Phase 11.

---

## 2. Investigate RenderDoc Texture and Replay APIs

Investigate the actual RenderDoc APIs supported by the installed version.

Relevant API concepts may include:

- `ReplayController`
- `ReplayOutput`
- `TextureDescription`
- `TextureDisplay`
- `TextureSave`
- `Subresource`
- `PixelValue`
- `CompType`
- `ResourceId`
- `PickPixel`
- `GetTextureData`
- `SaveTexture`
- `GetMinMax`
- `GetHistogram`
- `ReadbackOutputTexture`

These names are investigation targets.

Verify actual API signatures and behavior before implementing functionality.

### 2.1 Texture Data Access

Determine how to retrieve:

- Raw texture contents.
- Individual pixel values.
- Individual mip levels.
- Array slices.
- Depth slices.
- Multisampled texture contents.
- Relevant texture component values.

Investigate whether the APIs return:

- Original-format texture data.
- Converted pixel data.
- Rendered display data.
- Subresource-specific data.

Do not assume all texture formats can be handled identically.

### 2.2 Texture Display and Export

Determine whether RenderDoc provides supported mechanisms for:

- Rendering a texture into a displayable image.
- Exporting textures to common image formats.
- Selecting display channels.
- Applying display ranges.
- Visualizing depth textures.
- Handling floating-point and integer textures.
- Displaying individual subresources.

Prefer RenderDoc's existing texture display and export functionality where practical.

Avoid implementing a comprehensive GPU texture format decoder unnecessarily.

### 2.3 Replay Context Requirements

Determine whether texture inspection can operate through the existing RenderDoc GUI replay context.

Do not open a second copy of the capture as the default approach.

Do not assume that calls into the replay controller are safe from arbitrary IPC worker threads.

Use the supported replay-thread execution mechanism.

### 2.4 API Limitations

Record any limitations involving:

- Unsupported texture formats.
- Multisampled textures.
- Compressed textures.
- Depth/stencil access.
- GPU resource readback.
- Remote replay.
- Graphics API differences.
- Extension API restrictions.

Do not fabricate capabilities that are not supported by the installed RenderDoc version.

---

## 3. Texture and Subresource Identity

Every texture inspection request must preserve its capture and resource context.

### 3.1 Required Identity

Associate requests with:

- GUI session.
- Capture identity.
- Texture resource ID.
- Relevant event ID, when applicable.
- Requested subresource.

Use the existing Phase 7–9 identity mechanisms.

### 3.2 Subresource Selection

Support explicit selection of:

- Mip level.
- Array slice.
- Depth slice, where applicable.
- Multisample index or supported resolve behavior.
- Component interpretation where relevant.

Use RenderDoc's actual subresource model.

Do not assume that every texture has the same subresource dimensions.

### 3.3 Coordinate Validation

Pixel coordinates must be validated against the selected subresource dimensions.

For example, mip level 3 may be substantially smaller than mip level 0.

Do not validate every pixel request against the base texture dimensions.

Use integer-safe calculations.

### 3.4 Capture Changes

If the developer changes the loaded capture:

- Previously obtained texture IDs must be treated as stale.
- Inspection results must not be attributed to the new capture.
- Requests in progress must preserve or validate their original capture identity.

Return a structured capture-changed result where appropriate.

### 3.5 Event-Specific Texture Contents

A texture's contents may differ at different replay events.

Clearly distinguish:

- A resource's static metadata.
- Its contents at the current replay event.
- Its contents at a specifically requested event.

Do not silently move the replay position to inspect another event.

If arbitrary-event inspection requires changing replay state, document the limitation and preserve the Phase 8 read-only non-interference policy.

---

## 4. Texture Image Retrieval

Implement retrieval of a viewable image representing a texture.

Suggested MCP tool:

`get_texture_image`

Reuse an existing tool if suitable functionality already exists.

This is a core Phase 11 feature.

### 4.1 Required Functionality

Support:

- Texture resource ID.
- Mip level.
- Array slice.
- Depth slice where applicable.
- Sample selection where supported.
- Image dimensions or maximum output size.
- Display channel selection.
- Display range.

Use sensible defaults for optional parameters.

### 4.2 Image Representation

Support a standard image representation suitable for MCP clients.

Prefer PNG for lossless visual debugging.

Other formats may be supported when there is a demonstrated need.

If the existing MCP framework supports image content directly, use that mechanism.

Otherwise, use an existing project-supported binary transfer or artifact mechanism.

Do not assume that every MCP client supports arbitrary local image paths.

### 4.3 MCP Image Content

Investigate the MCP transport and client capabilities.

Prefer returning image content using the standard MCP image representation where supported.

Ensure the tool response includes:

- MIME type.
- Image dimensions.
- Texture identity.
- Subresource selection.
- Display interpretation.

Avoid wrapping large images in redundant JSON structures.

Do not invent nonstandard MCP image delivery mechanisms when the existing protocol already supports the use case.

### 4.4 Image Size Limits

GPU textures may be extremely large.

Do not return full-resolution images by default.

Introduce bounded output dimensions.

For example, a default maximum dimension of 1024 pixels may be reasonable, subject to existing project conventions and validation.

Preserve aspect ratio unless the caller explicitly requests otherwise.

Provide a documented maximum output dimension and payload size.

If the resulting encoded image exceeds transport limits, return a clear error or apply an explicitly documented bounded strategy.

Do not silently send multi-megabyte images through MCP without limits.

### 4.5 Texture Regions

Support optional region-based extraction.

Parameters may include:

- X coordinate.
- Y coordinate.
- Width.
- Height.

The region must be validated against the selected subresource.

Region extraction is useful for inspecting:

- Small rendering artifacts.
- Individual objects.
- UI elements.
- Shadow map regions.
- G-buffer areas.

Prefer extracting only the requested region when supported.

If the API requires processing a larger source image, enforce memory and size limits.

### 4.6 Channel Selection

Support common display modes:

- RGBA.
- RGB.
- Red.
- Green.
- Blue.
- Alpha.

Do not assume that all channels exist in every texture format.

Preserve clear semantics for missing channels.

### 4.7 Color and Numeric Interpretation

Texture display may involve:

- sRGB interpretation.
- Linear color values.
- HDR tone mapping.
- Floating-point ranges.
- Signed or unsigned integer formats.
- Component swizzling.
- Normalized values.

The returned image is a visualization, not necessarily the original numeric resource data.

Document any display transformations.

Do not use display-converted image values as substitutes for exact raw pixel values.

---

## 5. Pixel Value Inspection

Implement exact or API-supported pixel-value inspection.

Suggested MCP tool:

`get_pixel_value`

This is another core Phase 11 feature.

### 5.1 Required Parameters

Support:

- Texture resource ID.
- X coordinate.
- Y coordinate.
- Selected mip level.
- Selected array slice.
- Depth slice where applicable.
- Sample index or resolve mode where supported.
- Component interpretation when required.

Use the current capture and session resolution rules.

### 5.2 Pixel Data

Return the available pixel components in a typed representation.

Potential examples include:

- Floating-point RGBA.
- Unsigned integer components.
- Signed integer components.
- Depth values.
- Stencil values.

Do not assume every texture contains four floating-point color components.

Preserve the component type and interpretation.

### 5.3 Example Response

Conceptual example:

```json
{
  "resource_id": "resource-201",
  "subresource": {
    "mip": 0,
    "slice": 0,
    "sample": 0
  },
  "coordinate": {
    "x": 640,
    "y": 360
  },
  "format": "R16G16B16A16_FLOAT",
  "value": {
    "type": "float",
    "components": [0.5, 0.25, 0.75, 1.0]
  }
}
```

This is an illustrative response format.

Adapt it to existing conventions and the actual RenderDoc API.

### 5.4 Numeric Accuracy

Do not derive precise pixel values by decoding the PNG display image.

Use RenderDoc's supported pixel or resource-data inspection APIs.

Preserve:

- Integer values.
- Floating-point values.
- Component interpretation.
- Sample selection.
- Subresource identity.

Represent NaN and infinity explicitly in JSON-compatible form.

### 5.5 Coordinate Semantics

Document the coordinate origin and interpretation.

Be explicit about:

- Texture coordinates versus screen coordinates.
- Pixel indices versus normalized UV coordinates.
- Mip-specific dimensions.
- Array and depth slice selection.

Do not silently flip coordinates.

### 5.6 Unsupported Pixel Access

Some formats or sample configurations may not support direct pixel retrieval.

Return an explicit unsupported or unavailable result.

Do not substitute a color from a rendered preview without identifying it as a display-derived approximation.

---

## 6. Multiple Pixel Sampling

Support efficient inspection of a small number of pixels.

Prefer extending `get_pixel_value` with bounded coordinate arrays or adding a compact batch mechanism if necessary.

### 6.1 Use Cases

Examples:

- Compare a few neighboring pixels.
- Inspect a small set of G-buffer values.
- Sample several positions in a shadow map.
- Check whether a region contains unexpected values.

### 6.2 Limits

Enforce a conservative maximum number of samples per request.

Do not expose unrestricted texture-wide pixel enumeration.

### 6.3 Consistency

All pixels in a single batch must refer to the same validated capture, texture, subresource, and replay context.

Do not mix results obtained from different capture generations or replay events.

### 6.4 Raw Region Reads

Do not implement unrestricted rectangular raw-pixel dumping by default.

For large regions, image visualization or bounded statistical queries are more appropriate.

---

## 7. Render Target and Attachment Inspection

Integrate Phase 11 with the Phase 8 pipeline-state inspection.

Suggested MCP capability:

`get_render_targets`

Reuse the existing output attachment inspection functionality if available.

### 7.1 Graphics Output Bindings

For the currently selected draw call, retrieve:

- Color render targets.
- Depth attachment.
- Stencil attachment, where applicable.
- Relevant subresource selections.
- Attachment/resource identifiers.
- Available format information.

Handle graphics API differences through the existing RenderDoc pipeline abstraction.

### 7.2 Attachment Metadata

For each attachment, provide useful information such as:

- Resource ID.
- Resource name.
- Format.
- Dimensions.
- Mip level.
- Array slice.
- Sample count.
- Attachment index or binding location.

Reuse Phase 9 metadata inspection.

Do not duplicate entire texture descriptions in every response.

### 7.3 Direct Texture Inspection

The agent should be able to take a resource ID returned by render-target inspection and pass it directly to:

- `get_texture_info`
- `get_texture_image`
- `get_pixel_value`

Ensure identifier formats are consistent.

### 7.4 Selected Event Context

Distinguish the attachments bound at the selected event from the texture contents visible at the current replay event.

Do not promise a post-draw output image when the available replay state does not correspond to that draw.

### 7.5 Compute Outputs

Compute shaders may write to textures through storage/UAV bindings rather than framebuffer attachments.

Reuse Phase 8 and Phase 10 resource-binding information to locate these textures.

Do not classify compute storage textures as ordinary color render targets.

---

## 8. Depth and Stencil Inspection

Support practical inspection of depth/stencil resources.

This is essential for diagnosing:

- Missing objects.
- Incorrect occlusion.
- Shadow mapping problems.
- Depth precision issues.
- Incorrect depth pre-pass behavior.
- Stencil masking problems.

### 8.1 Depth Pixel Values

Support retrieval of depth values through the available RenderDoc APIs.

Preserve the actual depth representation and interpretation.

Do not automatically convert stored depth to linear world-space distance.

Depth linearization depends on projection parameters that may not be available or may not follow a conventional projection model.

### 8.2 Stencil Pixel Values

Investigate whether the installed RenderDoc APIs support retrieving stencil values separately.

Where supported, expose the actual stencil value.

Where unsupported, return an explicit limitation.

Do not treat the depth component as a replacement for stencil data.

### 8.3 Depth Visualization

Support a viewable depth image.

Prefer RenderDoc's existing texture display functionality.

Allow explicit display ranges where supported.

For example:

- Full normalized depth range.
- User-specified minimum and maximum.
- Narrow depth range for visual inspection.

Do not silently apply nonlinear depth transformations.

### 8.4 Stencil Visualization

Where supported, expose a stencil visualization.

Keep the representation clear and deterministic.

Do not assume stencil values represent colors.

### 8.5 Depth/Stencil Formats

Handle relevant depth/stencil formats as supported by RenderDoc.

Avoid implementing format-specific decoding assumptions without verifying the actual data layout.

---

## 9. Texture Statistics

Add lightweight statistical inspection where supported.

Suggested MCP tool:

`get_texture_statistics`

This is a secondary Phase 11 feature.

### 9.1 Minimum and Maximum

Investigate RenderDoc's available minimum/maximum pixel-value APIs.

Support:

- Resource ID.
- Subresource selection.
- Component interpretation.

Return per-component minimum and maximum values where available.

### 9.2 Histogram

Where supported, retrieve a bounded histogram.

Potential parameters:

- Selected channels.
- Value range.
- Subresource.
- Supported bin count or output structure.

Do not invent histogram precision or sampling semantics.

### 9.3 Useful Debugging Questions

Statistics should help answer questions such as:

- Is the render target entirely black?
- Are all alpha values zero?
- Does the depth texture contain meaningful variation?
- Is a floating-point texture saturated?
- Are there unexpectedly large or negative values?

Do not overinterpret statistics.

For example, a minimum and maximum of zero do not prove that a shader never executed.

### 9.4 Resource Cost

Statistics may require GPU processing.

Do not automatically compute histograms whenever texture metadata is requested.

Only perform statistical inspection when explicitly requested.

---

## 10. Texture Comparison

Texture comparison is a lower-priority capability.

Implement only if the core Phase 11 features are complete and the existing APIs support it safely.

### 10.1 Comparison Targets

Potential operations include:

- Comparing two selected texture subresources.
- Comparing two image regions.
- Computing basic numeric differences.
- Producing a visual difference image.

### 10.2 Capture Scope

Prefer comparison within the same loaded capture.

Cross-capture comparisons require reliable access to two capture contexts and additional lifecycle management.

Do not introduce a second replay session solely for comparison in Phase 11.

### 10.3 Comparison Semantics

If comparison is implemented, explicitly define:

- Component interpretation.
- Numeric conversion.
- Resolution mismatch behavior.
- Channel mapping.
- Difference metric.
- Display scaling.

Do not compare tone-mapped previews and present the result as an exact GPU resource difference.

### 10.4 Deferral

If texture comparison would require substantial additional infrastructure, defer it to a later phase.

It must not delay the core texture and pixel inspection capabilities.

---

## 11. MCP Tool Surface

Keep the tool interface compact.

Suggested capabilities:

| Tool | Purpose |
|---|---|
| `get_texture_image` | Retrieve a bounded visual representation of a texture |
| `get_pixel_value` | Retrieve exact or API-supported pixel components |
| `get_render_targets` | Identify attachments bound to an event |
| `get_texture_statistics` | Retrieve min/max and histogram data |

Continue using Phase 9:

- `list_resources`
- `get_resource_info`
- `get_texture_info`

Do not duplicate Phase 9 metadata functionality.

### 11.1 Optional Batch Operations

Multiple pixel sampling may be exposed through `get_pixel_value` rather than through a separate tool.

### 11.2 Tool Parameters

Use consistent naming for:

- Session ID.
- Capture identity.
- Event ID.
- Resource ID.
- Mip level.
- Array slice.
- Depth slice.
- Sample index.
- Pixel coordinates.
- Image dimensions.
- Display range.

### 11.3 Tool Discoverability

Tool descriptions should clearly distinguish:

- Metadata queries.
- Exact numeric pixel inspection.
- Visual image retrieval.
- Statistical queries.

Agents should not confuse display-converted image colors with original resource values.

---

## 12. Image Delivery and Data Transport

Image transfer requires special attention.

### 12.1 Binary IPC

Investigate existing IPC support for binary payloads.

Avoid unnecessary intermediate Base64 encoding when the IPC transport already supports binary data.

Encode data into MCP image content only at the appropriate boundary.

### 12.2 Standard MCP Content Types

Use protocol-supported response types.

Return image content when supported by the MCP server and client integration.

Metadata may accompany image content through structured or text content as appropriate.

### 12.3 Output Size

Enforce maximums for:

- Image width.
- Image height.
- Encoded image size.
- Number of images per request.
- Intermediate memory allocation.

### 12.4 Avoid Persistent Temporary Files

Prefer in-memory processing when practical.

If temporary files are required:

- Use safe temporary paths.
- Avoid filename collisions.
- Clean files after use.
- Do not overwrite user captures.
- Do not leak files between requests.

### 12.5 Security and Input Validation

Treat MCP request parameters as untrusted input.

Validate numeric dimensions, coordinates, format selections, and output options.

Do not allow image export parameters to become arbitrary filesystem write operations.

---

## 13. GUI Non-Interference

All Phase 11 operations should be read-only from the developer's perspective.

Inspection must not unexpectedly:

- Change the loaded capture.
- Change the selected draw call.
- Change the replay event.
- Change the displayed texture.
- Change channel or range settings in the existing Texture Viewer.
- Open additional RenderDoc windows.
- Close existing replay outputs.

### 13.1 Separate Visualization State

If image generation requires a `ReplayOutput` or texture display configuration, investigate whether an independent, appropriately owned output can be used without modifying the GUI's existing Texture Viewer.

Do not borrow and reconfigure a developer-visible output without explicit authorization.

### 13.2 Resource Lifecycle

Ensure temporary replay outputs or other inspection resources are properly released.

Respect their thread ownership and shutdown requirements.

### 13.3 Unsupported Non-Interfering Operations

If a requested inspection would necessarily modify developer-visible replay state, report the limitation.

Do not silently change the GUI and attempt to restore it afterward.

---

## 14. Replay State Consistency

Pixel contents are event-dependent.

This must be treated as a core correctness requirement.

### 14.1 Current Event

When an agent requests texture contents without an explicit event ID, use the project's established current replay-event semantics.

Do not assume that the selected event and replay event are identical.

### 14.2 Explicit Event Requests

If an event ID is supplied, verify that the requested texture contents correspond to that event.

If the installed API cannot inspect the requested event without modifying GUI replay state, return a meaningful unsupported result.

Do not return contents from another event while labeling them as the requested event.

### 14.3 Snapshot Identity

Inspection results should contain sufficient context:

- Session identity.
- Capture identity.
- Resource identity.
- Subresource.
- Replay event identity, when relevant.

### 14.4 Concurrent GUI Interaction

Consider the following scenario:

1. Agent starts a pixel inspection request.
2. Developer changes the selected event.
3. Developer changes the loaded capture.
4. Replay resources are invalidated.

The implementation must safely detect invalid state or return a correctly identified result from a validated snapshot.

Do not mix state from multiple captures or events.

---

## 15. Multi-Agent Concurrency

Preserve Phase 6 multi-agent behavior.

Both Claude Code and Codex should be able to request texture and pixel information through the same Shared IPC Service.

### 15.1 Request Isolation

Ensure:

- Each request has a unique identity.
- Responses are routed to the correct client.
- Resource identity is validated.
- Temporary output resources are not shared unsafely.
- Concurrent image requests cannot overwrite each other's results.

### 15.2 Replay Thread Scheduling

Serialize replay operations where required by RenderDoc.

Do not hold shared IPC locks while waiting for replay operations.

### 15.3 Large Image Requests

Large image transfers must not indefinitely block smaller metadata or pixel queries.

Apply appropriate limits and scheduling.

Avoid a complex priority scheduler unless necessary.

### 15.4 Disconnection Handling

Handle:

- MCP client disconnect.
- Shared IPC Service restart.
- RenderDoc GUI shutdown.
- Capture unload.
- Replay controller loss.

Ensure request cleanup and resource release.

---

## 16. Testing

Implement automated tests and real RenderDoc integration tests where practical.

### 16.1 Unit Tests

Cover:

- Texture identity validation.
- Capture generation validation.
- Subresource selection.
- Mip-dependent dimensions.
- Pixel coordinate bounds.
- Region bounds.
- Integer overflow protection.
- Image size limits.
- Output format validation.
- Channel selection.
- Numeric value serialization.
- Special floating-point values.
- Invalid sample indices.
- Unsupported formats.
- IPC payload handling.
- Temporary resource cleanup.

### 16.2 Image Processing Tests

Use deterministic image fixtures.

Verify:

- Pixel coordinate mapping.
- Aspect ratio preservation.
- Region cropping.
- Downscaling.
- Channel selection.
- Alpha handling.
- Image encoding.
- Output dimensions.
- Output size limits.

Do not depend only on visual inspection.

### 16.3 Pixel Correctness Tests

Test representative formats:

- 8-bit normalized color.
- 32-bit floating-point color.
- Integer textures.
- Depth textures.
- Stencil-containing textures, where supported.
- Multisampled textures, where supported.

Verify values against known data or RenderDoc's own pixel inspection.

### 16.4 Integration Tests

Verify:

1. A texture can be identified from an event binding.
2. Texture metadata is available through Phase 9.
3. A viewable texture image can be retrieved.
4. Mip and array slice selection works.
5. Region extraction works.
6. Pixel values match RenderDoc.
7. Depth pixel inspection works where supported.
8. Stencil inspection works where supported.
9. Min/max values can be retrieved where supported.
10. Histograms can be retrieved where supported.
11. Capture changes invalidate stale resource IDs.
12. Concurrent MCP clients can inspect the same capture.

### 16.5 Manual Debugging Workflows

**Scenario A — Inspect a Color Render Target**

1. Open a graphics capture.
2. Select a draw call.
3. Identify its color render target.
4. Retrieve texture metadata.
5. Request a viewable image.
6. Compare the image against RenderDoc's Texture Viewer.

**Scenario B — Inspect a Pixel**

1. Select a render target.
2. Choose a known pixel coordinate.
3. Retrieve numeric component values.
4. Compare against RenderDoc's pixel inspection.
5. Verify coordinate and component semantics.

**Scenario C — Inspect a Depth Texture**

1. Select a draw using a depth attachment.
2. Identify the depth resource.
3. Retrieve depth metadata.
4. Retrieve a depth visualization.
5. Query selected depth values.
6. Compare against RenderDoc.

**Scenario D — Inspect a Compute Output Texture**

1. Select a compute dispatch.
2. Identify its bound storage/UAV texture.
3. Retrieve resource metadata.
4. Retrieve a viewable image.
5. Inspect selected pixels.

**Scenario E — Multi-Agent Inspection**

1. Connect Claude Code and Codex.
2. Open a capture in RenderDoc.
3. Have one agent retrieve a texture image.
4. Have the other query pixel values.
5. Confirm both results refer to the correct capture and resource.
6. Change the loaded capture.
7. Confirm stale resource identities are rejected.

### 16.6 GUI Non-Interference Test

Record:

- Loaded capture.
- Selected event.
- Replay event.
- Currently displayed texture.
- Texture Viewer configuration where observable.

Perform Phase 11 operations.

Verify that developer-visible GUI state remains unchanged.

### 16.7 Regression Tests

Confirm that:

- Phase 6 IPC and multi-agent behavior works.
- Phase 7 GUI state discovery works.
- Phase 8 event and pipeline inspection works.
- Phase 9 resource and buffer inspection works.
- Phase 10 shader inspection works.

Do not claim tests passed unless they were executed.

---

## 17. Documentation

Update the README and technical documentation.

Include:

- Texture inspection overview.
- How to retrieve the current render target.
- How to retrieve texture images.
- MCP image response behavior.
- How to query exact pixel values.
- Subresource selection rules.
- Depth/stencil inspection.
- Display conversion semantics.
- Coordinate conventions.
- Texture statistics.
- Supported formats.
- Image and payload limits.
- Replay event consistency rules.
- Known RenderDoc API limitations.

### Example Workflow A — Inspect Render Target

```text
Developer:
"Show me the render target used by the
currently selected draw call."

Agent:
1. Resolves the selected event.
2. Retrieves the bound render targets.
3. Identifies the desired texture.
4. Requests its image.
5. Presents the image with relevant metadata.
```

### Example Workflow B — Inspect Pixel Value

```text
Developer:
"What is the pixel value at (640, 360)
in the current render target?"

Agent:
1. Resolves the current render target.
2. Identifies its texture resource.
3. Requests pixel (640, 360).
4. Returns the typed component values.
```

### Example Workflow C — Investigate Depth

```text
Developer:
"Why might this object be failing the depth test?"

Agent:
1. Retrieves the selected draw call.
2. Inspects its depth test configuration.
3. Identifies the depth attachment.
4. Queries relevant depth pixel values.
5. Retrieves depth visualization if useful.
6. Reports observations and possible causes.
```

### Example Workflow D — Inspect a G-buffer

```text
Developer:
"Inspect the normal and roughness G-buffer
textures for this draw call."

Agent:
1. Resolves the relevant render targets.
2. Retrieves their texture metadata.
3. Requests viewable texture images.
4. Retrieves specific pixel values.
5. Correlates the findings with shader bindings
   from Phase 10.
```

---

## 18. Out of Scope

Do not implement the following in Phase 11:

- Pixel History.
- Shader execution tracing.
- Shader breakpoints.
- Shader variable stepping.
- Mesh visualization.
- Vertex and index buffer visualization.
- GPU performance profiling.
- Shader replacement.
- Capture opening or closing.
- Automatic replay event navigation.
- Persistent GUI Texture Viewer manipulation.
- General-purpose image editing.
- Texture modification.
- Large-scale cross-capture comparison infrastructure.
- Automated rendering bug diagnosis.
- Major IPC architecture redesign.

Phase 11 is focused on accurate and safe texture, render-target, and pixel inspection.

---

## 19. Implementation Principles

**Use the existing RenderDoc GUI capture.**

Do not reopen the capture unnecessarily.

**Distinguish pixel data from visualization.**

An image rendered for human or AI viewing is not equivalent to the original typed pixel values.

**Respect replay-event context.**

Texture contents may change between events.

**Preserve resource and subresource identity.**

Do not mix textures, mips, slices, samples, or captures.

**Prefer RenderDoc's built-in capabilities.**

Avoid implementing unnecessary texture decoders and GPU image conversion pipelines.

**Keep image outputs bounded.**

Do not return unrestricted full-resolution GPU textures.

**Support the existing debugging workflow.**

Resource IDs should flow naturally from pipeline inspection to texture inspection.

**Avoid GUI interference.**

Do not unexpectedly modify the developer's Texture Viewer or replay state.

**Preserve multi-agent compatibility.**

Concurrent MCP clients must remain safe.

**Prioritize practical debugging.**

Focus on features that help identify real rendering problems.

---

## 20. Deliverables

When implementation is complete, provide:

### Implementation Summary

- Modified components.
- New or extended MCP tools.
- Texture image retrieval implementation.
- Pixel-value inspection implementation.
- Render-target integration.
- Depth/stencil inspection.
- Image transport mechanism.

### RenderDoc API Findings

- APIs used for texture image retrieval.
- APIs used for pixel inspection.
- Depth/stencil support.
- Subresource behavior.
- Supported texture formats.
- Replay-thread restrictions.
- Event-dependent texture access limitations.

### Data Transport and Safety

- MCP image content support.
- IPC binary transport behavior.
- Image size limits.
- Memory allocation limits.
- Temporary resource cleanup.
- GUI non-interference guarantees.

### Test Report

- Unit tests executed.
- Integration tests executed.
- Manual GUI tests executed.
- Graphics APIs tested.
- Texture formats tested.
- Multi-agent test results.
- Known limitations and unverified scenarios.

### Documentation

- Updated README.
- MCP tool documentation.
- Image and pixel inspection examples.
- Known limitations.

---

## 21. Acceptance Criteria

Phase 11 is complete when:

- [ ] Agents can identify render targets bound to the currently selected draw call.
- [ ] Existing Phase 9 texture metadata tools integrate with Phase 11.
- [ ] Agents can retrieve a viewable texture image from the active capture.
- [ ] Texture image retrieval supports explicit mip and slice selection where applicable.
- [ ] Sample selection or resolve semantics are explicit for multisampled textures.
- [ ] Image retrieval supports bounded output dimensions.
- [ ] Region-based image retrieval works for supported textures.
- [ ] Channel selection is available where supported.
- [ ] Display conversion is distinguished from original resource values.
- [ ] Agents can retrieve typed pixel values at explicit coordinates.
- [ ] Pixel coordinates are validated against subresource dimensions.
- [ ] Depth values can be inspected where supported.
- [ ] Stencil values are inspected or explicitly reported unsupported.
- [ ] Depth visualization is available for supported depth textures.
- [ ] Texture min/max and histogram capabilities are available where supported, or limitations are documented.
- [ ] Render targets and compute output textures can be resolved through existing resource bindings.
- [ ] Requests preserve capture, resource, subresource, and relevant event identity.
- [ ] Stale resource identifiers cannot be silently reused across captures.
- [ ] Read-only inspection does not unexpectedly modify developer-visible GUI state.
- [ ] Image transfers and memory use are bounded.
- [ ] Multiple MCP clients can inspect textures concurrently.
- [ ] IPC disconnects and capture unloads are handled safely.
- [ ] Existing Phase 6–10 functionality remains operational.
- [ ] Automated tests validate pixel and image correctness.
- [ ] Real RenderDoc captures are used for integration testing.
- [ ] Documentation and known limitations are updated.

If an acceptance criterion cannot be satisfied because of a RenderDoc API limitation, document that limitation and mark the criterion incomplete or partially implemented.

Do not present unavailable or approximated pixel values as exact data.

---

## Final Goal

After Phase 11, a developer should be able to inspect the actual visual and numeric contents of GPU textures associated with the current RenderDoc session.

For example:

**"Show me the render target produced by this draw call, and inspect the pixel values around the broken area."**

The AI agent should be able to:

1. Identify the selected draw call.
2. Determine its render targets.
3. Retrieve the appropriate texture metadata.
4. Display a bounded image of the render target.
5. Inspect exact pixel values.
6. Examine depth/stencil information where relevant.
7. Correlate the observations with shader and resource information from previous phases.
8. Report findings grounded in the actual capture.

The agent must not require manual texture export, capture reopening, or control of the developer's RenderDoc GUI.

Phase 11 should establish the visual and pixel-level inspection foundation needed for subsequent geometry inspection and advanced GPU debugging.
