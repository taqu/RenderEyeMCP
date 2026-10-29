# RenderEyeMCP — Phase 4 Implementation Instructions

## Objective

Implement **Phase 4: MCP Tools & Agent Workflow** of RenderEyeMCP.

Previous development phases established the following components:

- **Phase 0 — Foundation & Feasibility:** MCP server foundation, RenderDoc integration research, and local IPC proof of concept.
- **Phase 1 — Capture Discovery & Registry:** Automatic `.rdc` discovery, capture readiness validation, persistent Capture IDs, and latest-capture resolution.
- **Phase 2 — Instance & Session Management:** RenderDoc process discovery, window management, session lifecycle, safe window control, and Capture ID integration.
- **Phase 3 — RenderDoc Extension & IPC Integration:** Authoritative GUI state reporting, multiple extension connections, session synchronization, and supported GUI operations.

Phase 4 must integrate these components into a consistent, stable, and agent-friendly MCP interface.

The primary goal is to allow coding agents such as Claude Code to discover captures, open the correct `.rdc` file, manage multiple RenderDoc windows, and reliably track debugging sessions without requiring manual identification of files or windows.

**This phase focuses on MCP API quality, workflow reliability, integration testing, and practical Claude Code usability.**

Implement working functionality rather than only producing documentation.

---

## 1. Environment and Constraints

### Existing Environment

- Primary operating system: Windows.
- Primary implementation language: Python.
- Python package and environment manager: `uv`, already installed.
- RenderDoc installation directory: `D:\Programs\RenderDoc`
- Unity integration test project: `tests/TestProject`
- Existing Phase 0–3 implementation in the repository.

### Mandatory Constraints

- Do not modify the production engine.
- Do not modify RenderDoc source code.
- Do not rebuild RenderDoc.
- Do not automatically terminate existing RenderDoc processes.
- Do not close unmanaged RenderDoc windows.
- Do not modify Unity project settings unnecessarily.
- Do not overwrite existing `.rdc` files.
- Do not implement GPU pipeline analysis.
- Do not implement shader or texture debugging.
- Do not implement automatic frame comparison.
- Do not introduce unnecessary remote services.
- Do not begin Phase 5 release preparation beyond changes required to validate Phase 4.

### Implementation Principles

1. Preserve the architecture established in previous phases.
2. Reuse existing managers and data models.
3. Prefer a small, coherent MCP API over an excessive number of tools.
4. Use stable Capture IDs, Session IDs, and Instance IDs.
5. Keep operations deterministic wherever possible.
6. Return structured, machine-readable results.
7. Never report success before an operation has been verified.
8. Preserve ownership and protection rules.
9. Make failure states explicit and actionable.
10. Keep MCP tool descriptions clear enough for an autonomous coding agent to select and use them correctly.

---

## 2. Task A — Repository and API Audit

Before implementing Phase 4:

1. Inspect the entire repository.
2. Read existing architecture and development documentation.
3. Inspect all MCP tools currently registered by the server.
4. Inspect Capture Registry APIs.
5. Inspect Instance Manager and Session Manager APIs.
6. Inspect the RenderDoc Extension and IPC protocol.
7. Review GUI state synchronization behavior.
8. Review session persistence and recovery behavior.
9. Inspect existing configuration files.
10. Run the complete existing test suite.

### API Inventory

Produce an inventory of existing MCP tools.

For each tool, record:

- Tool name
- Purpose
- Input parameters
- Input validation
- Output structure
- Error behavior
- Underlying manager or service
- Whether the operation is read-only
- Whether the operation can modify GUI state
- Whether the operation can close a session

Identify:

- Duplicate tools
- Inconsistent parameter names
- Inconsistent response formats
- Missing validation
- Ambiguous tool descriptions
- Unnecessary implementation coupling
- Missing error handling
- Incomplete Phase 3 integration

### Compatibility

Do not remove or rename existing tools without justification.

Prefer internal refactoring and compatibility-preserving improvements.

If breaking changes are unavoidable, document them explicitly.

### Deliverable

A documented MCP API inventory and a focused integration plan.

---

## 3. Task B — MCP Tool Architecture

Implement a consistent MCP tool layer over the existing application services.

The intended architecture is:

```text
Claude Code
    |
    | MCP Tool Calls
    v
RenderEyeMCP
    |
    +-- MCP Tool Layer
    |      |
    |      +-- Input Validation
    |      +-- Request Coordination
    |      +-- Result Serialization
    |      +-- Error Mapping
    |
    +-- Capture Registry
    |
    +-- Session Manager
    |
    +-- Instance Manager
    |
    +-- Extension Connection Manager
           |
           v
      RenderDoc GUI
```

### Requirements

- MCP handlers must remain thin.
- Business logic must remain in existing service layers.
- Avoid filesystem scanning directly inside MCP handlers.
- Avoid direct Windows API calls inside MCP handlers.
- Avoid direct IPC framing logic inside MCP handlers.
- Reuse shared validation and response models.
- Support asynchronous operations where justified.
- Ensure long-running work does not block unrelated MCP requests.
- Preserve compatibility with the installed MCP SDK.

### Structured Outputs

Use the installed MCP Python SDK's supported structured-output capabilities.

Prefer typed response models.

Ensure actual tool results conform to their published schemas.

Do not accidentally serialize Python object representations instead of structured data.

### Tool Descriptions

Each tool must clearly describe:

- What the tool does
- When an agent should use it
- Whether it changes GUI state
- Required identifiers
- Whether the result is verified or inferred
- Important safety restrictions

Avoid vague descriptions.

### Deliverable

A consistent, maintainable MCP tool integration layer.

---

## 4. Task C — Capture Management Tools

Finalize the capture-management MCP API.

### Required Tool: `capture_list`

List captures known to the Capture Registry.

Suggested parameters:

- `status`
- `directory`
- `limit`
- `offset`

Requirements:

- Support deterministic ordering.
- Support pagination.
- Return stable Capture IDs.
- Include capture readiness information.
- Avoid returning an unbounded number of captures.
- Preserve Unicode paths.
- Clearly distinguish missing and inaccessible captures.

Example result:

```json
{
  "captures": [
    {
      "capture_id": "cap-000018",
      "filename": "frame018.rdc",
      "path": "D:/Captures/frame018.rdc",
      "status": "ready"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Required Tool: `capture_get`

Retrieve a capture by Capture ID.

Parameters:

- `capture_id`

Return:

- Capture ID
- File path
- File size
- Registry status
- Readiness validation level
- Creation and modification timestamps
- Discovery timestamp
- Last verification timestamp, if available

Do not fabricate unavailable metadata.

### Required Tool: `capture_latest`

Resolve the latest eligible capture.

Suggested parameters:

- `directory`
- `include_pending`

Requirements:

- Use the Phase 1 ordering policy.
- Return the resolved Capture ID.
- Include the selection basis.
- Include confidence or uncertainty information.
- Exclude pending or invalid captures by default.
- Handle an empty registry gracefully.

Do not imply that filesystem-based ordering is always equivalent to actual frame capture chronology.

### Required Tool: `capture_rescan`

Request Capture Registry reconciliation.

Requirements:

- Use the existing Phase 1 scanner.
- Avoid duplicate concurrent scans.
- Do not block indefinitely.
- Distinguish scheduled, running, and completed rescans.
- Report partial failures.
- Return completion only after reconciliation has actually finished.

### Required Tool: `capture_registry_status`

Report:

- Registry health
- Configured capture directories
- Watcher status
- Last successful scan
- Capture counts by state
- Pending validation count
- Persistent storage status
- Recent operational errors

### Deliverable

A consistent Capture Registry MCP interface.

---

## 5. Task D — Instance and Session Query Tools

Finalize read-only session and instance management tools.

### Required Tool: `instance_list`

List discovered RenderDoc instances.

Return:

- Instance ID
- Process ID
- Process start time when available
- Executable path
- Ownership classification
- Connection status
- Extension status
- Associated Window IDs
- Associated Session IDs
- State verification status

Do not expose unverified process information as authoritative.

### Required Tool: `session_list`

List known sessions.

Suggested parameters:

- `status`
- `capture_id`
- `managed_only`
- `limit`
- `offset`

Return:

- Session ID
- Capture ID
- Instance ID
- Window ID
- Session status
- Ownership classification
- Protection state
- GUI synchronization status
- Current loaded capture when confirmed

### Required Tool: `session_get`

Retrieve a specific Session ID.

Return detailed information about:

- Logical session identity
- Capture association
- Actual loaded GUI capture
- Process and window association
- Session lifecycle state
- Managed or external ownership
- Protection state
- Extension connectivity
- Last authoritative GUI update
- Association confidence
- Relevant operational limitations

### Optional Tool: `instance_gui_state`

Retain or introduce this tool only when it provides information not already available through `instance_list` or `session_get`.

Avoid duplicate tools exposing the same information without clear purpose.

### Deliverable

Agent-friendly instance and session inspection tools.

---

## 6. Task E — Capture Opening Workflow

Finalize `capture_open` as the central capture-to-GUI operation.

### Parameters

Suggested interface:

```json
{
  "capture_id": "latest",
  "open_mode": "new_window",
  "target_session_id": null,
  "focus": true
}
```

### Capture Selection

Support:

- Explicit Capture ID
- `latest` selector

Resolve `latest` exactly once for each operation.

Retain the resolved Capture ID throughout execution.

Do not resolve `latest` again during asynchronous continuation or retries.

### Readiness Validation

Before opening:

1. Resolve the Capture ID.
2. Confirm the capture is eligible.
3. Verify the file still exists.
4. Verify the file has not unexpectedly changed.
5. Verify access permissions.
6. Confirm the file is suitable for the requested operation according to available validation.

A successful historical readiness check does not guarantee that the file remains accessible.

### Opening Modes

#### `new_window`

Request a separate RenderDoc window.

Requirements:

- Preserve existing sessions.
- Use the verified launch mechanism.
- Discover the resulting process and window.
- Establish session association.
- Verify GUI state through the extension when possible.
- Return explicit uncertainty when independent-window creation cannot be confirmed.

Do not silently reuse an existing window.

#### `reuse`

Find a confirmed existing session for the selected capture.

Requirements:

- Use the actual loaded capture association when available.
- Do not rely solely on the window title.
- Reuse a suitable existing session.
- Optionally focus the session.
- Create a new session when no suitable session exists.

Do not create unnecessary duplicate windows.

#### `replace`

Replace the capture loaded in an explicitly selected managed session.

Requirements:

- Require `target_session_id`.
- Reject protected sessions.
- Reject external sessions.
- Verify target Session ID and Instance ID.
- Ensure the GUI supports capture replacement.
- Use the supported extension command.
- Verify the resulting loaded capture.

Do not close the RenderDoc window merely to simulate replacement unless a separately documented, explicitly authorized strategy permits it.

### Operation Lifecycle

Model opening as a multi-stage operation:

```text
REQUESTED
    |
    v
VALIDATING
    |
    v
LAUNCHING / LOADING
    |
    v
WAITING_FOR_GUI
    |
    v
VERIFYING
    |
    v
CONFIRMED
```

Handle additional outcomes:

- `failed`
- `unsupported`
- `timed_out`
- `unknown_outcome`

A launch request being accepted does not mean a capture was loaded successfully.

### Example Result

```json
{
  "operation_id": "op-000042",
  "status": "confirmed",
  "capture_id": "cap-000018",
  "session_id": "session-000007",
  "instance_id": "instance-000004",
  "window_id": "window-000004",
  "open_mode": "new_window",
  "loaded_capture_verified": true
}
```

### Deliverable

A reliable and verifiable `capture_open` workflow.

---

## 7. Task F — Session Control Tools

Finalize safe session operations.

### Required Tool: `session_focus`

Parameters:

- `session_id`

Requirements:

1. Resolve the session.
2. Verify current process and window identities.
3. Reject stale or ambiguous window associations.
4. Attempt foreground activation.
5. Verify the observed focus result where possible.
6. Report Windows foreground restrictions accurately.

Do not report guaranteed focus when the operating system prevents it.

### Required Tool: `session_close`

Parameters:

- `session_id`

Requirements:

1. Resolve the session.
2. Verify that it is managed.
3. Verify that it is not protected.
4. Revalidate process and window identity.
5. Request graceful closure.
6. Observe the resulting GUI or process state.
7. Update Session Manager state.
8. Report whether closure was confirmed.

Do not forcefully terminate the RenderDoc process.

Do not close external windows.

Do not close other windows belonging to the same process.

### Required Tool: `session_protect`

Parameters:

- `session_id`
- `protected`

Requirements:

- Update session protection state.
- Persist protection settings.
- Preserve protection across MCP server restarts.
- Reject ambiguous or unauthorized protection modifications.
- Return the resulting protection state.

### Confirmed Outcomes

Distinguish:

- Request accepted
- Operation in progress
- Operation completed and verified
- Operation failed
- Operation outcome unknown

Do not use a simple `success: true` response for an unverified asynchronous GUI action.

### Deliverable

Reliable, safe, and agent-friendly session-control tools.

---

## 8. Task G — Consistent MCP Response Models

Implement shared response conventions across all tools.

### Common Fields

Where applicable, include:

- Operation status
- Capture ID
- Session ID
- Instance ID
- Window ID
- Error code
- Human-readable message
- Verification status
- State timestamp
- Operation ID for long-running operations

Do not require every tool to return unrelated fields.

### Response Design

Prefer concise structured objects.

Use explicit nullable fields instead of magic strings when appropriate.

Avoid mixing incompatible representations for the same concept.

For example, do not report session status as a Boolean in one tool and as an unrelated string enumeration in another.

### Error Schema

Define a consistent error representation.

Example:

```json
{
  "status": "failed",
  "error": {
    "code": "session_protected",
    "message": "The requested session is protected.",
    "retryable": false
  }
}
```

### Recommended Error Codes

Include:

- `capture_not_found`
- `capture_not_ready`
- `capture_unavailable`
- `session_not_found`
- `session_protected`
- `session_unmanaged`
- `instance_not_found`
- `window_not_found`
- `window_ambiguous`
- `extension_unavailable`
- `ipc_disconnected`
- `operation_unsupported`
- `operation_timeout`
- `operation_unknown_outcome`
- `state_conflict`
- `internal_error`

Keep the error model extensible.

### Retryability

Expose whether retrying is generally appropriate.

Do not mark operations as safely retryable when repeating them might create another RenderDoc window or duplicate a state-changing action.

### Deliverable

Consistent typed MCP result and error models.

---

## 9. Task H — Operation Coordination and Idempotency

GUI operations may be slow and may overlap with user actions.

Implement safe operation coordination.

### Requirements

- Assign operation IDs to multi-stage operations.
- Track active operations.
- Prevent conflicting operations on the same session.
- Handle concurrent `capture_open` requests.
- Handle simultaneous focus and close requests.
- Handle connection loss during an operation.
- Apply bounded timeouts.
- Avoid holding global locks while waiting for GUI changes.
- Prevent stale operations from overwriting newer session state.

### Idempotency

Where useful, introduce optional idempotency keys or equivalent operation deduplication.

For example, repeated delivery of the same request should not accidentally launch multiple RenderDoc windows when a previous launch is still pending.

Do not deduplicate distinct intentional `new_window` requests merely because their Capture IDs match.

### Timeout Semantics

A timeout does not necessarily mean that a GUI action failed.

Distinguish:

- Confirmed failure
- Confirmed completion
- Unknown completion state

Preserve enough operation information for reconciliation after a timeout.

### Operation Status

If operations can continue after the initial MCP request returns, expose a bounded status-query mechanism.

For example:

`operation_get(operation_id)`

Only add this tool if required by the actual asynchronous execution model.

Do not return a background operation ID without providing a way to inspect its outcome.

### Deliverable

Concurrency-safe operation coordination and explicit completion semantics.

---

## 10. Task I — Claude Code Integration

Make RenderEyeMCP usable as a project-local MCP server in Claude Code.

### Configuration

Provide a working Claude Code MCP configuration.

Prefer project-scoped configuration when appropriate.

Verify the configuration format against the installed Claude Code version.

A typical configuration may resemble:

```json
{
  "mcpServers": {
    "rendereye": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project",
        ".",
        "python",
        "-m",
        "rendereye_mcp"
      ]
    }
  }
}
```

This is illustrative and must be validated against the actual project layout and Claude Code configuration requirements.

### Working Directory

Do not assume that Claude Code always launches the MCP server from the repository root.

Ensure project and executable paths are resolved correctly.

Use an absolute project path or another verified startup strategy where required.

### Windows Compatibility

Test:

- Windows process launching
- Paths containing spaces
- Unicode file paths
- `uv` executable resolution
- Environment variable handling
- MCP stdio communication
- Server shutdown

Do not emit diagnostics to MCP stdout.

### Tool Discovery

Verify that Claude Code can:

1. Connect to RenderEyeMCP.
2. Discover the registered tools.
3. Read tool descriptions.
4. Invoke a read-only tool.
5. Receive and interpret a structured result.
6. Invoke an authorized GUI operation.
7. Handle a structured operation failure.

### Documentation

Provide:

- Claude Code setup instructions
- A validated MCP configuration example
- Connection verification instructions
- Example prompts
- Common troubleshooting procedures

### Deliverable

A reproducible Claude Code integration workflow.

---

## 11. Task J — Agent Workflow Validation

Test complete workflows instead of only testing individual functions.

### Workflow A — Discover Latest Capture

User request:

"Find the latest RenderDoc capture."

Expected agent behavior:

1. Invoke `capture_latest`.
2. Read the resolved Capture ID.
3. Report the filename and capture status.
4. Explain uncertainty when the ordering is heuristic.

The agent must not search the filesystem manually when the registry provides the necessary information.

### Workflow B — Open Latest Capture

User request:

"Open the latest RenderDoc capture."

Expected agent behavior:

1. Invoke `capture_open` with `capture_id="latest"`.
2. Use the default documented opening mode.
3. Inspect the result.
4. Verify the returned session status.
5. Report the opened capture and Session ID.

The agent must not assume that the operation succeeded before verification.

### Workflow C — Preserve Existing Windows

User request:

"Open the latest capture in a new window and keep the previous one."

Expected agent behavior:

1. Resolve or directly request the latest capture.
2. Invoke `capture_open` with `new_window`.
3. Verify the resulting session.
4. Preserve existing windows.

### Workflow D — Focus a Specific Capture

User request:

"Focus the window showing the previous capture."

Expected agent behavior:

1. Query the Capture Registry or existing sessions.
2. Identify the intended Capture ID.
3. Resolve the associated Session ID.
4. Invoke `session_focus`.
5. Report the observed result.

Do not guess a window based only on its screen position or title.

### Workflow E — Close a Specific Session

User request:

"Close Session A but keep Session B."

Expected agent behavior:

1. Identify Session A.
2. Inspect ownership and protection state.
3. Invoke `session_close` only for Session A.
4. Verify closure.
5. Confirm that Session B remains active.

### Workflow F — Protected Session

User request:

"Close the protected comparison session."

Expected agent behavior:

1. Attempt or prevalidate the requested operation.
2. Recognize the protection restriction.
3. Report that the session remains protected.
4. Do not silently remove protection.

### Workflow G — External RenderDoc Window

User request:

"Close all RenderDoc windows."

Expected agent behavior:

1. Inspect sessions and instances.
2. Identify managed and external windows.
3. Do not close external windows through managed-only tools.
4. Report the limitation and the actions actually performed.

Do not infer permission to override ownership merely from broad natural-language instructions.

### Deliverable

Verified agent workflows with reproducible execution instructions and test results.

---

## 12. Task K — MCP Tool Safety and Permissions

Review the safety characteristics of all exposed MCP tools.

### Read-Only Tools

Examples:

- `capture_list`
- `capture_get`
- `capture_latest`
- `capture_registry_status`
- `instance_list`
- `session_list`
- `session_get`
- `server_status`

These must not modify RenderDoc GUI state.

### State-Changing Tools

Examples:

- `capture_rescan`
- `capture_open`
- `session_focus`
- `session_close`
- `session_protect`

Clearly document their side effects.

### Destructive Operations

Treat closing or replacing an existing debugging session as potentially destructive.

Requirements:

- Use explicit Session IDs.
- Respect ownership restrictions.
- Respect protection flags.
- Revalidate state immediately before execution.
- Avoid broad process termination.
- Avoid implicit bulk closure.
- Reject ambiguous targets.

### MCP Metadata

Where supported by the installed MCP SDK, provide accurate tool annotations indicating read-only or potentially destructive behavior.

Do not use metadata as a substitute for server-side authorization and validation.

### Path Safety

Tools must not become unrestricted filesystem utilities.

- Validate Capture IDs through the registry.
- Restrict arbitrary path-based capture opening unless explicitly designed and authorized.
- Avoid accepting executable paths from untrusted tool parameters.
- Validate configured RenderDoc paths.
- Do not expose generic process execution.

### Deliverable

A documented, consistently enforced MCP tool safety model.

---

## 13. Task L — Automated Testing

Implement tests for the final MCP API and agent workflows.

### Tool Schema Tests

- Required tool names are present.
- Tool names are unique.
- Input schemas are valid.
- Output schemas are valid where supported.
- Optional parameters have correct defaults.
- Invalid input is rejected.
- Tool descriptions match actual behavior.

### Capture Tool Tests

- Empty registry
- Multiple captures
- Capture filtering
- Pagination
- Explicit Capture ID
- Latest Capture ID resolution
- Pending capture
- Deleted capture
- Registry scan failure

### Session Tool Tests

- Empty session list
- Multiple sessions
- Managed session
- External session
- Protected session
- Stale session
- Disconnected extension
- Ambiguous window mapping
- Valid focus operation
- Failed focus operation
- Confirmed closure
- Unconfirmed closure

### Capture Opening Tests

- Explicit Capture ID
- Latest capture
- New-window mode
- Reuse mode
- Replace mode
- Missing target Session ID
- Protected replacement target
- Concurrent requests
- Launch timeout
- IPC disconnection
- Capture changes during execution
- Unknown operation outcome

### Protocol Tests

- MCP initialization
- Tool discovery
- Tool invocation
- Structured output validation
- Tool error responses
- Server startup
- Server shutdown
- Multiple sequential requests
- Malformed tool arguments

### Regression Tests

Run all Phase 0–3 tests.

### Test Isolation

- Use mocks for Windows APIs.
- Use simulated RenderDoc extension connections.
- Use temporary capture files where possible.
- Do not close actual user windows during unit tests.
- Do not require Unity for standard unit tests.
- Do not require real RenderDoc for standard unit tests.

### Test Commands

Use the project's established development commands.

For example:

```bash
uv run pytest
uv run ruff check .
```

Run type checking if configured.

### Deliverable

Automated test coverage for the complete MCP tool layer.

---

## 14. Task M — Real RenderDoc End-to-End Testing

Use the installed RenderDoc application:

`D:\Programs\RenderDoc`

Use valid captures from the Phase 1 Capture Registry.

The Unity project under `tests/TestProject` may be used to generate additional test captures.

### Test 1 — Claude Code Connection

1. Start Claude Code with the RenderEyeMCP configuration.
2. Verify MCP server connectivity.
3. List registered tools.
4. Invoke `server_status`.

Expected result:

Claude Code can communicate with the running RenderEyeMCP server.

### Test 2 — Capture Discovery

1. Generate or locate a valid `.rdc`.
2. Invoke `capture_list`.
3. Invoke `capture_latest`.
4. Inspect returned metadata.

Expected result:

Capture IDs and latest-capture resolution match the registry state.

### Test 3 — Capture Opening

1. Invoke `capture_open` on a valid Capture ID.
2. Observe RenderDoc.
3. Verify the actual loaded capture through the extension.
4. Query the associated session.

Expected result:

The MCP operation reports a confirmed session only when the expected capture is actually loaded.

### Test 4 — Multiple Windows

1. Open Capture A.
2. Open Capture B using `new_window`.
3. List sessions.
4. Focus each session.

Expected result:

Both debugging contexts remain independently available.

### Test 5 — Session Closure

1. Open two managed test sessions.
2. Close one session.
3. Verify its closure.
4. Verify the other session remains available.

Expected result:

Only the intended session closes.

### Test 6 — Manual GUI State Change

1. Open Capture A through MCP.
2. Manually load Capture B through RenderDoc.
3. Query session state.

Expected result:

The agent receives the actual loaded capture information.

### Test 7 — MCP Restart

1. Open a managed test session.
2. Restart the MCP server.
3. Wait for extension reconnection.
4. Query session state.

Expected result:

Recoverable sessions remain identifiable.

### Test 8 — Missing Extension

1. Use a controlled RenderDoc instance without an active RenderEye extension.
2. Query instance and session information.
3. Attempt an operation requiring authoritative GUI state.

Expected result:

The operation returns an explicit unsupported, disconnected, or unverifiable result rather than fabricated success.

### Safety Requirements

- Preserve user-created windows.
- Never terminate unrelated processes.
- Do not overwrite capture files.
- Do not alter production engine code.
- Keep destructive integration tests explicitly opt-in.
- Report unexecuted tests as unverified.

### Deliverable

A documented end-to-end validation report covering real MCP and RenderDoc behavior.

---

## 15. Task N — Documentation and Examples

Update the repository documentation.

### README.md

Include:

- RenderEyeMCP overview
- Supported MCP tools
- Claude Code installation and configuration
- Opening the latest capture
- Working with multiple sessions
- Window focus and closure
- Safety guarantees
- Known limitations

### docs/mcp_api.md

Create an MCP API reference documenting:

- Tool names
- Descriptions
- Parameters
- Defaults
- Response schemas
- Error codes
- Side effects
- Usage examples

### docs/agent_workflows.md

Document reproducible agent workflows:

- Find latest capture
- Open latest capture
- Open multiple captures
- Reuse a session
- Replace a capture
- Focus a specific session
- Close a managed session
- Protect a debugging session
- Recover after disconnection

### docs/architecture.md

Update the complete workflow from MCP request to GUI confirmation.

### docs/development.md

Add:

- MCP client testing
- Claude Code configuration
- End-to-end test instructions
- Troubleshooting
- Debug logging procedures

### Example Configuration

Provide a validated project-level Claude Code configuration example.

Avoid hardcoding machine-specific absolute paths into portable sample configuration files.

---

## 16. Phase 4 Acceptance Scenarios

### Scenario A — Latest Capture Workflow

Claude Code is asked to open the latest capture.

RenderEyeMCP resolves the capture, launches or reuses the appropriate GUI instance, and reports the resulting session.

**Expected:** The correct capture is opened and its GUI association is verified.

### Scenario B — Multiple Capture Workflow

Claude Code is asked to keep an existing capture open while opening another.

**Expected:** Both debugging sessions remain available and independently identifiable.

### Scenario C — Safe Session Closure

Claude Code is asked to close a specific debugging session.

**Expected:** Only the intended managed, unprotected session is closed.

### Scenario D — Manual GUI Changes

The user changes the loaded capture manually.

**Expected:** Subsequent MCP queries reflect the actual GUI state rather than outdated assumptions.

### Scenario E — Connection Failure

The RenderDoc extension disconnects while a command is executing.

**Expected:** The operation returns an accurate failure or unknown-outcome state without corrupting Session Manager state.

### Scenario F — Agent Usability

Claude Code receives a natural-language request to find, open, or focus a capture.

**Expected:** The appropriate MCP tools can be discovered and used without manual filesystem searching or window guessing.

---

## 17. Definition of Done

Phase 4 is complete when:

- [ ] Existing MCP tools have been audited and consolidated.
- [ ] Tool names and parameters are consistent.
- [ ] Structured response models are implemented.
- [ ] MCP tool descriptions accurately describe behavior.
- [ ] Capture management tools work through MCP.
- [ ] Instance query tools work through MCP.
- [ ] Session query tools work through MCP.
- [ ] `capture_open` supports documented opening modes.
- [ ] `session_focus` operates on specific sessions.
- [ ] `session_close` respects ownership and protection.
- [ ] `session_protect` persists its state.
- [ ] Operations distinguish requested, pending, confirmed, failed, and unknown outcomes.
- [ ] Concurrent operations are coordinated safely.
- [ ] Claude Code configuration is provided and validated.
- [ ] Claude Code can discover and invoke RenderEyeMCP tools.
- [ ] Core natural-language workflows are verified.
- [ ] Existing Phase 0–3 tests remain passing.
- [ ] Real RenderDoc integration tests are performed where possible.
- [ ] Documentation is updated.

Phase 4 must not be marked fully complete if the actual MCP-to-RenderDoc workflow has not been verified.

If a real GUI or Claude Code test cannot be executed, document the limitation and report partial verification.

---

## 18. Execution Instructions

Execute the implementation in the following order:

1. Inspect the repository.
2. Run Phase 0–3 regression tests.
3. Audit existing MCP tools.
4. Define standardized response models.
5. Consolidate input validation and error handling.
6. Finalize capture-management tools.
7. Finalize instance and session query tools.
8. Implement the complete `capture_open` workflow.
9. Finalize session focus, close, and protection operations.
10. Implement operation coordination and completion tracking.
11. Review tool descriptions and safety metadata.
12. Configure Claude Code integration.
13. Add automated MCP protocol and tool tests.
14. Test realistic agent workflows.
15. Execute real RenderDoc integration tests.
16. Update documentation and examples.
17. Run the complete regression suite.
18. Review all Phase 4 acceptance criteria.

Work autonomously using the existing repository and available development tools.

Preserve working Phase 0–3 functionality.

Prefer small, verifiable changes over broad architectural rewrites.

Avoid unnecessary dependencies.

Do not implement GPU analysis, shader inspection, or automatic frame comparison.

Do not silently degrade safety guarantees when the RenderDoc extension is unavailable.

Do not claim that a GUI operation succeeded without evidence.

Do not begin Phase 5.

---

## 19. Final Report

After implementation, provide:

1. **Implementation Summary** — MCP integrations completed.
2. **Files Changed** — Important additions and modifications.
3. **MCP API** — Final tool inventory.
4. **Response Models** — Structured outputs and error conventions.
5. **Capture Opening** — Opening modes and verification behavior.
6. **Session Control** — Ownership and protection enforcement.
7. **Claude Code Integration** — Configuration and verified workflows.
8. **Automated Tests** — Exact tests executed and results.
9. **Real Integration Tests** — RenderDoc and Unity validation results.
10. **Known Limitations** — Unsupported or unverified behavior.
11. **Phase 4 Status** — Complete, partially verified, or blocked.
12. **Phase 5 Readiness** — Remaining release and reliability tasks.

Do not claim successful execution of tests that were not actually run.

Do not begin Phase 5.

**Phase 4 Focus: A complete, coherent, safe, and verifiable MCP interface that allows coding agents to manage RenderDoc captures and GUI sessions reliably.**
