# RenderEyeMCP — Phase 2 Implementation Instructions

## Objective

Implement **Phase 2: RenderDoc Instance & Session Management** of RenderEyeMCP.

Phase 0 established the MCP server foundation, RenderDoc integration proof of concept, and local IPC infrastructure.

Phase 1 implemented capture discovery, readiness validation, persistent Capture IDs, and the Capture Registry.

Phase 2 must build on these foundations to provide reliable management of RenderDoc processes, GUI windows, and debugging sessions.

The primary goal is to enable coding agents such as Claude Code to open multiple `.rdc` captures, identify the correct RenderDoc window, focus individual windows, and safely close managed sessions without disrupting unrelated debugging work.

**Implement working functionality, automated tests, and real RenderDoc integration wherever the local environment permits. Do not stop at architectural documentation.**

---

## 1. Environment and Project Constraints

### Existing Environment

- Operating system: Windows.
- Python is the primary implementation language.
- `uv` is already installed.
- RenderDoc is installed under:

  `D:\Programs\RenderDoc`

- A Unity test project is available at:

  `tests/TestProject`

- Phase 0 and Phase 1 implementations should already exist in the repository.

### RenderDoc Installation

Use `C:\Program Files\RenderDoc` as the preferred initial RenderDoc installation search location.

Do not assume that `qrenderdoc.exe` is necessarily located directly in that directory.

Inspect the directory and locate the actual executable.

Verify the installed RenderDoc version and supported command-line options.

Preserve support for user-configured executable paths.

Do not hardcode the installation path into the core implementation.

### Constraints

- Do not modify the production engine.
- Do not modify RenderDoc source code.
- Do not rebuild RenderDoc.
- Do not modify Unity project settings unnecessarily.
- Do not terminate unrelated RenderDoc processes.
- Do not close unmanaged windows automatically.
- Do not assume one process always corresponds to one window.
- Do not assume one window always corresponds to one capture.
- Do not assume every RenderDoc process was started by RenderEyeMCP.
- Do not implement GPU frame analysis.
- Do not implement full RenderDoc Extension integration from Phase 3 prematurely.

Preserve existing Phase 0 and Phase 1 functionality.

---

## 2. Review Existing Implementation

Before making changes:

1. Inspect the repository structure.
2. Review Phase 0 and Phase 1 documentation.
3. Inspect the MCP server implementation.
4. Inspect the Capture Registry and Capture ID model.
5. Review existing Windows process discovery helpers.
6. Review the RenderDoc extension proof of concept and IPC implementation.
7. Inspect the current configuration architecture.
8. Run the existing test suite.
9. Identify reusable components and unresolved integration limitations.

Do not create duplicate implementations of existing functionality.

If a Phase 0 or Phase 1 component requires a small compatibility adjustment, implement it and document the reason.

---

## 3. Architecture

Implement a dedicated instance and session management subsystem.

Suggested structure:

```text
src/rendereye_mcp/
├── captures/
│   └── ...                  # Existing Phase 1 implementation
│
├── instances/
│   ├── __init__.py
│   ├── models.py
│   ├── discovery.py
│   ├── launcher.py
│   └── manager.py
│
├── sessions/
│   ├── __init__.py
│   ├── models.py
│   ├── manager.py
│   ├── storage.py
│   └── reconciliation.py
│
├── platform/
│   ├── windows.py
│   └── window_control.py
│
├── server.py
└── config.py

tests/
├── instances/
│   ├── test_discovery.py
│   ├── test_launcher.py
│   └── test_manager.py
│
├── sessions/
│   ├── test_manager.py
│   ├── test_storage.py
│   └── test_reconciliation.py
│
├── test_window_control.py
├── test_session_mcp.py
└── TestProject/
```

Adapt this structure to the actual repository.

### Component Responsibilities

**Instance Discovery**

Discover RenderDoc GUI processes and identify associated windows.

**Instance Launcher**

Launch RenderDoc with a selected capture and observe the resulting process or window.

**Instance Manager**

Track known RenderDoc processes, runtime identities, and management ownership.

**Session Manager**

Manage logical debugging sessions independently of operating-system process IDs.

**Session Storage**

Persist session metadata and relationships.

**Session Reconciliation**

Synchronize persisted session state with actual running processes and windows.

**Windows Platform Adapter**

Provide process enumeration, window enumeration, focus operations, and safe close requests.

**MCP Interface**

Expose session-management operations to coding agents.

Keep process discovery and GUI control independent of MCP tool handlers.

---

## 4. Task A — Data Models and Identity

Define the following entities.

### Capture

Represents an `.rdc` capture already managed by the Phase 1 Capture Registry.

Use existing Capture IDs.

Do not introduce a separate capture identification system.

### Instance

Represents a discovered or managed RenderDoc GUI process.

Track:

- Instance ID
- Process ID
- Process creation time
- Executable path
- Command-line information when available
- Ownership classification
- Connection status
- Associated windows
- Last observation time

An Instance ID must not be equivalent to a process ID.

### Window

Represents a RenderDoc GUI window.

Track:

- Window ID
- Native window handle
- Owning process identity
- Window title
- Visibility state
- Last observation time
- Associated Session ID, if confirmed

A Window ID must not be equivalent to a native window handle.

### Session

Represents a logical debugging session managed by RenderEyeMCP.

Track:

- Session ID
- Capture ID
- Instance ID
- Window ID when available
- Session creation time
- Last activity time
- Session status
- Managed/unmanaged ownership
- Protection state
- Last known capture path
- Confidence of the capture-to-window association

Example:

```json
{
  "session_id": "session-000042",
  "capture_id": "cap-000018",
  "instance_id": "instance-000007",
  "window_id": "window-000007",
  "process_id": 18320,
  "status": "active",
  "managed": true,
  "protected": false,
  "association_status": "confirmed"
}
```

The example is illustrative.

### Identity Requirements

- Use stable logical IDs.
- Do not derive persistent IDs exclusively from PIDs or window handles.
- Handle PID reuse.
- Handle window handle reuse.
- Maintain explicit relationships between entities.
- Distinguish confirmed relationships from inferred relationships.
- Do not silently assign a capture to a window when the relationship is ambiguous.

Document entity identity and lifecycle semantics.

---

## 5. Task B — RenderDoc Process Discovery

Implement reliable RenderDoc process discovery on Windows.

### Requirements

- Discover currently running RenderDoc GUI processes.
- Identify the actual executable path.
- Collect process IDs and creation timestamps.
- Distinguish GUI processes from unrelated RenderDoc utilities.
- Avoid identifying unrelated processes solely by window title.
- Detect newly started processes.
- Detect exited processes.
- Handle insufficient permissions.
- Handle processes that exit during enumeration.
- Avoid querying unnecessary system-wide process information.

Use the installed RenderDoc executable under `D:\Programs\RenderDoc` as an initial trusted executable candidate, subject to verification.

### Ownership Classification

Classify discovered processes as:

- `managed` — Started and tracked by RenderEyeMCP.
- `external` — Discovered but not started by RenderEyeMCP.
- `unknown` — Ownership cannot be established reliably.

Do not classify a process as managed solely because its executable matches RenderDoc.

External processes must remain non-destructive observation targets unless an explicit, supported management operation establishes ownership or authorization.

### Process Identity

Use process creation time together with PID and verified executable identity to distinguish process lifetimes.

Be careful with Windows process ID reuse.

### Deliverable

A reusable RenderDoc process discovery component.

---

## 6. Task C — Window Discovery and Correlation

Implement Windows GUI window discovery.

### Requirements

- Enumerate top-level windows.
- Associate windows with owning process IDs.
- Identify candidate RenderDoc GUI windows.
- Collect window handles, titles, and visibility state.
- Handle hidden and minimized windows.
- Handle destroyed windows.
- Avoid treating child windows as independent GUI instances.
- Support more than one window per process.
- Revalidate handles before use.

Use appropriate Windows APIs.

Possible APIs include:

- `EnumWindows`
- `GetWindowThreadProcessId`
- `IsWindow`
- `IsWindowVisible`
- `GetWindowTextW`

Use `ctypes` or an existing lightweight dependency where appropriate.

Avoid introducing a large desktop automation framework unless necessary.

### Correlation

Correlate:

```text
RenderDoc Process
       |
       v
   Instance ID
       |
       v
   Window ID(s)
       |
       v
   Session ID(s)
```

Do not assume that window titles contain accurate capture paths.

Window title matching may be used as a diagnostic heuristic, but it must not be treated as authoritative proof of the loaded capture.

### Deliverable

A reliable process-to-window discovery and correlation layer.

---

## 7. Task D — RenderDoc Instance Launching

Implement a reusable RenderDoc launcher.

### Requirements

- Resolve the configured RenderDoc executable.
- Validate the selected Capture ID through the Phase 1 Registry.
- Verify that the capture is currently accessible.
- Launch RenderDoc using verified command-line syntax.
- Avoid shell command interpolation.
- Handle paths containing spaces and Unicode characters.
- Track the launched process when possible.
- Detect startup failures.
- Use bounded timeouts.
- Avoid leaving orphaned management state after launch failures.

### Important Investigation

Determine how the installed RenderDoc version behaves when:

1. No RenderDoc GUI is running.
2. One RenderDoc GUI is already running.
3. Multiple RenderDoc windows are already open.
4. The same capture is opened repeatedly.
5. A different capture is opened while another capture is open.

Specifically investigate whether RenderDoc reuses existing processes or windows.

Do not assume that launching `qrenderdoc.exe` always creates a new independent GUI instance.

### New Window Requirement

The `new_window` operation must have clearly defined semantics.

If the installed RenderDoc version cannot guarantee a new window using its supported interfaces, do not report a successful new-window operation merely because a launch command succeeded.

Return an explicit unsupported or ambiguous result when necessary.

Do not use undocumented or unsafe workarounds without validation.

### Deliverable

A verified RenderDoc launch component with documented behavior.

---

## 8. Task E — Session Manager

Implement a logical Session Manager independent of process discovery.

### Required Operations

```python
session_manager.create_session(...)
session_manager.list_sessions(...)
session_manager.get_session(...)
session_manager.focus_session(...)
session_manager.close_session(...)
session_manager.protect_session(...)
session_manager.reconcile(...)
```

Adapt method signatures to the existing codebase.

### Session Lifecycle

Define an explicit state machine.

Suggested states:

```text
CREATING
   |
   v
ACTIVE
   |
   +------> DISCONNECTED
   |             |
   |             v
   |          RECOVERING
   |             |
   |             v
   |           ACTIVE
   |
   +------> CLOSING
                |
                v
              CLOSED
```

Additional failure states may be introduced where justified.

### Requirements

- Assign stable Session IDs.
- Associate sessions with Capture IDs.
- Associate sessions with process and window identities.
- Track status transitions.
- Support multiple sessions simultaneously.
- Maintain separate sessions for distinct capture contexts.
- Avoid duplicate sessions when explicit reuse is requested.
- Support protected sessions.
- Support non-destructive session observation.
- Handle missing or terminated processes.
- Distinguish a logical session from an OS process.

### Protection

A protected session must not be closed or replaced implicitly.

Explicit unprotection or a documented authorized override must be required before a destructive operation.

### Deliverable

A functional Session Manager with stable logical identities.

---

## 9. Task F — Capture Opening Modes

Integrate Phase 1 Capture IDs with the Session Manager.

Define explicit capture opening modes.

### `new_window`

Request a new, independent RenderDoc GUI window for the selected capture.

Existing sessions must be preserved.

Verify the new window association before reporting the session as active and confirmed.

If independence cannot be guaranteed, return a clear result describing the limitation.

### `reuse`

Find an existing confirmed session associated with the requested Capture ID.

If a suitable session exists, return it and optionally focus it.

If no suitable session exists, create a new session.

Do not reuse a session merely because a window title resembles the requested filename.

### `replace`

Replace the capture associated with an explicitly selected managed session.

Requirements:

- Require an explicit target Session ID.
- Reject protected sessions.
- Reject unmanaged or uncertain ownership.
- Preserve unrelated sessions.
- Verify that the replacement is supported by the available integration.
- Do not fall back to destructive process termination.

If reliable capture replacement requires Phase 3 Extension functionality, implement the API boundary and return a structured `not_supported` result until it becomes available.

### Capture Selector

Support a Capture ID and the `latest` selector.

Resolve `latest` once per operation.

Pass the resolved Capture ID through subsequent steps.

Do not repeatedly resolve `latest` during the same operation.

### Deliverable

A capture-to-session opening workflow with safe, documented semantics.

---

## 10. Task G — Window Focus and Close Operations

Implement safe window control.

### Focus

`session_focus(session_id)` must:

1. Resolve the Session ID.
2. Identify its associated window.
3. Revalidate the process and window identities.
4. Attempt to restore and focus the window.
5. Return the actual observed outcome.

Use appropriate Windows APIs.

Consider Windows foreground activation restrictions.

Do not report success solely because `SetForegroundWindow` was called.

If Windows denies foreground activation, return a nonfatal failure or partial result.

### Close

`session_close(session_id)` must:

1. Resolve the Session ID.
2. Confirm that the session is managed.
3. Confirm that it is not protected.
4. Revalidate its process and window identities.
5. Send a graceful close request to the correct window.
6. Observe whether the window closes.
7. Update session state accordingly.

Prefer a graceful GUI close request such as `WM_CLOSE` where appropriate.

Do not use `TerminateProcess` or an equivalent forced termination mechanism for ordinary session closure.

Do not terminate the entire process when doing so could close unrelated windows or sessions.

If a process hosts multiple sessions and the target window cannot be safely closed independently, return a structured failure.

### Unsaved State

RenderDoc may display confirmation dialogs or other modal UI.

Do not automatically dismiss unknown dialogs.

Report when the close operation remains pending or cannot be confirmed.

### Deliverable

Safe, targeted focus and graceful close operations.

---

## 11. Task H — Session Persistence and Recovery

Implement lightweight session metadata persistence.

Reuse the existing Phase 1 SQLite infrastructure where appropriate.

### Persist

- Session IDs
- Capture IDs
- Last known capture paths
- Instance and window association metadata
- Ownership classification
- Protection flags
- Lifecycle status
- Creation and update timestamps
- Reconciliation information

### Restart Behavior

On MCP server restart:

1. Load persisted session metadata.
2. Discover existing RenderDoc processes.
3. Discover their windows.
4. Compare runtime identities.
5. Restore associations only when identity evidence is sufficient.
6. Reconcile session statuses.
7. Preserve protected-session metadata.
8. Mark uncertain associations explicitly.

### Important Limitation

Do not assume that an old PID or window handle still identifies the same process or window.

Do not automatically relaunch closed sessions.

Do not automatically terminate stale processes.

Do not claim that a recovered session has the correct loaded capture when that cannot be verified.

### Phase 3 Compatibility

Keep the reconciliation architecture compatible with future authoritative status reports from the RenderDoc Extension.

### Deliverable

Restart-safe session metadata persistence and conservative reconciliation.

---

## 12. Task I — MCP Tool Integration

Extend the existing MCP server.

### Required Tools

#### `session_list`

List known sessions.

Suggested filters:

- `status`
- `managed_only`
- `capture_id`
- `limit`
- `offset`

#### `session_get`

Return details for a Session ID.

#### `session_focus`

Focus a specific session's window.

#### `session_close`

Safely close a managed, unprotected session.

#### `session_protect`

Enable or disable protection for a session.

Suggested parameters:

- `session_id`
- `protected`

#### `capture_open`

Open a capture through the session-management system.

Suggested parameters:

```json
{
  "capture_id": "latest",
  "open_mode": "new_window",
  "target_session_id": null
}
```

Require `target_session_id` for `replace`.

#### `instance_list`

List discovered RenderDoc processes and associated windows.

Return ownership and confidence information.

### Existing Tools

Preserve:

- `server_status`
- `capture_list`
- `capture_get`
- `capture_latest`
- `capture_rescan`
- `capture_registry_status`

Integrate session information into `server_status` where useful.

### MCP Response Requirements

- Structured JSON-compatible responses.
- Stable identifiers.
- Consistent error codes.
- Explicit management ownership.
- Explicit operation outcome.
- Clear distinction between confirmed and inferred associations.
- No fabricated success states.
- No excessive logging in tool results.

### Error Handling

Define errors for:

- Unknown Session ID
- Unknown Capture ID
- Capture unavailable
- RenderDoc executable missing
- Launch failure
- Window not found
- Window association ambiguous
- Session protected
- Session unmanaged
- Operation unsupported
- Window focus denied
- Close not confirmed
- Session state changed during operation

### Deliverable

Functional MCP session-management tools accessible through Claude Code.

---

## 13. Task J — Concurrency and Lifecycle Safety

The MCP server may receive overlapping requests while filesystem monitoring and process discovery are running.

Ensure:

- Session creation is atomic.
- Two simultaneous `reuse` requests do not create unnecessary duplicate sessions.
- Concurrent close and focus requests are handled consistently.
- Session state transitions are validated.
- Process enumeration does not block MCP requests indefinitely.
- Long-running launch operations have bounded timeouts.
- Session storage transactions are consistent.
- Application shutdown cleans up monitoring resources.
- Shutdown never closes managed RenderDoc windows unless explicitly requested.

Implement appropriate locking or asynchronous coordination.

Avoid holding global locks while waiting for processes or windows.

### Deliverable

Thread-safe or concurrency-safe lifecycle management.

---

## 14. Task K — Real RenderDoc Integration Tests

Use the installation under:

`D:\Programs\RenderDoc`

### Test Preparation

1. Locate `qrenderdoc.exe`.
2. Determine the installed RenderDoc version.
3. Inspect supported launch arguments.
4. Identify available real `.rdc` captures.
5. Use Phase 1 Capture Registry to select test captures.
6. Preserve existing user-created RenderDoc windows.

The Unity project at `tests/TestProject` may be used to generate additional captures if necessary.

Do not modify Unity rendering settings merely to create test data.

### Scenario A — Single Capture

1. Register a valid `.rdc`.
2. Invoke `capture_open`.
3. Observe the launched RenderDoc instance.
4. Identify its process and window.
5. Create or confirm the associated session.
6. Invoke `session_focus`.

Expected result:

The capture is opened, and its managed window can be identified and focused.

### Scenario B — Multiple Captures

1. Open Capture A.
2. Open Capture B using `new_window`.
3. Verify that both windows remain available.
4. Verify that each session has a separate logical identity.
5. Focus Session A.
6. Focus Session B.

Expected result:

Both captures remain independently accessible without overwriting each other.

If RenderDoc does not support the required window isolation, document the limitation rather than reporting success.

### Scenario C — Existing External Window

1. Start RenderDoc manually.
2. Open a capture manually.
3. Start or rescan RenderEyeMCP.
4. Discover the external RenderDoc window.
5. Verify that it is classified as external.

Expected result:

The external window is visible in discovery results but cannot be closed through managed-only destructive operations.

### Scenario D — Protected Session

1. Create a managed session.
2. Mark it protected.
3. Invoke `session_close`.

Expected result:

The close request is rejected, and the RenderDoc window remains open.

### Scenario E — Graceful Closure

1. Open a capture in a managed session.
2. Invoke `session_close`.
3. Confirm that only the intended window closes.
4. Verify the updated session state.

Expected result:

Unrelated RenderDoc windows remain unchanged.

### Scenario F — Server Restart

1. Open managed sessions.
2. Restart the MCP server without closing RenderDoc.
3. Reconcile persisted sessions with running processes.
4. Query `session_list`.

Expected result:

Recoverable associations are preserved, and uncertain associations are explicitly marked.

### Scenario G — Process Crash

1. Create a managed session.
2. Simulate an unexpected process exit using an isolated test process or another safe mechanism.
3. Reconcile the session state.

Expected result:

The session no longer reports an active, verified window.

Do not force-terminate unrelated or user-created RenderDoc processes.

---

## 15. Automated Testing

Implement tests that can run without RenderDoc installed.

### Instance Discovery

- No RenderDoc processes
- One RenderDoc process
- Multiple RenderDoc processes
- Process exit during enumeration
- Insufficient process permissions
- PID reuse
- Incorrect executable identity

### Window Discovery

- No windows
- Multiple windows per process
- Hidden windows
- Minimized windows
- Destroyed window
- Window handle reuse
- Ambiguous process/window association

### Session Management

- Create session
- Retrieve session
- List sessions
- Duplicate capture sessions
- Protected session
- Unmanaged session
- State transitions
- Session closure
- Persistence
- Restart reconciliation
- Ambiguous recovery

### Capture Opening

- Valid Capture ID
- Unknown Capture ID
- Latest capture
- Deleted capture
- Incomplete capture
- New-window mode
- Reuse mode
- Replace mode
- Concurrent reuse requests
- Launch failure

### Window Operations

- Successful focus
- Focus denied
- Successful graceful close
- Close timeout
- Window disappears before operation
- Window identity changes before operation
- Multiple windows sharing a process
- Protected session rejection
- External window rejection

### MCP Integration

- Tool discovery
- Tool invocation
- Structured response validation
- Error handling
- Phase 0 regression
- Phase 1 regression

Use mocks or test doubles for Windows APIs and process launches.

Ensure unit tests never close real RenderDoc windows.

Separate destructive or environment-dependent integration tests behind explicit opt-in flags.

Run:

```bash
uv run pytest
uv run ruff check .
```

Use the existing repository commands when different.

---

## 16. Documentation

Update the existing documentation.

### README.md

Add:

- RenderDoc installation discovery
- Session management overview
- Opening modes
- MCP tool examples
- Protected session behavior
- Multi-window workflow
- Known limitations

### docs/architecture.md

Document:

- Capture, Instance, Window, and Session relationships
- Ownership model
- Window correlation strategy
- Session lifecycle
- Concurrency model
- Phase 3 Extension integration boundaries

### docs/session_management.md

Create a dedicated document describing:

- Session identifiers
- Lifecycle states
- Session persistence
- Process and window relationships
- Managed vs. external ownership
- Protected sessions
- Window focus behavior
- Safe close behavior
- Restart recovery

### docs/renderdoc_integration.md

Update:

- Verified executable path
- Installed RenderDoc version
- Verified launch arguments
- Multi-window launch behavior
- Process and window correlation results
- Unsupported GUI operations
- Phase 3 requirements discovered during testing

### docs/development.md

Add:

- Running session tests
- Starting the MCP server
- Testing capture opening
- Running optional integration tests
- Inspecting process and session logs

---

## 17. Phase 2 Acceptance Scenarios

### Scenario A — Open Latest Capture

1. A valid capture is available in the Phase 1 Registry.
2. Invoke `capture_open` with `latest`.
3. RenderEyeMCP resolves the Capture ID.
4. RenderDoc opens the selected capture.
5. A Session ID is returned.

**Expected:** The result accurately reports the launched process, window association, and any remaining verification uncertainty.

### Scenario B — Multiple Independent Windows

1. Open Capture A.
2. Open Capture B.
3. List sessions.
4. Focus Session A.
5. Focus Session B.

**Expected:** Separate sessions can be individually addressed without closing unrelated windows.

### Scenario C — Safe Closure

1. Open two managed sessions.
2. Close Session A.
3. Query Session B.

**Expected:** Session B remains active and unaffected.

### Scenario D — External Window Protection

1. Start RenderDoc manually.
2. Discover the running process.
3. Attempt to close it using a managed-only session operation.

**Expected:** The operation is rejected.

### Scenario E — Restart Recovery

1. Create managed sessions.
2. Restart RenderEyeMCP.
3. Reconcile runtime state.
4. Query session information.

**Expected:** Recoverable sessions retain their identities, and unsupported recovery cases are clearly reported.

---

## 18. Definition of Done

Phase 2 is complete when:

- [ ] RenderDoc executable discovery works with `D:\Programs\RenderDoc`.
- [ ] Running RenderDoc GUI processes can be discovered.
- [ ] Top-level RenderDoc windows can be enumerated.
- [ ] Processes and windows have stable logical identifiers.
- [ ] Managed and external processes are distinguished.
- [ ] Sessions can be created, listed, queried, and persisted.
- [ ] Capture IDs can be associated with sessions.
- [ ] Capture opening works through the verified RenderDoc launch mechanism.
- [ ] Multiple capture contexts can be managed without unintended replacement.
- [ ] Window focus operations report their actual outcomes.
- [ ] Managed sessions can be closed safely.
- [ ] Protected sessions cannot be closed implicitly.
- [ ] External windows are protected from destructive operations.
- [ ] Restart reconciliation handles identity uncertainty conservatively.
- [ ] MCP tools expose session-management functionality.
- [ ] Phase 0 and Phase 1 regression tests pass.
- [ ] Real RenderDoc integration behavior is documented.
- [ ] Phase 3 integration requirements are identified.

If the installed RenderDoc version prevents required independent-window behavior, report Phase 2 as partially verified or blocked rather than pretending the requirement is satisfied.

---

## 19. Execution Instructions

Execute implementation in this order:

1. Inspect the repository.
2. Run existing tests.
3. Inspect `D:\Programs\RenderDoc`.
4. Verify executable location and RenderDoc version.
5. Investigate process and window behavior.
6. Define Instance, Window, and Session models.
7. Implement process discovery.
8. Implement window discovery.
9. Implement RenderDoc launching.
10. Implement Session Manager.
11. Integrate Phase 1 Capture IDs.
12. Implement opening modes.
13. Implement focus and graceful close operations.
14. Implement session persistence.
15. Implement restart reconciliation.
16. Expose MCP tools.
17. Add automated tests.
18. Run safe real RenderDoc integration tests.
19. Update documentation.
20. Run the full regression suite.
21. Review all acceptance criteria.

Work autonomously using the available tools.

Use the existing project architecture and development conventions.

Prefer verified RenderDoc behavior over speculative assumptions.

Avoid unnecessary abstractions and unrelated features.

Do not automatically terminate or close preexisting user windows during testing.

Do not implement Phase 3's full extension synchronization yet.

If a feature requires authoritative information unavailable through the current integration, expose the limitation explicitly and document the Phase 3 dependency.

---

## 20. Final Report

After implementation, provide:

1. **Implementation Summary** — Features implemented.
2. **Files Changed** — Important created and modified files.
3. **RenderDoc Environment** — Executable path, version, and verified launch behavior.
4. **Instance Management** — Process and window discovery design.
5. **Session Management** — Identity, lifecycle, and persistence behavior.
6. **MCP Tools** — Available tools and parameters.
7. **Test Results** — Tests actually executed and their outcomes.
8. **Real Integration Results** — Behavior observed with the installed RenderDoc.
9. **Known Limitations** — Ambiguous correlations and unsupported operations.
10. **Phase 2 Status** — Complete, partially verified, or blocked.
11. **Phase 3 Readiness** — Features requiring extension-provided GUI state.

Do not claim a successful integration test unless it was actually executed.

Do not begin Phase 3.

**Phase 2 Focus: Reliable RenderDoc process discovery, independent window control, safe session lifecycle management, and Capture ID integration.**
