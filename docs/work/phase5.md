# RenderEyeMCP — Phase 5 Implementation Instructions

## Objective

Implement **Phase 5: Reliability, Testing & v1.0 Release** of RenderEyeMCP.

This is the final development phase for the initial RenderEyeMCP release.

Previous phases established:

- **Phase 0 — Foundation & Feasibility:** MCP server foundation, RenderDoc integration feasibility, and local IPC.
- **Phase 1 — Capture Discovery & Registry:** Automatic `.rdc` discovery, persistent Capture Registry, and latest-capture resolution.
- **Phase 2 — Instance & Session Management:** RenderDoc process discovery, multiple-window management, session lifecycle, and safe GUI control.
- **Phase 3 — RenderDoc Extension & IPC Integration:** Authoritative GUI state reporting, multiple extension connections, and session synchronization.
- **Phase 4 — MCP Tools & Agent Workflow:** Stable MCP APIs, structured results, operation coordination, and Claude Code integration.

Phase 5 must harden, validate, document, package, and prepare these capabilities for the first stable release.

**The primary goal is to make RenderEyeMCP v1.0 reliable, safe, reproducible, and suitable for everyday graphics debugging workflows.**

Do not stop after reviewing existing code or writing recommendations. Implement necessary fixes, execute tests, validate real workflows where possible, and prepare release artifacts.

Do not automatically publish a release or push changes to a remote repository.

---

## 1. Environment and Constraints

### Existing Environment

- Primary operating system: Windows.
- Primary implementation language: Python.
- Python environment and package manager: `uv`, already installed.
- RenderDoc installation directory: `D:\Programs\RenderDoc`
- Unity integration test project: `tests/TestProject`
- Existing Phase 0–4 implementations.

### Release Target

Prepare a stable **RenderEyeMCP v1.0.0** release.

Use semantic versioning.

Do not label the implementation as v1.0.0 stable until all mandatory release criteria have passed.

### Mandatory Constraints

- Do not modify the production engine.
- Do not modify RenderDoc source code.
- Do not rebuild RenderDoc.
- Do not upgrade the Unity project automatically.
- Do not automatically terminate unrelated RenderDoc processes.
- Do not close unmanaged RenderDoc windows.
- Do not overwrite or delete user-created `.rdc` files.
- Do not weaken protected-session restrictions.
- Do not introduce GPU pipeline analysis.
- Do not implement automatic frame comparison.
- Do not implement shader or texture debugging.
- Do not introduce unrelated features.
- Preserve backward compatibility with Phase 4 MCP tools unless a critical defect requires a documented change.

### Core Release Principles

1. Safety takes priority over convenience.
2. A failed operation must not corrupt registry or session state.
3. A timeout must not be reported as confirmed success.
4. Stale GUI information must not be represented as current.
5. Unmanaged processes must remain protected.
6. Recovery must not cause unexpected GUI actions.
7. Installation and uninstallation must not damage existing RenderDoc configuration.
8. Every release claim must be backed by test evidence.

---

## 2. Task A — Baseline Audit and Release Gap Analysis

Before changing the implementation:

1. Inspect the entire repository.
2. Review the Phase 0–4 roadmap and implementation reports.
3. Inspect existing MCP tools and response schemas.
4. Inspect Capture Registry implementation.
5. Inspect Instance Manager and Session Manager.
6. Inspect RenderDoc Extension and IPC implementation.
7. Inspect configuration and logging.
8. Inspect existing installation scripts.
9. Inspect automated tests.
10. Run the complete existing test suite.
11. Run linting and configured static type checks.
12. Review known limitations and unresolved issues.

### Baseline Report

Record:

- Python version
- `uv` version
- MCP SDK version
- RenderDoc version
- RenderDoc executable path
- Git revision
- Number of existing tests
- Passing tests
- Failing tests
- Skipped tests
- Existing warnings
- Known integration limitations

### Gap Classification

Classify discovered problems as:

- **P0 — Release blocker:** Data loss, unauthorized window closure, severe correctness failure, security defect, or broken core workflow.
- **P1 — Must fix:** Significant reliability issue affecting normal use.
- **P2 — Should fix:** Limited edge case, usability defect, or maintainability concern.
- **P3 — Deferred:** Nonessential enhancement outside the initial release scope.

Do not expand the project scope to address unrelated improvements.

### Deliverable

Create `docs/release_readiness.md` containing the initial audit, release blockers, and remediation plan.

---

## 3. Task B — Capture Registry Reliability

Review and harden the complete `.rdc` discovery lifecycle.

### Filesystem Conditions

Test and handle:

- Empty capture directories
- Missing directories
- Inaccessible directories
- Deeply nested directories
- Unicode directory and filenames
- Long Windows paths
- Multiple configured directories
- Overlapping directories
- Filesystem watcher failures
- Rapid file creation
- Rapid file modification
- File renaming
- File moving
- File deletion
- File replacement
- Temporary filesystem errors
- Missed filesystem events

### Capture Readiness

Verify that the registry correctly handles:

- Partially written captures
- Files growing over time
- Temporary pauses during writing
- File locking
- Permission failures
- Zero-length files
- Invalid `.rdc` files
- Captures deleted during validation
- Captures replaced after readiness confirmation

### Readiness Semantics

Preserve the distinction between:

- Filesystem stability
- Filesystem accessibility
- RenderDoc format validity
- Actual replay compatibility

Do not claim that an `.rdc` is valid solely because its size has stopped changing.

When format validation is unavailable, report the actual validation level.

### Capture Identity

Test:

- Stable Capture IDs across restarts
- Duplicate filenames
- Rename behavior
- Move behavior
- File copies
- File replacement
- Registry reconciliation
- Database migration

Avoid unnecessary full-file hashing during normal discovery.

### Latest Capture Resolution

Verify:

- Deterministic ordering
- Correct exclusion of incomplete captures
- Same-timestamp behavior
- Directory-specific filtering
- Correct handling of deleted captures
- Explicit uncertainty when ordering is heuristic

Do not promise exact capture chronology without sufficient evidence.

### Deliverable

A stable Capture Registry that maintains consistent identities and accurate readiness information under common filesystem failures.

---

## 4. Task C — Process, Window, and Session Safety

Audit all RenderDoc process and window operations.

### Process Identity

Verify:

- PID reuse handling
- Process creation-time validation
- Executable identity checks
- Process exit during discovery
- Permission-denied process queries
- Multiple RenderDoc instances
- GUI process reuse behavior

### Window Identity

Verify:

- Native window handle reuse
- Multiple windows per process
- Minimized windows
- Hidden windows
- Destroyed windows
- Foreground activation restrictions
- Modal dialogs
- Ambiguous process-to-window relationships

Never use window titles alone as authoritative identity.

### Ownership

Preserve these classifications:

- Managed
- External
- Unknown

A process discovered through OS enumeration or a connected extension must not automatically become managed.

### Protected Sessions

Verify that protected sessions cannot be:

- Closed implicitly
- Replaced implicitly
- Removed through automatic cleanup
- Affected by unrelated session operations

Protection must survive server restarts.

### Closing Behavior

Use graceful, targeted closure.

Do not use forced process termination as normal cleanup.

If a close command times out, report the actual observed state.

Do not assume a timeout means the window remained open or closed.

### Shutdown Behavior

Stopping RenderEyeMCP must not close RenderDoc windows.

Stopping the server must not terminate managed GUI instances automatically.

### Deliverable

Verified process, window, and session safety guarantees.

---

## 5. Task D — IPC and Extension Reliability

Harden the communication between RenderEyeMCP and RenderDoc GUI extensions.

### Connection Lifecycle

Test:

- Extension starts before the server
- Server starts before the extension
- Server restart
- Extension reload
- RenderDoc normal shutdown
- Unexpected RenderDoc process exit
- Temporary IPC disconnection
- Multiple simultaneous extension connections
- Protocol version mismatch
- Authentication failure
- Slow client
- Unresponsive client

### Message Handling

Validate:

- Message framing
- Partial reads
- Multiple messages in one transport read
- Malformed JSON
- Invalid UTF-8
- Oversized messages
- Unknown message types
- Duplicate request IDs
- Late responses
- Missing responses
- Out-of-order state notifications

### Reconnection

Ensure that:

- Reconnection uses bounded backoff.
- Repeated failures do not consume excessive CPU.
- Stale connections are released.
- Duplicate active connections are prevented.
- Reconnected instances obtain fresh GUI snapshots.
- State revisions prevent old updates from overwriting new ones.

### GUI Thread Safety

Verify that:

- Socket communication does not block the GUI thread.
- GUI API calls execute in the supported context.
- Extension unload does not leave unsafe callbacks.
- Worker threads terminate cleanly.
- Background exceptions are logged and isolated.

### Security

Verify that:

- IPC endpoints are local-only.
- Authentication is enforced.
- Secrets are not logged.
- Unauthorized clients cannot issue GUI commands.
- Arbitrary code execution is unavailable.
- Oversized or malformed messages cannot exhaust server resources.

### Deliverable

A reliable multi-instance IPC and extension subsystem with graceful failure recovery.

---

## 6. Task E — Persistence and Crash Recovery

Validate Capture Registry and Session Manager persistence.

### Failure Scenarios

Test:

- Clean MCP server shutdown
- Unexpected MCP server termination
- Server restart
- RenderDoc crash
- Extension disconnection
- Database lock contention
- Interrupted database transaction
- Missing registry database
- Corrupted database
- Partial configuration corruption

### Database Integrity

Where SQLite is used:

- Use transactions correctly.
- Verify schema migrations.
- Validate foreign-key relationships where applicable.
- Handle database busy conditions.
- Avoid holding database locks during slow GUI operations.
- Ensure migration failure does not silently discard user state.

### Recovery Rules

After restart:

1. Load persisted registry and session metadata.
2. Discover currently running RenderDoc instances.
3. Re-establish extension connections.
4. Obtain fresh GUI state snapshots.
5. Reconcile Capture IDs and Session IDs.
6. Mark uncertain associations explicitly.
7. Preserve protection settings.
8. Do not automatically open or close captures.
9. Do not claim stale process information is current.

### Corrupted Storage

Prefer explicit diagnostic failures and safe recovery mechanisms over silently resetting the registry.

If the database requires recreation, preserve the damaged file for inspection when practical.

Do not discard user metadata without explicit authorization.

### Deliverable

Crash-resilient persistence and conservative state recovery.

---

## 7. Task F — Operation Coordination and Timeout Handling

Review state-changing MCP operations.

### Operations

Focus on:

- `capture_open`
- `session_focus`
- `session_close`
- `session_protect`
- `capture_rescan`

### Requirements

- Validate parameters before execution.
- Resolve `latest` once per operation.
- Preserve resolved Capture IDs.
- Revalidate target sessions before GUI actions.
- Prevent conflicting operations.
- Track operation state.
- Enforce bounded timeouts.
- Preserve request correlation.
- Handle IPC loss during operations.
- Avoid duplicate unintended launches.
- Avoid repeating potentially destructive operations blindly.

### Operation Outcomes

Distinguish:

- Requested
- Pending
- Confirmed
- Failed
- Unsupported
- Timed out
- Unknown outcome

Do not report a successful GUI operation solely because the command was sent.

### Idempotency

Test repeated requests.

Ensure request retries do not unintentionally:

- Open duplicate windows
- Close the wrong session
- Replace the wrong capture
- Corrupt operation state

Distinct intentional `new_window` requests must still be supported.

### Deliverable

Predictable operation behavior under concurrency, retries, and failures.

---

## 8. Task G — Automated Test Expansion

Expand the automated test suite to cover release-critical behaviors.

### Unit Tests

Cover:

- Configuration validation
- Capture discovery
- Capture readiness
- Capture identity
- Latest-capture selection
- Registry persistence
- Process identity
- Window identity
- Session lifecycle
- Session protection
- IPC serialization
- IPC authentication
- IPC reconnection
- GUI state synchronization
- Operation coordination
- MCP response models

### Integration Tests

Cover:

- Capture Registry and SQLite
- Watcher and registry reconciliation
- Session Manager and Instance Manager
- IPC server and simulated extension
- MCP tools and application services
- MCP server initialization and shutdown

### MCP Protocol Tests

Use a real MCP client implementation compatible with the installed SDK.

Verify:

- Initialization
- Tool discovery
- Tool input validation
- Tool invocation
- Structured results
- Tool errors
- Multiple sequential calls
- Graceful shutdown

Where supported by the installed MCP Python SDK, use its in-memory client testing mechanisms for integration tests.

Also verify the actual stdio startup path, because in-memory tests alone do not cover process startup and stdout contamination.

### Failure Injection

Create deterministic simulations for:

- Process crash
- IPC disconnection
- Database failure
- Filesystem watcher failure
- Window disappearance
- Operation timeout
- Delayed GUI response
- Stale state update

Prefer controlled mocks, simulated clients, and isolated test processes.

Do not force-terminate unrelated RenderDoc processes.

### Test Determinism

Avoid unnecessary time-based sleeps.

Use explicit synchronization and controlled clocks where practical.

Make failures reproducible.

### Coverage

Measure test coverage if the project already uses a compatible coverage tool or introducing one is lightweight.

Prioritize high-risk code paths over achieving an arbitrary percentage.

Do not weaken assertions merely to increase passing test counts.

### Deliverable

A comprehensive automated regression suite with reproducible results.

---

## 9. Task H — Real RenderDoc Integration Testing

Use the installed RenderDoc application:

`D:\Programs\RenderDoc`

Use real `.rdc` captures from the Capture Registry.

The Unity project under `tests/TestProject` may be used to generate additional captures if needed.

### Test Environment

Record:

- Windows version
- RenderDoc version
- Python version
- MCP SDK version
- RenderEye Extension version
- Test capture paths
- Relevant GPU and graphics API information when available

Do not include private machine identifiers or unnecessary personal data in public reports.

### Scenario A — Capture Discovery

1. Generate or locate real `.rdc` captures.
2. Start RenderEyeMCP.
3. Query `capture_list`.
4. Query `capture_latest`.
5. Compare results to actual files.

Expected:

Correct capture discovery and deterministic latest selection.

### Scenario B — Open Latest Capture

1. Generate a new capture.
2. Wait for readiness validation.
3. Invoke `capture_open` with `latest`.
4. Observe the RenderDoc GUI.
5. Query the resulting session.

Expected:

The correct capture is loaded and the result is confirmed through actual GUI state.

### Scenario C — Multiple Windows

1. Open Capture A.
2. Open Capture B using `new_window`.
3. Confirm both windows remain accessible.
4. Query both sessions.
5. Focus each independently.

Expected:

Distinct sessions maintain correct capture associations.

### Scenario D — Manual GUI Changes

1. Open Capture A through MCP.
2. Manually load Capture B through RenderDoc.
3. Query the session.

Expected:

The reported GUI state reflects Capture B rather than stale Capture A information.

### Scenario E — Protected Session

1. Open a managed test session.
2. Protect it.
3. Attempt closure.
4. Attempt replacement.
5. Restart RenderEyeMCP.
6. Verify protection remains.

Expected:

Protected sessions are never modified by rejected destructive operations.

### Scenario F — External Window

1. Launch RenderDoc manually.
2. Open a capture manually.
3. Discover the instance through RenderEyeMCP.
4. Attempt an operation restricted to managed sessions.

Expected:

The external window remains unaffected.

### Scenario G — Server Restart

1. Open multiple managed sessions.
2. Restart the MCP server.
3. Allow extension reconnection.
4. Query session state.

Expected:

Recoverable associations are restored without closing or reopening GUI windows.

### Scenario H — Extension Disconnection

1. Establish a working extension connection.
2. Disconnect or reload the extension through a controlled procedure.
3. Query session state.
4. Restore the extension connection.

Expected:

State becomes stale during disconnection and is refreshed after reconnection.

### Scenario I — Session Closure

1. Open two managed test sessions.
2. Close Session A.
3. Query Session B.

Expected:

Only Session A is closed.

### Scenario J — Unity Capture Workflow

1. Inspect `tests/TestProject`.
2. Launch the existing Unity project if the environment supports it.
3. Generate a RenderDoc capture through the available Unity workflow.
4. Discover the capture through RenderEyeMCP.
5. Open it through MCP.
6. Verify the loaded capture in RenderDoc.

Expected:

The complete Unity → `.rdc` → RenderEyeMCP → RenderDoc workflow functions without modifying production engine code.

### Safety

- Do not terminate user-created RenderDoc processes.
- Do not close unrelated windows.
- Do not overwrite captures.
- Do not modify Unity rendering configuration unnecessarily.
- Do not run destructive integration tests automatically without an isolated test target.
- Clearly distinguish tests executed against real RenderDoc from simulated tests.

### Deliverable

A reproducible real-world integration test report.

---

## 10. Task I — Performance and Resource Stability

Measure resource usage during normal operation.

### Performance Scenarios

Test:

- Registry containing 100 captures
- Registry containing 1,000 captures
- Registry containing 10,000 captures, using synthetic metadata where appropriate
- Multiple capture directories
- Burst creation of capture files
- Repeated `capture_list` queries
- Repeated `session_list` queries
- Multiple concurrent extension connections
- Repeated server startup and shutdown

### Measurements

Record where practical:

- Server startup time
- Initial capture scan duration
- Capture discovery latency
- Registry query latency
- MCP tool response latency
- CPU usage during idle monitoring
- Memory usage
- Open handles
- Background thread count
- IPC reconnect behavior

Do not invent performance numbers.

### Stability Requirements

- Avoid continuous busy polling.
- Avoid unnecessary full-directory scans.
- Bound memory usage for large capture lists.
- Paginate large results.
- Release sockets and handles.
- Avoid uncontrolled thread creation.
- Prevent unbounded retry queues.

### Performance Targets

Establish reasonable targets based on observed baseline performance and the intended local workstation use case.

Document targets and actual results.

Do not introduce premature optimization that increases complexity without measurable benefit.

### Deliverable

A concise performance and resource stability report.

---

## 11. Task J — Installation and Distribution

Prepare a reproducible local installation workflow.

### Python Package

Verify:

- `pyproject.toml` metadata
- Package name and version
- Supported Python versions
- Dependencies
- Optional dependencies
- Console entry point
- Included package resources
- License metadata
- README metadata

### uv Installation

Support a documented setup using `uv`.

For development:

```bash
uv sync
```

For running the MCP server:

```bash
uv run rendereye-mcp
```

Use the actual console entry point defined by the project.

If the existing entry point differs, document the verified command instead.

### Build Validation

Build the Python distribution using the existing project build backend.

For example:

```bash
uv build
```

Verify that the produced wheel and source distribution contain all required files.

Test installation into an isolated environment.

Do not assume that a successful build guarantees the package starts correctly.

### RenderDoc Extension Package

Prepare an installable extension distribution.

Requirements:

- Correct extension metadata
- Required Python files
- Compatible IPC protocol version
- Installation instructions
- Upgrade procedure
- Uninstallation procedure

Do not package or redistribute RenderDoc binaries unless distribution terms and project requirements have been explicitly reviewed.

### Installation Scripts

If installation scripts are provided, they must:

- Validate source and destination paths.
- Avoid overwriting unrelated extensions.
- Preserve user configuration.
- Report installation errors.
- Support repeat execution safely.
- Avoid requiring administrator privileges unnecessarily.
- Avoid modifying RenderDoc executables.

### Configuration

Provide example configurations without hardcoding developer-specific absolute paths.

The installation directory `D:\Programs\RenderDoc` is a development environment detail, not a universal default.

### Deliverable

Reproducible Python package and RenderDoc extension distribution.

---

## 12. Task K — Claude Code Installation and Verification

Provide a clean Claude Code integration experience.

### Requirements

- Provide a validated MCP configuration example.
- Verify stdio startup.
- Verify `uv` command resolution.
- Verify working-directory behavior.
- Verify paths containing spaces.
- Verify Unicode paths.
- Confirm that logs do not contaminate MCP stdout.
- Confirm that startup errors are actionable.

### Example Workflow

A new developer should be able to:

1. Clone or obtain RenderEyeMCP.
2. Install Python dependencies using `uv`.
3. Install the RenderDoc extension.
4. Configure capture directories.
5. Register RenderEyeMCP with Claude Code.
6. Start Claude Code.
7. Verify MCP connectivity.
8. Query available captures.
9. Open the latest capture.
10. Manage debugging sessions safely.

### Validation

Use a real MCP client to verify the complete connection path.

If Claude Code is installed, validate the supplied configuration directly.

If Claude Code is unavailable, test with another real MCP client and report Claude Code integration as not directly verified.

### Deliverable

A reproducible end-user setup and verification guide.

---

## 13. Task L — Diagnostics and Troubleshooting

Improve operational diagnostics.

### Required Information

Expose or log:

- Server version
- RenderDoc version
- Extension version
- IPC protocol version
- Capture Registry status
- Watched directory status
- Connected extension count
- Known instance count
- Active session count
- Last successful GUI synchronization
- Last significant IPC failure
- Last significant registry failure

### Logging

- Keep logs separate from MCP stdio output.
- Include request and instance identifiers.
- Avoid excessive repetitive logging.
- Avoid logging authentication credentials.
- Avoid leaking sensitive environment information.
- Use consistent severity levels.

### Troubleshooting Guide

Document how to diagnose:

- RenderDoc executable not found
- Extension not loaded
- Extension cannot connect
- Protocol version mismatch
- No captures discovered
- Latest capture not ready
- Incorrect capture directory
- Capture opening fails
- Window cannot be focused
- Session cannot be closed
- Session state is stale
- MCP server fails to start
- Claude Code cannot discover tools

### Deliverable

Useful diagnostics and a troubleshooting guide suitable for ordinary users.

---

## 14. Task M — Documentation Finalization

Review and complete all user-facing documentation.

### README.md

Include:

- Project description
- Main features
- Supported platforms
- Requirements
- Installation
- Configuration
- Claude Code setup
- Basic usage
- Multi-window workflow
- Safety behavior
- Known limitations
- Troubleshooting links

### docs/architecture.md

Describe the complete architecture:

- Capture Registry
- Instance Manager
- Session Manager
- RenderDoc Extension
- IPC Connection Manager
- MCP Tool Layer

### docs/mcp_api.md

Ensure that every public MCP tool has:

- Description
- Parameters
- Defaults
- Output schema
- Error codes
- Side effects
- Usage example

### docs/capture_registry.md

Document:

- Capture identity
- Readiness validation
- Latest-capture ordering
- Persistence
- Filesystem limitations

### docs/session_management.md

Document:

- Session identity
- Lifecycle states
- Ownership
- Protection
- Process/window associations
- Restart recovery

### docs/ipc_protocol.md

Document:

- Transport
- Authentication
- Protocol version
- Message framing
- Message types
- Connection lifecycle
- Error handling
- Compatibility rules

### docs/agent_workflows.md

Include practical examples:

- Find latest capture
- Open latest capture
- Open two captures
- Focus a session
- Protect a session
- Close a managed session
- Recover from a disconnected extension

### Additional Release Documentation

Create:

- `CHANGELOG.md`
- `docs/release_readiness.md`
- `docs/release_testing.md`
- `docs/troubleshooting.md`
- `docs/release_notes_v1.0.md`

Avoid duplicating large sections of documentation unnecessarily.

### Deliverable

Complete and internally consistent documentation for v1.0.

---

## 15. Task N — Release Packaging and Versioning

Prepare the v1.0.0 release.

### Version Consistency

Ensure version information is consistent across:

- Python package
- MCP server
- RenderDoc extension
- IPC protocol compatibility metadata
- Documentation
- Release notes

The IPC protocol version does not need to equal the application version.

Document compatibility independently.

### Build Artifacts

Prepare:

- Python wheel
- Python source distribution
- RenderDoc extension package
- Example configuration
- Installation instructions
- Release notes

A combined release archive may be provided if it materially improves installation.

### Build Verification

Verify:

- Clean package builds
- Correct package contents
- No missing modules
- No accidental test artifacts
- No sensitive configuration files
- No authentication tokens
- No temporary `.rdc` files
- No unnecessary Unity-generated files
- No bundled RenderDoc binaries

### Reproducibility

Use locked dependencies where appropriate.

Verify installation from the built distribution rather than relying exclusively on a development checkout.

### Release Metadata

Prepare:

- Version number
- Release date
- Supported environment
- Known limitations
- Installation instructions
- Upgrade instructions
- Uninstallation instructions

Do not create a Git tag, publish a GitHub release, or upload packages without explicit authorization.

### Deliverable

Validated local release artifacts and release metadata.

---

## 16. Task O — Security and Privacy Review

Perform a focused security review appropriate for a local MCP server controlling GUI applications.

### IPC Security

Verify:

- Local-only binding
- Authentication
- Message validation
- Connection identity
- Permission enforcement
- Secret handling
- Resource limits

### Filesystem Security

Verify:

- Path normalization
- Directory scope restrictions
- Symlink and junction handling
- Capture path validation
- No arbitrary file deletion
- No unrestricted file reading
- No unsafe executable invocation

### Process Control Security

Verify:

- No generic shell execution tools
- No arbitrary process termination
- No external window closure
- No bypass of protected sessions
- No unsafe PID-only identity assumptions

### MCP Security

Verify:

- Tool inputs are validated.
- Error responses do not leak unnecessary secrets.
- State-changing tools enforce ownership.
- Tool annotations accurately describe side effects.
- Configuration defaults are safe.

### Deliverable

A focused security review with any unresolved risks documented.

---

## 17. Task P — Release Acceptance Testing

Execute the final release acceptance suite.

### Core Workflow 1 — Capture Discovery

- Existing captures are discovered.
- New captures are detected.
- Incomplete captures are not falsely reported as format-validated.
- Capture IDs remain stable.
- Latest capture resolution works.

### Core Workflow 2 — Capture Opening

- Explicit Capture IDs work.
- `latest` works.
- Opening results are verified.
- Existing windows remain unaffected.
- Unsupported opening modes fail explicitly.

### Core Workflow 3 — Multi-Window Management

- Multiple sessions can coexist.
- Each session is independently identifiable.
- Correct window focus is attempted.
- Safe targeted closure works.
- Protected and external sessions remain safe.

### Core Workflow 4 — GUI Synchronization

- Actual loaded captures are reported.
- Manual GUI changes are reflected.
- Disconnected extension state becomes stale.
- Reconnection restores verified state.

### Core Workflow 5 — Restart Recovery

- Capture Registry state is restored.
- Session identities are reconciled.
- Protection flags persist.
- No GUI windows are unexpectedly closed.
- No duplicate sessions are created without justification.

### Core Workflow 6 — Agent Integration

- MCP server starts through the documented command.
- Tools are discoverable.
- Tool schemas are valid.
- Tool results are structured.
- Claude Code or a real MCP client can execute the core workflows.

### Acceptance Rules

A workflow passes only when its expected behavior is observed.

Automated simulated tests do not substitute for required real RenderDoc validation.

If the environment cannot execute a required test, mark it unverified rather than passed.

Maintain evidence for failures and corrective actions.

### Deliverable

A completed acceptance matrix with evidence.

---

## 18. Release Decision

Evaluate release readiness using three possible outcomes.

### READY

All mandatory acceptance criteria pass.

No unresolved P0 or P1 defects remain.

Required real RenderDoc workflows have been verified.

Release artifacts and documentation are valid.

### CONDITIONAL

Core functionality works, but noncritical limitations or incomplete optional validation remain.

Document every remaining limitation and its impact.

Do not automatically classify a conditional release as stable.

### BLOCKED

One or more release-critical conditions remain unresolved.

Examples:

- Incorrect capture-to-session association
- Unintended window closure
- Broken latest-capture resolution
- IPC security failure
- Data loss during persistence
- Nonfunctional MCP startup
- Unverified critical real RenderDoc integration
- Critical packaging defects

### Release Gate

Do not mark RenderEyeMCP v1.0.0 as stable unless the release status is READY.

If the status is CONDITIONAL or BLOCKED, prepare the artifacts and report exactly what prevents stable release.

Do not hide limitations or weaken acceptance criteria to obtain a passing result.

---

## 19. Definition of Done

Phase 5 is complete when:

- [ ] Existing Phase 0–4 functionality has been audited.
- [ ] All release-blocking defects have been resolved.
- [ ] Capture Registry reliability tests pass.
- [ ] Process and window safety tests pass.
- [ ] Session protection tests pass.
- [ ] IPC failure and recovery tests pass.
- [ ] Session persistence and reconciliation tests pass.
- [ ] Operation timeout and concurrency tests pass.
- [ ] Automated regression tests pass.
- [ ] Real RenderDoc integration tests pass.
- [ ] Unity workflow has been validated where available.
- [ ] Performance and resource behavior have been measured.
- [ ] Python package builds successfully.
- [ ] Built distributions install successfully.
- [ ] RenderDoc extension packaging is verified.
- [ ] Claude Code integration is documented and validated.
- [ ] Security review is completed.
- [ ] Documentation is complete.
- [ ] Release notes are prepared.
- [ ] Release acceptance matrix is complete.
- [ ] Release status is explicitly reported.

A release marked CONDITIONAL or BLOCKED may have completed its assessment and packaging work, but it does not satisfy the stable v1.0.0 release gate.

---

## 20. Execution Instructions

Execute the following sequence:

1. Inspect the repository and current implementation.
2. Establish the test and environment baseline.
3. Identify release blockers.
4. Fix Capture Registry reliability defects.
5. Fix process, window, and session safety defects.
6. Harden IPC and extension lifecycle behavior.
7. Validate persistence and crash recovery.
8. Review operation coordination.
9. Expand automated tests.
10. Execute the complete regression suite.
11. Perform real RenderDoc integration tests.
12. Test Unity capture workflows where possible.
13. Measure performance and resource stability.
14. Implement and validate installation procedures.
15. Build and test distribution packages.
16. Verify Claude Code integration.
17. Complete the security review.
18. Finalize documentation.
19. Prepare release notes.
20. Execute final release acceptance tests.
21. Evaluate the release gate.
22. Produce the final report.

Work autonomously using the available tools and repository.

Do not stop at planning.

Prioritize actual defects and release-critical failures.

Avoid broad rewrites of stable components.

Preserve backward compatibility where practical.

Do not introduce functionality beyond the v1.0 roadmap.

Do not modify production engine code.

Do not publish packages or create a remote release without authorization.

If an integration test requires unavailable hardware or software, complete all remaining work and explicitly report the unverified requirement.

---

## 21. Final Report

After implementation, provide the following:

### 1. Implementation Summary

Describe reliability improvements, fixes, and packaging changes.

### 2. Files Changed

List important added or modified files.

### 3. Environment

Report verified Python, `uv`, MCP SDK, RenderDoc, and Windows versions.

### 4. Automated Tests

Report:

- Commands executed
- Tests passed
- Tests failed
- Tests skipped
- Relevant warnings

### 5. Real RenderDoc Validation

Report the exact workflows executed against the installed RenderDoc application.

### 6. Unity Integration

Report whether the Unity → `.rdc` → RenderEyeMCP → RenderDoc workflow was verified.

### 7. Security and Safety

Summarize ownership, session protection, IPC security, and filesystem safeguards.

### 8. Performance

Report measured performance and resource results.

### 9. Release Artifacts

List generated package files and their locations.

### 10. Known Limitations

List unresolved defects, unverified assumptions, and compatibility restrictions.

### 11. Release Readiness

Classify the result as:

- READY
- CONDITIONAL
- BLOCKED

Explain the evidence supporting the decision.

### 12. Remaining Actions

List only actions genuinely necessary before a stable v1.0.0 release.

Do not propose additional feature development unless it is required to resolve a release blocker.

Do not claim successful tests that were not actually executed.

Do not publish or tag the release automatically.

**Phase 5 Focus: Deliver a secure, reliable, thoroughly tested, reproducible, and release-ready RenderEyeMCP v1.0.0 without expanding the project's functional scope.**
