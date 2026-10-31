# RenderEyeMCP — Complete Go Migration and Eliminate Legacy Python Service Dependencies

## Objective

Complete the migration of RenderEyeMCP's MCP and Shared IPC infrastructure from Python to Go.

A critical functional regression has been identified:

```text
GPU counter collection failed again:
the running Go service doesn’t implement collect_gpu_counters;
it requires the Python Shared IPC Service
```

This is unacceptable for the official Go distribution.

The Go implementation must support all previously implemented RenderEyeMCP functionality without requiring the legacy Python MCP Bridge or Python Shared IPC Service.

**Do not fix only `collect_gpu_counters`. Perform a comprehensive functional parity audit and eliminate all remaining runtime dependencies on the legacy Python infrastructure.**

The RenderDoc Python Extension must remain because it provides access to RenderDoc's embedded Python API.

---

## 1. Investigate the GPU Counter Failure

Trace the complete execution path for `collect_gpu_counters`.

Inspect the following components:

1. MCP Tool registration and dispatch in the Go MCP Bridge.
2. Go IPC client request construction.
3. IPC protocol serialization and request naming.
4. Go Shared IPC Service request dispatch.
5. Request routing to the RenderDoc Extension.
6. RenderDoc Extension counter collection.
7. Response serialization and error propagation.
8. MCP Tool result formatting.

Determine exactly why the Go Shared IPC Service cannot execute this operation.

Possible causes include:

- Missing IPC handler registration.
- Missing implementation of an existing Python IPC operation.
- Differences between Python and Go operation names.
- Incomplete request/response schema support.
- Missing RenderDoc Extension routing.
- Incorrect handling of long-running operations.
- Missing binary or structured payload support.
- An intentional Python fallback left during migration.

Do not assume the cause before inspecting the implementation.

### Required Fix

Implement the missing functionality in Go while preserving existing protocol compatibility.

The expected request flow is:

```text
MCP: collect_gpu_counters
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
RenderDoc Python Extension
       |
       v
RenderDoc GPU Counter API
       |
       v
Go Shared IPC Service
       |
       v
Go MCP Tool Result
```

Preserve existing counter discovery, selection, collection, descriptions, units, event associations, and result semantics wherever supported by the existing implementation.

RenderDoc replay-dependent operations must continue to respect the required RenderDoc replay-thread execution rules.

Do not independently implement GPU hardware counter collection in Go.

Use the existing RenderDoc API through the Python Extension.

---

## 2. Audit All IPC Operations

The GPU counter failure suggests that additional operations may be missing from the Go Shared IPC Service.

Perform a complete audit of IPC operation coverage.

### Audit Sources

Inspect:

- Legacy Python Shared IPC Service request handlers.
- Legacy Python MCP Bridge.
- Existing Go Shared IPC Service handlers.
- Existing Go MCP Bridge Tool implementations.
- RenderDoc Extension IPC handlers.
- IPC protocol definitions.
- Existing protocol tests and golden fixtures.
- MCP contract tests.
- Integration tests.

Do not assume the roadmap's feature list represents the full implemented API.

Use the actual repository implementation as the authoritative source.

### Build an Operation Compatibility Matrix

For every supported operation, record:

| Field | Description |
|---|---|
| Operation | IPC request or MCP Tool name |
| Python implementation | Existing legacy handler |
| Go implementation | Corresponding Go handler |
| Extension support | Required RenderDoc Extension operation |
| Request schema | Expected input structure |
| Response schema | Expected output structure |
| Test coverage | Available validation |
| Status | Complete, missing, incompatible, or obsolete |

Include every implemented operation, not merely the publicly documented Tools.

Pay particular attention to:

- Capture/session discovery and lifecycle.
- Event hierarchy and draw/dispatch inspection.
- Pipeline state inspection.
- Texture and buffer inspection.
- Shader inspection and reflection.
- Render target and pixel inspection.
- GPU performance counters.
- Geometry and mesh inspection.
- Pixel history.
- Shader debugging.
- Binary payload transport.
- Error handling and capability discovery.

Also audit internal operations such as registration, heartbeats, session synchronization, request cancellation, and service lifecycle management.

### Required Outcome

Every operation required by the supported MCP Tool set must be available through the Go infrastructure.

Missing implementations must be completed.

Schema or behavioral incompatibilities must be corrected.

Obsolete operations may be removed only after verifying that no supported functionality depends on them.

---

## 3. Complete the Go Shared IPC Service

Make the Go Shared IPC Service the sole supported Shared IPC Service implementation.

### Requirements

- Support all required IPC operations.
- Preserve the existing communication protocol where possible.
- Preserve request and response compatibility.
- Preserve session identification and request routing.
- Support multiple independent MCP clients.
- Correctly route requests to the appropriate RenderDoc session.
- Prevent responses from being delivered to the wrong client.
- Preserve structured and binary payloads.
- Handle connection loss and reconnection.
- Handle request timeouts and cancellation.
- Prevent goroutine and socket leaks.
- Return meaningful errors for unsupported RenderDoc capabilities.

The Go Service must not:

- Launch the Python Shared IPC Service.
- Invoke the Python MCP Bridge.
- Execute legacy Python server modules as subprocesses.
- Require a Python virtual environment.
- Fall back to the Python Service when an operation is unavailable.
- Silently ignore unsupported operations.
- Fabricate successful responses for missing functionality.

If a required operation is missing, implement it rather than redirecting the request to the legacy Python Service.

### Service Lifecycle

Preserve the existing design:

```text
rendereye-mcp          # MCP Bridge
rendereye-mcp service  # Shared IPC Service
```

The Bridge and Service are independent processes using the same Go executable.

Multiple Bridges must safely reuse one Shared IPC Service.

Verify that automatic startup, concurrent startup protection, service discovery, shutdown, and restart continue working.

---

## 4. Verify Go MCP Bridge Functional Parity

Audit all MCP Tools registered by the Go MCP Bridge.

Compare their behavior against the supported legacy Tool contracts.

Verify:

- Tool names.
- Tool descriptions.
- Input schemas.
- Output schemas.
- Structured content.
- Image content.
- Binary data handling.
- Error results.
- Timeout and cancellation behavior.
- RenderDoc capability reporting.

No supported MCP Tool should depend on the legacy Python Bridge or Shared IPC Service.

Do not introduce incompatible MCP changes unless absolutely necessary.

Do not rename existing Tools solely to simplify the Go implementation.

---

## 5. Preserve the RenderDoc Python Extension

The RenderDoc Extension is intentionally implemented in Python.

It must remain responsible for interacting with RenderDoc's Python API.

### Responsibilities

- Access RenderDoc GUI state.
- Access loaded captures and ReplayController.
- Perform replay-dependent inspection operations.
- Collect GPU performance counters through RenderDoc.
- Execute pixel history and shader debugging operations.
- Serialize results for the IPC transport.
- Respect RenderDoc's threading and replay constraints.

Do not attempt to replace RenderDoc's Python API with a custom Go GPU debugger.

Do not move replay-dependent operations into Go merely to eliminate Python source files.

The migration target is the MCP and IPC infrastructure, not the embedded RenderDoc Extension.

Modify the Extension only where necessary to complete reliable communication with the Go Service or correct existing functionality.

---

## 6. Eliminate Legacy Python Runtime Dependencies

After functional parity has been verified, remove the legacy Python MCP and Shared IPC infrastructure from active runtime paths.

Inspect:

- Go service startup logic.
- MCP Bridge startup logic.
- Installation scripts.
- Release packaging.
- Environment variables.
- Default configuration files.
- CI/CD workflows.
- Integration test infrastructure.
- README.md and installation documentation.

Remove obsolete dependencies on:

- Python MCP server entry points.
- Python Shared IPC Service startup.
- Python subprocess fallbacks.
- Python virtual environments for MCP execution.
- pip or uv for normal user installation.
- Legacy Python service executable paths.

Keep Python files needed by the RenderDoc Extension.

Historical protocol fixtures and compatibility tests may remain when useful, but must not be required for normal runtime operation.

Do not remove tests or reference implementations before the Go parity tests are sufficient to replace their coverage.

---

## 7. Add Comprehensive Regression Tests

### IPC Contract Tests

Test every supported IPC operation against its documented request and response contract.

Verify:

- Request dispatch.
- Serialization and deserialization.
- Session routing.
- Error propagation.
- Optional and missing fields.
- Binary payload integrity.
- Timeout behavior.

### GPU Counter Tests

Add explicit coverage for `collect_gpu_counters`.

Test:

1. Counter operation registration.
2. Request forwarding through the Go Service.
3. Counter discovery and selection.
4. Successful counter collection.
5. Result serialization.
6. Unsupported counters.
7. Unsupported hardware or RenderDoc capabilities.
8. Capture/session changes.
9. Replay failures.
10. Concurrent client requests.

Use mock or fixture-based tests for protocol behavior.

Use real RenderDoc captures for end-to-end validation.

If the hardware or RenderDoc version does not support GPU counters, verify correct capability reporting and error handling rather than claiming a successful counter collection.

### Multi-Agent Tests

Run at least two independent Go MCP Bridge processes against one Go Shared IPC Service.

Verify:

- Both agents connect successfully.
- Requests are correctly isolated.
- Responses reach the requesting agent.
- Concurrent inspection requests do not corrupt shared state.
- Expensive replay-dependent operations are coordinated safely.
- Disconnecting one agent does not interrupt unrelated requests.
- Capture changes are detected correctly.

### Go-Only Integration Tests

Perform an end-to-end test with:

```text
Go MCP Bridge
      |
Go Shared IPC Service
      |
RenderDoc Python Extension
      |
RenderDoc GUI
```

The Python MCP Bridge and Python Shared IPC Service must not be running.

A successful test must demonstrate that the required operations work without those legacy processes.

---

## 8. Update Windows Distribution

Preserve the new portable installation design.

The Go executable must run directly from the extracted GitHub Releases directory.

Do not restore the old executable-copy installation model.

The Windows installer should continue installing the RenderDoc Extension into:

```text
%APPDATA%\qrenderdoc\extensions\rendereye
```

The standard user workflow must not require a separately installed Python runtime.

Verify that the distributed executable includes all Go-side functionality needed by the supported MCP Tools.

Do not include a legacy Python Shared IPC Service as a hidden runtime dependency.

---

## 9. Documentation Updates

Update README.md and the English/Japanese documentation after the implementation is validated.

Document the final architecture:

```text
Coding Agents
     |
Go MCP Bridge
     |
Go Shared IPC Service
     |
RenderDoc Python Extension
     |
RenderDoc
```

Do not describe the Python Shared IPC Service as necessary for GPU counter collection or any other supported operation.

Document actual capability limitations imposed by RenderDoc, GPU hardware, drivers, and operating systems.

Do not create end-user Python-to-Go migration documentation.

---

## 10. Acceptance Criteria

The work is complete only when:

1. `collect_gpu_counters` is fully implemented in the Go IPC request path.
2. GPU counter collection works through the Go infrastructure on a supported test environment.
3. Every required IPC operation has a corresponding Go implementation.
4. Every supported MCP Tool works without legacy Python MCP or Shared IPC processes.
5. Existing MCP Tool contracts remain compatible.
6. Multi-agent operation remains reliable.
7. RenderDoc capture and replay state remain safe.
8. No runtime fallback to the Python Shared IPC Service exists.
9. The Go-only end-to-end integration suite passes for supported capabilities.
10. Release packaging and documentation no longer require the legacy Python infrastructure.
11. The RenderDoc Python Extension continues functioning correctly.

Do not consider the migration complete merely because the Go executable builds or the MCP server starts.

Functional parity must be demonstrated through tests.

## Deliverables

Provide:

- Implemented Go IPC handlers.
- Completed `collect_gpu_counters` support.
- A full IPC operation compatibility matrix.
- Corrections for all discovered missing operations.
- Regression and integration tests.
- Removal of obsolete runtime dependencies.
- Updated documentation where necessary.
- A concise implementation report.

The report must distinguish:

- Fully tested operations.
- Operations validated using mocks or fixtures only.
- Operations requiring unavailable RenderDoc or GPU capabilities.
- Remaining known limitations.

## Execution Instructions

First inspect the repository and identify the missing functionality.

Then implement the required Go-side changes.

Do not stop after writing an analysis or migration proposal.

Do not apply superficial fixes that only suppress the reported error.

Prioritize complete functional parity, correct RenderDoc integration, and runtime reliability.

Do not publish a release or create a release tag as part of this task.
