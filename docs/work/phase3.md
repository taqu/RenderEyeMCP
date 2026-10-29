# RenderEyeMCP — Phase 3 Implementation Instructions

## Objective

Implement **Phase 3: RenderDoc Extension & IPC Integration** of RenderEyeMCP.

Previous phases established:

- **Phase 0:** MCP server foundation, RenderDoc integration feasibility, and local IPC proof of concept.
- **Phase 1:** Capture discovery, persistent Capture Registry, stable Capture IDs, and latest-capture resolution.
- **Phase 2:** RenderDoc process discovery, window management, Session Manager, capture opening, and safe session lifecycle control.

Phase 3 must establish reliable, production-oriented communication between the RenderEyeMCP server and RenderDoc's Python GUI extension.

The primary goal is to replace uncertain OS-level observations with authoritative information reported by the RenderDoc GUI itself.

The MCP server must be able to determine which capture is actually loaded in each connected RenderDoc instance, synchronize that information with existing sessions, and safely execute supported GUI operations.

**Implement functional code, integrate it with the existing architecture, and validate it using the installed RenderDoc application. Do not stop at documentation or proof-of-concept demonstrations.**

---

## 1. Environment and Constraints

### Existing Environment

- Operating system: Windows.
- Python is the primary implementation language.
- `uv` is already installed.
- RenderDoc installation directory:

  `D:\Programs\RenderDoc`

- Unity integration test project:

  `tests/TestProject`

- The repository should contain Phase 0–2 implementations.

### Mandatory Constraints

- Do not modify the production engine.
- Do not modify RenderDoc source code.
- Do not rebuild RenderDoc.
- Do not require custom RenderDoc binaries.
- Do not automatically terminate existing RenderDoc processes.
- Do not close unrelated RenderDoc windows.
- Do not overwrite existing captures.
- Do not modify Unity project settings unnecessarily.
- Preserve Phase 0–2 MCP APIs and data models wherever possible.
- Do not implement GPU frame analysis.
- Do not implement automatic capture comparison.
- Do not begin Phase 4.

### Architecture Principles

1. Keep the MCP server independent of RenderDoc GUI processes.
2. Keep the Python extension lightweight.
3. Avoid long-running work on the RenderDoc GUI thread.
4. Use RenderDoc's supported Python GUI APIs.
5. Treat extension-reported GUI state as authoritative only for the currently connected and verified instance.
6. Never infer loaded capture identity solely from window titles.
7. Preserve unmanaged and protected sessions.
8. Recover gracefully from extension crashes, disconnects, and server restarts.
9. Maintain backward compatibility with Phase 2 session-management APIs.
10. Fail safely when an operation cannot be verified.

---

## 2. Review Existing Implementation

Before making changes:

1. Inspect the entire repository.
2. Review Phase 0, Phase 1, and Phase 2 documentation.
3. Identify the existing IPC implementation.
4. Inspect the RenderDoc extension proof of concept.
5. Inspect Session Manager and Instance Manager implementations.
6. Review process and window identity models.
7. Review Capture Registry integration.
8. Inspect existing MCP tools.
9. Run the existing automated tests.
10. Identify incomplete Phase 2 operations that depend on Extension integration.

### RenderDoc API Verification

Inspect the installed RenderDoc distribution under:

`D:\Programs\RenderDoc`

Determine:

- RenderDoc version
- Embedded Python runtime version
- Supported extension registration APIs
- Available `qrenderdoc` interfaces
- Available capture-loaded state APIs
- Available capture viewer callbacks
- GUI-thread invocation mechanisms
- Supported capture opening and closing operations
- Extension installation directories and loading behavior

Consult RenderDoc documentation or source corresponding to the installed version.

Do not assume that API signatures remain identical across RenderDoc versions.

Document verified APIs and unsupported assumptions.

---

## 3. Target Architecture

The intended architecture is:

```text
Claude Code
    |
    | MCP
    v
RenderEyeMCP Server
    |
    +-- Capture Registry
    |      |
    |      +-- Capture IDs
    |      +-- .rdc metadata
    |
    +-- Session Manager
    |      |
    |      +-- Session IDs
    |      +-- Instance IDs
    |      +-- Window IDs
    |
    +-- Extension Connection Manager
           |
           +-- IPC Connection A
           |       |
           |       v
           |   RenderDoc GUI A
           |       |
           |       +-- RenderEye Extension
           |       +-- Capture A.rdc
           |
           +-- IPC Connection B
                   |
                   v
               RenderDoc GUI B
                   |
                   +-- RenderEye Extension
                   +-- Capture B.rdc
```

The MCP server is the coordinator.

Each RenderDoc GUI process runs an independent extension instance.

The extension reports its actual GUI state and executes verified GUI operations.

### Recommended Module Structure

```text
src/rendereye_mcp/
├── ipc/
│   ├── protocol.py
│   ├── transport.py
│   ├── connection.py
│   ├── authentication.py
│   └── manager.py
│
├── instances/
│   ├── manager.py
│   └── synchronization.py
│
├── sessions/
│   ├── manager.py
│   └── reconciliation.py
│
├── captures/
│   └── ...
│
└── server.py

extensions/
└── rendereye/
    ├── __init__.py
    ├── extension.json
    ├── ipc_client.py
    ├── gui_context.py
    ├── gui_dispatcher.py
    └── state_observer.py

tests/
├── ipc/
├── extensions/
├── integration/
└── TestProject/
```

Adapt the structure to the existing repository.

Do not duplicate working modules simply to follow this example.

---

## 4. Task A — RenderDoc Extension Lifecycle

Upgrade the Phase 0 extension into a reliable GUI integration component.

### Requirements

The extension must:

- Initialize when loaded by RenderDoc.
- Identify the running RenderDoc version.
- Identify its own extension version.
- Identify its process ID.
- Establish communication with the MCP server.
- Report its initial GUI state.
- Handle MCP server disconnection.
- Reconnect when the server becomes available.
- Release resources during extension unloading.
- Avoid preventing RenderDoc from closing normally.

### Extension Registration

Use the extension registration mechanism supported by the installed RenderDoc version.

Verify the actual extension metadata format and callback signatures.

Do not manually invoke callbacks owned by RenderDoc.

### Cleanup

Ensure extension unloading:

- Stops IPC communication.
- Stops background workers.
- Releases registered callbacks.
- Removes temporary observers or timers.
- Prevents callbacks from accessing destroyed objects.
- Does not leave Python worker threads running indefinitely.

### Failure Isolation

Unexpected extension errors must not terminate the RenderDoc GUI.

Catch exceptions at appropriate extension boundaries and report them through diagnostics.

Do not silently suppress errors.

### Deliverable

A reloadable and lifecycle-safe RenderDoc Python extension.

---

## 5. Task B — Authoritative GUI State Reporting

Implement reliable acquisition of the current RenderDoc GUI state.

### Minimum State

Each connected extension must report:

- RenderDoc version
- Extension version
- Process ID
- Runtime instance identity
- Whether a capture is loaded
- Current capture path, if available
- Capture loading or unloading status
- Last successful state observation
- State revision or sequence number

Example:

```json
{
  "type": "gui_state",
  "protocol_version": 1,
  "instance_id": "instance-000007",
  "revision": 42,
  "state": {
    "capture_loaded": true,
    "capture_path": "D:/Captures/frame042.rdc",
    "capture_state": "loaded"
  }
}
```

The example is illustrative.

### Capture Identification

Use the actual RenderDoc GUI context to identify the loaded capture.

Do not derive capture identity from:

- Window title alone
- Command-line arguments alone
- Process creation time
- Recently discovered capture files
- Previously requested capture paths

These values may assist correlation but are not authoritative evidence of the current GUI state.

### Important Distinction

A loaded capture path is not automatically a valid Phase 1 Capture ID.

Resolve the reported path through the Capture Registry.

If the file is outside configured directories, define a safe explicit behavior, such as:

- Reporting the external path without assigning a Capture ID
- Registering it through an approved registry mechanism
- Marking the association as unresolved

Do not fabricate Capture IDs.

### Capture Events

Investigate supported RenderDoc capture viewer callbacks.

Prefer real GUI events when available.

Relevant transitions include:

- No capture loaded
- Capture loading started
- Capture loaded successfully
- Capture loading failed
- Capture unloaded
- Capture replaced

If callbacks are unavailable, implement a bounded and documented polling fallback.

Do not block the GUI thread while waiting for filesystem or IPC operations.

### State Accuracy

Distinguish:

- `loaded`
- `unloaded`
- `loading`
- `error`
- `unknown`

Do not treat an old successful state report as proof of current GUI state after a connection is lost.

### Deliverable

An authoritative GUI state provider with documented freshness and confidence semantics.

---

## 6. Task C — IPC Protocol and Connection Management

Upgrade the Phase 0 IPC implementation for reliable multi-instance operation.

### Transport

Reuse the transport selected during Phase 0 unless testing demonstrates a significant limitation.

Supported possibilities include:

- Windows named pipes
- Loopback TCP sockets

Do not introduce an external message broker.

### Required Protocol Features

Implement:

- Protocol version negotiation
- Extension handshake
- Instance registration
- Connection authentication
- Heartbeat or liveness checking
- Request/response correlation
- GUI state snapshots
- GUI state notifications
- Structured error responses
- Explicit connection teardown

### Suggested Message Types

```text
hello
hello_ack

register_instance
register_ack

get_status
status_response

get_gui_state
gui_state_response
gui_state_changed

execute_gui_command
gui_command_result

heartbeat
heartbeat_ack

error
goodbye
```

Adapt message names to the existing protocol.

### Request Correlation

Every request requiring a response must include a unique request ID.

Responses must include the corresponding request ID.

Handle:

- Unknown request IDs
- Duplicate responses
- Request timeouts
- Late responses
- Connection loss during execution
- Protocol version mismatch

### Framing

Use explicit message framing.

Do not assume that a single socket read corresponds to exactly one JSON message.

Implement:

- Maximum message size
- UTF-8 encoding
- Framing validation
- Partial-read handling
- Malformed-message rejection

### Multiple Connections

The MCP server must support multiple RenderDoc extension clients simultaneously.

Each connection must have an independent:

- Runtime connection ID
- Authentication state
- Heartbeat state
- Outstanding request map
- Instance association
- Connection lifecycle

One failed extension connection must not affect other RenderDoc instances.

### Deliverable

A reliable, versioned, multi-client IPC subsystem.

---

## 7. Task D — IPC Security

The IPC channel controls local GUI functionality and must be treated as a privileged local control interface.

### Requirements

- Restrict communication to the local machine.
- Authenticate extension connections.
- Validate the protocol version.
- Validate all incoming messages.
- Reject unknown commands.
- Apply bounded timeouts.
- Apply maximum payload sizes.
- Avoid exposing arbitrary file access.
- Avoid arbitrary shell command execution.
- Avoid arbitrary Python evaluation.
- Do not execute serialized Python objects.

### Authentication

Select a practical local authentication mechanism.

For loopback TCP, consider a per-server random authentication token stored with user-restricted permissions.

For named pipes, evaluate Windows access control lists and connection authentication.

Do not rely solely on the claimed process ID in a JSON message.

### Instance Verification

Correlate extension registration information with the existing Instance Manager.

Use available operating-system identity evidence where practical.

If instance identity cannot be verified, classify the connection as untrusted or unresolved instead of silently attaching it to a managed session.

### Privileged Commands

Commands that can modify or close GUI state must require a verified, authorized connection.

Do not allow an unauthenticated or ambiguously associated client to execute destructive commands.

### Deliverable

Locally secured IPC communication with explicit trust boundaries.

---

## 8. Task E — GUI Thread Safety

Ensure RenderDoc API calls execute on an appropriate GUI thread or supported RenderDoc execution context.

### Requirements

- Investigate RenderDoc's Python GUI-thread invocation mechanisms.
- Do not access GUI objects from arbitrary worker threads.
- Do not block the GUI event loop with socket reads.
- Do not perform long blocking network operations from GUI callbacks.
- Avoid deadlocks between the extension and MCP server.
- Keep command execution time bounded where possible.

### Recommended Separation

**IPC Worker**

Responsible for:

- Transport communication
- JSON serialization
- Connection monitoring
- Message validation
- Request queues

**GUI Dispatcher**

Responsible for:

- Scheduling supported GUI operations
- Reading GUI state
- Executing GUI commands
- Returning results to the IPC worker

Use an appropriate mechanism verified against the installed RenderDoc and Qt/Python environment.

Do not assume that Qt bindings such as PySide or PyQt are available to the extension.

### Replay Thread

Do not directly use replay-thread APIs for ordinary GUI management.

Avoid implementing replay analysis.

Follow RenderDoc's documented thread-affinity requirements.

### Deliverable

A GUI-safe dispatcher and nonblocking IPC integration.

---

## 9. Task F — Instance Registration and Identity Reconciliation

Integrate connected extensions with the Phase 2 Instance Manager.

### Registration

When an extension connects:

1. Validate the IPC handshake.
2. Authenticate the connection.
3. Obtain RenderDoc process information.
4. Correlate it with a discovered RenderDoc instance.
5. Assign or recover the logical Instance ID.
6. Request an authoritative GUI state snapshot.
7. Update Instance Manager state.
8. Notify Session Manager of any relevant changes.

### Important Identity Rules

- A connection ID is not an Instance ID.
- A process ID is not a persistent Instance ID.
- A window handle is not a stable identity.
- A reconnecting extension may receive a new connection ID.
- The same RenderDoc process may reconnect multiple times.
- A restarted process must not inherit the identity of an unrelated previous process.

### Window Association

Use authoritative extension information where available.

Combine it with verified OS process-to-window mapping.

Do not assume that the extension can directly expose native top-level window handles.

If multiple windows belong to a process and the extension cannot identify the corresponding top-level window, preserve the ambiguity.

Do not create a confirmed association based only on window titles.

### Ownership Preservation

An externally launched RenderDoc instance remains external after its extension connects.

Extension connectivity does not grant permission to close or replace an unmanaged window.

Preserve the Phase 2 ownership model.

### Deliverable

Reliable extension-to-instance association without compromising ownership classification.

---

## 10. Task G — Session State Synchronization

Integrate GUI state reporting with the existing Session Manager.

### Objectives

- Resolve actual loaded captures.
- Detect manual GUI changes.
- Update session associations.
- Detect stale session state.
- Recover session information after reconnection.
- Avoid incorrect capture-to-window associations.

### Synchronization Flow

```text
RenderDoc GUI
    |
    | Capture loaded/unloaded
    v
RenderEye Extension
    |
    | gui_state_changed
    v
IPC Connection Manager
    |
    v
Instance Manager
    |
    v
Capture Registry Lookup
    |
    v
Session Manager Reconciliation
```

### Manual GUI Changes

Handle the following scenario:

1. Claude Code opens Capture A.
2. RenderEyeMCP creates Session A.
3. The user manually opens Capture B in the same RenderDoc GUI.
4. The extension reports the new loaded capture.
5. The Session Manager updates its state.

Expected result:

Session state must no longer claim that Capture A is currently loaded.

Define whether a manual capture replacement updates the current Session's capture association or transitions the existing Session to another documented state.

Choose consistent semantics and document them.

### State Revision

Use a monotonically increasing revision or equivalent sequence mechanism per extension runtime.

Prevent delayed notifications from overwriting newer snapshots.

After reconnection, require a fresh state snapshot before treating the connection as synchronized.

### Connection Loss

When an extension disconnects:

- Mark its authoritative GUI state as stale.
- Preserve historical metadata.
- Avoid incorrectly marking the RenderDoc process as terminated.
- Keep OS-level process discovery operational.
- Disable commands requiring a live extension connection.

Do not assume IPC disconnection means RenderDoc has closed.

### Reconciliation

On reconnection:

1. Authenticate the new connection.
2. Reidentify the process.
3. Obtain a complete GUI state snapshot.
4. Match the instance to existing sessions.
5. Reconcile capture associations.
6. Resolve stale or contradictory information.
7. Resume normal operation.

Do not automatically close windows or reload captures during reconciliation.

### Deliverable

A synchronized Session Manager using authoritative RenderDoc GUI state.

---

## 11. Task H — Supported GUI Commands

Implement a small, explicitly defined set of GUI commands.

The initial command set should support the requirements of existing Phase 2 MCP tools.

### Minimum Commands

**`get_gui_state`**

Return current GUI capture state.

**`focus_window`**

Focus the target RenderDoc GUI window where supported and verified.

If extension-side focus is not supported, retain Phase 2 Windows API behavior.

**`open_capture`**

Open a specified capture in the connected GUI using supported RenderDoc UI APIs.

**`close_capture`**

Close or unload the currently loaded capture where supported.

Do not confuse closing a capture with closing the entire RenderDoc window.

### Optional Command

**`request_window_close`**

Request graceful closure of the RenderDoc GUI window if a supported mechanism exists.

If unsupported, continue using the validated Phase 2 close implementation.

### Command Safety

For state-changing commands:

1. Verify the connection.
2. Verify the Instance ID.
3. Verify the Session ID.
4. Verify ownership and protection state.
5. Revalidate relevant preconditions immediately before execution.
6. Execute using the appropriate GUI context.
7. Obtain a post-operation GUI state snapshot.
8. Report the observed result.

### Capture Opening

Do not load a capture directly through low-level replay APIs when this would bypass or conflict with RenderDoc's GUI capture state.

Prefer RenderDoc's supported UI-level capture loading mechanism.

### Operation Preconditions

Use expected capture identity, GUI state revision, or equivalent guards where appropriate.

Reject stale commands instead of accidentally applying them to a different capture.

### Timeouts

A timeout does not prove that a GUI command failed.

If execution may have occurred but confirmation was lost, report an `unknown_outcome` state.

Do not blindly retry non-idempotent commands.

### Deliverable

A minimal, validated GUI command interface suitable for session management.

---

## 12. Task I — MCP Server Integration

Preserve all existing MCP tools.

Integrate authoritative GUI state into Phase 2 operations.

### Existing Tools to Update

#### `session_get`

Include:

- Extension connection status
- Actual loaded capture
- Capture association status
- Last GUI state update
- State freshness

#### `session_list`

Expose connection and synchronization status when useful.

#### `instance_list`

Include extension connectivity and identity verification status.

#### `capture_open`

Use Extension-provided GUI operations when appropriate.

Preserve `new_window`, `reuse`, and `replace` semantics from Phase 2.

Do not silently convert `new_window` into opening a capture inside an existing window.

#### `session_focus`

Use the best verified GUI focus implementation.

#### `session_close`

Preserve managed-only and protected-session safety requirements.

Do not weaken the existing closing rules.

#### `server_status`

Report:

- Active extension connections
- Synchronized instances
- Disconnected instances
- IPC listener health
- Protocol version
- Extension compatibility status

### Optional Diagnostic Tool

Add:

`instance_gui_state(instance_id)`

This tool returns the latest authoritative or cached GUI state with explicit freshness metadata.

Only add it if the information cannot be represented cleanly through existing APIs.

### Response Semantics

Distinguish:

- `confirmed`
- `inferred`
- `stale`
- `unavailable`
- `unsupported`
- `unknown_outcome`

Never present a stale capture association as confirmed.

### Deliverable

Existing MCP tools backed by synchronized RenderDoc GUI state.

---

## 13. Task J — Reconnection and Failure Recovery

Implement recovery mechanisms for common failures.

### Required Scenarios

**MCP Server Starts After RenderDoc**

A running extension must be able to connect when the server becomes available.

**MCP Server Restarts**

Extensions must reconnect without requiring RenderDoc restart where technically possible.

**RenderDoc Starts After MCP Server**

A newly loaded extension must register automatically.

**RenderDoc Exits Normally**

The server must detect the lost connection and reconcile process state.

**Extension Reload**

Reloading the extension must not produce duplicate active connections or sessions.

**Temporary IPC Failure**

Transient failures must trigger bounded reconnection attempts.

**Multiple Instances**

One disconnected instance must not disrupt other connected instances.

### Backoff

Implement bounded exponential backoff or an equivalent mechanism.

Avoid tight reconnect loops.

### Session Recovery

Preserve logical Session IDs when the runtime identity can be reliably matched.

Do not restore a confirmed relationship from stale PID or window-handle information alone.

### Failure Outcomes

Report explicit failures for:

- Extension unavailable
- Protocol mismatch
- Authentication failure
- Instance identity mismatch
- GUI state unavailable
- Command rejected
- Command timed out
- State synchronization failed
- Connection lost
- Unsupported GUI operation

### Deliverable

Reliable recovery without unintended GUI side effects.

---

## 14. Task K — Extension Installation and Distribution

Make the RenderEye extension straightforward to install.

### Requirements

- Verify the correct RenderDoc extension directory.
- Package the required extension files.
- Provide installation instructions.
- Provide a development installation method.
- Avoid modifying RenderDoc installation binaries.
- Avoid overwriting unrelated extensions.
- Support clean extension updates.
- Support uninstalling RenderEye without affecting other extensions.

### Development Installation

Provide a documented command or script to install the extension into the supported RenderDoc extension directory.

If an installer is implemented:

- Make it idempotent.
- Verify destination paths.
- Show which files will be copied.
- Avoid deleting unrelated files.
- Avoid modifying the RenderDoc executable.
- Handle insufficient filesystem permissions.

### Python Compatibility

RenderDoc uses its own Python environment.

Do not assume that the extension can import the MCP server package or packages installed through `uv`.

Keep extension dependencies minimal.

If shared protocol definitions are required, consider a lightweight dependency-free module or a build-time packaging step.

Avoid maintaining two inconsistent protocol implementations.

### Deliverable

A reproducible RenderDoc extension installation workflow.

---

## 15. Task L — Automated Tests

Implement automated tests that do not require RenderDoc or Unity for ordinary unit testing.

### Extension Lifecycle Tests

- Initialization
- Registration
- Unregistration
- Connection failure
- Extension reload
- Cleanup after failure

### IPC Tests

- Handshake success
- Protocol version mismatch
- Authentication failure
- Malformed message
- Oversized message
- Partial message
- Unknown command
- Request timeout
- Duplicate request ID
- Lost response
- Multiple concurrent clients
- Disconnection
- Reconnection
- Heartbeat timeout

### GUI State Tests

- No capture loaded
- Capture loading
- Capture loaded
- Capture unload
- Capture replacement
- State observation failure
- Out-of-order notifications
- Stale snapshots
- Missing capture path

### Instance Synchronization Tests

- One extension instance
- Multiple extension instances
- Reconnection to an existing process
- Process restart
- PID reuse
- Window handle reuse
- Ambiguous window association
- Unmanaged external instance

### Session Synchronization Tests

- Capture association updates
- Manual GUI capture replacement
- Extension disconnect
- Extension reconnect
- Capture ID resolution
- External capture path
- Session persistence after restart
- Protected session behavior

### GUI Command Tests

- Successful command
- Unsupported command
- Unauthorized command
- Stale state revision
- Command timeout
- Unknown execution outcome
- Command rejected due to ownership
- Command rejected due to protection

### Regression Tests

Ensure all Phase 0–2 tests continue to pass.

Use mocks or test doubles for RenderDoc GUI APIs.

Do not require real GUI windows for regular unit tests.

### Commands

Use the existing development workflow, including:

```bash
uv run pytest
uv run ruff check .
```

Run any existing static type checks where configured.

---

## 16. Task M — Real RenderDoc Integration Tests

Use the installed RenderDoc application:

`D:\Programs\RenderDoc`

Use real `.rdc` captures from the Phase 1 Capture Registry.

The Unity project in `tests/TestProject` may be used to generate additional captures if necessary.

### Scenario A — Extension Registration

1. Start the MCP server.
2. Start RenderDoc.
3. Load the RenderEye extension.
4. Observe extension registration.
5. Query `server_status`.

Expected:

The MCP server identifies the connected extension and verified RenderDoc instance.

### Scenario B — Loaded Capture Identification

1. Open Capture A in RenderDoc.
2. Query GUI state through the extension.
3. Compare the reported path to the actual loaded capture.
4. Resolve the path against the Capture Registry.

Expected:

The correct loaded capture is identified without relying on window title matching.

### Scenario C — Manual Capture Replacement

1. Open Capture A.
2. Verify the session association.
3. Manually open Capture B in the same GUI.
4. Observe the state update.
5. Query the associated session.

Expected:

The server reports Capture B as the current GUI capture and does not incorrectly retain Capture A as active.

### Scenario D — Multiple GUI Instances

1. Start two independent RenderDoc GUI instances where supported.
2. Load different captures.
3. Confirm separate extension connections.
4. Query both GUI states.
5. Focus each session independently.

Expected:

Each session reports the correct capture, and operations remain isolated.

### Scenario E — Server Restart

1. Start RenderDoc with an active capture.
2. Confirm extension connectivity.
3. Restart the MCP server.
4. Observe extension reconnection.
5. Query the recovered session.

Expected:

The extension reconnects and reports a fresh state snapshot without requiring the user to reopen the capture.

### Scenario F — Existing External RenderDoc

1. Launch RenderDoc manually.
2. Open a capture.
3. Start RenderEyeMCP.
4. Confirm the extension connects.
5. Attempt a destructive managed-only operation.

Expected:

The external window remains protected despite successful IPC connectivity.

### Scenario G — Extension Reload

1. Connect the extension.
2. Reload or disable and re-enable it using supported RenderDoc functionality.
3. Inspect connection state.

Expected:

No duplicate active extension connections or orphaned worker threads remain.

### Scenario H — Graceful GUI Operation

1. Open an owned test session.
2. Request a supported GUI operation.
3. Verify the resulting GUI state.
4. Close the managed test session when safe.

Expected:

The command affects only the intended managed GUI context.

### Test Safety

- Do not terminate existing user-created RenderDoc processes.
- Do not automatically close unrelated windows.
- Do not overwrite captures.
- Do not modify the production engine.
- Do not assume all tests can run unattended.
- Clearly separate automated tests from manual GUI tests.
- Report unexecuted tests explicitly.

---

## 17. Documentation

Update the existing documentation.

### README.md

Add:

- RenderEye Extension overview
- Extension installation instructions
- Connection setup
- Multi-instance behavior
- Troubleshooting
- Known limitations

### docs/architecture.md

Document:

- Extension architecture
- IPC transport
- GUI dispatcher
- Instance registration
- Session synchronization
- Trust boundaries
- Failure recovery

### docs/renderdoc_integration.md

Document:

- Installed RenderDoc version
- Verified Python GUI APIs
- Extension loading behavior
- Capture state reporting behavior
- Supported GUI operations
- GUI thread requirements
- Version-specific limitations

### docs/ipc_protocol.md

Create or update a protocol specification covering:

- Transport
- Authentication
- Message framing
- Protocol version
- Message schemas
- Connection lifecycle
- Request correlation
- Error codes
- Timeout semantics
- State revision handling

### docs/session_management.md

Update:

- Authoritative GUI state integration
- Capture association rules
- Reconciliation behavior
- Extension connection states
- Ownership and protection semantics

### docs/development.md

Add:

- Extension development workflow
- Extension installation commands
- IPC debugging
- Reconnection testing
- Integration test commands
- Troubleshooting procedures

---

## 18. Phase 3 Acceptance Scenarios

### Scenario A — Authoritative Capture State

A RenderDoc GUI has a capture open.

The extension reports the actual loaded capture path through IPC.

The Session Manager associates that path with the correct Capture ID.

**Expected:** The MCP server identifies the correct capture using verified GUI state.

### Scenario B — Independent GUI Sessions

Two RenderDoc instances have different captures loaded.

Both extensions communicate with the MCP server.

**Expected:** Each instance maintains independent connections and correct capture associations.

### Scenario C — User Changes Capture Manually

The user replaces the loaded capture through RenderDoc's GUI.

**Expected:** RenderEyeMCP updates the affected session without requiring Claude Code to reopen it.

### Scenario D — IPC Failure

A RenderDoc extension loses communication with the server.

**Expected:** Its authoritative GUI state becomes stale, while unrelated sessions remain operational.

### Scenario E — Recovery

The connection is restored.

**Expected:** A fresh GUI state snapshot is obtained, and session associations are safely reconciled.

### Scenario F — Non-Destructive Control

An external or protected RenderDoc window is connected to the MCP server.

**Expected:** Extension connectivity does not bypass ownership or protection restrictions.

---

## 19. Definition of Done

Phase 3 is complete when:

- [ ] The RenderEye extension can be loaded by the installed RenderDoc version.
- [ ] Extension initialization and shutdown are reliable.
- [ ] The extension communicates with the MCP server.
- [ ] IPC supports multiple independent clients.
- [ ] IPC messages are versioned and validated.
- [ ] IPC authentication and local access restrictions are implemented.
- [ ] The extension reports actual GUI capture state.
- [ ] Manual capture changes are detected.
- [ ] GUI state reports include freshness information.
- [ ] Existing Capture IDs can be resolved from reported paths.
- [ ] Instance identities are correlated safely.
- [ ] Session state is synchronized with GUI state.
- [ ] Connection loss does not invalidate unrelated sessions.
- [ ] Reconnection and state reconciliation work.
- [ ] Supported GUI commands execute in the correct context.
- [ ] Unsupported commands fail explicitly.
- [ ] Protected and unmanaged sessions remain safe.
- [ ] Extension installation is documented and reproducible.
- [ ] Unit tests pass.
- [ ] Phase 0–2 regression tests pass.
- [ ] Real RenderDoc integration tests are executed where possible.
- [ ] Limitations are documented accurately.

Do not mark Phase 3 complete if the primary end-to-end GUI state reporting path has not been verified against real RenderDoc.

If the installed RenderDoc version lacks required APIs, document the limitation and report partial completion.

---

## 20. Execution Instructions

Execute the implementation in the following order:

1. Inspect the repository and existing documentation.
2. Run Phase 0–2 regression tests.
3. Inspect the installed RenderDoc distribution.
4. Verify Python extension and GUI API availability.
5. Review and improve extension lifecycle handling.
6. Upgrade IPC protocol framing and message validation.
7. Implement secure connection registration.
8. Implement multiple extension connection management.
9. Implement GUI-safe execution.
10. Implement authoritative GUI state reporting.
11. Implement capture load/unload observation.
12. Integrate extension identity with Instance Manager.
13. Implement Session Manager synchronization.
14. Implement supported GUI commands.
15. Implement reconnection and recovery.
16. Implement reproducible extension installation.
17. Add unit and integration tests.
18. Test against the installed RenderDoc GUI.
19. Update documentation.
20. Run the full regression suite.
21. Review all acceptance criteria.

Work autonomously using the existing repository and available development tools.

Prefer minimal, verified APIs over speculative integration mechanisms.

Preserve existing functionality.

Avoid unnecessary dependencies.

Keep the extension lightweight.

Do not weaken session ownership or protection rules.

Do not silently report success for operations that cannot be verified.

If a particular RenderDoc API is unavailable, implement the supported subset and document the exact limitation.

Do not implement GPU analysis features.

Do not begin Phase 4.

---

## 21. Final Report

After implementation, provide:

1. **Implementation Summary** — What was implemented.
2. **Files Changed** — Main additions and modifications.
3. **RenderDoc Environment** — Installed version and verified Python APIs.
4. **Extension Architecture** — Lifecycle and GUI state reporting.
5. **IPC Protocol** — Transport, authentication, and message handling.
6. **Session Synchronization** — Capture and instance association behavior.
7. **GUI Commands** — Supported and unsupported operations.
8. **Test Results** — Exact tests executed and outcomes.
9. **Real RenderDoc Integration Results** — Verified behavior with the installed GUI.
10. **Known Limitations** — Unsupported APIs and unresolved risks.
11. **Phase 3 Status** — Complete, partially verified, or blocked.
12. **Phase 4 Readiness** — Stable APIs and remaining work for agent workflows.

Do not claim successful verification of tests that were not executed.

Do not begin Phase 4.

**Phase 3 Focus: Reliable RenderDoc Extension communication, authoritative GUI state synchronization, multi-instance IPC, and safe GUI control.**
