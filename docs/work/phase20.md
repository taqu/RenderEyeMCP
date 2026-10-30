# Phase 20 — Reliability Hardening, Migration & Compatibility

## Objective

Complete the migration of RenderEyeMCP's MCP and IPC infrastructure from Python to Go by improving reliability, validating cross-platform compatibility, finalizing migration procedures, and establishing a responsible deprecation policy for the legacy Python infrastructure.

Phase 20 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 16 — IPC Protocol Contract & Compatibility Tests.
- Phase 17 — Go Shared IPC Service Migration.
- Phase 18 — Go MCP Bridge Migration.
- Phase 19 — Single Binary & Cross-Platform Distribution.

The intended architecture is:

```text
Claude Code ── Go MCP Bridge ──┐
                              │
Codex ─────── Go MCP Bridge ──┼── Go Shared IPC Service
                              │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension┘
```

The MCP Bridges and Shared IPC Service use the same Go executable, operating in different modes.

The Shared IPC Service remains an independent process.

The RenderDoc Extension continues using RenderDoc's Python API.

The primary objectives are:

1. Improve service and client lifecycle reliability.
2. Eliminate resource leaks, deadlocks, and stale state.
3. Strengthen multi-agent concurrency.
4. Validate correct behavior during capture and session changes.
5. Establish supported RenderDoc and platform compatibility.
6. Verify clean installation and upgrade procedures.
7. Finalize migration from the Python MCP infrastructure.
8. Establish a safe deprecation policy for legacy Python components.
9. Implement long-term regression testing and release quality gates.
10. Prepare the Go implementation to become the official default distribution.

**Phase 20 must focus on reliability, compatibility, and maintainability rather than adding new GPU debugging features.**

---

## 1. Audit the Current Implementation

Before making changes, inspect the actual repository and the outcomes of Phases 16–19.

Identify:

- Go MCP Bridge implementation.
- Go Shared IPC Service implementation.
- Unified executable entry point.
- Existing IPC protocol library.
- Python RenderDoc Extension.
- Legacy Python MCP Bridge.
- Legacy Python Shared IPC Service.
- Service autostart and discovery.
- Configuration loading.
- Session lifecycle management.
- Request routing.
- Replay operation coordination.
- Long-running GPU operations.
- Existing installation and release workflows.
- Current automated tests.
- Previous compatibility reports.
- Outstanding known issues.

Do not assume that every previous phase is fully implemented simply because a design document exists.

### 1.1 Establish an Implementation Status Matrix

Classify each capability as:

- Implemented and verified.
- Implemented but insufficiently tested.
- Partially implemented.
- Not implemented.
- Unsupported by the environment.
- Known defective.

Prioritize correcting reliability defects in implemented functionality.

### 1.2 Establish the Go Baseline

Verify that the unified Go executable supports:

```text
rendereye-mcp
rendereye-mcp service
rendereye-mcp version
```

Use the actual command names present in the repository.

Confirm that:

- Default mode starts the MCP stdio server.
- Service mode starts the independent IPC daemon.
- Multiple Bridges can share the daemon.
- The Python Extension connects without protocol changes.
- The default IPC endpoint remains compatible.
- Existing MCP Tool contracts remain intact.

### 1.3 Preserve the Architecture

Do not collapse all components into one long-running process.

Maintain:

- One MCP Bridge process per coding-agent connection.
- One shared IPC daemon per configured endpoint.
- RenderDoc Extension inside RenderDoc.
- Independent lifecycles and explicit ownership.

---

## 2. Define Reliability Invariants

Document the invariants that must always hold.

At minimum:

1. Only one Shared IPC Service owns a configured endpoint.
2. A Bridge never terminates a service used by another Bridge.
3. A response is delivered only to the originating request.
4. A request cannot silently switch to a different capture.
5. A disconnected RenderDoc session cannot receive new work.
6. No replay-dependent operation executes in an unsupported context.
7. Failed operations release their resources.
8. Client disconnects do not corrupt unrelated sessions.
9. MCP stdout contains only valid MCP protocol traffic.
10. Background processes cannot accumulate without bounds.
11. Existing capture files are never modified by inspection operations.
12. The service remains restricted to its intended local communication boundary.

Turn these invariants into automated tests wherever practical.

Do not rely exclusively on manual verification.

---

## 3. Shared IPC Service Lifecycle Hardening

Improve the reliability of the standalone Go daemon.

### 3.1 Service Discovery

Verify connection-first behavior.

When a Bridge starts:

1. Check for an existing service.
2. Verify that it is a compatible RenderEyeMCP service.
3. Reuse it when available.
4. Start a new service only when required.
5. Wait for readiness using bounded retries.
6. Connect and register safely.

Do not interpret every occupied TCP port as an existing RenderEyeMCP service.

### 3.2 Concurrent Startup

Test simultaneous launches from multiple coding agents.

The system must avoid:

- Duplicate service processes.
- Port-binding races.
- Repeated process spawning.
- Orphaned service candidates.
- Unbounded readiness retries.
- Accidental termination of a healthy service.

Preserve the service ownership strategy established in earlier phases.

### 3.3 Stale Ownership State

Investigate what happens when the daemon terminates unexpectedly.

Ensure stale locks, files, or process ownership records do not prevent future startup.

Do not remove a lock solely because its owner appears absent without following the established safe ownership procedure.

### 3.4 Service Restart

Test:

- Normal restart.
- Unexpected process termination.
- Restart while Bridges are connected.
- Restart while RenderDoc is connected.
- Restart during an outstanding request.
- Restart with multiple Bridges waiting to reconnect.

Do not claim that all operations survive a restart.

Outstanding operations may fail, but the failure must be explicit and bounded.

### 3.5 Idle Lifetime

Review the existing daemon idle and shutdown policy.

Determine whether it:

- Remains running until explicitly stopped.
- Exits after a bounded idle period.
- Uses another documented policy.

If unnecessary daemon persistence complicates installation or upgrades, evaluate a safe idle-shutdown policy.

Any change must preserve correct behavior when multiple agents are connected.

Do not terminate the daemon merely because one Bridge disconnects.

### 3.6 Graceful Shutdown

Verify that shutdown:

- Stops accepting new connections.
- Notifies or terminates pending operations appropriately.
- Closes network connections.
- Releases listeners.
- Cleans up temporary resources.
- Exits within a bounded period.

Avoid indefinite waits on disconnected clients.

---

## 4. MCP Bridge Lifecycle Hardening

The Go MCP Bridge is normally started and stopped by a coding agent.

### 4.1 Startup

Verify:

- Configuration loading.
- IPC Service discovery.
- Service autostart.
- MCP initialization.
- Tool registration.
- Correct error reporting.

Do not require RenderDoc to already be running unless the existing MCP contract explicitly requires it.

### 4.2 stdio Integrity

Ensure stdout is reserved exclusively for MCP messages.

Test startup, logging, subprocess spawning, panics, and shutdown for accidental stdout output.

### 4.3 Client Shutdown

When the coding agent closes its MCP connection:

- Stop Bridge-owned work.
- Close the IPC connection.
- Release resources.
- Exit normally.
- Leave the shared daemon and other agents unaffected.

### 4.4 Unexpected Client Termination

Verify cleanup when a client crashes or terminates without a normal MCP shutdown.

### 4.5 Long-Running Requests

Ensure that a disconnected Bridge does not retain:

- Blocked goroutines.
- Pending response channels.
- Unreleased timers.
- Stale request registrations.

Preserve backend job semantics.

### 4.6 Restart

A new Bridge process must be able to connect after the previous Bridge exits unexpectedly.

Do not rely on stale process-local state.

---

## 5. RenderDoc Extension Lifecycle

The Python Extension remains the integration point for RenderDoc APIs.

This phase must strengthen its interaction with the Go daemon without unnecessarily rewriting it.

### 5.1 RenderDoc Startup

Verify behavior when:

- The Shared IPC Service starts before RenderDoc.
- RenderDoc starts before the service.
- A coding agent starts before both.
- The Extension loads after a capture is already open.

### 5.2 Capture Lifecycle

Test:

- No capture loaded.
- Capture opened.
- Capture unloaded.
- Capture replaced.
- Capture reopened.
- Multiple captures across independent GUI sessions.
- RenderDoc process shutdown.

### 5.3 State Synchronization

Ensure the service does not retain misleading active-capture state after a disconnect.

On reconnection, synchronize the actual GUI state using the existing Phase 7 mechanism.

Do not invent capture state from stale cached information.

### 5.4 Extension Reload

Investigate how the Extension behaves when reloaded without restarting RenderDoc.

Avoid duplicate connections and lingering callbacks.

### 5.5 RenderDoc Shutdown

If RenderDoc terminates during an IPC operation, ensure pending requests fail cleanly.

Do not indefinitely wait for a response from a terminated GUI process.

### 5.6 Independent Sessions

Ensure one disconnected RenderDoc session does not invalidate unrelated healthy sessions.

---

## 6. Capture Identity and Stale State Protection

Incorrect capture association is a high-priority reliability risk.

### 6.1 Capture Generation

Review existing session and capture identity semantics.

Use the established identity model to distinguish:

- The same file reopened.
- A new capture loaded at the same path.
- A capture replaced within the same GUI.
- A new RenderDoc process.
- A reconnected Extension.

Do not use file paths alone as live capture identity.

### 6.2 Stale Requests

Test:

1. Agent requests information from capture A.
2. Capture A unloads.
3. Capture B loads.
4. The original request completes late.

The result must not be presented as data from capture B.

### 6.3 Stale Results

Preserve the distinction between:

- Current capture data.
- Historical measurement results.
- Completed shader debug traces.
- Invalidated live references.

Historical results may remain usable if explicitly associated with their original capture.

### 6.4 Explicit Event Targeting

Verify that explicit event queries remain attached to the intended capture and session.

Changing the GUI-selected event must not silently change an explicitly targeted request.

### 6.5 State Consistency Testing

Add deterministic tests for rapid capture and selection changes during concurrent requests.

---

## 7. Request Routing and Concurrency Safety

Verify all routing logic under realistic multi-agent workloads.

### 7.1 Request Correlation

Ensure request identifiers remain unique within the required scope.

Avoid collisions between different MCP Bridges.

### 7.2 Out-of-Order Responses

Where supported by the protocol, handle responses arriving out of order.

### 7.3 Late Responses

A late response after timeout or cancellation must not be delivered to a different request.

### 7.4 Slow Clients

A client that stops reading must not stall the entire daemon.

Use bounded queues or other appropriate flow control.

### 7.5 Cancellation

Cancellation must clean up Bridge and Service state.

Do not assume that cancellation can safely interrupt an active RenderDoc Replay API operation.

### 7.6 Locking

Review locking across:

- Client maps.
- Session maps.
- Request tables.
- Result caches.
- Replay operation coordination.
- Shutdown operations.

Avoid holding shared locks during blocking network I/O.

### 7.7 Deadlock Prevention

Add tests for simultaneous:

- Request completion and client disconnect.
- Service shutdown and response forwarding.
- Session removal and request dispatch.
- Capture unload and replay operation completion.
- Cancellation and timeout.

### 7.8 Race Detection

Run Go's race detector where supported.

Fix reported data races.

---

## 8. Replay-Dependent Operation Reliability

Some RenderEyeMCP operations perform additional GPU replay work.

Relevant operation categories may include:

- GPU performance counter collection.
- Post-VS geometry extraction.
- Pixel History.
- Shader Debugging.

Review only functionality actually implemented in the repository.

### 8.1 Replay Ownership

Determine where replay operation serialization and thread ownership are enforced.

Preserve the existing RenderDoc requirements.

### 8.2 Concurrent Operations

Verify that conflicting replay-dependent operations cannot execute unsafely against the same replay context.

Do not introduce a second independent scheduler that conflicts with the Extension's replay scheduling.

### 8.3 Timeouts

A timeout at the MCP level must not leave the backend permanently locked.

If the underlying RenderDoc API cannot be interrupted safely, allow it to finish while preventing new conflicting work from corrupting its state.

### 8.4 Cancellation

Document whether cancellation is:

- Immediate.
- Cooperative.
- Deferred until a supported safe point.
- Unsupported for a particular operation.

Do not claim immediate cancellation when it is not available.

### 8.5 Resource Cleanup

Verify cleanup of:

- Debugger resources.
- Replay outputs.
- Temporary buffers.
- GPU measurement jobs.
- Post-VS extraction state.
- Pending operation records.

### 8.6 GUI Non-Interference

Run tests to detect unexpected changes to:

- Loaded capture.
- Selected event.
- Current replay event.
- Texture Viewer.
- Mesh Viewer.
- Shader Debugger.

Document legitimate limitations rather than assuming every replay operation is invisible.

---

## 9. Memory, Resource, and Process Leak Testing

Long-running stability is a central Phase 20 objective.

### 9.1 Connection Churn

Repeatedly create and destroy MCP and IPC connections.

Verify cleanup of:

- Sockets.
- Goroutines.
- Request records.
- Session records.
- Timers.
- Channels.
- Buffers.

### 9.2 Large Payloads

Test representative:

- Texture images.
- Buffer reads.
- Shader disassembly.
- Geometry results.
- GPU measurement results.
- Debug traces.

Enforce existing size limits.

### 9.3 Slow Consumer Behavior

Test a client that consumes responses slowly or stops reading.

Avoid unbounded queues and memory growth.

### 9.4 Long-Running Test

Implement a bounded soak test that repeatedly performs common operations and disconnect/reconnect cycles.

Make the duration configurable.

Do not require long-running tests for every routine development build.

### 9.5 Metrics

Collect useful test observations such as:

- Active connection count.
- Pending request count.
- Goroutine count.
- Memory usage.
- Request failures.
- Unexpected service restarts.

Do not build a permanent telemetry backend merely for these tests.

### 9.6 Acceptance Thresholds

Define reproducible, environment-appropriate thresholds before evaluating the results.

Account for normal allocator caching and garbage collection.

Do not classify every temporary memory increase as a leak.

---

## 10. Network and Local Security Hardening

The Shared IPC Service uses local TCP communication.

### 10.1 Binding Scope

Verify that the service binds only to the intended loopback interface by default.

Do not expose the listener publicly.

### 10.2 Local Trust Boundary

Document the fact that loopback TCP does not automatically authenticate the connecting process.

Review what existing authorization or role validation is available.

### 10.3 Malformed Input

Test:

- Invalid frame lengths.
- Truncated payloads.
- Unknown operations.
- Invalid session references.
- Oversized messages.
- Unexpected message sequences.
- Unsupported client roles.

Malformed input must not destabilize unrelated sessions.

### 10.4 Resource Exhaustion

Enforce bounded:

- Incoming message size.
- Outgoing queues.
- Pending requests.
- Connections.
- Cached results.
- Operation jobs.

### 10.5 Compatibility Constraints

Avoid introducing a protocol-breaking authentication mechanism during Phase 20 without an explicit compatibility plan.

If a security issue requires a breaking protocol change, document the threat, migration requirement, and affected clients before implementation.

### 10.6 Logging

Do not log full capture payloads, shader traces, or other potentially proprietary data by default.

---

## 11. RenderDoc Version Compatibility

Establish a practical compatibility policy for RenderDoc versions.

### 11.1 Supported Versions

Inspect which RenderDoc API versions the Extension actually supports.

Do not assume support for every RenderDoc release.

### 11.2 Capability Detection

Prefer detecting actual API and replay capabilities rather than relying exclusively on version-number checks.

### 11.3 API Differences

Investigate compatibility-sensitive areas such as:

- Extension initialization.
- ReplayController API access.
- Pipeline state.
- Resource inspection.
- GPU counters.
- Post-VS extraction.
- Pixel History.
- Shader debugging.

Only include implemented features.

### 11.4 Unsupported Features

Expose unsupported capabilities clearly through existing MCP error or capability mechanisms.

Do not silently substitute invented values.

### 11.5 Compatibility Matrix

Maintain a test matrix of:

- RenderDoc version.
- Operating system.
- Graphics API.
- Extension load status.
- Basic MCP integration.
- Advanced inspection capabilities.

### 11.6 Update Policy

Document how future RenderDoc releases will be evaluated.

Do not require redesigning the Go Bridge whenever the RenderDoc Python API changes.

Keep RenderDoc-specific adaptation inside the Extension where possible.

---

## 12. Cross-Platform Reliability

Phase 19 introduced native cross-platform distribution.

Phase 20 must establish actual support levels.

### 12.1 Windows

Windows remains the primary supported environment.

Validate:

- Clean installation.
- Service autostart.
- Multiple MCP Bridges.
- RenderDoc Extension loading.
- Capture inspection.
- Upgrade and rollback.
- Process cleanup.

Include installation paths containing spaces and Unicode characters.

### 12.2 Linux

Where RenderDoc is supported, validate:

- Native executable startup.
- IPC communication.
- Service lifecycle.
- Extension installation.
- Capture detection.
- Basic and advanced operations as available.

Do not claim complete Linux support based on successful cross-compilation.

### 12.3 macOS

Evaluate the Go Bridge and Service independently from RenderDoc integration.

Report distinct statuses for:

- Compilation.
- Native execution.
- MCP functionality.
- IPC functionality.
- RenderDoc Extension availability.
- Full capture inspection.

Do not claim full RenderEyeMCP support on a platform where the required RenderDoc environment is unavailable.

### 12.4 Platform-Specific Process Behavior

Review:

- Windows process creation and Job Object behavior.
- POSIX signal handling.
- Process detachment.
- Child-process cleanup.
- File permissions.
- Executable path resolution.
- Service ownership.

Do not assume identical behavior across operating systems.

### 12.5 Minimum Supported Platforms

Document the verified OS and architecture combinations.

Unsupported or unverified combinations must be labeled accurately.

---

## 13. Configuration and Installation Reliability

Validate installation and configuration as user-facing product features.

### 13.1 Configuration Sources

Preserve existing configuration behavior, including the relevant environment-file conventions.

Verify:

- Explicit configuration path.
- Process environment variables.
- `.env` loading.
- Built-in defaults.
- Command-line options.

### 13.2 Configuration Precedence

Document the actual precedence and test it.

Do not silently change established behavior.

### 13.3 Paths

Test:

- Default installation directories.
- Custom installation directories.
- Paths containing spaces.
- Unicode paths.
- Read-only installation directories.

### 13.4 Reinstallation

Running the installer again should not corrupt a functioning installation.

### 13.5 Upgrade

An upgrade must preserve user-managed configuration.

### 13.6 Uninstall

Uninstallation must not delete unrelated RenderDoc files, captures, or coding-agent configuration.

### 13.7 Diagnostics

Improve existing setup diagnostics for:

- Missing RenderDoc installation.
- Missing Extension.
- Invalid configuration.
- Service unavailable.
- Port conflict.
- Version mismatch.
- Unsupported platform.

Reuse any existing `doctor` or diagnostic command.

Do not create a large diagnostic framework unnecessarily.

---

## 14. Python-to-Go Migration Completion

Establish a supported migration path for existing users.

### 14.1 Identify Legacy Components

The potential deprecation targets are:

- Python MCP Bridge.
- Python Shared IPC Service.
- Python-only startup and packaging infrastructure associated with those components.

**The RenderDoc Python Extension is not a deprecation target.**

### 14.2 Inventory Existing Installations

Investigate common installations using:

- `pip`.
- `uv`.
- Virtual environments.
- Existing Python executable entry points.
- Old service processes.
- Existing MCP configurations.

### 14.3 Migration Procedure

Document how users:

1. Obtain the Go release.
2. Stop the legacy Shared IPC Service safely.
3. Install the Go executable.
4. Update the RenderDoc Extension if necessary.
5. Update coding-agent MCP configurations.
6. Verify successful operation.
7. Confirm only one Shared IPC Service owns the endpoint.

Do not automatically terminate an arbitrary process based only on its TCP port.

### 14.4 Configuration Migration

Preserve:

- Custom RenderDoc paths.
- IPC endpoint configuration.
- Logging configuration.
- Existing environment-file settings.
- Other relevant user-managed preferences.

### 14.5 Parallel Installation

Python and Go distributions may coexist on disk during migration.

They must not independently run competing Shared IPC Services on the same endpoint.

### 14.6 Rollback

Provide a documented rollback procedure.

A user must be able to return to the Python implementation if a serious Go regression is discovered during the supported migration period.

### 14.7 No Forced Deletion

Do not delete Python installations or virtual environments automatically.

### 14.8 Migration Validation

Test migration using an installation that resembles a real existing Python deployment, not only a clean Go installation.

---

## 15. Legacy Python Deprecation Policy

Decide whether and when to deprecate the Python MCP infrastructure.

Do not equate successful Go compilation with sufficient evidence for deprecation.

### 15.1 Deprecation Stages

Use a controlled progression.

**Stage A — Parallel Support**

Both Python and Go implementations remain available.

The Go version is recommended for testing.

**Stage B — Go as Default**

The Go distribution becomes the recommended installation after its release gates pass.

The Python infrastructure remains available for rollback and compatibility.

**Stage C — Python Deprecated**

The Python MCP Bridge and Shared IPC Service are explicitly marked deprecated.

New features are implemented in Go by default.

Critical compatibility and security fixes may continue during a defined transition period.

**Stage D — Python Removal**

Removal may be considered in a future release after evaluating compatibility, adoption, and maintenance costs.

Do not automatically proceed to Stage D during Phase 20.

### 15.2 Deprecation Decision Criteria

Require evidence that:

- Go MCP functionality is equivalent.
- IPC compatibility tests pass.
- Multi-agent operation is stable.
- Clean installation works.
- Upgrades work.
- Major RenderDoc workflows are validated.
- Supported platforms meet their documented quality level.
- No critical migration blocker remains.
- Rollback documentation exists.

### 15.3 PyPI and TestPyPI

Preserve the previously established separate publishing workflows:

```text
.github/workflows/publish-testpypi.yml
.github/workflows/publish-pypi.yml
```

Do not merge these workflows.

Review whether the Python package should:

- Remain supported temporarily.
- Become a clearly documented legacy distribution.
- Stop receiving new feature releases.
- Eventually be retired through a separate maintenance decision.

Do not silently repurpose an existing PyPI package into an incompatible installer.

Do not publish a new production package or release without explicit authorization.

### 15.4 Communication

Document:

- Recommended installation method.
- Legacy support status.
- Migration procedure.
- Rollback procedure.
- Known limitations.
- Future maintenance expectations.

Avoid promising an unsupported end-of-support date.

### 15.5 RenderDoc Extension

Continue maintaining the Python Extension independently of the legacy Python MCP infrastructure.

The Extension is still required by the Go-based architecture.

---

## 16. Regression Test Strategy

Create a sustainable test strategy for long-term maintenance.

### 16.1 Unit Tests

Cover:

- Configuration.
- IPC framing and serialization.
- Session management.
- Request routing.
- Error handling.
- Timeouts.
- Cancellation.
- Process lifecycle.
- Resource cleanup.

### 16.2 Protocol Compatibility

Reuse Phase 16 Golden Fixtures.

Prevent unintended changes to:

- Message framing.
- Request and response envelopes.
- Error formats.
- Session and capture identities.
- Binary payloads.

### 16.3 MCP Compatibility

Reuse Phase 18 MCP contract snapshots.

Verify:

- Tool names.
- Descriptions.
- Input schemas.
- Output formats.
- Error semantics.
- Content types.

### 16.4 End-to-End Scenarios

Maintain representative scenarios for implemented features:

- Active capture discovery.
- Draw call inspection.
- Pipeline state inspection.
- Resource and shader inspection.
- Texture and pixel inspection.
- GPU performance analysis.
- Geometry inspection.
- Pixel History and Shader Debugging.

Only include capabilities that actually exist.

### 16.5 Real Capture Fixtures

Where licensing and confidentiality permit, maintain small reproducible test captures.

Avoid including proprietary game assets in public test fixtures.

### 16.6 Multi-Agent Regression

Test at least two independent MCP clients sharing one daemon.

### 16.7 Failure Injection

Test:

- Service crash.
- Bridge crash.
- Extension disconnect.
- Capture unload.
- Request timeout.
- Malformed IPC input.
- Slow client.
- Concurrent startup.

### 16.8 Test Layering

Separate:

- Fast deterministic tests.
- IPC and MCP integration tests.
- Platform-specific tests.
- Real RenderDoc GUI tests.
- Extended soak tests.

Keep routine CI reasonably fast.

---

## 17. Continuous Integration and Release Quality Gates

Improve the existing CI without creating an unnecessarily complex release system.

### 17.1 Pull Request Checks

Run:

- Go unit tests.
- Protocol compatibility tests.
- MCP contract tests.
- Static analysis.
- Formatting checks.
- Build verification.
- Race detection where practical.

### 17.2 Platform Matrix

Run supported tests on:

- Windows.
- Linux.
- macOS for the components that can operate there.

Do not treat a platform-specific test skip as a pass.

### 17.3 Release Candidate Validation

Before an official release, verify:

1. Version metadata.
2. Release archive contents.
3. Executable startup.
4. Service mode.
5. MCP mode.
6. Extension packaging.
7. Installation and upgrade.
8. Supported-platform behavior.
9. Multi-agent operation.
10. Known compatibility limitations.

### 17.4 Artifact Integrity

Preserve release checksums and other existing artifact validation.

### 17.5 Publishing Isolation

Keep GitHub Releases and Python package publication independently controlled.

Do not accidentally trigger PyPI publication from an unrelated Go release-validation job.

### 17.6 Production Release Authorization

Do not publish a production release automatically as part of Phase 20 implementation or validation without explicit authorization.

### 17.7 Release Gate Report

Generate a concise report with:

- Required tests passed.
- Required tests failed.
- Tests not executed.
- Supported platforms.
- Known critical issues.
- Release recommendation.

Use actual test evidence.

---

## 18. Observability and Diagnostics

Provide enough diagnostics to investigate operational failures.

### 18.1 Structured Logging

Ensure logs identify:

- Component and mode.
- Service startup and shutdown.
- Client connection and disconnection.
- Session registration.
- Capture state changes.
- Request correlation where appropriate.
- Timeouts and routing failures.

### 18.2 Process Identity

Record useful process and service identifiers in diagnostics.

Do not use process IDs as globally stable session identifiers.

### 18.3 Health Checks

Reuse existing protocol health mechanisms.

If a diagnostic command exists, ensure it can distinguish:

- Service not running.
- Incompatible listener.
- Service running but no RenderDoc connected.
- Extension connected but no capture loaded.
- Capture available.
- Incompatible or unsupported capability.

### 18.4 No Mandatory Telemetry

Do not introduce cloud telemetry or mandatory external services.

### 18.5 Privacy

Do not transmit capture contents, shaders, or resource data to external services from RenderEyeMCP itself.

Existing coding-agent data handling remains outside this IPC infrastructure task.

### 18.6 Diagnostic Usability

Prefer actionable errors rather than large unstructured stack traces.

Keep detailed stack traces available in developer logs where appropriate.

---

## 19. Documentation

Update English and Japanese documentation.

### 19.1 User Documentation

Cover:

- Recommended Go installation.
- Supported operating systems.
- RenderDoc requirements.
- Extension installation.
- Claude Code setup.
- Codex setup.
- Multi-agent behavior.
- Upgrading.
- Troubleshooting.
- Python-to-Go migration.
- Rollback.

### 19.2 Developer Documentation

Cover:

- Go Bridge architecture.
- Shared IPC Service lifecycle.
- Protocol contract.
- MCP contract tests.
- Replay coordination.
- Cross-platform considerations.
- Debugging and diagnostics.
- Release validation procedures.

### 19.3 Compatibility Matrix

Provide an accurate matrix of tested RenderDoc versions and operating systems.

Distinguish compiled, runtime-tested, and fully integrated environments.

### 19.4 Deprecation Documentation

Clearly identify which Python components are deprecated or remain supported.

Do not label the RenderDoc Python Extension as deprecated merely because the MCP infrastructure moved to Go.

### 19.5 Known Issues

Maintain an explicit list of known reliability and compatibility limitations.

Do not hide unsupported combinations behind generic statements such as "cross-platform support."

### 19.6 Documentation Consistency

Ensure English and Japanese instructions describe the same actual behavior.

---

## 20. Implementation Order

Perform the work incrementally.

### Step 1 — Baseline Audit

Review the existing Go implementation and outstanding Phase 16–19 issues.

### Step 2 — Reliability Invariants

Define critical operational invariants and corresponding tests.

### Step 3 — Lifecycle Hardening

Fix service startup, shutdown, disconnection, and restart issues.

### Step 4 — Session and Capture Safety

Fix stale identity and routing problems.

### Step 5 — Multi-Agent Concurrency

Run simultaneous-client tests and eliminate deadlocks or races.

### Step 6 — Replay Safety

Verify coordination of implemented replay-dependent operations.

### Step 7 — Resource Stability

Run bounded stress and leak tests.

### Step 8 — Platform Validation

Test native behavior on supported operating systems.

### Step 9 — RenderDoc Compatibility

Establish the supported RenderDoc version and capability matrix.

### Step 10 — Migration Validation

Test real Python-to-Go installation upgrades and rollback.

### Step 11 — CI and Release Gates

Integrate deterministic and release-candidate tests.

### Step 12 — Documentation

Finalize bilingual user and developer documentation.

### Step 13 — Deprecation Assessment

Determine whether Go can become the recommended default and whether Python can be marked deprecated.

### Step 14 — Final Report

Produce an evidence-based readiness assessment.

Do not remove the legacy Python implementation merely to simplify the repository before completing the migration assessment.

---

## 21. Out of Scope

Do not implement:

- New RenderDoc debugging APIs.
- New GPU profiling capabilities.
- A new Shader Debugger.
- A new Mesh Viewer.
- A replacement for RenderDoc's ReplayController.
- A new IPC transport.
- An unrelated protocol redesign.
- Mandatory Windows Services, systemd, or launchd integration.
- Mandatory cloud services.
- Automatic background updates.
- A new general-purpose process supervisor.
- A new coding-agent orchestration framework.
- Automatic deletion of Python installations.
- Immediate removal of legacy Python source code.
- New production package publication without authorization.

Focus on improving the reliability of the existing architecture.

---

## 22. Acceptance Criteria

Phase 20 is complete when:

- [ ] Existing Phase 16–19 functionality is audited.
- [ ] Critical reliability invariants are documented.
- [ ] Service startup behavior is validated.
- [ ] Concurrent startup creates only one service.
- [ ] Existing services are safely reused.
- [ ] Unknown processes occupying the IPC endpoint are handled safely.
- [ ] Bridge shutdown does not terminate other Bridges.
- [ ] Service shutdown releases resources.
- [ ] Service crash and restart behavior is tested.
- [ ] MCP client disconnection is handled.
- [ ] RenderDoc Extension disconnection is handled.
- [ ] Capture unload and replacement are handled.
- [ ] Stale capture references cannot be misattributed.
- [ ] Request correlation remains correct under concurrency.
- [ ] Late responses cannot be delivered to unrelated requests.
- [ ] Timeouts release pending state.
- [ ] Cancellation follows safe backend semantics.
- [ ] Replay-dependent operations are coordinated correctly.
- [ ] Resource cleanup is verified.
- [ ] No known critical goroutine or socket leaks remain.
- [ ] Go race detection passes on supported test environments.
- [ ] Multi-agent stress tests pass.
- [ ] Large payload handling remains bounded.
- [ ] Malformed IPC traffic does not crash the daemon.
- [ ] The service remains restricted to the intended local interface.
- [ ] Supported RenderDoc versions are documented.
- [ ] Unsupported RenderDoc capabilities are reported accurately.
- [ ] Windows clean installation and integration are validated.
- [ ] Linux support is validated to its documented level.
- [ ] macOS support limitations are documented accurately.
- [ ] Upgrade and reinstall behavior is tested.
- [ ] Python-to-Go migration is documented and tested.
- [ ] Rollback remains possible during the supported migration period.
- [ ] Phase 16 IPC compatibility tests remain passing.
- [ ] Phase 18 MCP contract tests remain passing.
- [ ] Real RenderDoc capture inspection remains functional.
- [ ] Representative advanced workflows are validated where implemented.
- [ ] CI includes appropriate reliability and compatibility checks.
- [ ] Release quality gates are documented.
- [ ] English documentation is updated.
- [ ] Japanese documentation is updated.
- [ ] A Python deprecation decision is documented.
- [ ] The RenderDoc Python Extension remains supported.
- [ ] No production release is published without explicit authorization.

Do not mark criteria as passed without execution evidence.

Where a platform or capability cannot be tested, report it as unverified.

---

## 23. Deliverables

### A. Reliability Improvements

Provide:

- Service lifecycle fixes.
- MCP Bridge lifecycle fixes.
- Session and capture safety fixes.
- Request routing and concurrency improvements.
- Replay coordination fixes where necessary.
- Resource leak fixes.
- Improved diagnostics.

### B. Automated Tests

Provide:

- IPC protocol regression tests.
- MCP contract regression tests.
- Service lifecycle tests.
- Multi-agent concurrency tests.
- Failure-injection tests.
- Resource cleanup tests.
- Platform-specific tests.
- End-to-end RenderDoc tests where possible.

### C. Compatibility Report

Provide:

- Supported operating systems.
- Supported architectures.
- Tested RenderDoc versions.
- Graphics API coverage.
- Supported MCP clients.
- Known limitations.
- Unverified combinations.

### D. Migration Report

Provide:

- Python-to-Go migration procedure.
- Configuration preservation rules.
- Upgrade test results.
- Rollback instructions.
- Remaining Python dependencies.
- Legacy infrastructure deprecation recommendation.

### E. Documentation

Provide:

- English installation and migration documentation.
- Japanese installation and migration documentation.
- Troubleshooting updates.
- Developer reliability notes.
- Release checklist.
- Compatibility matrix.

### F. Final Readiness Assessment

Classify the Go implementation as one of:

**Ready for Default Distribution**

Core compatibility, installation, and reliability requirements have been validated.

**Ready with Documented Limitations**

The implementation is usable, but noncritical limitations remain and are clearly identified.

**Not Ready**

Critical defects, missing compatibility, or insufficient mandatory validation prevent default adoption.

Include concrete evidence supporting the classification.

---

## 24. Final Goal

After Phase 20, RenderEyeMCP should provide a reliable native installation that allows developers to use multiple coding agents against the same RenderDoc GUI without managing a separate Python environment.

The target architecture remains:

```text
Claude Code ── rendereye-mcp ──┐
                               │
Codex ─────── rendereye-mcp ──┼── rendereye-mcp service
                               │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

The system should:

1. Start reliably.
2. Reuse the existing shared daemon.
3. Recover predictably from disconnects and service failures.
4. Preserve capture and session identity.
5. Coordinate replay-dependent operations safely.
6. Handle multiple agents concurrently.
7. Run without user-managed Python, uv, pip, or Go tooling.
8. Support documented operating systems and RenderDoc versions.
9. Provide simple installation, upgrade, and rollback procedures.
10. Maintain automated compatibility and regression tests.

The Python MCP Bridge and Python Shared IPC Service may be deprecated once the Go implementation meets the documented readiness criteria.

Do not remove them automatically.

The RenderDoc Python Extension remains an essential supported component.

**Phase 20 is successful when the Go implementation is demonstrably reliable enough to become RenderEyeMCP's recommended default, with a clear compatibility policy and a safe transition path for existing users.**
