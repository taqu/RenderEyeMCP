# RenderEyeMCP — Phase 6 Implementation Instructions

## Shared IPC Service, Multi-Process MCP Support & Lifecycle Reliability

## Objective

Redesign RenderEyeMCP's internal IPC architecture to support multiple independent MCP server processes without TCP port conflicts.

The existing implementation starts an IPC TCP listener inside each MCP stdio server process.

This design assumes that only one RenderEyeMCP server process exists at a time.

However, coding agents such as OpenAI Codex may launch multiple MCP server processes during initialization, tool discovery, session creation, or reconnection.

Additionally, multiple coding agents may be used simultaneously.

RenderEyeMCP must support these scenarios reliably.

**Phase 6 must eliminate the assumption that every MCP server process owns a dedicated listener on the same fixed IPC port.**

Implement a shared IPC service architecture that supports multiple MCP clients and multiple RenderDoc GUI extensions while preserving existing capture/session management functionality.

This is an architectural implementation phase, not merely a workaround for Codex.

---

## 1. Background and Confirmed Problem

The following behavior was observed when Codex launched RenderEyeMCP:

```text
08:03:13 RenderEyeMCP starting: pid=44240
08:03:13 IPC transport listening on 127.0.0.1:37020
08:03:13 Starting MCP stdio server pid=44240

08:03:16 RenderEyeMCP starting: pid=45876
08:03:16 RenderEyeMCP shutdown started
08:03:16 RenderEyeMCP shutdown finished
```

The second process did not successfully start its own IPC listener.

A related failure was reported:

```text
OSError: [Errno 10048]
error while attempting to bind on address
```

Windows error 10048 indicates an address/port binding conflict.

### Existing Architecture

```text
Coding Agent A
    |
    v
MCP Server A
    |
    +-- IPC TCP Listener :37020

Coding Agent B
    |
    v
MCP Server B
    |
    +-- IPC TCP Listener :37020
                |
                v
           Port Conflict
```

### Confirmed Observations

- Claude Code can use RenderEyeMCP successfully.
- Claude Code continues working after restart.
- Codex may launch multiple RenderEyeMCP processes.
- At least two separate RenderEyeMCP PIDs were observed.
- An IPC listener successfully bound to port 37020.
- A subsequent process failed during initialization.
- Codex reported connection and tool discovery failures.

### Important Distinction

Do not assume that Codex is incorrectly launching multiple processes.

An MCP stdio client may start independent server processes.

RenderEyeMCP must not depend on a particular coding agent's process management behavior.

### Primary Problem

The IPC listener is owned by an individual MCP process even though the RenderDoc communication endpoint is conceptually shared across coding agents.

This is the architectural assumption Phase 6 must eliminate.

---

## 2. Target Architecture

Implement the following logical structure:

```text
Claude Code
    |
    | MCP stdio
    v
MCP Server Process A
    |
    | Local IPC Client
    |
    +------------------------+
                             |
Codex                        |
    |                        |
    | MCP stdio              |
    v                        |
MCP Server Process B         |
    |                        |
    | Local IPC Client       |
    |                        |
    +------------------------+
                             |
Codex Session 2              |
    |                        |
    | MCP stdio              |
    v                        |
MCP Server Process C         |
    |                        |
    | Local IPC Client       |
    |                        |
    +------------------------+
                             |
                             v
                   Shared IPC Service
                   (Single Owner)
                             |
               +-------------+-------------+
               |                           |
               v                           v
        Capture Registry             Session Manager
               |                           |
               +-------------+-------------+
                             |
                             v
                         IPC Router
                             |
                +------------+------------+
                |                         |
                v                         v
       RenderDoc Extension A     RenderDoc Extension B
                |                         |
                v                         v
          RenderDoc GUI A           RenderDoc GUI B
```

### Component Responsibilities

**MCP Server Process**

- Owns one MCP stdio connection.
- Registers and exposes MCP tools.
- Translates MCP requests into internal service requests.
- Connects to the shared IPC service.
- Does not bind the shared RenderDoc IPC port.
- Can terminate independently of other MCP processes.

**Shared IPC Service**

- Owns the internal IPC listener.
- Manages connected MCP clients.
- Manages RenderDoc extension connections.
- Routes commands and responses.
- Owns shared mutable application state.
- Coordinates Capture Registry and Session Manager operations.
- Maintains shared session and capture identity.
- Survives individual MCP client disconnections.

**RenderDoc Extension**

- Connects to the shared IPC service.
- Reports GUI and capture state.
- Receives authorized GUI commands.
- Maintains its existing CaptureContext integration.
- Reconnects when the shared service restarts.

### Core Invariant

**Only one active shared IPC service may own a given RenderEyeMCP service endpoint.**

Multiple MCP processes must be supported simultaneously.

---

## 3. Task A — Audit the Existing Architecture

Before modifying code, inspect the current implementation.

### Required Components

Inspect:

- MCP server creation
- MCP stdio entry points
- IPC transport implementation
- IPC authentication
- IPC connection manager
- RenderDoc extension IPC client
- Capture Registry
- Session Manager
- Persistent storage
- Process and instance identity
- Existing discovery mechanisms
- Server shutdown logic

### Questions to Answer

1. Which component currently creates the IPC listener?
2. Which component owns port 37020?
3. How does the RenderDoc extension discover that port?
4. How does the extension authenticate?
5. Which objects exist per MCP process?
6. Which objects must be shared?
7. Which components currently write to SQLite?
8. Which operations are already safe for concurrent access?
9. How are session identities persisted?
10. What happens when the MCP process terminates?
11. What happens when the extension reconnects?
12. Can multiple RenderDoc extensions already connect simultaneously?
13. Which existing protocol messages can be reused?
14. Which protocol changes are unavoidable?

### Preserve Existing Functionality

Do not discard working Capture Registry or Session Manager implementations.

Move ownership and adapt interfaces rather than rewriting components unnecessarily.

### Deliverable

A documented architecture audit and migration plan.

---

## 4. Task B — Implement a Dedicated Shared IPC Service

Implement a long-lived, local, per-user RenderEyeMCP service.

### Requirements

The service must:

- Run independently of individual MCP stdio sessions.
- Support multiple concurrent MCP clients.
- Support multiple RenderDoc extension connections.
- Own the shared IPC listener.
- Manage shared state.
- Provide explicit startup and shutdown behavior.
- Remain operational when one MCP client exits.
- Detect and recover from stale connections.

### Recommended CLI

Provide an internal service entry point such as:

```powershell
rendereye-mcp service run
```

This command is intended for the service supervisor or controlled manual operation.

The exact CLI may be adapted to the existing application.

### Windows

Initially, implement the service as a user-level background process.

Do not require:

- Administrator privileges
- Windows Service installation
- A system-wide daemon
- Modifying machine environment variables

Avoid implementing a privileged Windows Service unless there is a verified requirement.

### Linux

Use an equivalent per-user service model.

Do not hardcode Windows process-management APIs into shared service logic.

### Service Lifetime

The service must not shut down simply because a coding agent exits.

Define an explicit service lifetime policy.

Prefer an independently managed service that remains available across MCP client restarts.

Provide an optional controlled idle-shutdown policy only if it does not break extension reconnection or other active clients.

### Deliverable

A dedicated shared IPC service that can operate independently of MCP stdio processes.

---

## 5. Task C — Eliminate Fixed-Port Ownership from MCP Processes

Modify the existing MCP server startup implementation.

### Current Behavior

The MCP server currently performs:

```python
if ipc_transport is not None:
    await ipc_transport.start()

await registry.start()
session_manager.start()
session_manager.reconcile()

await server.run_stdio_async()
```

The IPC transport attempts to bind:

```text
127.0.0.1:37020
```

### Required Change

The MCP stdio process must no longer create the shared IPC listener.

Instead, it must connect to the shared service as a client.

### Conceptual New Behavior

```python
async def run_mcp_server():
    service_client = await connect_to_shared_service()

    try:
        await mcp_server.run_stdio_async()
    finally:
        await service_client.close()
```

This is illustrative.

Adapt the code to the actual MCP SDK and existing architecture.

### Important

Do not create a new listener when the shared service is already available.

Do not treat an arbitrary process listening on port 37020 as a trusted RenderEyeMCP service.

Do not suppress binding exceptions and continue with a disconnected server.

### Deliverable

MCP stdio servers that can coexist without competing for the same IPC listener.

---

## 6. Task D — Shared Service Startup and Discovery

Implement reliable discovery and startup of the shared service.

### Expected Behavior

When an MCP process starts:

1. Resolve the shared service endpoint.
2. Attempt to connect.
3. Authenticate and validate compatibility.
4. If a valid service exists, reuse it.
5. If no service exists, coordinate service startup.
6. Wait for the new service to become ready.
7. Connect to the ready service.
8. Begin MCP request processing.

### Concurrent Startup

Two or more MCP processes may start at nearly the same time.

They must not launch competing shared services.

### Startup Coordination

Implement a cross-process coordination mechanism.

Possible mechanisms include:

- Windows named mutex
- Linux advisory file locking
- Cross-platform process locking
- Endpoint ownership handshake combined with safe startup coordination

Choose a mechanism appropriate for the supported platforms.

### Race Conditions

Handle:

- Two MCP processes starting simultaneously
- Service starting but not ready
- Service crashing during startup
- Service exiting before a connection completes
- Stale endpoint metadata
- Failed authentication
- Incompatible service version
- Existing unrelated process using the configured port

### Important Safety Rule

Do not automatically terminate an existing process merely because it owns the expected port.

Verify identity and ownership through the service protocol.

### Deliverable

A race-safe service discovery and startup mechanism.

---

## 7. Task E — Local IPC Transport

Reuse the existing IPC protocol where practical.

### Requirements

- Support multiple concurrent connections.
- Support request-response correlation.
- Support asynchronous notifications.
- Support disconnection detection.
- Support bounded request timeouts.
- Support reconnection.
- Support protocol version negotiation.
- Support authentication.

### Transport Selection

For initial compatibility, the shared service may continue using loopback TCP.

Example:

```text
127.0.0.1:37020
```

However, the TCP listener must be owned only by the shared service.

Do not introduce a new hardcoded port per MCP process.

### Future Transport Flexibility

Keep the transport abstraction compatible with:

- Windows named pipes
- Linux Unix domain sockets
- Loopback TCP

Do not require implementing all transport types in Phase 6.

### Security

The shared service must bind only to the intended local interface.

Do not expose an unauthenticated administrative control service over the network.

Do not assume that loopback TCP alone provides sufficient access control.

### Deliverable

A multi-client local IPC transport with explicit ownership and authentication.

---

## 8. Task F — Authentication and Service Identity

The shared service must distinguish trusted RenderEyeMCP clients from arbitrary local processes.

### Requirements

- Authenticate MCP bridge connections.
- Authenticate RenderDoc extension connections.
- Verify service identity during discovery.
- Reject incompatible or unauthorized connections.
- Protect credentials stored on disk.
- Avoid logging authentication secrets.

### Service Identity

Provide a stable service identity for discovery and an ephemeral runtime instance identity for diagnostics.

Do not use process ID alone as proof of service identity.

### Authentication Material

Reuse existing IPC authentication infrastructure where possible.

If authentication tokens are stored locally:

- Use a user-private directory.
- Apply restrictive file permissions.
- Avoid embedding secrets in public `.env.example`.
- Avoid exposing secrets through MCP responses.
- Support recovery from stale or invalid credentials.

### Windows

Respect user-level installation and process isolation.

### Linux

Apply suitable filesystem permissions.

### Deliverable

Authenticated service discovery and client connections.

---

## 9. Task G — Shared Capture Registry and Session Manager

Review ownership of all shared mutable state.

### Current Risk

If every MCP process independently creates:

- Capture Registry
- Session Manager
- SQLite storage
- Session reconciliation

then simultaneous MCP processes may observe inconsistent state or compete over database operations.

### Required Design

Move shared mutable state ownership into the shared service, or implement a rigorously validated concurrent access model.

Prefer a single logical owner.

### Shared State

Include:

- Capture records
- Capture identities
- Latest capture resolution
- RenderDoc instance records
- Session identities
- Protected session state
- GUI connection state
- Capture-to-session relationships
- Pending GUI operations

### Persistence

Preserve existing SQLite databases and schemas wherever possible.

If a migration is necessary:

1. Back up existing databases.
2. Validate the current schema.
3. Apply a controlled migration.
4. Verify migrated data.
5. Preserve rollback capability.

### Reconciliation

Avoid running destructive or conflicting reconciliation concurrently in multiple MCP processes.

The shared service should coordinate registry and session reconciliation.

### Deliverable

Consistent shared capture/session state across all MCP clients.

---

## 10. Task H — MCP Bridge and Tool Compatibility

Preserve the existing MCP interface.

### Public MCP Tools

Existing tools must remain available, including implemented equivalents of:

- `server_status`
- `capture_list`
- `capture_get`
- `capture_latest`
- `capture_open`
- Session listing and management
- RenderDoc instance operations
- Diagnostics

Use the actual public tool names registered in the repository.

### Tool Registration

MCP tools must be registered even when the shared service is temporarily unavailable.

Service availability must not silently reduce the tool list to zero.

### Tool Execution

When an MCP tool is invoked:

1. Validate its arguments.
2. Forward the request to the shared service.
3. Await the corresponding response.
4. Translate the response into the existing MCP result schema.
5. Preserve existing error semantics.

### Service Unavailable

If the shared service cannot be contacted:

- Attempt supported recovery.
- Report an actionable service-unavailable error if recovery fails.
- Do not fabricate successful results.
- Do not suppress the exception and return an empty result.

### Compatibility

Preserve existing MCP tool names and parameter schemas.

Do not require coding agents to change their MCP configuration solely because of Phase 6.

### Deliverable

An MCP bridge that preserves the existing public API while using the shared service.

---

## 11. Task I — Multi-Client Request Routing

Implement safe routing for requests originating from multiple MCP processes.

### Request Identity

Every internal request must have a correlation identifier.

The shared service must associate:

- Request ID
- Client connection
- Requested operation
- Target RenderDoc instance
- Target session or capture, where applicable
- Completion status

### Concurrent Requests

Support concurrent operations from different MCP clients.

Examples:

- Claude Code lists captures while Codex queries sessions.
- Two MCP clients request different captures.
- One client disconnects while another operation continues.
- One client times out while another request succeeds.

### GUI Operations

Operations that modify the same RenderDoc GUI session must be coordinated.

Do not allow two simultaneous requests to corrupt session state.

Use suitable per-session serialization or concurrency control.

Do not globally serialize every operation unless required for correctness.

### Idempotency

Preserve existing idempotency guarantees.

Do not reissue potentially destructive GUI commands automatically after an uncertain timeout unless the operation is demonstrably idempotent.

### Responses

Responses must be routed to the originating MCP client.

Do not deliver one client's response to another client.

### Deliverable

Correct multi-client request routing with concurrency safety.

---

## 12. Task J — RenderDoc Extension Integration

Adapt the existing RenderDoc extension to communicate with the shared service.

### Requirements

- Preserve the verified RenderDoc extension API lifecycle.
- Preserve `register(version, pyrenderdoc)` compatibility.
- Preserve proper unregistration and cleanup.
- Preserve GUI-thread-safe dispatch.
- Preserve capture-state reporting.
- Preserve extension reconnection behavior.

### Service Connection

The RenderDoc extension should connect to the shared IPC service rather than an individual MCP stdio process.

### Multiple RenderDoc Windows

Support:

```text
RenderDoc GUI A → Shared Service
RenderDoc GUI B → Shared Service
RenderDoc GUI C → Shared Service
```

Maintain independent instance/session identities.

### State Notifications

The shared service must distribute relevant GUI state changes to interested MCP clients or update authoritative shared state.

Do not create duplicate Capture Registry records because multiple MCP clients observe the same event.

### Reconnection

If the shared service restarts:

1. Detect disconnection.
2. Reconnect using the documented policy.
3. Reauthenticate.
4. Reannounce extension identity.
5. Resynchronize current GUI and capture state.
6. Avoid duplicating session records.

### Deliverable

RenderDoc extension integration with the shared service and reliable reconnection.

---

## 13. Task K — Lifecycle Management

Define explicit lifecycle ownership.

### MCP Process Startup

- Connect to the shared service.
- Register MCP tools.
- Start stdio MCP transport.
- Serve client requests.

### MCP Process Shutdown

- Cancel outstanding bridge requests appropriately.
- Close its own service connection.
- Release local resources.
- Exit without stopping the shared service.

### Shared Service Startup

- Acquire startup ownership.
- Initialize authentication and IPC.
- Open persistent storage.
- Start Capture Registry.
- Start Session Manager.
- Reconcile persistent state.
- Accept extension and MCP connections.
- Advertise readiness.

### Shared Service Shutdown

- Stop accepting new requests.
- Resolve or cancel outstanding operations.
- Notify connected clients where supported.
- Close extension connections safely.
- Stop registry watchers.
- Stop session management.
- Close storage.
- Release the IPC endpoint.
- Release startup ownership.

### Cleanup Safety

Fix the previously identified startup cleanup weaknesses.

Initialization must be covered by reliable cleanup handling.

Cleanup failures in one component must not prevent cleanup of unrelated components.

Partially initialized components must be safe to clean up.

### Forced Termination

A process killed by the operating system may not execute Python `finally` blocks.

The service must recover correctly after abrupt termination.

Do not depend on graceful shutdown for correctness of persisted state.

### Important Safety Requirement

Stopping the shared service must not automatically close unrelated RenderDoc GUI windows.

Preserve protected sessions and externally owned windows.

### Deliverable

Explicit and reliable lifecycle behavior for MCP clients, shared service, and RenderDoc extensions.

---

## 14. Task L — Service Failure and Recovery

Handle shared service failures without corrupting application state.

### Required Scenarios

- Service process crashes.
- Service is forcibly terminated.
- IPC listener unexpectedly closes.
- Authentication state becomes invalid.
- Storage is temporarily unavailable.
- Client disconnects during an operation.
- RenderDoc extension disconnects.
- Service restarts while multiple clients exist.

### Recovery

Implement bounded retries with backoff where appropriate.

Do not implement unbounded busy-loop reconnection.

Do not create a new service for every failed connection attempt.

### Startup Conflicts

If the service endpoint is already occupied:

1. Attempt the authenticated service handshake.
2. Determine whether it is the expected RenderEyeMCP service.
3. If valid, connect to it.
4. If incompatible, return a specific error.
5. If unrelated, do not terminate it.
6. Do not use unsafe socket reuse options to bypass exclusive ownership.

### State Reconciliation

After recovery, reconcile:

- Capture Registry
- Session Registry
- Extension connections
- Loaded captures
- Pending operations

Preserve uncertainty where authoritative confirmation is unavailable.

### Deliverable

Reliable service restart and recovery behavior.

---

## 15. Task M — Installation and Configuration

Integrate the shared service with existing installation methods.

### Supported End-User Installation

- `uv tool install`
- Standard Python wheel installation using pip
- Manual installation

### Development

Keep `uv sync` in developer documentation only.

### Required CLI Behavior

Preserve:

```powershell
rendereye-mcp serve
rendereye-mcp setup
rendereye-mcp setup-agent codex
rendereye-mcp doctor
```

Add service-management commands where appropriate.

Suggested commands:

```powershell
rendereye-mcp service status
rendereye-mcp service start
rendereye-mcp service stop
rendereye-mcp service restart
```

These commands are proposed interfaces.

Adapt to the existing CLI and implementation.

### Automatic Startup

Normal coding agent usage should not require the user to start the shared service manually.

The MCP bridge should discover or initiate the shared service through the supported startup mechanism.

### Configuration

Continue using:

`RENDEREYE_ENV_FILE`

to locate the application `.env`.

Do not add unnecessary persistent system environment variables.

### Agent Configuration

Existing coding agent configurations should remain simple:

```text
rendereye-mcp serve
```

Do not require Codex-specific or Claude Code-specific service initialization scripts.

### Upgrade

Preserve existing application configuration and registry databases.

Handle any service process using an older application version.

Do not silently connect incompatible protocol versions.

### Deliverable

A shared service integrated into the existing user-friendly installation workflow.

---

## 16. Task N — Diagnostics and Observability

Improve lifecycle and IPC diagnostics.

### Required Log Fields

Include:

- Timestamp
- Process ID
- Process role
- Runtime instance ID
- Service identity
- Connection ID
- Protocol version
- Relevant request IDs

### Example

```text
08:03:13 [MCP] pid=44240 connecting to shared service
08:03:13 [SERVICE] pid=12000 listening on 127.0.0.1:37020
08:03:13 [MCP] pid=44240 connected service=12000

08:03:16 [MCP] pid=45876 connecting to shared service
08:03:16 [MCP] pid=45876 connected service=12000
```

### Important

Process IDs in this example are illustrative.

Do not log credentials or authentication tokens.

### Doctor Command

Extend:

```powershell
rendereye-mcp doctor
```

Report:

- Shared service state
- Shared service PID
- IPC endpoint
- Protocol compatibility
- Connected MCP client count
- Connected RenderDoc extension count
- Registry availability
- Session Manager availability
- Connection errors

Do not expose sensitive client data unnecessarily.

### stdout Safety

MCP stdio processes must never emit ordinary diagnostic text to stdout.

Use stderr or configured log files.

Ensure Python stderr output is valid UTF-8 for clients that require it.

### Deliverable

Diagnostics sufficient to distinguish process creation, service connection, and service ownership problems.

---

## 17. Task O — Automated Tests

Create a comprehensive multi-process test suite.

### Test 1 — Single MCP Client

Start one MCP client.

Expected:

- Shared service starts or is discovered.
- MCP initializes.
- Tools are discoverable.
- Read-only tools work.

### Test 2 — Concurrent MCP Clients

Start two independent MCP processes simultaneously.

Expected:

- Both initialize successfully.
- Both connect to the same shared service.
- Neither attempts to bind port 37020.
- Both expose the expected MCP tools.

### Test 3 — Three or More Clients

Start at least three independent MCP processes.

Expected:

- No listener conflict.
- No duplicate shared service.
- All clients remain functional.

### Test 4 — Simultaneous Service Startup

Start multiple MCP processes while no shared service is running.

Expected:

- Exactly one shared service takes ownership.
- All MCP processes eventually connect.
- Startup remains bounded.

### Test 5 — One Client Disconnects

Disconnect MCP Client A while Client B remains active.

Expected:

- Client B continues operating.
- Shared service remains available.
- RenderDoc extension connection remains active.

### Test 6 — Multiple RenderDoc Extensions

Connect two simulated extension instances.

Expected:

- Both are tracked independently.
- State reports remain isolated.
- Requests route to the correct extension.

### Test 7 — Shared Service Crash

Terminate the shared service unexpectedly in an isolated test environment.

Expected:

- Clients detect disconnection.
- Recovery follows documented behavior.
- No duplicate service ownership occurs.
- Persistent state remains valid.

### Test 8 — Repeated Codex-Like Starts

Simulate:

```text
Start MCP A
Start MCP B
Stop MCP A
Start MCP C
Stop MCP B
Start MCP D
```

Expected:

- All valid MCP processes initialize successfully.
- No port-binding errors occur.
- No orphaned bridge processes accumulate.

### Test 9 — Conflicting Endpoint

Use a separate test process to occupy the configured endpoint.

Expected:

- RenderEyeMCP does not kill that process.
- Authentication or identity verification fails safely.
- An actionable error is returned.

### Test 10 — Shared Registry Consistency

Execute concurrent capture queries and session operations.

Expected:

- Consistent Capture IDs
- Consistent Session IDs
- No duplicate logical records
- No database corruption

### Test 11 — Forced Shutdown

Terminate an MCP bridge without graceful cleanup.

Expected:

- Shared service remains operational.
- Other clients remain connected.
- Stale client state is eventually removed.

### Test 12 — MCP Tool Discovery

Run MCP initialization and `tools/list` independently for every client.

Expected:

- Nonempty tool list
- Correct schemas
- Successful read-only invocation

### Test 13 — Authentication

Verify:

- Valid client authentication
- Invalid client rejection
- Protocol mismatch rejection
- Unauthorized endpoint rejection

### Test 14 — Cross-Platform

Run supported headless tests on Windows and Linux.

Do not require a real GPU or RenderDoc GUI for ordinary CI tests.

### Deliverable

Automated evidence that RenderEyeMCP supports multiple independent MCP clients safely.

---

## 18. Task P — Real Coding Agent Verification

Test the architecture with actual coding agents where available.

### Claude Code

1. Configure RenderEyeMCP.
2. Launch Claude Code.
3. Verify MCP tools.
4. Invoke read-only tools.
5. Restart Claude Code.
6. Verify reconnection.

### Codex

1. Configure RenderEyeMCP.
2. Launch Codex.
3. Execute `/mcp`.
4. Confirm RenderEye reports connected.
5. Confirm a nonzero tool count.
6. Exit Codex.
7. Relaunch Codex.
8. Repeat `/mcp`.
9. Verify tools remain available.

### Simultaneous Usage

1. Start Claude Code.
2. Start Codex.
3. Connect both to RenderEyeMCP.
4. Verify both clients can list captures.
5. Verify independent MCP sessions.
6. Close one coding agent.
7. Verify the other remains functional.
8. Confirm RenderDoc GUI windows remain open.

### Additional Agents

Where installed, test Cursor, VS Code/Copilot, and Gemini CLI.

### Verification

Collect:

- MCP client status
- MCP tool count
- Shared service PID
- MCP bridge PIDs
- Active IPC connections
- Relevant errors

Do not mark an untested client as verified.

### Deliverable

A real multi-agent interoperability report.

---

## 19. Task Q — Documentation

Update:

- `README.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/installation.md`
- `docs/troubleshooting.md`
- Coding agent integration guides
- IPC protocol documentation

### Required Documentation

Explain:

- Why the shared IPC service exists.
- Why MCP stdio processes are independent.
- How the shared service starts.
- How service discovery works.
- How RenderDoc extensions connect.
- How multiple coding agents share RenderDoc state.
- How to inspect service status.
- How to restart the service safely.
- How to diagnose authentication or port conflicts.
- How service failure recovery works.

### README

Update the architecture overview to reflect the shared service.

Do not leave diagrams showing every MCP process independently owning port 37020.

### User Experience

Keep normal installation and agent setup simple.

Users should not need to understand the internal service architecture to use RenderEyeMCP.

### Deliverable

Accurate and approachable documentation for the new architecture.

---

## 20. Migration and Compatibility

Phase 6 changes internal service ownership.

Review compatibility carefully.

### Existing Installations

Preserve:

- `.env`
- Capture Registry database
- Session Registry database
- User-defined capture directories
- Protected sessions
- Agent MCP configuration

### Existing Extension

If the existing extension protocol remains compatible, reuse it.

If protocol changes are necessary:

- Introduce explicit protocol versioning.
- Detect incompatibility.
- Provide a clear upgrade path.
- Avoid silently accepting incompatible messages.

### Existing Service Process

An older RenderEyeMCP process may already own port 37020.

Do not automatically terminate it without verified ownership and an explicit safe migration policy.

### Rollback

Document rollback limitations.

Avoid irreversible database migrations without backup and recovery procedures.

### Deliverable

A controlled migration from per-MCP IPC listeners to the shared IPC service.

---

## 21. Scope Boundaries

Do not implement unrelated functionality.

Excluded:

- Shader debugging
- Texture inspection
- GPU frame analysis
- Automatic frame comparison
- Autonomous GPU diagnosis
- New capture formats
- Unrelated coding agent integrations
- Production engine modifications

Do not change public MCP schemas without necessity.

Do not replace working RenderDoc GUI session safety mechanisms.

Do not use `SO_REUSEADDR` or equivalent socket options as a workaround for multiple services binding the same logical endpoint.

Do not terminate unrelated processes.

Do not weaken IPC authentication to simplify service discovery.

---

## 22. Definition of Done

Phase 6 is complete when:

- [ ] Shared IPC service architecture is implemented.
- [ ] MCP stdio processes no longer independently bind the shared IPC port.
- [ ] Only one service owns the configured endpoint.
- [ ] Concurrent service startup is race-safe.
- [ ] Multiple MCP clients can connect simultaneously.
- [ ] Multiple RenderDoc extensions can connect simultaneously.
- [ ] IPC authentication remains enforced.
- [ ] Service identity is verified.
- [ ] Capture Registry has consistent shared ownership.
- [ ] Session Manager has consistent shared ownership.
- [ ] Existing MCP tools remain available.
- [ ] MCP `tools/list` returns the expected tools.
- [ ] Request routing preserves client identity and response correlation.
- [ ] Concurrent GUI operations are safely coordinated.
- [ ] MCP client shutdown does not terminate the shared service.
- [ ] Shared service shutdown cleans up resources safely.
- [ ] Forced termination does not corrupt persistent state.
- [ ] Service recovery is implemented.
- [ ] Extension reconnection works.
- [ ] Protected RenderDoc GUI sessions remain protected.
- [ ] Existing `.env` configuration is preserved.
- [ ] Existing coding agent configurations remain compatible where possible.
- [ ] Installation workflows support the shared service.
- [ ] Diagnostics report service and client state.
- [ ] Multi-process automated tests pass.
- [ ] Windows CI tests pass.
- [ ] Linux tests pass where supported.
- [ ] Real Claude Code integration is verified where available.
- [ ] Real Codex integration is verified where available.
- [ ] Simultaneous multi-agent usage is verified where available.
- [ ] README and architecture documentation are updated.
- [ ] Existing Phase 0–5 regression tests remain passing.

### Mandatory Release Gate

**Do not mark Phase 6 complete if starting two independent MCP server processes causes a port-binding failure.**

The architecture must allow multiple coding agents to operate simultaneously without requiring users to manually terminate existing RenderEyeMCP processes.

Also, do not mark Phase 6 fully verified if only mocked single-client tests have been executed.

At minimum, run real concurrent subprocess tests against the shared service.

---

## 23. Execution Instructions

Execute the implementation in this order:

1. Inspect the existing architecture.
2. Reproduce the fixed-port conflict in an automated test.
3. Identify shared and per-client state.
4. Define service ownership boundaries.
5. Design service discovery and authentication.
6. Implement the dedicated shared IPC service.
7. Implement race-safe startup coordination.
8. Move the IPC listener out of MCP stdio processes.
9. Implement MCP-to-service connections.
10. Migrate shared registry and session ownership.
11. Implement multi-client request routing.
12. Adapt RenderDoc extension connectivity.
13. Implement service and extension reconnection.
14. Implement safe service lifecycle handling.
15. Implement failure recovery.
16. Add service-management CLI support.
17. Integrate with existing installation workflows.
18. Add diagnostics and structured logging.
19. Implement multi-process regression tests.
20. Verify simultaneous MCP connections.
21. Verify service crash and restart behavior.
22. Verify database and session consistency.
23. Execute Windows and Linux tests where available.
24. Test Claude Code and Codex integration.
25. Test simultaneous coding agent usage.
26. Update README and architecture documentation.
27. Run the complete regression suite.
28. Review all acceptance criteria.
29. Produce the final implementation report.

Work autonomously using the existing repository and development environment.

Do not stop after making the second bind failure disappear.

Do not silently disable IPC functionality in additional MCP processes.

Do not implement an unreliable fallback that reports connected while RenderDoc communication is unavailable.

Do not modify RenderDoc source code.

Do not modify the production engine.

Do not publish a GitHub Release without explicit authorization.

---

## 24. Final Report

After implementation, provide:

1. **Root Cause Summary** — Why multiple MCP processes conflicted.
2. **Architecture Changes** — Old and new process/IPC ownership models.
3. **Files Changed** — Service, MCP bridge, IPC, registry, session, tests, and documentation.
4. **Shared Service Implementation** — Startup, discovery, authentication, and lifecycle.
5. **Multi-Client Routing** — Request handling and concurrency guarantees.
6. **RenderDoc Integration** — Extension connection and reconnection behavior.
7. **State Consistency** — Registry and Session Manager ownership.
8. **Security Review** — Authentication and endpoint protection.
9. **Automated Tests** — Exact commands and results.
10. **Concurrent Process Tests** — Number of clients and observed behavior.
11. **Real Coding Agent Tests** — Claude Code, Codex, and other tested clients.
12. **Failure Recovery Tests** — Service crash, restart, and stale connection handling.
13. **Migration Results** — Existing configuration and database compatibility.
14. **Documentation Changes** — README and relevant guides.
15. **Known Limitations** — Unsupported scenarios or remaining issues.
16. **Phase 6 Status** — COMPLETE, PARTIALLY VERIFIED, or BLOCKED.
17. **Release Readiness** — Whether shared IPC and multi-agent support are reliable enough for distribution.

Distinguish implemented behavior from verified behavior.

Do not claim success for tests that were not executed.

**Primary Goal: Allow multiple independent MCP server processes and coding agents to share RenderDoc safely through a single authenticated IPC service, eliminating fixed-port conflicts and preserving reliable capture/session management.**
