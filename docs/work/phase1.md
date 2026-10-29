# RenderEyeMCP — Phase 1 Implementation Instructions

## Objective

Implement **Phase 1: Capture Discovery & Registry** of RenderEyeMCP.

Phase 0 established the MCP server foundation, RenderDoc integration proof of concept, and local IPC infrastructure.

Phase 1 must implement a reliable system for discovering, tracking, validating, and querying RenderDoc capture files (`.rdc`).

The primary goal is to enable coding agents such as Claude Code to identify the latest available capture without manually searching directories or guessing filenames.

A Unity project is available at:

`tests/TestProject`

Use this project as an optional integration-testing environment for generating real RenderDoc captures.

**Implement the actual functionality, automated tests, and MCP integration. Do not stop at documentation or architectural proposals.**

---

## 1. Project Constraints

### Environment

- Python is the primary implementation language.
- `uv` is already installed and must be used for dependency management.
- Windows is the primary target platform.
- Preserve the Phase 0 MCP server and RenderDoc extension architecture.
- Reuse existing project modules and conventions wherever practical.
- Use the existing MCP Python SDK and remain compatible with the installed version.

### Integration Constraints

- Do not modify the existing production engine.
- Do not modify RenderDoc source code.
- Do not require rebuilding RenderDoc.
- Do not implement RenderDoc GUI session management in this phase.
- Do not implement GPU frame analysis.
- Do not introduce unnecessary external services.
- Do not assume capture files always use a fixed directory.
- Do not assume filesystem modification time accurately represents capture creation order.

### Unity Test Project

A Unity project exists at `tests/TestProject`.

- Inspect its structure before use.
- Detect the Unity version from `ProjectSettings/ProjectVersion.txt` when available.
- Do not overwrite project settings or change rendering pipelines unnecessarily.
- Do not upgrade the Unity project automatically.
- Do not modify assets, scenes, or packages unless required for an explicitly scoped test.
- Do not delete generated capture files without explicit ownership and cleanup rules.
- Keep Unity-specific test infrastructure separate from core Capture Registry functionality.

The Capture Registry must function independently of Unity.

---

## 2. Review Phase 0

Before implementing Phase 1:

1. Inspect the repository.
2. Review the Phase 0 implementation and documentation.
3. Identify the existing MCP server entry point.
4. Review configuration and logging mechanisms.
5. Review the IPC protocol and RenderDoc extension.
6. Run the existing automated tests.
7. Identify any incomplete Phase 0 functionality relevant to Phase 1.

Preserve backward compatibility with existing MCP tools.

Do not rewrite working Phase 0 modules unnecessarily.

If a Phase 0 limitation prevents Phase 1 integration, implement the smallest required fix and document it.

---

## 3. Capture Registry Architecture

Implement a dedicated Capture Registry subsystem.

Suggested structure:

```text
src/rendereye_mcp/
├── captures/
│   ├── __init__.py
│   ├── models.py
│   ├── discovery.py
│   ├── watcher.py
│   ├── readiness.py
│   ├── registry.py
│   └── storage.py
│
├── server.py
└── config.py

tests/
├── captures/
│   ├── test_discovery.py
│   ├── test_watcher.py
│   ├── test_readiness.py
│   ├── test_registry.py
│   ├── test_storage.py
│   └── test_mcp_tools.py
│
└── TestProject/
    └── ...
```

Adapt the structure to the existing repository where necessary.

### Architecture Requirements

Separate the following responsibilities:

**Capture Discovery**

Find `.rdc` files in configured directories.

**Filesystem Monitoring**

Detect file creation, modification, deletion, and rename events.

**Capture Readiness**

Determine whether a capture is sufficiently stable to be exposed as usable.

**Capture Registry**

Maintain capture identities, metadata, lifecycle states, and query operations.

**Persistent Storage**

Preserve capture history and metadata across MCP server restarts.

**MCP Interface**

Expose capture information to coding agents.

Do not tightly couple filesystem watchers to MCP protocol handlers.

Core registry functionality should be testable without running the MCP server.

---

## 4. Task A — Capture Directory Configuration

Implement configurable capture search locations.

### Requirements

- Support one or more capture directories.
- Support absolute and relative paths.
- Expand environment variables and user-home paths where appropriate.
- Normalize paths using platform-aware filesystem semantics.
- Support configurable recursive scanning.
- Support configurable exclusions.
- Avoid following symbolic-link or junction cycles.
- Handle nonexistent directories gracefully.
- Handle permission errors without crashing the server.
- Support Unicode directory and filenames.
- Avoid scanning the entire filesystem by default.

### Default Locations

Investigate RenderDoc's actual capture locations.

Possible locations include:

- Explicitly configured capture directories
- Temporary directories used by RenderDoc
- Capture directories identified during Phase 0
- User-selected capture output directories

Do not treat these as universally valid defaults.

Only enable automatically discovered directories when their scope and ownership are sufficiently clear.

Prefer explicit configuration when uncertainty exists.

### Configuration Example

```toml
[captures]
enabled = true
recursive = false
scan_interval_seconds = 10
readiness_stability_seconds = 2

[[captures.directories]]
path = "D:/RenderDoc/Captures"
recursive = true

[[captures.directories]]
path = "C:/Temp/RenderDoc"
recursive = false
```

This is an illustrative configuration format.

Adapt it to the existing configuration architecture.

### Deliverable

A validated configuration model and directory discovery mechanism.

---

## 5. Task B — Initial Capture Discovery

Implement startup scanning of configured directories.

### Requirements

- Discover existing `.rdc` files.
- Treat file extensions case-insensitively on Windows.
- Ignore unrelated files.
- Collect filesystem metadata without opening the capture through RenderDoc.
- Avoid loading entire `.rdc` files into memory.
- Handle inaccessible files gracefully.
- Deduplicate overlapping directory results.
- Avoid inserting duplicate registry records for the same discovered file.
- Produce deterministic results.
- Continue scanning when individual files fail.

### Capture Metadata

Track at least:

```json
{
  "capture_id": "cap-000001",
  "path": "D:/RenderDoc/Captures/frame001.rdc",
  "filename": "frame001.rdc",
  "file_size": 10485760,
  "created_at": "2026-10-23T12:00:00Z",
  "modified_at": "2026-10-23T12:00:01Z",
  "discovered_at": "2026-10-23T12:00:03Z",
  "status": "ready"
}
```

The example values are illustrative.

### Timestamp Semantics

Distinguish:

- Filesystem creation time
- Filesystem modification time
- Registry discovery time
- Last observation time
- Readiness confirmation time

Use timezone-aware timestamps.

Do not interpret filesystem creation time as authoritative RenderDoc capture generation time.

### Deliverable

Startup scanning that populates the Capture Registry.

---

## 6. Task C — Filesystem Monitoring

Implement automatic detection of newly generated `.rdc` files.

### Requirements

- Detect newly created files.
- Detect modifications.
- Detect renames and moves where observable.
- Detect deletions.
- Handle bursts of filesystem events.
- Avoid duplicate processing.
- Avoid expensive full-directory rescans for every event.
- Support multiple watched directories.
- Shut down watcher threads cleanly.
- Prevent filesystem monitoring failures from crashing the MCP server.

### Implementation

Evaluate using `watchdog` for filesystem monitoring.

Install it using `uv` if selected.

```bash
uv add watchdog
```

Use the native observer where supported.

Investigate whether polling fallback is necessary for the target filesystem.

### Periodic Reconciliation

Filesystem notifications must not be treated as perfectly reliable.

Implement periodic rescanning to recover from:

- Missed events
- Watcher restarts
- Temporary directory inaccessibility
- Rapid file operations
- Files created while the MCP server is offline

The filesystem scan and event watcher must share the same registry reconciliation logic.

### Deliverable

Continuous capture discovery with periodic recovery.

---

## 7. Task D — Capture Readiness Detection

A newly discovered `.rdc` file must not immediately be assumed usable.

RenderDoc or the application may still be writing the file.

### Requirements

Implement a readiness state machine.

Recommended states:

```text
DISCOVERED
    |
    v
PENDING
    |
    v
READY
```

Additional states:

- `MISSING`
- `INACCESSIBLE`
- `INVALID`
- `STALE`

Define precise meanings and legal transitions for each state.

### Readiness Checks

Consider:

1. File exists.
2. File extension matches `.rdc`.
3. File size exceeds a defensible minimum.
4. File size remains stable across multiple checks.
5. File modification timestamp remains stable.
6. The file can be opened for reading.
7. The file is not known to be actively written.

Do not assume a fixed stability interval proves the capture is complete.

A file can remain unchanged temporarily while a writer is still active.

### Validation Levels

Separate:

- **Filesystem-ready:** The file passes stability and accessibility checks.
- **Format-validated:** A supported RenderDoc mechanism confirms that the file is a valid capture.

If format validation requires expensive operations or unavailable APIs, keep it optional.

Do not represent filesystem stability as definitive RenderDoc format validation.

### Failure Handling

- Retry transient failures with bounded backoff.
- Avoid permanent busy loops.
- Handle disappearing files.
- Handle file replacement during validation.
- Avoid blocking the MCP server event loop.
- Allow recovery when previously inaccessible files become readable.

### Deliverable

A configurable, testable readiness state machine.

---

## 8. Task E — Capture Identity and Deduplication

Assign a stable ID to each capture.

### Requirements

- Capture IDs must survive MCP server restarts.
- IDs must not depend only on list position.
- IDs must not depend only on filenames.
- Multiple captures with identical filenames must remain distinguishable.
- Directory overlap must not create duplicate captures.
- Repeated scans must be idempotent.
- File replacements must not silently inherit unrelated capture identities.
- Deleted captures must not be confused with newly created files.

### Identity Strategy

Investigate a combination of:

- Persistent registry-assigned identifiers
- Canonical filesystem paths
- File size and timestamps
- Platform-specific file identity where available
- Optional content hashing

Avoid hashing entire large `.rdc` files during routine discovery.

A hash may be calculated explicitly or lazily if required.

Document how identity behaves after:

- File rename
- File move
- File copy
- File deletion
- File replacement
- Registry restart

If the system cannot confidently establish that a moved file is the same capture, prefer a conservative new identity or explicit uncertainty over an incorrect association.

### Deliverable

Stable and documented Capture ID behavior.

---

## 9. Task F — Latest Capture Resolution

Implement reliable latest-capture selection.

### Requirements

- Return only ready captures by default.
- Support filtering by capture directory.
- Support deterministic selection.
- Avoid depending exclusively on filename sorting.
- Avoid depending exclusively on file modification time.
- Handle multiple captures with identical timestamps.
- Handle newly discovered but incomplete captures.
- Handle missing or deleted latest captures.
- Return a clear result when no suitable capture exists.

### Ordering Policy

Define an explicit ordering policy.

A possible policy:

1. Use authoritative capture generation timestamps when available.
2. Otherwise, use documented filesystem timestamp heuristics.
3. Use persisted discovery information as a secondary signal.
4. Use stable Capture IDs as deterministic tie-breakers.

Do not claim exact capture generation order when only approximate ordering information is available.

Include the ordering basis in returned metadata.

### Example Response

```json
{
  "capture_id": "cap-000042",
  "path": "D:/RenderDoc/Captures/frame042.rdc",
  "status": "ready",
  "selection_basis": "filesystem_creation_time",
  "ordering_confidence": "heuristic"
}
```

### Race Conditions

The selected capture may be deleted or replaced after resolution.

Design APIs so later operations can reference the resolved Capture ID rather than repeatedly resolving `latest`.

Document the limitations of filesystem-only discovery.

### Deliverable

Deterministic latest-capture resolution.

---

## 10. Task G — Persistent Registry

Implement lightweight persistence for capture metadata.

### Storage

Prefer SQLite through Python's standard library unless an existing repository component provides an appropriate alternative.

Do not introduce an external database server.

### Requirements

- Persist Capture IDs.
- Persist capture paths and metadata.
- Persist discovery and readiness information.
- Preserve identities across MCP server restarts.
- Support schema versioning and migrations.
- Handle database initialization.
- Handle concurrent access safely.
- Use transactions where necessary.
- Avoid blocking filesystem monitoring unnecessarily.
- Recover gracefully from missing or damaged storage when possible.

### Startup Reconciliation

At startup:

1. Load existing registry state.
2. Initialize configured watchers.
3. Scan capture directories.
4. Reconcile registry records against actual filesystem state.
5. Revalidate previously ready captures where necessary.
6. Mark missing captures appropriately.
7. Make the latest-capture selector available after initial reconciliation.

Avoid exposing stale registry state as if it had already been verified.

### Deliverable

A persistent, restart-safe Capture Registry.

---

## 11. Task H — Capture Query API

Implement an internal Capture Registry API independent of MCP.

Suggested operations:

```python
registry.list_captures(...)
registry.get_capture(capture_id)
registry.get_latest_capture(...)
registry.rescan(...)
registry.get_registry_status()
```

### Requirements

- Support filtering by status.
- Support filtering by configured directory.
- Support deterministic ordering.
- Support pagination.
- Support limits to avoid excessively large responses.
- Provide clear errors for unknown Capture IDs.
- Return serializable data models.
- Avoid exposing mutable internal registry state.

### Concurrency

Ensure consistency when:

- Filesystem watchers update the registry.
- The background scanner performs reconciliation.
- MCP tools query the registry simultaneously.

Use synchronization appropriate to the implementation.

Avoid holding database locks during slow filesystem operations.

### Deliverable

A stable internal API usable by later phases.

---

## 12. Task I — MCP Tool Integration

Extend the existing MCP server with capture-management tools.

### Required Tools

#### `capture_list`

Return captures from the registry.

Suggested parameters:

- `status`
- `directory`
- `limit`
- `offset`

Include a total count or equivalent pagination metadata.

#### `capture_get`

Return metadata for a specified Capture ID.

Required parameter:

- `capture_id`

#### `capture_latest`

Return the latest eligible capture.

Suggested parameters:

- `directory`
- `include_pending` — Diagnostic opt-in only; must not label pending files as ready.

#### `capture_rescan`

Trigger a registry reconciliation operation.

The operation must be bounded and must not block the MCP protocol indefinitely.

If a rescan runs asynchronously, return a job identifier or documented status rather than reporting completion prematurely.

#### `capture_registry_status`

Report:

- Configured directories
- Watcher health
- Last successful scan
- Capture counts by state
- Pending validation count
- Registry storage status
- Last significant error

### Integration Requirements

- Use the existing MCP SDK.
- Preserve `server_status`.
- Reuse Phase 0 configuration and logging.
- Return structured JSON-compatible results.
- Provide consistent error handling.
- Avoid excessive output.
- Do not expose arbitrary filesystem reading functionality through capture query tools.

### Deferred Functionality

Do not implement `capture_open` in Phase 1.

That tool requires the session and instance-management functionality planned for Phase 2.

### Deliverable

Functional capture-management MCP tools accessible through Claude Code.

---

## 13. Task J — Unity Integration Testing

A Unity project is available at:

`tests/TestProject`

Use it to validate capture discovery using realistic rendering workloads.

### Initial Inspection

1. Verify that `tests/TestProject` is a Unity project.
2. Identify its Unity Editor version.
3. Inspect the current scene and rendering configuration.
4. Determine whether the Unity Editor is installed.
5. Determine whether the RenderDoc capture workflow is available.

### Real Capture Test

If the environment supports Unity and RenderDoc integration:

1. Open the existing Unity project.
2. Use the available RenderDoc workflow to generate a capture.
3. Identify the actual `.rdc` output location.
4. Configure RenderEyeMCP to monitor that location.
5. Generate one capture.
6. Confirm that the registry discovers it.
7. Confirm that the file transitions to ready only after its readiness checks pass.
8. Generate another capture.
9. Confirm that both captures retain separate IDs.
10. Confirm that `capture_latest` selects the expected capture according to the documented ordering policy.
11. Restart the MCP server.
12. Verify that the capture registry preserves identity and metadata.

Do not assume Unity always writes the capture directly into the project directory.

Do not move or rename generated capture files unless necessary for the test.

### Safety

- Avoid modifying Unity project settings.
- Avoid Unity version upgrades.
- Avoid deleting user-created capture files.
- Avoid modifying production engine code.
- Keep generated test artifacts out of version control.
- Do not automatically launch expensive Unity operations as part of normal unit tests.

### Optional Test Fixtures

If real `.rdc` files are available, create a small reusable test fixture set or reference local fixtures through configurable paths.

Do not commit large capture binaries without an explicit repository policy.

Document how to reproduce the Unity integration tests.

### Fallback

If Unity or RenderDoc is unavailable:

- Implement simulated filesystem tests.
- Implement an optional manual integration-test procedure.
- Report which scenarios were not executed.

Do not claim that synthetic `.rdc` files prove RenderDoc replay compatibility.

### Deliverable

A documented, reproducible Unity-to-RenderEyeMCP capture discovery workflow.

---

## 14. Task K — Automated Testing

Implement comprehensive automated tests.

### Discovery Tests

- Empty directory
- One `.rdc` file
- Multiple `.rdc` files
- Nested directories
- Duplicate directory roots
- Case-insensitive extension handling
- Unicode paths
- Missing directory
- Permission-denied directory

### Filesystem Monitoring Tests

- New file creation
- File modification
- File deletion
- File rename
- File move
- Rapid successive events
- Missed-event reconciliation
- Watcher restart

### Readiness Tests

- Partially written file
- Stable file
- File growing during observation
- File disappearing during validation
- Inaccessible file
- Invalid file
- File replaced after becoming ready
- Temporary writer pause
- Validation retry and recovery

### Registry Tests

- Stable Capture IDs
- Duplicate filename handling
- Persistence after restart
- Deletion and rediscovery
- Concurrent registry access
- Deterministic ordering
- Latest capture with identical timestamps
- Missing latest capture
- Pending newest capture
- Corrupted or missing registry database

### MCP Tests

- Tool discovery
- Valid tool invocation
- Invalid Capture ID
- Empty registry
- Pagination
- Filtering
- Rescan handling
- Registry status reporting
- Compatibility with Phase 0 tools

### Test Requirements

- Use `pytest`.
- Use temporary directories for filesystem fixtures.
- Do not require Unity for ordinary unit tests.
- Do not require RenderDoc for ordinary unit tests.
- Make timing-sensitive tests deterministic where practical.
- Avoid flaky tests dependent on arbitrary sleeps.
- Explicitly separate real integration tests from simulated tests.

Run tests through `uv`.

```bash
uv run pytest
uv run ruff check .
```

Adapt commands if the project already provides equivalent scripts.

---

## 15. Documentation

Update existing documentation.

### README.md

Add:

- Capture Registry overview
- Configuration examples
- Capture directory setup
- MCP tool reference
- Usage examples
- Unity integration-testing instructions
- Known limitations

### docs/architecture.md

Document:

- Capture Discovery architecture
- Filesystem watcher behavior
- Readiness state machine
- Capture identity strategy
- Persistence model
- Registry concurrency model

### docs/capture_registry.md

Create a dedicated document describing:

- Registry data model
- State transitions
- Latest-capture ordering
- Timestamp semantics
- Duplicate handling
- Rename and deletion behavior
- Storage schema
- Error handling

### docs/development.md

Add commands for:

- Running the Capture Registry
- Configuring capture directories
- Running registry tests
- Running Unity integration tests
- Inspecting registry diagnostics

Document technical decisions that affect later phases.

---

## 16. Phase 1 Acceptance Scenarios

### Scenario A — Existing Captures

1. Configure a directory containing three existing `.rdc` files.
2. Start RenderEyeMCP.
3. Allow initial reconciliation to complete.
4. Invoke `capture_list`.

**Expected:** All three files are represented by distinct, queryable registry records.

### Scenario B — New Capture Discovery

1. Start RenderEyeMCP.
2. Create a new `.rdc` file in a monitored directory.
3. Observe the discovery and readiness transitions.
4. Invoke `capture_latest`.

**Expected:** The new capture is selected after it satisfies the configured readiness policy.

### Scenario C — Incomplete Capture

1. Create a file with a `.rdc` extension.
2. Write data in multiple stages with a pause between writes.
3. Query the registry during the write.

**Expected:** The registry follows the documented readiness policy and does not present unverified filesystem stability as guaranteed format validity.

### Scenario D — Multiple Directories

1. Configure two capture directories.
2. Create captures with identical filenames in both directories.
3. Query the registry.

**Expected:** Each capture has a distinct identity, and directory filtering works correctly.

### Scenario E — Restart Recovery

1. Discover multiple captures.
2. Shut down the MCP server.
3. Restart the server.
4. Reconcile with the filesystem.

**Expected:** Existing captures preserve their IDs and valid metadata.

### Scenario F — Deleted Capture

1. Discover a valid capture.
2. Delete or move it outside watched directories.
3. Reconcile the registry.

**Expected:** The registry no longer reports the unavailable file as ready.

### Scenario G — Unity Capture

1. Generate a real RenderDoc capture through the Unity test project.
2. Discover it through RenderEyeMCP.
3. Query the latest capture through MCP.

**Expected:** The real capture is correctly identified without modifying the Unity project or requiring manual filename selection.

---

## 17. Phase 1 Definition of Done

Phase 1 is complete when:

- [ ] Capture directories are configurable.
- [ ] Startup scanning discovers existing `.rdc` files.
- [ ] Filesystem monitoring detects new captures.
- [ ] Periodic reconciliation recovers missed events.
- [ ] Capture readiness is evaluated using a documented policy.
- [ ] Stable Capture IDs are assigned.
- [ ] Registry metadata persists across restarts.
- [ ] Deleted and replaced files are handled correctly.
- [ ] Latest capture resolution is deterministic.
- [ ] Capture query tools are available through MCP.
- [ ] Phase 0 functionality remains operational.
- [ ] Automated tests pass.
- [ ] Documentation is updated.
- [ ] Unity integration has been tested or explicitly reported as unverified.

---

## 18. Execution Instructions

Execute the implementation in this order:

1. Inspect the repository and Phase 0 implementation.
2. Run the existing tests.
3. Inspect `tests/TestProject`.
4. Define capture models and lifecycle states.
5. Implement configuration and startup discovery.
6. Implement stable Capture IDs and deduplication.
7. Implement Capture Registry persistence.
8. Implement readiness detection.
9. Implement filesystem monitoring.
10. Implement periodic reconciliation.
11. Implement latest-capture selection.
12. Integrate capture tools into the MCP server.
13. Add automated tests.
14. Test with real RenderDoc captures where possible.
15. Perform Unity integration testing where available.
16. Update documentation.
17. Run the complete regression suite.
18. Review the Phase 1 acceptance criteria.

Work autonomously using the available development tools.

When implementation details are unspecified, choose the simplest reliable design consistent with the existing architecture.

Do not replace working Phase 0 components unnecessarily.

Do not create a second independent MCP server.

Do not introduce features belonging to Phase 2 or later.

If an environment-dependent test cannot run, continue with the remaining implementation and report the limitation.

**Prioritize correct Capture Registry behavior and real MCP integration over additional abstractions or speculative features.**

---

## 19. Final Report

After implementation, provide:

1. **Implementation Summary** — Features implemented.
2. **Files Changed** — Major files added or modified.
3. **Architecture** — Capture Registry and monitoring design.
4. **MCP Tools** — Available tools and parameters.
5. **Test Results** — Exact tests executed and outcomes.
6. **Unity Integration Results** — Whether real `.rdc` captures were tested.
7. **Known Limitations** — Unverified behaviors and edge cases.
8. **Phase 1 Status** — Complete, partially verified, or blocked.
9. **Phase 2 Readiness** — APIs and components ready for session management.

Do not claim successful execution of tests that were not actually run.

Do not start Phase 2.

**Phase 1 Focus: Reliable `.rdc` discovery, readiness validation, persistent capture identity, and deterministic latest-capture resolution.**
