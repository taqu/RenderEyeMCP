# Phase 18 — Go MCP Bridge Migration

## Objective

Replace RenderEyeMCP's Python MCP Bridge with a Go implementation while preserving its existing MCP interface, tool behavior, and communication with the Shared IPC Service.

Phase 18 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 16 — IPC Protocol Contract & Compatibility Tests.
- Phase 17 — Go Shared IPC Service Migration.

At the end of Phase 17, the expected architecture is:

```text
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Go Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The Phase 18 target is:

```text
Claude Code ── Go MCP Bridge ──────┐
                                   │
Codex ─────── Go MCP Bridge ──────┼── Go Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The Go Shared IPC Service must remain an independent process.

The Python RenderDoc Extension must continue accessing RenderDoc's Replay APIs.

**The primary success criterion is that coding agents can use the Go MCP Bridge as a drop-in replacement for the Python MCP Bridge, without changes to existing RenderDoc functionality or IPC protocol semantics.**

The long-term roadmap remains:

- Phase 18 — Go MCP Bridge.
- Phase 19 — Single Binary & Cross-Platform Distribution.
- Phase 20 — Reliability, Migration, and Python Deprecation.

Prioritize compatibility, installation simplicity, and operational reliability over adding MCP features.

---

## 1. Inspect the Existing Repository

Before implementing the Go MCP Bridge, investigate the actual Python implementation.

Identify:

1. Python MCP server initialization.
2. MCP SDK or framework in use.
3. MCP protocol version and advertised capabilities.
4. MCP tool registration.
5. Tool names and descriptions.
6. Tool argument schemas.
7. Tool response formats.
8. Tool error semantics.
9. Text, image, and other content types.
10. MCP resources and prompts, if implemented.
11. Shared IPC client implementation.
12. Connection and retry behavior.
13. Daemon startup behavior.
14. Configuration loading.
15. Logging behavior.
16. Executable entry points.
17. Python package version reporting.
18. Existing automated and manual tests.

Inspect the Phase 16 protocol documentation and the Phase 17 Go implementation.

Do not assume that the previous design documents accurately represent every tool currently implemented.

### 1.1 Establish the Complete MCP Surface

Enumerate every MCP feature exposed by the Python Bridge.

This includes more than just tools.

Check for:

- Tools.
- Resources.
- Resource templates.
- Prompts.
- Notifications.
- Completion.
- Logging.
- Progress reporting.
- Cancellation behavior.
- Other advertised capabilities.

Only migrate features that actually exist.

Do not advertise unsupported MCP capabilities.

### 1.2 Tool Inventory

For every implemented tool, record:

| Property | Required information |
|---|---|
| Name | Exact MCP tool identifier |
| Description | Existing description and usage guidance |
| Input schema | Exact accepted arguments |
| Output schema | If currently declared |
| Content types | Text, image, structured content, etc. |
| Error behavior | Tool errors and protocol errors |
| IPC operation | Actual backend operation |
| Timeout | Existing behavior |
| Side effects | Metadata query or explicit replay operation |
| Limits | Result size and pagination |
| Availability | Relevant RenderDoc capability restrictions |

This inventory is the migration baseline.

### 1.3 Detect Dynamic Tool Behavior

Determine whether tools are:

- Registered statically.
- Generated dynamically.
- Conditional on configuration.
- Conditional on RenderDoc capabilities.
- Conditional on connection state.

Do not assume all tools are always available.

Preserve the existing behavior unless a change is explicitly justified.

---

## 2. Migration Principles

Follow these principles throughout Phase 18.

**Maintain MCP compatibility.**

Preserve existing tool identifiers, input contracts, outputs, and error semantics.

**Reuse Phase 17 IPC infrastructure.**

Do not implement another independent Go IPC protocol client.

**Keep RenderDoc logic in the Extension.**

The Go Bridge must not call RenderDoc Replay APIs directly.

**Keep the Shared IPC Service independent.**

Do not combine Bridge and Service during Phase 18.

**Preserve stdio transport.**

Coding agents must continue launching the MCP Bridge as a local stdio server.

**Keep stdout protocol-clean.**

Never write diagnostics or progress messages directly to stdout outside the MCP protocol.

**Avoid unnecessary abstractions.**

The Bridge should remain a thin adapter between MCP and the existing IPC protocol.

**Preserve the Python implementation during migration.**

Retain the Python Bridge for compatibility testing and rollback.

**Do not introduce unrelated functionality.**

New GPU debugging tools and protocol changes are outside this phase.

---

## 3. Official Go MCP SDK

Prefer the official MCP Go SDK:

```text
github.com/modelcontextprotocol/go-sdk/mcp
```

Documentation:

https://github.com/modelcontextprotocol/go-sdk

### 3.1 Verify SDK Compatibility

Select a supported, stable SDK version.

Confirm compatibility with the MCP protocol versions required by existing coding agents.

Inspect the actual SDK API before implementing the server.

Do not assume examples from different SDK versions remain source-compatible.

### 3.2 Server Initialization

Implement a Go MCP server with:

- The same server identity where appropriate.
- Compatible server version information.
- Appropriate advertised capabilities.
- stdio transport.
- Clean initialization and shutdown.

### 3.3 Tool Registration

Use the SDK's supported Tool registration mechanisms.

The Go SDK may infer JSON Schemas from Go types.

**Do not rely on automatically generated schemas without comparing them with the existing Python schemas.**

If inferred schemas differ in meaningful ways, use explicit schemas or an appropriate adapter.

### 3.4 Tool Results

Preserve the MCP result representation.

Depending on the existing tool, this may include:

- `Content`.
- `StructuredContent`.
- `IsError`.
- Text content blocks.
- Image content blocks.
- Other supported content blocks.

Do not automatically convert every tool result into a JSON string.

### 3.5 SDK Semantics

Investigate SDK handling of:

- Schema validation.
- Required and optional arguments.
- Default values.
- Null values.
- Content encoding.
- Structured outputs.
- Tool errors.
- Context cancellation.

Where the SDK defaults differ from Python, implement a compatibility adapter rather than modifying the user-facing contract.

---

## 4. Go Project Organization

Extend the Go module introduced in Phase 16 or Phase 17.

Do not create an unrelated Go module without justification.

An illustrative structure is:

```text
go/
  go.mod
  go.sum

  cmd/
    rendereye-ipc/
      main.go

    rendereye-mcp/
      main.go

  internal/
    protocol/
      ...

    ipcclient/
      ...

    service/
      ...

    mcpbridge/
      ...
```

Adapt this structure to the existing Go repository layout.

### 4.1 Separate Responsibilities

Keep clear boundaries between:

- MCP server initialization.
- Tool registration.
- Tool argument validation.
- IPC request execution.
- Response translation.
- Configuration.
- Logging and lifecycle management.

### 4.2 Avoid Tool-Specific IPC Implementations

Do not create separate TCP clients for individual MCP tools.

All tool handlers must use the shared Go IPC client abstraction.

### 4.3 Avoid Overengineering

Do not introduce:

- An application plugin framework.
- A new service discovery system.
- A generic dependency injection container.
- A custom MCP protocol implementation.
- A new RPC serialization framework.

Prefer small, testable Go components.

---

## 5. Reuse the Existing IPC Client

Phase 16 introduced a minimal Go IPC probe, and Phase 17 implemented the Go Shared IPC Service.

Reuse the established protocol implementation.

### 5.1 IPC Connection

The Go MCP Bridge should connect to the Shared IPC Service using the existing configured endpoint.

The current default is:

```text
127.0.0.1:37020
```

Preserve the actual configuration contract.

### 5.2 Client Registration

Use the existing IPC protocol to register the Go MCP Bridge.

Preserve:

- Client role.
- Registration messages.
- Session identification.
- Connection state.
- Request correlation.

### 5.3 Request Routing

The normal request path must be:

```text
MCP Tool Call
     |
     v
Go MCP Bridge
     |
     v
Go IPC Client
     |
     v
Go Shared IPC Service
     |
     v
Python RenderDoc Extension
```

Responses must follow the reverse path.

### 5.4 Do Not Change the Wire Protocol

Do not add Go-specific IPC fields merely to simplify the Bridge.

Phase 17's service must remain compatible with the existing Python clients.

### 5.5 IPC Error Handling

Preserve existing handling for:

- Service unavailable.
- Session unavailable.
- Capture unloaded.
- Invalid event.
- Unsupported operation.
- Timeout.
- Connection loss.
- Backend error.

### 5.6 Large Payloads

Reuse existing binary and large-message support.

Do not serialize large binary data through an unnecessary intermediate string representation.

---

## 6. MCP Tool Contract Compatibility

This is the most important part of Phase 18.

### 6.1 Preserve Tool Names

Every existing Python MCP tool must retain its name.

Do not rename tools to follow Go naming conventions.

For example, if a Python tool is named:

```text
get_pipeline_state
```

The Go implementation must expose the same name.

### 6.2 Preserve Tool Descriptions

Preserve tool descriptions and parameter documentation as closely as practical.

Descriptions influence how coding agents choose tools.

An apparently harmless description change may alter agent behavior.

Do not simplify or rewrite descriptions merely because the implementation language changed.

### 6.3 Preserve Input Schemas

For every tool, compare:

- Parameter names.
- JSON types.
- Required parameters.
- Optional parameters.
- Default values.
- Enumerations.
- Nested object schemas.
- Array schemas.
- Numeric constraints.
- String constraints.
- Additional property handling.
- Nullability.

Avoid the common Go migration error of treating every non-pointer field as required or replacing omitted values with zero values.

### 6.4 Preserve Output Schemas

Where output schemas are declared, preserve them.

Where output schemas are not explicitly declared, preserve the actual result representation.

### 6.5 Preserve Optional and Null Semantics

Distinguish:

- Parameter omitted.
- Parameter explicitly set to `null`.
- Parameter set to zero.
- Parameter set to false.
- Empty string.
- Empty list.
- Empty object.

Use pointer types or custom decoding only where required.

Do not introduce different defaults.

### 6.6 Numeric Compatibility

Ensure correct handling of:

- Large integer identifiers.
- Floating-point measurements.
- GPU counters.
- Event IDs.
- Resource IDs.
- Buffer offsets.
- Pixel coordinates.

Avoid loss of precision through `float64` conversion of large integers.

### 6.7 Preserve Tool Ordering Where Relevant

If tools are registered or presented in a stable order by the Python implementation, preserve that order when practical.

However, do not depend on list ordering for correctness unless it is explicitly part of the existing contract.

### 6.8 Dynamic Tool Availability

If tool availability depends on server configuration or runtime state, preserve the relevant semantics.

Do not remove tools merely because RenderDoc is temporarily disconnected unless the Python implementation does so.

---

## 7. Tool Registration Strategy

Avoid manually duplicating large quantities of tool metadata across languages without a verification mechanism.

### 7.1 Inventory-Driven Registration

Prefer a central Go Tool registry that maps:

- MCP Tool definition.
- Input schema.
- Backend IPC operation.
- Response translation.
- Execution characteristics.

Keep the registry straightforward.

### 7.2 Shared Tool Metadata

If the existing Python implementation already maintains machine-readable Tool definitions, investigate whether they can be reused.

Do not introduce a source-code generator solely for this phase unless it materially reduces drift and maintenance cost.

### 7.3 Explicit Schemas

For complex tools, explicit JSON Schemas may be preferable to automatically inferred Go schemas.

The primary requirement is compatibility, not maximizing use of SDK convenience features.

### 7.4 Generic IPC Tool Adapter

Where existing Python tools simply forward validated requests to the IPC Service, implement an equivalent reusable Go adapter.

The adapter should handle:

1. Argument decoding.
2. Existing default values.
3. IPC request construction.
4. Backend execution.
5. Error translation.
6. MCP result construction.

Keep specialized result transformations only where necessary.

### 7.5 Preserve Specialized Tools

Some tools may require special handling, including:

- Texture image retrieval.
- Binary buffer results.
- Shader debug traces.
- GPU measurement operations.
- Long-running job status.
- Structured content output.

Do not force these through a lossy generic JSON-only adapter.

---

## 8. MCP Response Compatibility

Implement response translation carefully.

### 8.1 Text Content

Preserve expected text formatting and JSON serialization semantics where they are part of the Python Bridge behavior.

### 8.2 Structured Content

If Python tools return MCP `StructuredContent`, preserve the structured response.

Do not replace structured results with text-only responses.

### 8.3 Image Content

For tools returning images:

- Preserve MIME type.
- Preserve original image bytes.
- Preserve content ordering.
- Use the SDK's supported image content representation.

Avoid double Base64 encoding.

### 8.4 Multiple Content Blocks

If a tool returns both text and image content, preserve the block order and types.

### 8.5 Tool Errors

Distinguish:

- MCP protocol errors.
- Tool execution errors.
- IPC transport errors.
- RenderDoc operation errors.

Do not convert every backend failure into an MCP protocol-level exception.

### 8.6 Error Semantics

Preserve the existing Python Bridge's use of error content and `IsError`.

### 8.7 Empty Results

Preserve existing behavior for:

- Empty lists.
- Empty objects.
- Null values.
- Missing optional fields.
- No content.
- Unsupported capabilities.

Do not fabricate data to satisfy a Go type declaration.

### 8.8 Result Size

Preserve existing output limits and pagination.

Do not increase default response sizes unintentionally.

---

## 9. Long-Running Operations and Cancellation

RenderEyeMCP supports operations that may take longer than ordinary metadata queries.

Examples include:

- GPU counter collection.
- Geometry extraction.
- Pixel History.
- Shader debugging.

### 9.1 Existing Job Semantics

Reuse the existing backend job model.

Do not introduce an independent Go-side job scheduler unless the Python Bridge already performs equivalent scheduling.

### 9.2 MCP Cancellation

Investigate cancellation support in the selected Go MCP SDK.

Map cancellation to the existing IPC behavior.

Do not assume cancelling an MCP request safely interrupts RenderDoc replay execution.

### 9.3 Timeouts

Preserve tool-specific timeout behavior.

Use Go contexts appropriately.

### 9.4 Disconnection

If the coding agent terminates while a tool is running:

- Release Bridge-owned resources.
- Close connections cleanly.
- Follow existing backend cancellation semantics.
- Avoid leaving orphaned Bridge goroutines.

### 9.5 Status Polling

Preserve existing measurement or debugging status tools.

Do not automatically block an MCP request until a long-running backend operation completes if the Python implementation returns a job ID.

### 9.6 Partial Results

Preserve existing partial, failed, cancelled, and truncated result semantics.

---

## 10. MCP Bridge Lifecycle

The Go MCP Bridge will be launched independently by each coding agent.

### 10.1 Default Execution

The default executable behavior should start the MCP stdio server.

For example:

```text
rendereye-mcp
```

This is a development-stage command name.

Final executable packaging is deferred to Phase 19.

### 10.2 stdio Ownership

Reserve stdout exclusively for MCP messages.

Write diagnostics to stderr or the existing configured log destination.

### 10.3 Agent Shutdown

When the MCP client disconnects or stdin closes:

- Stop accepting new work.
- Cancel Bridge-owned contexts.
- Close the IPC connection.
- Release resources.
- Exit cleanly.

Do not terminate the shared daemon merely because one MCP Bridge exits.

### 10.4 Service Connection

Preserve Python Bridge behavior for connecting to the existing daemon.

### 10.5 Service Autostart

Investigate whether the Python Bridge automatically starts the Shared IPC Service.

If it does, preserve the externally observable behavior where necessary.

However, keep service process management separate from MCP Tool implementation.

Do not merge Bridge and Service binaries during Phase 18.

### 10.6 Startup Races

Multiple Go Bridges may start simultaneously.

They must not start competing service instances.

Reuse the existing Phase 6 and Phase 17 ownership rules.

### 10.7 Daemon Restart

If the Shared IPC Service restarts while the Bridge is running, follow the established connection recovery policy.

Do not silently hang forever.

### 10.8 RenderDoc Not Running

The Go MCP Bridge should handle the absence of RenderDoc according to the existing Python behavior.

MCP startup should not fail merely because no capture is currently loaded unless the current contract explicitly requires it.

---

## 11. Configuration Compatibility

Preserve the current configuration experience.

### 11.1 Configuration Sources

Inspect existing:

- Environment variables.
- `.env` files.
- Explicit configuration paths.
- Default configuration values.
- Logging settings.
- IPC endpoint settings.

### 11.2 Environment File Support

RenderEyeMCP has used the environment variable:

```text
RENDEREYE_ENV_FILE
```

Verify its current semantics before implementation.

Preserve how `.env` values are loaded and how they interact with existing process environment variables.

### 11.3 Configuration Precedence

Document and preserve precedence among:

- Explicit command-line options.
- Process environment.
- Environment file.
- Built-in defaults.

Do not assume this order without inspecting the existing implementation.

### 11.4 Default Paths

Do not introduce developer-specific absolute paths.

### 11.5 Runtime Dependencies

The Go Bridge must not require:

- Python.
- `pip`.
- `uv`.
- A virtual environment.

The RenderDoc Extension may continue using RenderDoc's embedded Python environment.

### 11.6 Logging

Preserve relevant configuration and log levels.

Do not write configuration diagnostics to MCP stdout.

---

## 12. Multi-Agent Support

Verify that multiple Go MCP Bridges work through the same Go Shared IPC Service.

### 12.1 Required Architecture

```text
Claude Code ── Go MCP Bridge A ──┐
                                │
Codex ─────── Go MCP Bridge B ──┼── Go Shared IPC Service
                                │
RenderDoc ─── Python Extension ─┘
```

### 12.2 Session Consistency

Both agents should discover the same live RenderDoc sessions where appropriate.

### 12.3 Request Isolation

Agent A must not receive Agent B's responses.

### 12.4 Capture Changes

Both Bridges must respect changes in active capture state.

### 12.5 Long-Running Operations

Concurrent GPU measurement and debugging requests must follow existing replay coordination rules.

Do not introduce an additional incompatible Bridge-level lock.

### 12.6 Client Termination

If one agent terminates its Bridge, the other agent and the Shared IPC Service must remain operational.

### 12.7 Mixed Migration

During migration, support the following configuration:

```text
Python MCP Bridge ──┐
                    ├── Go Shared IPC Service
Go MCP Bridge ──────┘
```

This is important for incremental adoption and differential testing.

---

## 13. MCP Contract Snapshot Tests

Create a machine-readable snapshot of the Python MCP interface.

This should become the compatibility baseline for the Go Bridge.

### 13.1 Capture the Python MCP Surface

Using an actual MCP client, retrieve:

- Server initialization information.
- Advertised capabilities.
- Tool list.
- Tool descriptions.
- Tool input schemas.
- Tool output schemas, if present.
- Resource definitions, if present.
- Prompt definitions, if present.

### 13.2 Snapshot Format

Store a normalized representation suitable for comparison.

Avoid recording unstable process-specific values.

### 13.3 Schema Comparison

Compare semantic JSON Schema behavior.

Check:

- Tool names.
- Required fields.
- Types.
- Defaults.
- Enums.
- Nullability.
- Constraints.
- Nested structures.
- Additional properties.

Do not require irrelevant differences such as JSON object key order to match.

### 13.4 Descriptions

Compare descriptions exactly unless a change is explicitly approved.

### 13.5 Capability Comparison

The Go Bridge must not advertise capabilities that it does not implement.

### 13.6 Contract Drift

Make the test fail when Go and Python MCP interfaces diverge unexpectedly.

Document approved compatibility exceptions.

---

## 14. Differential Tool Testing

For representative tools, invoke the same requests against both Bridges.

### 14.1 Comparison Setup

Prefer:

```text
Python MCP Bridge ──┐
                    ├── Go Shared IPC Service
Go MCP Bridge ──────┘
```

Both Bridges should use the same backend implementation and target capture.

### 14.2 Compare Results

Verify:

- Content types.
- Structured content.
- Error flags.
- Result schemas.
- Numerical values.
- Resource identifiers.
- Capture identifiers.
- Binary content.
- Missing fields.
- Pagination behavior.

### 14.3 Nondeterministic Data

Some fields may differ because of:

- Timestamps.
- Generated IDs.
- GPU measurement variability.
- Mutable RenderDoc GUI state.
- Session lifecycle timing.

Normalize only fields that are genuinely nondeterministic and not part of the compatibility contract.

### 14.4 Read-Only Tools First

Start with deterministic, read-only inspection operations.

Examples:

- Session discovery.
- Current capture information.
- Event enumeration.
- Pipeline state.
- Resource metadata.
- Shader reflection.

Use the actual tool names discovered in the repository.

### 14.5 Binary and Image Tools

Compare binary/image content byte-for-byte when both implementations request the same underlying data and the result is expected to be deterministic.

### 14.6 Replay-Dependent Tools

Run explicit replay-dependent operations separately and compare their result structure and semantics.

Do not require exact equality of independent GPU timing measurements.

### 14.7 Errors

Test:

- No RenderDoc session.
- No loaded capture.
- Invalid event.
- Invalid resource.
- Unsupported counter.
- Invalid pixel coordinate.
- Timeout.
- IPC service unavailable.

The Go Bridge should produce compatible MCP-level behavior.

---

## 15. Full Tool Coverage

Do not stop after migrating a few demonstration tools.

Phase 18 must migrate the complete implemented MCP surface.

### 15.1 Tool Groups

Audit the actual implemented tools corresponding to:

- Session and capture discovery.
- Event and pipeline inspection.
- GPU resource and buffer inspection.
- Shader inspection and reflection.
- Render target and pixel inspection.
- GPU performance analysis.
- Geometry and mesh inspection.
- Pixel History.
- Shader debugging.
- Other existing functionality.

### 15.2 Implemented vs Planned

Do not treat roadmap documents as proof that a tool exists.

Migrate implemented tools only.

### 15.3 Coverage Report

Produce a tool migration table.

For example:

| Tool | Python baseline | Go implementation | Contract test | Integration test |
|---|---|---|---|---|
| Tool A | Available | Complete | Passed | Passed |
| Tool B | Available | Complete | Passed | Not executed |
| Tool C | Not implemented | Not applicable | N/A | N/A |

Use actual tool names in the report.

### 15.4 No Silent Omissions

If an existing Python tool cannot be migrated, document the blocker.

Do not call Phase 18 complete while required existing functionality remains missing.

---

## 16. Testing

Add automated Go MCP Bridge tests.

### 16.1 Unit Tests

Cover:

- Tool registration.
- Input schema compatibility.
- Optional parameter semantics.
- Default arguments.
- Argument validation.
- IPC request construction.
- IPC error translation.
- Text content.
- Structured content.
- Image content.
- Multiple content blocks.
- Numeric precision.
- Binary response preservation.
- Cancellation.
- Timeouts.
- Connection cleanup.

### 16.2 MCP Protocol Tests

Use an actual MCP client to test the Go server.

Verify:

1. Initialization succeeds.
2. The advertised capabilities are correct.
3. Tool listing succeeds.
4. Tool invocation succeeds.
5. Invalid arguments produce compatible errors.
6. Tool execution failures are represented correctly.
7. stdio remains protocol-clean.
8. Shutdown is handled correctly.

### 16.3 Python Comparison Tests

Run Python and Go MCP Bridge tests against equivalent backend conditions.

### 16.4 Go Race Detection

Run:

```shell
go test -race ./...
```

where supported.

### 16.5 Service Unavailable

Verify that the Go Bridge handles the absence of the Shared IPC Service correctly.

### 16.6 Service Restart

Test service interruption and reconnection.

### 16.7 Large Responses

Test representative large:

- Buffer results.
- Texture images.
- Shader debug traces.
- Event lists.

### 16.8 Resource Cleanup

Verify that repeated MCP client connections do not leave orphaned goroutines or sockets.

---

## 17. Real RenderDoc Integration Testing

Verify end-to-end operation with the actual RenderDoc GUI.

### 17.1 Basic Scenario

1. Start the Go Shared IPC Service.
2. Launch RenderDoc.
3. Load an existing capture.
4. Connect the Python RenderDoc Extension.
5. Start the Go MCP Bridge.
6. Discover the active capture.
7. Enumerate events.
8. Inspect a draw call.
9. Retrieve pipeline state.
10. Inspect a GPU resource.

### 17.2 Shader Scenario

Retrieve shader information and reflection.

Compare the results with the Python MCP Bridge.

### 17.3 Texture Scenario

Retrieve an image or pixel value using the existing supported tools.

Verify content types and data correctness.

### 17.4 Performance Scenario

Where Phase 13 functionality is implemented and supported:

1. Discover available GPU counters.
2. Start a measurement.
3. Retrieve measurement status.
4. Retrieve GPU timings.
5. Identify expensive events.

Do not invent GPU counter values.

### 17.5 Geometry Scenario

Where Phase 14 functionality is implemented:

1. Select or target a draw.
2. Retrieve vertex input information.
3. Retrieve selected vertices and indices.
4. Inspect Post-VS geometry where supported.

### 17.6 Advanced Debugging Scenario

Where Phase 15 functionality is implemented and supported:

1. Retrieve Pixel History.
2. Start a supported Shader Debug Trace.
3. Retrieve bounded trace results.
4. Inspect variable values.

### 17.7 GUI Non-Interference

Verify that the Go Bridge does not introduce unexpected GUI state changes.

### 17.8 Record Evidence

Report actual results.

Do not claim support based solely on mocked tests.

---

## 18. Claude Code and Codex Validation

Both coding agents are important target clients.

### 18.1 Claude Code

Configure Claude Code to launch the Go MCP Bridge.

Use the actual current configuration format supported by the installed client.

Verify:

- MCP connection.
- Tool discovery.
- Tool invocation.
- Capture discovery.
- Error handling.
- Shutdown behavior.

### 18.2 Codex

Configure Codex to launch an independent Go MCP Bridge.

Verify the same capabilities.

### 18.3 Simultaneous Use

Run both agents concurrently.

Both should connect through separate Go MCP Bridge processes to the same Shared IPC Service.

### 18.4 Session Consistency

Verify that both agents discover the same active RenderDoc capture where appropriate.

### 18.5 Independent Lifecycles

Terminate one coding agent.

Verify the other remains operational.

### 18.6 Comparison With Python

Where possible, repeat representative tasks through the original Python MCP Bridge.

Document functional differences.

---

## 19. Cross-Platform Preparation

The Go Bridge should be portable across the intended platforms.

### 19.1 Target Platforms

Prepare for:

- Windows.
- Linux.
- macOS, subject to RenderDoc availability and support.

### 19.2 Avoid Python Runtime Dependencies

The Go Bridge must not invoke the Python runtime for ordinary MCP operations.

### 19.3 Avoid OS-Specific Paths

Do not hardcode Windows installation paths in the Bridge.

### 19.4 Environment Variables

Use portable environment handling.

### 19.5 IPC Transport

Reuse the existing TCP protocol.

Do not introduce different IPC protocols for Windows and Linux.

### 19.6 Build Verification

Verify cross-platform compilation.

A successful build does not prove runtime compatibility.

### 19.7 Runtime Testing

Run protocol and MCP tests on available operating systems.

Test actual RenderDoc integration only where supported.

---

## 20. CI Integration

Extend the Go CI pipeline.

### 20.1 Required Checks

Include:

- Go compilation.
- Unit tests.
- Race detection where supported.
- MCP schema snapshot comparison.
- MCP protocol tests.
- Tool contract tests.
- IPC integration tests.
- Representative tool differential tests.
- Cross-platform build checks.

### 20.2 Python Baseline

Keep Python MCP Bridge tests available during migration.

### 20.3 GUI-Independent CI

Most contract and protocol tests should run without RenderDoc.

### 20.4 GUI Integration

Keep RenderDoc-dependent tests separate where necessary.

### 20.5 No Automatic Publishing

Do not publish the Go Bridge as an official user-facing release during Phase 18 unless separately authorized.

---

## 21. Developer Installation and Testing

Provide simple development instructions.

### 21.1 Build

Use the existing Go module and repository layout.

An illustrative command is:

```shell
go build -o rendereye-mcp ./cmd/rendereye-mcp
```

Adjust the path to the actual module structure.

### 21.2 Run

The Go Bridge should launch as a stdio MCP server by default.

### 21.3 Configuration

Document required environment variables and configuration files.

### 21.4 Python Comparison

Provide an easy way to switch a coding agent between the Python and Go MCP Bridge for testing.

### 21.5 No Production Migration Yet

Do not remove the existing Python installation documentation until Phase 19 or Phase 20 explicitly addresses migration.

---

## 22. Documentation

Update development documentation.

Suggested files:

```text
docs/
  development/
    go-mcp-bridge.md
    mcp-contract-compatibility.md
    go-migration-readiness.md
```

Adapt to existing project conventions.

### 22.1 Required Topics

Document:

- Go Bridge architecture.
- Official Go MCP SDK selection.
- MCP tool registration.
- IPC client integration.
- Configuration.
- Lifecycle.
- Logging.
- Error handling.
- Compatibility guarantees.
- Test execution.
- Known limitations.

### 22.2 Migration Documentation

Explain how to test:

- Python MCP Bridge + Go Service.
- Go MCP Bridge + Go Service.
- Mixed Python and Go Bridges + Go Service.

### 22.3 User Documentation

Update English and Japanese user documentation only for implemented, user-visible changes.

Do not present the Go Bridge as the default production installation prematurely.

---

## 23. Implementation Order

Follow an incremental approach.

### Step 1 — Baseline Snapshot

Capture the complete Python MCP interface.

### Step 2 — SDK Selection

Choose a supported Go MCP SDK version and verify relevant APIs.

### Step 3 — Basic stdio Server

Implement MCP initialization, lifecycle, and logging.

### Step 4 — IPC Client Integration

Connect through the existing Phase 16/17 Go IPC implementation.

### Step 5 — Representative Tool

Migrate one simple, read-only tool.

Verify its schema and response against Python.

### Step 6 — Generic Tool Adapter

Implement reusable request forwarding and response conversion where appropriate.

### Step 7 — Full Tool Registration

Migrate all implemented tools.

### Step 8 — Specialized Results

Handle binary, image, structured, and long-running result types.

### Step 9 — Contract Tests

Validate tools, schemas, capabilities, and errors.

### Step 10 — Differential Tests

Compare representative Python and Go tool responses.

### Step 11 — Real RenderDoc Tests

Verify actual capture inspection.

### Step 12 — Multi-Agent Tests

Run Claude Code and Codex simultaneously through separate Go Bridges.

### Step 13 — CI and Documentation

Finalize tests, developer documentation, and migration readiness.

Do not migrate all tools before establishing that the basic MCP + IPC path works.

---

## 24. Acceptance Criteria

Phase 18 is complete when:

- [ ] The Go MCP Bridge builds successfully.
- [ ] The official Go MCP SDK is used unless a documented blocker requires otherwise.
- [ ] The Bridge uses stdio MCP transport.
- [ ] stdout contains only MCP protocol messages.
- [ ] MCP initialization is compatible with the Python baseline.
- [ ] Advertised capabilities match implemented functionality.
- [ ] All existing Python MCP tools are inventoried.
- [ ] All implemented Python tools are migrated.
- [ ] Tool names are preserved.
- [ ] Tool descriptions are preserved or approved changes are documented.
- [ ] Input schemas are semantically compatible.
- [ ] Output schemas are compatible where declared.
- [ ] Optional parameters and defaults behave correctly.
- [ ] Text content is preserved.
- [ ] Structured content is preserved.
- [ ] Image content is preserved.
- [ ] Binary data is not corrupted.
- [ ] Tool error semantics are compatible.
- [ ] MCP protocol errors are handled correctly.
- [ ] The Phase 16/17 Go IPC client implementation is reused.
- [ ] The Go Shared IPC Service requires no protocol changes.
- [ ] The Python RenderDoc Extension requires no protocol changes.
- [ ] Capture and session identities remain correct.
- [ ] Long-running operations preserve backend job semantics.
- [ ] Cancellation and timeouts are handled safely.
- [ ] Bridge shutdown does not terminate the shared daemon.
- [ ] Multiple Go Bridges can use one Go Shared IPC Service.
- [ ] Mixed Python and Go Bridges are supported during migration.
- [ ] Service restart and disconnection behavior are tested.
- [ ] Automated MCP contract snapshot tests pass.
- [ ] Differential tests cover representative tools.
- [ ] Unit and integration tests pass.
- [ ] Go race detection is performed where supported.
- [ ] Real RenderDoc integration is tested.
- [ ] Claude Code can connect and use the Go Bridge.
- [ ] Codex can connect and use the Go Bridge.
- [ ] Both agents can operate simultaneously.
- [ ] Windows compatibility is validated.
- [ ] Cross-platform builds are verified.
- [ ] Existing Python Bridge remains available for rollback.
- [ ] English and Japanese documentation reflects actual user-visible behavior.
- [ ] Phase 19 migration requirements are documented.

Do not mark a test as passed unless it was executed.

If the environment lacks RenderDoc or a particular coding agent, mark the relevant validation as pending.

Do not claim complete drop-in compatibility while required Python MCP functionality remains unavailable in Go.

---

## 25. Deliverables

### A. Go MCP Bridge

Provide:

- MCP server executable.
- Official Go SDK integration.
- Tool registration and schemas.
- IPC client integration.
- Result conversion.
- Lifecycle management.
- Configuration and logging.

### B. Compatibility Baseline

Provide:

- Python MCP tool inventory.
- Server capability snapshot.
- Tool schema snapshots.
- Approved compatibility exceptions.

### C. Automated Tests

Provide:

- MCP initialization tests.
- Tool schema compatibility tests.
- Result compatibility tests.
- Error handling tests.
- IPC integration tests.
- Differential tool tests.
- Multi-client tests.

### D. Real Integration Validation

Provide:

- RenderDoc test results.
- Claude Code test results.
- Codex test results.
- Multi-agent test results.
- Supported graphics API coverage.
- Known limitations.

### E. Documentation

Provide:

- Go MCP Bridge build instructions.
- Developer startup instructions.
- Python-to-Go comparison instructions.
- Configuration reference.
- Migration and rollback notes.
- Phase 19 readiness report.

### F. Completion Report

Clearly distinguish:

- Implemented.
- Tested.
- Partially tested.
- Not tested.
- Blocked.

List all deviations from the Python baseline.

---

## Final Goal

After Phase 18, RenderEyeMCP should support:

```text
Claude Code ── Go MCP Bridge ──┐
                               │
Codex ─────── Go MCP Bridge ──┼── Go Shared IPC Service
                               │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

Developers should be able to use the same natural-language debugging workflows they used with the Python MCP Bridge.

For example:

> Inspect the draw call currently selected in RenderDoc. Retrieve its pipeline state, shaders, resource bindings, and render targets. Identify suspicious configuration or data.

The Go MCP Bridge must expose the same capabilities and return compatible results.

At this stage, the Go Bridge and Go Shared IPC Service may remain separately built and launched executables.

Single-binary packaging, automatic service-mode selection, and end-user installation simplification belong to Phase 19.

**Phase 18 is successful when the Python MCP Bridge can be replaced with Go without changing the RenderDoc Extension, Shared IPC protocol, or Coding Agent debugging workflows.**
