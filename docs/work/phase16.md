# Phase 16 — IPC Protocol Contract & Compatibility Tests

## Objective

Prepare RenderEyeMCP for the planned migration of its Python MCP infrastructure to Go by documenting, validating, and testing the existing inter-process communication protocol.

The current architecture consists of independent processes:

```text
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The Shared IPC Service is a standalone daemon process, not an in-process component of an MCP Bridge.

Phase 6 established this shared-service architecture to support multiple independent MCP clients without competing for ownership of the same IPC port.

**Phase 16 must preserve this architecture and establish a reliable protocol contract before any production Go migration begins.**

The long-term migration plan is:

- Phase 16 — IPC Protocol Contract & Compatibility Tests.
- Phase 17 — Go Shared IPC Service.
- Phase 18 — Go MCP Bridge.
- Phase 19 — Single Binary & Cross-Platform Distribution.
- Phase 20 — Reliability, Migration, and Python Deprecation.

Phase 16 must provide the foundation for implementing the Go Shared IPC Service in Phase 17 without requiring simultaneous changes to the Python MCP Bridge or RenderDoc Extension.

The primary objectives are:

1. Discover and document the existing IPC protocol.
2. Preserve existing wire-level behavior.
3. Define message framing, serialization, and request/response semantics.
4. Establish a reproducible compatibility test suite.
5. Validate multiple simultaneous clients.
6. Validate connection failure and reconnection behavior.
7. Implement a small Go protocol probe to demonstrate interoperability.
8. Identify platform dependencies that affect future Go implementation.
9. Produce a clear compatibility contract for Phase 17.

Do not rewrite the Shared IPC Service or MCP Bridge during this phase.

---

## 1. Repository Investigation

Before modifying code, inspect the actual repository.

Identify the implementations of:

- Python MCP Bridge.
- Shared IPC Service.
- RenderDoc Extension.
- TCP client and server communication.
- Service startup and discovery.
- Port binding and connection establishment.
- Session registration.
- Request routing.
- Response routing.
- Event and capture state synchronization.
- Request timeouts and cancellation.
- Message serialization and deserialization.
- Binary data transfer.
- Error propagation.
- Background tasks and asynchronous operations.
- Logging and diagnostics.
- Existing tests.

Identify every module that sends or receives messages through the Shared IPC Service.

Do not assume all IPC clients share the same connection implementation.

### 1.1 Establish Component Responsibilities

Determine which component currently owns each responsibility.

Examples include:

| Responsibility | Determine actual owner |
|---|---|
| TCP listener | Shared IPC Service |
| MCP stdio transport | MCP Bridge |
| RenderDoc API access | RenderDoc Extension |
| Session discovery | Inspect implementation |
| Request routing | Inspect implementation |
| Service autostart | Inspect implementation |
| Client registration | Inspect implementation |
| Replay operation coordination | Inspect implementation |
| Job state management | Inspect implementation |
| Request timeout enforcement | Inspect implementation |
| Capture state caching | Inspect implementation |

Do not assign responsibilities based only on earlier design documents.

Treat the existing implementation as the source of truth.

### 1.2 Produce an Implementation Inventory

Document the relevant modules, classes, functions, and configuration settings.

Identify public and private interfaces.

Classify behavior as:

- Protocol-level behavior.
- Service implementation detail.
- MCP Bridge implementation detail.
- RenderDoc Extension implementation detail.
- Operating-system-specific behavior.

This classification will determine what must be compatible in Go and what can be reimplemented freely.

---

## 2. Protocol Contract Principles

The purpose of Phase 16 is to document and verify the existing protocol, not to design a new one.

Follow these principles.

**Preserve observed behavior.**

Do not silently change existing message formats or semantics.

**Separate protocol from implementation.**

Python classes, module names, and internal data structures are not automatically part of the wire protocol.

**Make implicit assumptions explicit.**

Document requirements currently enforced only by the implementation.

**Preserve multi-agent behavior.**

Multiple independent MCP Bridges must continue to communicate through one Shared IPC Service.

**Avoid speculative features.**

Do not add protocol capabilities solely because they might be convenient in Go.

**Prefer interoperability over redesign.**

Phase 17 should be able to replace the Python Shared IPC Service while retaining existing clients.

**Ensure evidence-based documentation.**

Every protocol claim must be supported by code inspection, tests, or observed messages.

---

## 3. Wire Protocol Discovery

Investigate the exact bytes exchanged over TCP.

Do not assume the protocol uses JSON, newline-delimited JSON, MessagePack, or any other specific encoding.

### 3.1 Transport

Document:

- Transport protocol.
- Default host.
- Default port.
- Configurable endpoints.
- Address-family assumptions.
- Connection direction.
- Persistent versus short-lived connections.
- Socket ownership.
- Connection shutdown behavior.

The current default endpoint is:

```text
127.0.0.1:37020
```

Verify that this remains the actual default.

Do not change the endpoint in Phase 16 without a demonstrated correctness or security requirement.

### 3.2 Message Framing

Determine exactly how the receiver identifies message boundaries.

Investigate whether framing uses:

- Length prefixes.
- Delimiters.
- Fixed-size headers.
- Streaming records.
- Another existing mechanism.

Document:

- Header structure.
- Message length encoding.
- Byte order.
- Character encoding.
- Maximum permitted message size.
- Empty-message handling.
- Partial-read behavior.
- Multiple messages in one TCP read.
- EOF behavior.

TCP is a byte stream.

Do not assume that one socket read corresponds to one complete protocol message.

### 3.3 Serialization

Document:

- Payload encoding.
- Object structure.
- Field naming.
- Field types.
- Required fields.
- Optional fields.
- Null values.
- Default values.
- Integer and floating-point handling.
- Binary payload representation.
- Unicode behavior.
- Serialization of unsupported values.

If JSON is used, inspect how the Python implementation handles numbers, non-finite floating-point values, and binary data.

If another format is used, document its exact encoding rules.

### 3.4 Request/Response Structure

Determine whether requests contain:

- Request ID.
- Operation or method name.
- Session identifier.
- Capture identifier.
- Arguments.
- Timeout information.
- Protocol version.
- Other metadata.

Determine how responses represent:

- Successful results.
- Application errors.
- Transport errors.
- Unsupported operations.
- Partial results.
- Long-running jobs.
- Notifications.

Do not invent fields that do not currently exist.

### 3.5 Request Correlation

Identify how responses are matched to requests.

Determine:

- Whether multiple requests can be in flight.
- Whether responses may arrive out of order.
- Whether IDs are unique per connection or globally.
- What happens when a client reconnects.
- How duplicate request IDs are handled.
- How late responses are handled.

Record the actual behavior, including deficiencies.

Do not silently add new correlation semantics.

---

## 4. Message and Operation Inventory

Enumerate all IPC message types supported by the existing implementation.

This must include messages used by both the MCP Bridge and RenderDoc Extension.

Potential categories include:

- Client registration.
- Service discovery.
- Session registration.
- Session state updates.
- Capture state updates.
- Heartbeats or liveness checks.
- RenderDoc API requests.
- Responses.
- Error messages.
- Notifications.
- Long-running operation status.
- Disconnection or shutdown signals.

These categories are investigation targets, not assumptions about the current protocol.

### 4.1 Operation Catalog

For each actual operation, document:

| Field | Description |
|---|---|
| Operation name | Exact wire-level operation identifier |
| Sender | Component that sends the request |
| Receiver | Component responsible for handling it |
| Request schema | Actual serialized fields |
| Response schema | Actual serialized fields |
| Error semantics | Possible failures and representation |
| Side effects | Replay, capture, or service state changes |
| Timeout behavior | Actual handling |
| Concurrency | Relevant restrictions |

Preserve exact field names and operation identifiers.

### 4.2 Control Plane vs Data Plane

Identify which messages manage connections and sessions, and which messages transport RenderDoc inspection requests and results.

A useful classification is:

**Control plane**

- Service discovery.
- Client registration.
- Session state.
- Connection management.
- Liveness information.

**Data plane**

- RenderDoc inspection requests.
- GPU resource data.
- Pipeline state.
- Shader data.
- Geometry data.
- Performance results.
- Debug traces.

Only use this classification where supported by the actual implementation.

Do not create a separate network protocol merely to enforce the distinction.

### 4.3 Notification Semantics

For any server-initiated messages, determine:

- Who receives them.
- Whether delivery is guaranteed.
- Whether they are replayed after reconnect.
- Whether they require acknowledgment.
- How ordering is defined.

Do not assume notification delivery is reliable across disconnects.

---

## 5. Session, Capture, and Resource Identity

The protocol must preserve correct routing between agents, RenderDoc GUI sessions, and captures.

Investigate the actual identity model.

### 5.1 Session Identity

Document how the service identifies:

- MCP clients.
- RenderDoc Extension connections.
- RenderDoc GUI sessions.
- Active sessions.
- Disconnected sessions.

Determine whether identities survive reconnection and process restart.

### 5.2 Capture Identity

Document how capture identities are assigned and validated.

Determine:

- When an identity changes.
- What happens when a capture is unloaded.
- What happens when a new capture is opened.
- Whether multiple GUI sessions can load the same file.
- How stale requests are rejected.

### 5.3 Event and Resource Identity

Document how IPC messages represent:

- Event IDs.
- Resource IDs.
- Shader IDs.
- Measurement IDs.
- Geometry references.
- Debug operation IDs.

Do not confuse RenderDoc-native identifiers with RenderEyeMCP-generated identifiers.

### 5.4 Identifier Encoding

Verify:

- String versus integer representation.
- Width and signedness.
- Zero and invalid sentinel values.
- Serialization of 64-bit identifiers.
- Cross-language conversion.

The Go implementation must preserve identifiers exactly.

Avoid conversions through floating-point representations that could lose integer precision.

### 5.5 Stale Request Prevention

Create tests for:

1. Request targeting capture A.
2. Capture A unloads.
3. Capture B loads.
4. A late request or response for capture A arrives.

The system must not mistakenly apply data from capture A to capture B.

Document existing handling and any gaps.

Do not invent a new capture identity model without explicit justification.

---

## 6. Binary and Large Payload Compatibility

RenderEyeMCP may transport significant amounts of data, including:

- Texture images.
- Raw buffer data.
- Vertex and index data.
- Shader disassembly.
- Pixel History.
- Shader Debug Traces.
- GPU performance measurements.

Investigate how these payloads are transmitted.

### 6.1 Binary Encoding

Determine whether binary data is transferred through:

- Raw bytes.
- Base64.
- Encoded arrays.
- Separate frames.
- Temporary files.
- Another existing mechanism.

Document the exact behavior.

### 6.2 Payload Size Limits

Identify current limits on:

- Message size.
- Binary payload size.
- Image size.
- Buffer range size.
- Request count.
- In-memory buffering.

Do not assume these limits are adequate.

### 6.3 Partial Transfer

Test:

- Split TCP reads.
- Multiple frames in one read.
- Slow transmission.
- Connection loss during transfer.
- Invalid length declarations.
- Truncated payloads.

Do not permit malformed payloads to cause unbounded memory allocation.

### 6.4 Byte Preservation

Verify that raw binary payloads are preserved byte-for-byte.

Include fixtures containing:

- Zero bytes.
- High-bit bytes.
- Invalid UTF-8 byte sequences.
- Large binary blocks.
- Payloads near allowed limits.

Do not decode arbitrary binary data as UTF-8.

### 6.5 Response Bounding

Preserve the existing bounded-output behavior for large MCP tools.

Do not allow a Go client to bypass limits enforced by the Python implementation.

---

## 7. Error Contract

Document how errors are represented and propagated.

### 7.1 Error Categories

Inspect existing handling for:

- Connection refused.
- Service unavailable.
- Session unavailable.
- Capture unavailable.
- Invalid request.
- Unknown operation.
- Invalid arguments.
- Resource not found.
- Unsupported RenderDoc capability.
- Replay operation failure.
- Timeout.
- Cancellation.
- Service shutdown.
- Extension disconnect.
- Internal server error.

Use actual error codes and structures.

### 7.2 Error Propagation

Trace an error through:

```text
RenderDoc Extension
        |
        v
Shared IPC Service
        |
        v
MCP Bridge
        |
        v
Coding Agent
```

Determine whether errors are:

- Preserved exactly.
- Translated.
- Wrapped.
- Converted to generic failures.

Document each transformation.

### 7.3 Go Compatibility

The future Go implementation must preserve externally observable error semantics.

Avoid replacing all errors with generic strings.

### 7.4 Malformed Input

Verify that malformed messages:

- Do not crash the daemon.
- Do not corrupt other client sessions.
- Do not block the message reader indefinitely.
- Produce the expected error or connection termination.

Record any existing behavior that needs correction.

---

## 8. Connection and Lifecycle Semantics

The protocol contract must define connection behavior sufficiently for independent Go implementation.

### 8.1 Service Startup

Investigate:

- How the daemon is started.
- Who starts it.
- How clients discover it.
- How simultaneous startup requests are coordinated.
- How stale service state is detected.
- Whether existing clients can connect during startup.

### 8.2 Single-Service Ownership

Preserve the Phase 6 invariant:

**Multiple independent MCP processes must not create competing Shared IPC Services on the same endpoint.**

Document the actual mechanism that enforces this.

Do not assume that a successful TCP bind alone describes the complete service election mechanism.

### 8.3 Connection Establishment

Document:

- Handshake, if any.
- Registration sequence.
- Client role identification.
- Readiness checks.
- Initial state synchronization.
- Connection timeout.

If no handshake exists, explicitly document that fact.

### 8.4 Disconnection

Determine what occurs when:

- An MCP Bridge exits normally.
- An MCP Bridge crashes.
- The RenderDoc Extension disconnects.
- The Shared IPC Service exits.
- A TCP connection is interrupted.
- A client disappears during a long-running request.

### 8.5 Reconnection

Document:

- Retry behavior.
- Backoff strategy.
- State synchronization.
- Session re-registration.
- Pending request handling.
- Stale connection cleanup.

Do not assume TCP reconnection automatically restores the application's session state.

### 8.6 Service Restart

Test whether clients can recover after the daemon restarts.

Document whether restart requires manual intervention.

Do not introduce a process supervisor in Phase 16 unless needed to execute the compatibility tests.

---

## 9. Concurrency and Multi-Agent Semantics

The Shared IPC Service must continue supporting multiple independent agents.

### 9.1 Concurrent Clients

Test at least:

- Two MCP Bridge connections.
- One RenderDoc Extension connection.
- Simultaneous inspection requests.
- Connection and disconnection during active requests.

### 9.2 Request Routing

Ensure responses return to the correct requesting client.

No response intended for Agent A may be delivered to Agent B.

### 9.3 Out-of-Order Responses

If the protocol supports concurrent in-flight requests, test responses arriving in a different order from requests.

If the protocol is strictly sequential, document this limitation.

### 9.4 Shared State

Identify data that is shared between clients.

Examples may include:

- Current RenderDoc session information.
- Capture metadata.
- In-progress GPU measurements.
- Cached inspection results.
- Debugging operation status.

Do not assume all state is connection-local.

### 9.5 Replay Coordination

Determine which IPC operations may require exclusive RenderDoc replay access.

Examples:

- GPU counter collection.
- Post-VS extraction.
- Pixel History.
- Shader Debugging.

Document whether serialization is enforced by the IPC Service, the Extension, or both.

Do not implement a new replay locking mechanism during this phase unless a focused compatibility defect requires it.

### 9.6 Isolation Testing

Verify that one malfunctioning or disconnected client does not prevent healthy clients from continuing.

Test slow and stalled connections.

Ensure a large response for one client does not silently corrupt another client's messages.

---

## 10. Protocol Contract Documentation

Create a formal contract document.

Suggested path:

```text
docs/development/ipc-protocol.md
```

Adapt to existing documentation conventions.

### 10.1 Required Sections

The document must contain:

1. Architecture and process roles.
2. TCP endpoint configuration.
3. Connection lifecycle.
4. Message framing.
5. Serialization format.
6. Request envelope.
7. Response envelope.
8. Error representation.
9. Notification behavior.
10. Session and capture identity.
11. Operation catalog.
12. Binary payload handling.
13. Timeout and cancellation behavior.
14. Concurrency rules.
15. Service startup and restart.
16. Platform assumptions.
17. Compatibility guarantees.
18. Known gaps and limitations.

### 10.2 Message Examples

Include actual sanitized request and response examples.

Examples must come from:

- Existing tests.
- Captured protocol messages.
- Existing serialization code.

Do not invent field names or values and present them as real protocol messages.

### 10.3 Explicit Unknowns

When behavior cannot be established conclusively, mark it as:

- Undocumented.
- Unverified.
- Implementation-dependent.
- Unsupported.

Do not silently replace unknown behavior with an idealized specification.

### 10.4 Canonical Contract

The documentation and compatibility fixtures should become the reference for Phase 17.

If documentation and implementation disagree, investigate and resolve the discrepancy explicitly.

The current Python implementation remains authoritative until the discrepancy has been evaluated.

---

## 11. Golden Protocol Fixtures

Create reproducible serialized-message fixtures.

Suggested structure:

```text
tests/
  protocol/
    fixtures/
      connection/
      requests/
      responses/
      errors/
      notifications/
      binary/
      lifecycle/
```

Adapt the structure to existing test conventions.

### 11.1 Fixture Content

Each fixture should contain:

- Serialized message bytes or an exact encoded representation.
- Message category.
- Expected decoded structure.
- Expected re-encoding behavior.
- Relevant protocol assumptions.

### 11.2 Canonicalization

Determine whether the protocol requires byte-identical serialization or only equivalent decoded values.

For example, JSON object field ordering may not be semantically significant.

Do not enforce byte-for-byte equality where the wire contract does not require it.

However, framing, binary values, identifiers, and scalar types must remain compatible.

### 11.3 Fixture Sources

Derive fixtures from actual Python serialization behavior.

Keep sample data synthetic or sanitized where capture files may contain proprietary information.

### 11.4 Coverage

Include:

- Minimal valid request.
- Request with optional fields.
- Valid response.
- Error response.
- Unknown operation.
- Invalid request.
- Empty payload.
- Unicode strings.
- Large integers.
- Floating-point values.
- Binary payload.
- Maximum permitted payload.
- Truncated frame.
- Invalid frame length.
- Multiple consecutive frames.

Do not assume all examples apply to the existing protocol. Adapt to the discovered encoding.

---

## 12. Python Protocol Compatibility Tests

Add tests against the existing Python implementation.

### 12.1 Serialization Tests

Verify:

- Encoding.
- Decoding.
- Required fields.
- Optional fields.
- Type preservation.
- Error representation.
- Invalid input handling.

### 12.2 Framing Tests

Verify correct handling of:

- Partial reads.
- Split writes.
- Multiple frames in one read.
- Slow readers.
- Connection close mid-message.

### 12.3 Routing Tests

Verify that messages reach the correct client or RenderDoc session.

### 12.4 Lifecycle Tests

Verify:

- Client registration.
- Client disconnect.
- Extension disconnect.
- Service shutdown.
- Reconnection.
- Pending request cleanup.

### 12.5 Regression Baseline

The Python test suite must pass before introducing Go interoperability.

Record existing failures rather than modifying tests to conceal them.

---

## 13. Minimal Go Protocol Probe

Implement a small Go client to prove that the documented protocol can be implemented independently of Python.

This is a compatibility probe, not the new MCP Bridge or Shared IPC Service.

Suggested structure:

```text
tools/
  ipc-probe/
    main.go

internal/
  ipc/
    ...
```

Adapt to the repository's preferred organization.

### 13.1 Responsibilities

The Go probe should:

1. Connect to the existing Python Shared IPC Service.
2. Perform the required handshake or registration.
3. Send at least one valid protocol request.
4. Receive and decode the response.
5. Verify request/response correlation.
6. Handle a structured error.
7. Close the connection cleanly.

Prefer a harmless health or session-information request that already exists.

Do not introduce a new health-check operation merely to make the probe pass.

### 13.2 Transport Implementation

Use Go's standard networking facilities where appropriate.

Correctly handle:

- Partial reads.
- Partial writes.
- Framing.
- Timeouts.
- EOF.
- Cancellation.
- Connection cleanup.

### 13.3 No MCP SDK Requirement

The Go probe does not need to implement MCP.

MCP compatibility is the responsibility of Phase 18.

Phase 16 focuses on the existing Shared IPC Service wire protocol.

### 13.4 No Service Migration

Do not implement the production Go Shared IPC Service during Phase 16.

A minimal mock server may be used for protocol tests, but it must not become a competing production daemon.

### 13.5 Probe Diagnostics

The probe should clearly report:

- Connection success or failure.
- Protocol decoding success or failure.
- Response correlation result.
- Relevant protocol mismatch.
- Exit status.

Do not log potentially sensitive capture payloads by default.

---

## 14. Cross-Language Compatibility Tests

Establish compatibility between the existing Python service and the Go probe.

### 14.1 Required Test Matrix

| Client | Server | Purpose |
|---|---|---|
| Python | Python | Existing behavior baseline |
| Go probe | Python | Verify Go client interoperability |
| Python | Mock protocol server | Validate client expectations where useful |
| Go probe | Mock protocol server | Verify deterministic fixtures |

The production Go Shared IPC Service is deferred to Phase 17.

### 14.2 Golden Fixture Tests

Verify that the Go decoder accepts actual Python-generated messages.

Verify that the Python decoder accepts valid Go-generated messages.

### 14.3 Semantic Compatibility

Compare:

- Operation names.
- Field names.
- Value types.
- Required/default fields.
- Error codes.
- Identifier values.
- Binary bytes.
- Message ordering.

### 14.4 Protocol Round Trips

For supported message types:

1. Generate a message in Python.
2. Decode it in Go.
3. Re-encode it in Go.
4. Decode it in Python.
5. Compare semantic values.

Repeat the reverse direction where practical.

### 14.5 Conformance Results

Produce a machine-readable or documented pass/fail summary.

Do not claim full protocol compatibility based on a single successful connection test.

---

## 15. Integration Tests with Real RenderDoc

Where a RenderDoc environment is available, test with the actual Extension.

### 15.1 Basic Integration

1. Start RenderDoc.
2. Load a test capture.
3. Start or connect the Shared IPC Service.
4. Connect the Python MCP Bridge.
5. Connect the Go protocol probe.
6. Retrieve supported session or capture information.
7. Confirm identities and responses are consistent.

### 15.2 Multiple Agents

Run two independent Python MCP Bridges, representing separate coding-agent clients.

Verify:

- Both connect to the same service.
- Both can retrieve information.
- Neither attempts to own the service port.
- Requests are routed correctly.

### 15.3 Mixed Clients

Connect the Go probe while Python MCP Bridges remain active.

Verify that the probe does not disrupt them.

### 15.4 Capture Switching

1. Load capture A.
2. Issue inspection requests.
3. Switch to capture B.
4. Issue new requests.
5. Verify stale capture A state is not incorrectly reused.

### 15.5 Extension Reconnection

Disconnect and reconnect the RenderDoc Extension if feasible.

Verify service and client behavior.

### 15.6 Test Evidence

Record:

- Operating system.
- RenderDoc version.
- Python version.
- Go version.
- Test commands.
- Expected results.
- Actual results.
- Failures and limitations.

Do not claim real RenderDoc integration testing was performed if only mocks were available.

---

## 16. Failure Injection and Robustness

Add bounded fault-injection tests.

### 16.1 Client Failures

Test:

- Client exits without clean shutdown.
- Client closes connection during a request.
- Client sends incomplete message.
- Client stops reading responses.
- Client sends malformed payload.

### 16.2 Service Failures

Test:

- Service unavailable.
- Service terminates during request processing.
- Service restarts.
- Port already occupied.
- Connection rejected.

### 16.3 Extension Failures

Test:

- Extension disconnects.
- Capture unloads.
- Replay operation fails.
- Session disappears while a request is pending.

### 16.4 Isolation

A malformed message from one client must not corrupt unrelated client sessions.

Where existing behavior fails this requirement, record the issue and implement a focused correction if it can be made without changing the protocol.

### 16.5 Timeout Behavior

Use finite test timeouts.

Do not create tests that can block CI indefinitely.

### 16.6 Resource Cleanup

Verify:

- Sockets close.
- Pending requests are released.
- Disconnected clients are removed.
- Background tasks terminate.
- Service shutdown completes.

---

## 17. Security and Local IPC Boundaries

The Shared IPC Service currently listens on loopback TCP.

Investigate security assumptions before moving to Go.

### 17.1 Binding Scope

Verify that the service binds only to the intended loopback interface by default.

Do not silently change the listener to `0.0.0.0`.

### 17.2 Local Client Trust

Document whether the service authenticates clients.

Loopback TCP does not automatically authenticate the process or user connecting to it.

Determine whether arbitrary local processes can send requests.

### 17.3 Protocol Validation

Validate:

- Message size.
- Required fields.
- Input types.
- Operation names.
- Session references.
- Resource limits.

Malformed or malicious local inputs must not cause unbounded allocation or unsafe replay operations.

### 17.4 Secrets

Do not embed secrets or API tokens in protocol fixtures.

Do not log sensitive capture contents or entire binary payloads by default.

### 17.5 Compatibility vs Hardening

If security deficiencies are found, document them and assess whether a compatible fix can be made in Phase 16.

Protocol-breaking authentication or handshake changes require an explicit migration plan.

Do not silently impose a new handshake that existing Python clients cannot satisfy.

---

## 18. Cross-Platform Preparation

Identify operating-system assumptions that will affect the Go migration.

Target platforms:

- Windows.
- Linux.
- macOS, subject to actual RenderDoc support and availability.

### 18.1 Investigate OS Dependencies

Review:

- Process spawning.
- Daemon lifecycle.
- TCP binding.
- Port reuse.
- File paths.
- Environment variables.
- Signal handling.
- Process termination.
- Temporary files.
- Logging destinations.
- Service discovery.
- Locks or mutexes.

### 18.2 Separate Protocol from OS Behavior

The IPC wire protocol should not depend on:

- Windows file paths.
- Python object serialization internals.
- Platform-native handle values.
- Process IDs used as stable session identities.
- OS-specific character encodings.

If such assumptions exist, document them.

Do not redesign the transport during this phase unless required for correctness.

### 18.3 Go Build Verification

Ensure the minimal Go probe can be compiled for the intended target operating systems.

A successful cross-compilation does not prove that RenderDoc integration works on that OS.

### 18.4 Platform Test Matrix

Document which tests can run:

- Without RenderDoc.
- With a mock protocol service.
- With the Python Shared IPC Service.
- With an actual RenderDoc GUI.

Avoid requiring a GUI for every CI protocol test.

---

## 19. Protocol Versioning and Compatibility Policy

Define a documented compatibility policy for Phase 17.

### 19.1 Current Version

Determine whether the existing IPC protocol already has an explicit version field or handshake.

If so, document the current behavior.

If not, describe the existing wire format as a baseline compatibility contract without inventing an on-wire version field.

### 19.2 Compatibility Guarantees

Define which elements Phase 17 must preserve.

At minimum, consider:

- Message framing.
- Serialization.
- Operation identifiers.
- Required fields.
- Optional field semantics.
- Response correlation.
- Error behavior.
- Session identity.
- Capture identity.
- Binary payloads.
- Connection lifecycle.

### 19.3 Additive Changes

If future extensions are required, define how to evaluate additive fields and operations.

Do not assume unknown fields are ignored unless current decoders demonstrate that behavior.

### 19.4 Breaking Changes

Document how incompatible changes would be introduced.

Possible mechanisms include:

- Explicit protocol negotiation.
- Separate compatibility modes.
- Coordinated version upgrades.

Do not implement these mechanisms prematurely.

### 19.5 Mixed-Version Support

The Phase 17 Go Shared IPC Service should initially support the current Python clients without requiring an immediate coordinated upgrade.

If this is impossible, identify the exact incompatibility and propose the smallest migration strategy.

---

## 20. Continuous Integration

Integrate deterministic protocol tests into GitHub Actions.

### 20.1 Fast Test Suite

Run without RenderDoc:

- Python serialization tests.
- Go serialization tests.
- Golden fixture tests.
- Framing tests.
- Error handling tests.
- Mock server tests.
- Tag-independent unit tests relevant to IPC.

### 20.2 Service Integration

Where feasible, launch the real Python Shared IPC Service in CI.

Run the Go probe against it.

Avoid dependence on an installed RenderDoc GUI for basic protocol conformance.

### 20.3 Platform Coverage

Prefer a CI matrix covering:

- Windows.
- Linux.
- macOS.

If existing service implementation constraints prevent a platform from running, report the limitation and retain cross-compilation or fixture tests where appropriate.

### 20.4 Real RenderDoc Tests

Keep GUI-dependent tests separate from deterministic CI tests.

Do not block routine CI solely because a RenderDoc GUI is unavailable on a runner.

### 20.5 Test Reporting

Distinguish:

- Unit test passed.
- Protocol conformance passed.
- Service integration passed.
- Real RenderDoc integration passed.
- Not executed.
- Unsupported environment.

---

## 21. Documentation Deliverables

Produce the following documents, adapting paths to the repository layout.

```text
docs/
  development/
    ipc-architecture.md
    ipc-protocol.md
    ipc-compatibility.md
    go-migration-readiness.md
```

### 21.1 IPC Architecture

Explain:

- Process responsibilities.
- Connection topology.
- Shared service lifecycle.
- Multi-agent routing.
- Replay operation ownership.

### 21.2 IPC Protocol

Describe the actual wire contract.

Include verified message examples and field semantics.

### 21.3 Compatibility

Describe:

- Test fixtures.
- Conformance testing.
- Backward-compatibility expectations.
- Error behavior.
- Versioning policy.
- Unsupported assumptions.

### 21.4 Go Migration Readiness

Summarize:

- Protocol components suitable for direct Go implementation.
- Python-specific dependencies.
- Operating-system-specific dependencies.
- Known ambiguities.
- Potential breaking changes.
- Phase 17 implementation recommendations.

Keep internal development documentation in English.

Update Japanese documentation where it describes installation, architecture, or user-visible behavior affected by this work.

Do not expand the user-facing README with internal protocol details unnecessarily.

---

## 22. Scope Restrictions

Do not implement:

- Production Go Shared IPC Service.
- Production Go MCP Bridge.
- New MCP tools.
- New RenderDoc debugging features.
- New GPU profiling capabilities.
- A new IPC transport.
- A new wire serialization format.
- A complete protocol redesign.
- A new service supervisor.
- A single-binary distribution system.
- Python infrastructure deprecation.
- Unrelated packaging changes.

Small, compatible bug fixes in existing IPC code are permitted when required for reliable conformance tests.

Document such fixes explicitly.

---

## 23. Implementation Principles

**Existing behavior is the baseline.**

Inspect the implementation before defining the contract.

**Capture the protocol at the wire boundary.**

Do not treat Python implementation details as protocol requirements.

**Do not redesign the transport prematurely.**

Retain the current TCP approach unless a real blocking issue is found.

**Preserve multi-agent support.**

Phase 6 behavior is a compatibility requirement.

**Build reusable tests.**

The same fixtures must support the Phase 17 Go Shared IPC Service.

**Avoid GUI-dependent tests where unnecessary.**

Protocol conformance should be testable independently of RenderDoc.

**Preserve identity and routing.**

Responses must not be confused between clients, sessions, or captures.

**Bound memory and execution.**

Malformed or large messages must not destabilize the service.

**Do not claim unsupported behavior.**

Document unknowns and current limitations explicitly.

**Keep the migration incremental.**

Phase 17 must be able to replace the service without replacing every client simultaneously.

---

## 24. Deliverables

### A. Protocol Analysis

Provide:

- Module and responsibility inventory.
- Actual transport and framing specification.
- Serialization specification.
- Operation catalog.
- Session/capture identity rules.
- Error contract.
- Lifecycle behavior.
- Concurrency semantics.

### B. Compatibility Test Suite

Provide:

- Golden protocol fixtures.
- Python protocol tests.
- Framing and serialization tests.
- Multi-client routing tests.
- Failure-injection tests.
- Cross-language round-trip tests.

### C. Go Protocol Probe

Provide:

- Minimal Go IPC client.
- Connection and request handling.
- Response decoding.
- Error handling.
- Compatibility test commands.

### D. CI Integration

Provide:

- Deterministic protocol test workflow.
- Python/Go test execution.
- Supported OS matrix.
- Test result reporting.

### E. Migration Readiness Report

Explain:

- Which protocol behavior is fully understood.
- Which behavior is verified by tests.
- Which behavior remains uncertain.
- Which platform dependencies remain.
- What Phase 17 must implement.
- Which compatibility risks are most important.

---

## 25. Acceptance Criteria

Phase 16 is complete when:

- [ ] Existing IPC implementations have been inspected.
- [ ] Process roles and responsibilities are documented.
- [ ] TCP connection behavior is documented.
- [ ] Message framing is documented and tested.
- [ ] Serialization behavior is documented and tested.
- [ ] Request and response envelopes are documented.
- [ ] Existing operation identifiers are inventoried.
- [ ] Error formats are documented.
- [ ] Session and capture identity rules are documented.
- [ ] Binary payload handling is documented and tested.
- [ ] Partial TCP reads and writes are handled correctly.
- [ ] Multi-message framing is tested.
- [ ] Multiple MCP clients can communicate concurrently.
- [ ] Responses are routed to the correct client.
- [ ] Client disconnection does not corrupt other sessions.
- [ ] Service disconnection and restart behavior is tested.
- [ ] Stale capture references are tested.
- [ ] Malformed messages are handled safely.
- [ ] Protocol fixtures are derived from actual Python behavior.
- [ ] Python protocol conformance tests pass.
- [ ] A minimal Go IPC probe is implemented.
- [ ] The Go probe can communicate with the Python service.
- [ ] Python-generated messages can be decoded in Go.
- [ ] Go-generated messages can be decoded in Python.
- [ ] Cross-language compatibility tests pass for the supported fixture set.
- [ ] Platform-specific dependencies are identified.
- [ ] The Go probe can be built for intended target platforms.
- [ ] CI runs deterministic protocol tests.
- [ ] Existing RenderDoc functionality remains operational.
- [ ] No production Go daemon replacement is introduced.
- [ ] A clear Phase 17 migration contract is available.
- [ ] Unverified behaviors and remaining risks are documented.

If a behavior cannot be verified in the available environment, explicitly report it as unverified rather than marking it complete.

---

## Final Goal

After Phase 16, the development team should have:

1. An accurate specification of RenderEyeMCP's existing IPC protocol.
2. Automated tests proving the current Python behavior.
3. Reusable golden fixtures for cross-language interoperability.
4. A small Go client that can communicate with the existing Python Shared IPC Service.
5. Evidence that multiple clients remain isolated and correctly routed.
6. A documented compatibility contract for implementing the Go Shared IPC Service.

The future Phase 17 implementation should be able to use the Phase 16 test suite as its primary compatibility baseline.

The intended Phase 17 transition is:

```text
Before:

Python MCP Bridge ──┐
Python MCP Bridge ──┼── Python Shared IPC Service
RenderDoc Extension ┘

After:

Python MCP Bridge ──┐
Python MCP Bridge ──┼── Go Shared IPC Service
RenderDoc Extension ┘
```

**Phase 16 must make this replacement possible without redesigning the IPC protocol or simultaneously migrating the MCP Bridges and RenderDoc Extension.**
