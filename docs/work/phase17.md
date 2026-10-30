# Phase 17 — Go Shared IPC Service Migration

## Objective

Replace RenderEyeMCP's standalone Python Shared IPC Service with a compatible Go implementation while preserving the existing IPC protocol and all externally observable behavior.

This phase builds directly on Phase 16 — IPC Protocol Contract & Compatibility Tests.

The current architecture is:

```text
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Python Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The target architecture for Phase 17 is:

```text
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Go Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The Shared IPC Service must remain an independent daemon process.

Do not merge the service into the MCP Bridge during this phase.

The long-term migration roadmap is:

- Phase 16 — IPC Protocol Contract & Compatibility Tests.
- **Phase 17 — Go Shared IPC Service.**
- Phase 18 — Go MCP Bridge.
- Phase 19 — Single Binary & Cross-Platform Distribution.
- Phase 20 — Reliability, Migration, and Python Deprecation.

The principal success criterion is:

**The existing Python MCP Bridges and RenderDoc Extension must operate correctly against the Go Shared IPC Service without requiring protocol changes.**

Prioritize behavioral compatibility, concurrency safety, lifecycle reliability, and testability over new features.

---

## 1. Review Phase 16 Deliverables

Before implementing the Go service, inspect the actual repository and Phase 16 outputs.

Identify:

1. The documented IPC protocol.
2. Message framing specification.
3. Serialization format.
4. Request and response envelopes.
5. Error semantics.
6. Client registration and connection lifecycle.
7. Session and capture identity rules.
8. Request routing behavior.
9. Notification behavior.
10. Binary payload handling.
11. Service startup and ownership rules.
12. Timeout and cancellation semantics.
13. Golden protocol fixtures.
14. Python protocol compatibility tests.
15. The Phase 16 Go IPC probe.
16. Identified compatibility gaps and limitations.

Suggested reference documents may include:

```text
docs/development/ipc-architecture.md
docs/development/ipc-protocol.md
docs/development/ipc-compatibility.md
docs/development/go-migration-readiness.md
```

Use the actual paths in the repository.

### 1.1 Existing Behavior Is Authoritative

Do not treat the Phase 16 design document as a substitute for the actual implementation.

If the documentation, fixtures, and Python implementation disagree:

1. Investigate the discrepancy.
2. Determine the existing observable behavior.
3. Identify the impact on existing clients.
4. Correct the documentation or test fixtures where appropriate.
5. Document any required compatibility fixes.

Do not silently introduce protocol-breaking changes.

### 1.2 Identify Service Responsibilities

Determine the precise responsibilities currently implemented by the Python Shared IPC Service.

Potential responsibilities include:

- TCP listening.
- Client registration.
- Connection management.
- RenderDoc session registration.
- Request forwarding.
- Response correlation.
- Notifications.
- Shared session state.
- Capture state synchronization.
- Service discovery.
- Heartbeats.
- Pending request tracking.
- Long-running operation routing.
- Service startup coordination.
- Connection cleanup.

This is an investigation checklist.

Do not assume that all listed responsibilities exist.

Port only the responsibilities actually owned by the service.

### 1.3 Preserve Component Boundaries

Do not move RenderDoc Replay API calls into Go.

Do not move MCP tool implementations into the Go service.

The Go service must continue functioning as the same IPC intermediary that the Python implementation currently provides.

---

## 2. Implementation Scope

Implement the standalone Shared IPC Service in Go.

### In Scope

- Existing IPC protocol.
- TCP server.
- Client connections.
- Registration and session lifecycle.
- Request routing.
- Response forwarding.
- Existing notifications.
- Existing shared state.
- Service startup and shutdown.
- Timeout and cancellation behavior.
- Multi-client concurrency.
- Error handling.
- Resource cleanup.
- Logging and diagnostics.
- Configuration compatibility.
- Cross-platform compilation.
- Compatibility and integration tests.

### Out of Scope

- Rewriting the Python MCP Bridge.
- Rewriting the RenderDoc Extension.
- Migrating MCP tools to Go.
- Introducing a new MCP SDK.
- Changing RenderDoc Replay APIs.
- Replacing the IPC wire protocol.
- Introducing a new network transport.
- Combining Bridge and Service into one executable.
- Deprecating the Python Shared IPC Service.
- Changing release packaging to a single executable.
- Reworking installer architecture.
- Adding unrelated RenderDoc features.

Small compatibility fixes outside the Go service are allowed only when necessary and supported by tests.

Document every such change.

---

## 3. Go Project Structure

Create a maintainable Go implementation within the existing repository.

Prefer a small, idiomatic structure.

An illustrative layout is:

```text
go/
  go.mod
  go.sum

  cmd/
    rendereye-ipc/
      main.go

  internal/
    protocol/
      ...
    server/
      ...
    session/
      ...
    routing/
      ...
    lifecycle/
      ...
```

The exact layout may differ based on the repository.

Avoid introducing unnecessary packages.

### 3.1 Go Version

Select a supported stable Go version compatible with the project's CI and intended platforms.

Record the minimum required Go version in `go.mod`.

Do not introduce a dependency on a newer Go feature without justification.

### 3.2 Dependencies

Prefer the Go standard library for:

- TCP networking.
- Concurrency.
- Context cancellation.
- Logging.
- Process signals.
- Basic serialization when compatible.
- Testing.

Use third-party packages only when they provide clear value.

Avoid an extensive dependency tree for a relatively small IPC service.

### 3.3 Protocol Package

Reuse the Phase 16 Go probe's protocol implementation where possible.

Avoid maintaining two separate Go encoders or decoders.

The protocol implementation should be usable independently of server lifecycle logic.

### 3.4 Service Entry Point

Provide an executable entry point for running the daemon.

The executable name should follow existing repository naming conventions.

For example:

```text
rendereye-ipc
rendereye-ipc.exe
```

These names are illustrative.

Do not rename existing user-facing commands without reviewing compatibility.

---

## 4. Wire Protocol Compatibility

Implement the exact Phase 16 IPC wire protocol.

### 4.1 Transport

Preserve the existing transport behavior.

The default endpoint is expected to be:

```text
127.0.0.1:37020
```

Verify the actual configured endpoint.

Do not change the default port or binding behavior without a documented compatibility reason.

### 4.2 Framing

Implement the actual existing message framing.

Correctly handle:

- Partial TCP reads.
- Partial writes.
- Multiple messages received together.
- Large messages.
- Connection closure.
- Truncated messages.
- Invalid length information.

Never assume a TCP read corresponds to one complete message.

### 4.3 Serialization

Preserve:

- Field names.
- Required fields.
- Optional fields.
- Default values.
- Null semantics.
- Numeric representations.
- Boolean representations.
- String encoding.
- Binary payload encoding.

Do not substitute an alternative serialization format.

### 4.4 Numeric Precision

Pay particular attention to:

- 64-bit identifiers.
- Resource IDs.
- Event IDs.
- Large counters.
- Floating-point values.
- Integer signedness.

Do not pass large integer identifiers through floating-point representations that lose precision.

If JSON is used, investigate whether `json.Decoder.UseNumber()` or explicit typed decoding is required.

Choose the mechanism based on the actual protocol.

### 4.5 Unknown Fields

Match the Python implementation's handling of unknown fields.

Do not assume unknown fields should always be rejected or ignored.

### 4.6 Unknown Operations

Match existing behavior for unsupported operation names.

Return the expected error or termination behavior.

Do not silently discard requests.

### 4.7 Binary Preservation

Preserve binary payloads byte-for-byte.

Test texture data, buffer data, and other binary content supported by the existing protocol.

Do not apply Unicode transformations to binary data.

---

## 5. TCP Server Implementation

Implement a reliable TCP listener.

### 5.1 Binding

Bind to the configured endpoint.

Default to loopback-only access.

Do not expose the service publicly by default.

### 5.2 Connection Handling

Support multiple simultaneous clients.

Each connection must have an independent lifecycle.

A failure in one connection must not terminate the entire service unless the existing contract explicitly requires it.

### 5.3 Reader and Writer Responsibilities

Define clear ownership for connection reading and writing.

Avoid concurrent writes that can corrupt message framing.

If a dedicated writer goroutine is used, ensure all outgoing messages for that connection pass through it.

### 5.4 Backpressure

A slow client must not cause unlimited memory growth.

Use bounded queues or another appropriate flow-control strategy.

Do not silently discard protocol messages that require reliable delivery.

If overload occurs, follow compatible error or disconnection semantics.

### 5.5 Resource Limits

Enforce limits on:

- Incoming frame size.
- Outgoing queue size.
- Concurrent connections, if necessary.
- Pending requests.
- Buffered payloads.
- Per-client resource usage.

Match existing protocol limits where defined.

If additional safety limits are necessary, select conservative values and document compatibility implications.

### 5.6 Connection Cleanup

On disconnection:

- Stop connection-specific goroutines.
- Release socket resources.
- Remove obsolete connection references.
- Resolve or terminate pending requests appropriately.
- Update session state according to the existing contract.

Do not leak goroutines.

---

## 6. Client Registration and Session Management

Port the existing registration and session mechanisms.

### 6.1 Client Roles

Identify how the current service distinguishes:

- MCP Bridges.
- RenderDoc Extensions.
- Other supported clients.

Preserve the actual registration semantics.

Do not create a new role handshake unless required by the current protocol.

### 6.2 Session Identity

Preserve existing session identifiers and lifecycle rules.

Determine how connections are associated with logical RenderDoc sessions.

### 6.3 Session State

Port any existing state used to represent:

- Connected RenderDoc instances.
- Loaded captures.
- Selected events.
- Current replay context.
- Session availability.

Do not introduce new state fields without a documented reason.

### 6.4 Disconnect Semantics

When a RenderDoc Extension disconnects, ensure the service correctly updates or invalidates the corresponding session state.

Do not continue routing requests to disconnected sessions.

### 6.5 Reconnection

Restore the expected registration and synchronization behavior when a client reconnects.

Avoid carrying stale session ownership from an old TCP connection.

### 6.6 Capture Identity

Preserve the contract for capture identifiers.

Requests and responses from an old capture must not be misattributed to a newly loaded capture.

Do not assume that identical capture file paths imply identical live capture sessions.

---

## 7. Request Routing and Response Correlation

This is a core Phase 17 responsibility.

### 7.1 Routing

Preserve the current path:

```text
Python MCP Bridge
        |
        v
Go Shared IPC Service
        |
        v
Python RenderDoc Extension
        |
        v
Go Shared IPC Service
        |
        v
Python MCP Bridge
```

A response must return to the correct requesting client.

### 7.2 Request Identity

Preserve existing request identifiers and correlation rules.

Do not assume request IDs are globally unique unless the current protocol guarantees it.

If necessary, maintain internal connection-aware correlation state without changing the wire format.

### 7.3 Concurrent Requests

Support the concurrency model established in Phase 16.

If multiple requests can be in flight, ensure responses are routed correctly even when completion order differs from request order.

### 7.4 Pending Requests

Track pending operations using bounded, concurrency-safe data structures.

Define cleanup on:

- Successful response.
- Error response.
- Timeout.
- Client disconnect.
- Extension disconnect.
- Service shutdown.

### 7.5 Late Responses

A response arriving after timeout or cancellation must not be delivered to an unrelated request.

Do not reuse internal correlation identifiers unsafely.

### 7.6 Notifications

Preserve existing notification routing.

Do not convert notifications into ordinary responses or vice versa.

### 7.7 Long-Running Operations

Ensure the service correctly routes operations introduced in later phases, including:

- GPU performance measurements.
- Post-VS geometry extraction.
- Pixel History.
- Shader debugging.

The service need not understand their internal GPU semantics if the existing Python service treats them as opaque messages.

**Prefer protocol-level forwarding over implementing MCP-tool-specific logic inside the Go service.**

---

## 8. Multi-Agent Concurrency

Maintain the Phase 6 multi-agent design.

### 8.1 Required Scenario

At minimum, support:

```text
Claude Code ── Python MCP Bridge A ──┐
                                     │
Codex ─────── Python MCP Bridge B ──┼── Go Shared IPC Service
                                     │
RenderDoc ─── Python Extension ──────┘
```

Both Bridges must connect to the same service process.

### 8.2 Request Isolation

Ensure:

- Agent A receives only its intended responses.
- Agent B receives only its intended responses.
- Notifications reach the correct recipients.
- One client cannot overwrite another client's request correlation state.

### 8.3 Concurrency Model

Use Go concurrency primitives appropriately.

Possible mechanisms include:

- Goroutines for network connections.
- Channels for bounded message queues.
- Mutexes for small shared state.
- Contexts for cancellation.

Do not use one global mutex around all network and replay-related operations.

### 8.4 Avoid Locking During I/O

Do not hold shared-state locks while performing potentially blocking socket writes or waiting for remote responses.

Define a consistent locking order.

### 8.5 Slow Client Isolation

Test whether one slow or stalled client can delay other clients.

Prevent unbounded queues and global stalls.

### 8.6 Replay Coordination

Preserve the current coordination model for replay-sensitive requests.

Do not assume the IPC Service itself owns RenderDoc ReplayController operations.

Investigate where exclusivity is enforced.

Avoid introducing a second conflicting replay scheduler.

### 8.7 Shared Results

If the existing service shares completed operation results or status information between clients, preserve that behavior.

Do not automatically make connection-local state global.

---

## 9. Service Lifecycle and Ownership

The Go Shared IPC Service must remain a standalone daemon.

### 9.1 Startup Behavior

Preserve how the current Python service is discovered and started.

Investigate whether Python Bridges:

- Launch the daemon.
- Connect to an already running daemon.
- Retry after connection failure.
- Use a lock or ownership mechanism.
- Check service readiness.

### 9.2 Startup Compatibility

The production Go service must be usable through the existing client startup path.

However, do not force the Python MCP Bridge to launch Go when the Python service is still selected as the active backend.

Use explicit configuration or the existing service-selection mechanism.

### 9.3 Single-Service Invariant

Maintain the Phase 6 invariant:

**Exactly one service may own the configured IPC endpoint at a time.**

Multiple Bridges may start simultaneously.

Do not let each Bridge create a competing service.

### 9.4 Port Already in Use

Handle port conflicts correctly.

A successful TCP connection alone does not prove the listener is a compatible RenderEyeMCP service.

Use the existing protocol's readiness or identity mechanism, where available.

Do not invent a new handshake that would break Python clients.

If another process owns the port, fail clearly rather than connecting blindly or terminating that process.

### 9.5 Process Ownership

Do not kill an existing service merely because a new client starts.

Do not assume that an occupied port is stale.

Respect existing service ownership and shutdown behavior.

### 9.6 Graceful Shutdown

Handle operating-system termination signals where supported.

On shutdown:

1. Stop accepting new connections.
2. Stop or reject new operations appropriately.
3. Release pending requests.
4. Close active connections.
5. Release listener resources.
6. Exit without leaving stale ownership state.

### 9.7 Unexpected Termination

Test abrupt process termination and restart.

Ensure clients eventually detect that their connection is invalid.

Document the reconnect behavior of existing Python clients.

### 9.8 No Process Supervisor Redesign

Do not introduce Windows Services, systemd units, launchd agents, or a new watchdog architecture unless already required by the existing service design.

Those deployment concerns can be addressed in later phases.

---

## 10. Configuration Compatibility

Preserve the configuration behavior required by existing clients and installation scripts.

### 10.1 Configuration Discovery

Inspect existing configuration sources, including:

- Environment variables.
- `.env` files.
- Explicit configuration paths.
- Default values.
- Command-line parameters.

RenderEyeMCP previously used the `RENDEREYE_ENV_FILE` convention.

Verify its current implementation and semantics before relying on it.

### 10.2 Environment File Handling

If the Python service currently loads environment files, preserve its observable configuration behavior.

Determine precedence between:

- Process environment.
- Explicit environment file.
- Default environment file.
- Command-line options.

Document the actual order.

### 10.3 Go Configuration

Implement compatible configuration loading.

Do not require the user to install Python or `uv` to start the Go service.

### 10.4 Service Selection

During migration, provide a safe mechanism to choose between the Python and Go Shared IPC Service implementations.

Reuse existing configuration conventions where possible.

Do not require rewriting the MCP protocol.

### 10.5 Defaults

Preserve defaults relevant to the service, including the IPC endpoint.

Do not hardcode developer-specific installation paths.

---

## 11. Logging and Diagnostics

Provide structured, useful service diagnostics.

### 11.1 Logging Destination

Keep logs off stdout if stdout has a documented protocol role.

For a standalone service, follow existing logging conventions and available deployment requirements.

### 11.2 Useful Events

Log:

- Startup.
- Listener readiness.
- Client connection.
- Client registration.
- Session registration.
- Session disconnection.
- Request routing errors.
- Timeout events.
- Service shutdown.
- Unexpected failures.

### 11.3 Log Levels

Support existing log-level configuration where applicable.

### 11.4 Avoid Sensitive Data

Do not log:

- Full binary payloads.
- Entire captured textures.
- Raw shader debugging traces.
- Proprietary capture contents.
- Credentials.

Log identifiers and sizes instead where useful.

### 11.5 Request Diagnostics

Include request or correlation identifiers in logs where available.

Do not leak internal information into the IPC protocol unless required for compatibility.

---

## 12. Go Error Handling

Preserve protocol-level error behavior.

### 12.1 Errors

Handle:

- Invalid frames.
- Invalid payloads.
- Unknown operations.
- Missing sessions.
- Disconnected clients.
- Timeouts.
- Cancellation.
- Oversized messages.
- Invalid identifiers.
- Unsupported protocol behavior.
- Internal service errors.

### 12.2 No Panics from Client Input

Malformed or unexpected client data must not crash the service.

Use normal error returns and controlled connection termination.

### 12.3 Panic Recovery

If panic recovery is introduced at connection boundaries, use it to contain failures and log diagnostics.

Do not use broad panic recovery as a substitute for correct error handling.

### 12.4 Error Compatibility

Match Python service responses where compatibility requires it.

Do not replace structured protocol errors with generic Go error strings.

### 12.5 Partial Failure

One client failure must not corrupt unrelated clients or sessions.

---

## 13. Resource Management

Go's garbage collector does not eliminate the need for explicit resource cleanup.

### 13.1 Sockets

Close all connection and listener resources.

### 13.2 Goroutines

Ensure every connection-related goroutine has a termination path.

Avoid orphaned readers, writers, and timeout workers.

### 13.3 Pending Requests

Remove pending request entries on every terminal path.

### 13.4 Timers and Contexts

Release timers and cancel contexts when operations complete.

### 13.5 Buffers

Avoid retaining large payload buffers unnecessarily.

Use bounded allocations and reuse buffers only when safe.

### 13.6 Session State

Remove disconnected sessions according to existing lifecycle rules.

Avoid indefinite accumulation of dead connections.

### 13.7 Long-Running Stability

Include tests that repeatedly connect and disconnect clients and verify no sustained resource growth.

---

## 14. Protocol Compatibility Testing

Reuse the Phase 16 test suite as the primary compatibility baseline.

### 14.1 Golden Fixtures

Verify the Go service accepts all supported Python-generated request fixtures.

Verify it produces compatible responses and notifications.

### 14.2 Framing Tests

Cover:

- Split TCP reads.
- Split TCP writes.
- Multiple frames in one read.
- Truncated frames.
- Invalid lengths.
- Empty frames.
- Large payloads.
- Connection termination during transfer.

### 14.3 Serialization Tests

Cover:

- Unicode.
- Numeric precision.
- Binary payloads.
- Optional fields.
- Null values.
- Invalid data.
- Error encoding.

### 14.4 Compatibility Matrix

| Client | Service | Required |
|---|---|---|
| Python MCP Bridge | Python Shared IPC Service | Existing baseline |
| Python MCP Bridge | Go Shared IPC Service | **Primary Phase 17 target** |
| Go IPC Probe | Python Shared IPC Service | Phase 16 baseline |
| Go IPC Probe | Go Shared IPC Service | Required |
| Python RenderDoc Extension | Python Shared IPC Service | Existing baseline |
| Python RenderDoc Extension | Go Shared IPC Service | **Primary Phase 17 target** |

### 14.5 Differential Testing

Where practical, execute the same deterministic requests against both service implementations.

Compare:

- Response schemas.
- Field values.
- Error codes.
- Notification behavior.
- Routing behavior.
- Session state transitions.

Ignore intentionally nondeterministic values such as generated IDs, process IDs, timestamps, or connection order when they are not part of the compatibility contract.

Do not normalize away meaningful differences.

### 14.6 Test Coverage

Do not claim compatibility merely because basic connections succeed.

Include actual routed requests and state transitions.

---

## 15. Multi-Client Integration Testing

Use real or simulated Python clients.

### 15.1 Two-Bridge Test

1. Start the Go Shared IPC Service.
2. Connect Python MCP Bridge A.
3. Connect Python MCP Bridge B.
4. Register or discover a RenderDoc session.
5. Issue concurrent requests.
6. Confirm response isolation.
7. Disconnect one Bridge.
8. Verify the other continues working.

### 15.2 Extension Reconnection

1. Connect the Python RenderDoc Extension.
2. Establish session state.
3. Disconnect the Extension.
4. Verify session cleanup.
5. Reconnect the Extension.
6. Verify state synchronization.

### 15.3 Request Timeout

Send a request whose target does not respond.

Verify timeout behavior and pending request cleanup.

### 15.4 Out-of-Order Responses

Where the existing protocol supports concurrent requests, test replies arriving out of order.

### 15.5 Late Response

Send a response after the originating request has timed out or been cancelled.

Verify it cannot be misrouted.

### 15.6 Slow Client

Simulate a client that stops reading.

Verify memory usage remains bounded and other clients continue.

---

## 16. Real RenderDoc Validation

Test against the actual RenderDoc GUI and Python Extension.

This is required before declaring the Go service a drop-in replacement.

### 16.1 Environment

Record:

- Operating system.
- RenderDoc version.
- Python version.
- Go version.
- RenderEyeMCP revision.
- Test capture information.

### 16.2 Basic Workflow

1. Start the Go Shared IPC Service.
2. Launch RenderDoc.
3. Load an existing capture.
4. Connect the RenderDoc Extension.
5. Connect a Python MCP Bridge.
6. Discover the active capture.
7. Enumerate events.
8. Retrieve a draw call.
9. Inspect pipeline state.
10. Retrieve a supported resource or shader detail.

Use actual implemented MCP tools.

### 16.3 Multi-Agent Workflow

Connect Claude Code and Codex through separate Python MCP Bridges.

Verify:

- Both connect to the same Go service.
- Both discover the same capture.
- Both can execute inspection requests.
- Results remain associated with the correct clients.
- The selected GUI event is not unexpectedly modified.

### 16.4 Capture Switching

Test:

- Capture unload.
- Capture replacement.
- Session state updates.
- Stale request handling.

### 16.5 Advanced Operations

Where implemented and supported, exercise representative:

- GPU counter collection.
- Geometry extraction.
- Pixel History.
- Shader debugging.

The Go service should transport and coordinate these operations according to the existing protocol.

Do not reimplement the GPU operations in Go.

### 16.6 GUI Non-Interference

Verify that replacing the service does not introduce unexpected GUI state modifications.

### 16.7 Test Results

Record actual execution results.

Do not mark unexecuted advanced operations as passed.

---

## 17. Reliability and Stress Testing

The Go service must remain stable under repeated activity.

### 17.1 Connection Churn

Repeatedly connect and disconnect clients.

Verify:

- No goroutine leaks.
- No stale sessions.
- No unbounded memory growth.
- No permanently blocked routing operations.

### 17.2 Concurrent Requests

Test multiple clients sending requests simultaneously.

Include response delays and failures.

### 17.3 Service Restart

1. Start the Go service.
2. Connect clients.
3. Stop the service.
4. Restart it.
5. Verify reconnection according to the existing client behavior.

If Python clients cannot reconnect automatically, document the limitation.

Do not redesign the MCP Bridge during this phase.

### 17.4 Malformed Input

Test invalid frames and payloads.

A malformed client request must not terminate healthy connections.

### 17.5 Large Payloads

Test representative large responses, such as buffer or image data.

Verify byte preservation and bounded resource usage.

### 17.6 Race Detection

Run Go's race detector during testing where supported.

For example:

```shell
go test -race ./...
```

Fix races found in shared routing or session state.

### 17.7 Graceful Shutdown

Verify that shutdown:

- Stops accepting connections.
- Releases connections.
- Resolves pending requests.
- Exits within a bounded period.

### 17.8 Stress Test Reporting

Measure:

- Connection success.
- Request completion.
- Timeout behavior.
- Resource usage trends.
- Unexpected failures.

Avoid introducing complex performance benchmarking infrastructure unless a specific issue requires it.

---

## 18. Cross-Platform Foundations

Design the Go implementation to be portable.

Target:

- Windows.
- Linux.
- macOS, subject to RenderDoc availability.

### 18.1 Operating System Independence

Keep protocol, routing, and session logic independent of OS-specific behavior.

Isolate platform-specific code for:

- Process lifecycle.
- Signals.
- Service startup.
- Locking.
- Executable paths.
- Environment handling.

### 18.2 Network Binding

Use portable TCP networking.

Do not introduce Windows-only named pipes or Unix-only sockets during this phase.

### 18.3 Cross-Compilation

Verify the Go service can be built for intended platforms.

For example, validate supported combinations of `GOOS` and `GOARCH`.

Do not assume cross-compilation proves runtime compatibility.

### 18.4 Runtime Testing

Run deterministic protocol tests on available platforms.

Where RenderDoc cannot be used, run mock-client and mock-extension tests.

### 18.5 Windows Priority

Preserve the existing Windows user experience.

Cross-platform improvements must not break the current Windows installation or startup behavior.

### 18.6 Platform Limitations

Document OS-specific behavior that remains dependent on Python installation scripts or existing service launchers.

Those limitations can be addressed during Phases 18–19.

---

## 19. CI Integration

Add Go testing to the existing CI pipeline.

### 19.1 Required Checks

Include:

- `go test ./...`
- Race detection where supported.
- Static checks and formatting.
- Protocol fixture conformance.
- Python-to-Go compatibility tests.
- Service integration tests.
- Cross-platform builds.

### 19.2 Python Baseline

Continue running the existing Python IPC tests.

The Python implementation remains the reference during migration.

### 19.3 GUI-Independent CI

Ensure most tests can run without RenderDoc.

Use mock clients and deterministic fixtures.

### 19.4 Real RenderDoc Tests

Keep GUI-dependent integration tests separate where necessary.

Do not claim that a passing mock test proves actual RenderDoc compatibility.

### 19.5 Build Artifacts

CI may produce Go service binaries for testing.

Do not replace official distribution artifacts until the project explicitly adopts the Go service as the release implementation.

---

## 20. Migration and Rollback Strategy

The Python and Go services must remain separately runnable during Phase 17.

### 20.1 No Silent Replacement

Do not remove or disable the existing Python Shared IPC Service.

### 20.2 Explicit Service Selection

Provide a clear way for developers to select the Go service in testing.

Use existing configuration or launch mechanisms where possible.

### 20.3 Port Ownership

Never run both services on the same endpoint simultaneously.

Stop the active service before switching implementations, or use a separate test endpoint where supported.

### 20.4 Rollback

A developer must be able to return to the Python service without changing the IPC protocol or MCP tool definitions.

### 20.5 No Persistent State Assumptions

Investigate whether the current service persists state across restarts.

If the service uses only ephemeral state, document that.

Do not introduce persistent state migration machinery without a demonstrated need.

### 20.6 Compatibility During Transition

The Python MCP Bridge and RenderDoc Extension must remain compatible with both service implementations.

### 20.7 Release Policy

Do not make the Go service the default production implementation solely because basic tests pass.

Require the Phase 17 acceptance tests and document remaining risks.

---

## 21. Documentation

Update development documentation.

Suggested files:

```text
docs/
  development/
    go-shared-ipc-service.md
    go-migration-readiness.md
    ipc-compatibility.md
```

Adapt to the existing documentation organization.

### 21.1 Go Service Documentation

Explain:

- Architecture.
- Build instructions.
- Runtime configuration.
- Startup command.
- Shutdown behavior.
- Logging.
- Service selection.
- Compatibility expectations.
- Known limitations.

### 21.2 Developer Testing

Provide commands for:

- Building the Go service.
- Running unit tests.
- Running protocol compatibility tests.
- Starting the service.
- Connecting existing Python clients.
- Running integration tests.

### 21.3 Migration Documentation

Explain:

- Python service baseline.
- Go service testing.
- Known behavior differences.
- Rollback procedure.
- Remaining Phase 18 work.

### 21.4 User Documentation

Update user-facing English and Japanese documentation only where the behavior or installation instructions change.

Do not present the Go service as the default user installation until it is officially adopted.

---

## 22. Implementation Order

Follow an incremental implementation strategy.

### Step 1 — Contract Review

Validate Phase 16 documentation and tests.

Identify unresolved ambiguities.

### Step 2 — Protocol Library

Reuse or extend the Go IPC protocol implementation.

Implement complete framing, serialization, and decoding.

### Step 3 — Minimal TCP Service

Implement listening, accepting connections, and safe shutdown.

### Step 4 — Registration and Session State

Port existing client registration and session lifecycle behavior.

### Step 5 — Request and Response Routing

Implement request forwarding and correlation.

### Step 6 — Notifications and Lifecycle

Port notifications, disconnection, reconnect, and timeout handling.

### Step 7 — Python Compatibility

Run existing Python clients against the Go service.

Fix discrepancies without changing the wire contract.

### Step 8 — Multi-Agent Validation

Test concurrent Python MCP Bridges and one RenderDoc Extension.

### Step 9 — Real RenderDoc Validation

Run representative inspection workflows.

### Step 10 — Reliability Testing

Run concurrency, failure-injection, resource-leak, and restart tests.

### Step 11 — Cross-Platform CI

Verify portable builds and deterministic tests.

### Step 12 — Migration Documentation

Document how to select and test the Go service and how to roll back.

Avoid implementing the entire service before running any compatibility tests.

---

## 23. Acceptance Criteria

Phase 17 is complete when:

- [ ] The Go Shared IPC Service builds successfully.
- [ ] It runs as an independent daemon process.
- [ ] The existing IPC wire protocol is preserved.
- [ ] The default endpoint remains compatible.
- [ ] Existing Python MCP Bridges can connect without protocol modifications.
- [ ] The existing Python RenderDoc Extension can connect without protocol modifications.
- [ ] Registration and session lifecycle behavior is compatible.
- [ ] Request routing works correctly.
- [ ] Responses return to the correct requesting client.
- [ ] Concurrent in-flight requests are handled according to the existing contract.
- [ ] Notifications are forwarded correctly.
- [ ] Session and capture identities remain correct.
- [ ] Binary payloads are preserved.
- [ ] Large messages are handled safely.
- [ ] Error responses match the existing protocol.
- [ ] Disconnections clean up connection state.
- [ ] Timeouts clean up pending requests.
- [ ] Late responses cannot be misrouted.
- [ ] Multiple Python MCP Bridges can share one Go service.
- [ ] Concurrent startup does not create conflicting services.
- [ ] Another process owning the port is handled safely.
- [ ] Service shutdown releases resources.
- [ ] Service restart behavior is verified.
- [ ] Go unit and integration tests pass.
- [ ] Go race detection is executed on supported environments.
- [ ] Phase 16 golden protocol fixtures pass.
- [ ] Python-to-Go compatibility tests pass.
- [ ] Real RenderDoc integration is tested.
- [ ] Representative MCP inspection tools work through the Go service.
- [ ] Replay-sensitive operations are transported safely.
- [ ] No unexpected GUI state changes are introduced.
- [ ] Cross-platform compilation is verified.
- [ ] Platform-specific limitations are documented.
- [ ] The Python service remains available for rollback.
- [ ] Documentation describes the Go service and migration procedure.
- [ ] No production Go MCP Bridge is introduced.

Do not mark tests as passed unless they were executed.

Document unavailable testing environments and unsupported scenarios explicitly.

---

## 24. Deliverables

Provide the following.

### A. Go Implementation

- Standalone Go Shared IPC Service.
- Reusable Go protocol code.
- Session and connection management.
- Request routing.
- Lifecycle handling.
- Logging and diagnostics.

### B. Compatibility Tests

- Phase 16 fixture validation.
- Python client compatibility tests.
- Go protocol probe compatibility tests.
- Multi-client routing tests.
- Binary payload tests.
- Error and lifecycle tests.

### C. Reliability Tests

- Connection churn.
- Concurrent requests.
- Service restart.
- Slow clients.
- Malformed input.
- Resource cleanup.
- Race detection.

### D. Cross-Platform Validation

- Windows build.
- Linux build.
- macOS build where supported.
- Available runtime tests.
- Remaining platform-specific restrictions.

### E. Documentation

- Go service build and startup instructions.
- Protocol compatibility notes.
- Developer integration test instructions.
- Migration and rollback procedure.
- Phase 18 readiness report.

### F. Completion Report

Summarize:

- Implemented functionality.
- Tests executed.
- Tests not executed.
- Compatibility differences.
- Known bugs.
- Operational limitations.
- Remaining migration risks.

---

## Final Goal

At the end of Phase 17, the existing RenderEyeMCP clients must work with the Go Shared IPC Service.

The transition should be:

```text
Before Phase 17:

Python MCP Bridge ──┐
Python MCP Bridge ──┼── Python Shared IPC Service
RenderDoc Extension ┘


After Phase 17:

Python MCP Bridge ──┐
Python MCP Bridge ──┼── Go Shared IPC Service
RenderDoc Extension ┘
```

No changes to existing MCP tool definitions or RenderDoc inspection functionality should be required.

The Python Shared IPC Service must remain available as a reference and rollback implementation.

**Phase 17 is successful when the Go service is a tested, compatible replacement for the Python daemon, while the existing Python MCP Bridges and RenderDoc Extension continue to operate normally.**

Do not proceed with the production Go MCP Bridge migration until this compatibility baseline is established.
