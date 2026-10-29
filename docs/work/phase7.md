# Phase 7 — RenderDoc GUI State Discovery & Synchronization

## Objective

Implement reliable, read-only discovery and synchronization of the current RenderDoc GUI state, particularly the capture currently loaded in each RenderDoc instance.

RenderEyeMCP must support workflows where captures are opened externally, without any involvement from an AI coding agent.

Typical examples include:

- Unity opens a captured frame in RenderDoc.
- Unreal Engine launches RenderDoc and loads a capture.
- A developer manually opens an `.rdc` file through the RenderDoc GUI.
- A developer switches between captures while an AI agent is connected.
- Multiple RenderDoc GUI instances are running simultaneously.
- Multiple AI agents query the same RenderDoc state.

**The primary goal is to let AI agents observe and understand an existing RenderDoc session without requiring the agent to open or manage the capture itself.**

This phase builds on the existing Phase 6 Shared IPC Service architecture.

Do not redesign or replace the Phase 6 implementation unless a concrete limitation makes a small, targeted change necessary.

---

## 1. Initial Repository Investigation

Before making implementation changes, inspect the existing repository and identify:

1. The RenderDoc extension implementation.
2. The existing RenderDoc Extension API integration.
3. The Shared IPC Service introduced in Phase 6.
4. Session registration, discovery, and lifecycle management.
5. Existing MCP tools for querying RenderDoc information.
6. Existing capture identification and management mechanisms.
7. Existing event, callback, polling, or notification infrastructure.
8. Existing tests involving multiple RenderDoc processes or MCP clients.

Document the relevant components and their responsibilities.

Prefer extending existing abstractions rather than introducing parallel implementations.

Avoid creating duplicate MCP tools when existing tools can be extended without breaking their contracts.

Preserve compatibility with the current installation, startup, and configuration mechanisms.

## 2. Investigate RenderDoc Extension API Capabilities

Determine how the installed RenderDoc extension can access the state of its hosting GUI instance.

Investigate whether the available RenderDoc APIs expose:

- Whether a capture is currently loaded.
- The path of the loaded `.rdc` file.
- Capture load and unload transitions.
- Changes to the currently loaded capture.
- Capture loading or failure states.
- Relevant capture metadata.
- An identifier for the hosting RenderDoc GUI process.
- Notifications or callbacks for GUI state changes.

Inspect the actual RenderDoc API definitions, headers, extension interfaces, and existing integration code.

Do not assume that a particular API or callback exists.

If the installed RenderDoc version does not provide a direct capability, investigate supported alternatives.

Prefer the following approaches, in order:

1. Official RenderDoc Extension APIs and callbacks.
2. Existing RenderEyeMCP extension functionality.
3. Safe, lightweight state polling through supported APIs.
4. Other documented, version-compatible mechanisms.

Avoid:

- Reading RenderDoc process memory.
- GUI automation based on window titles.
- Depending on undocumented internal implementation details.
- Inferring the loaded capture solely from recently accessed files.
- Treating the last capture opened by an MCP tool as the currently loaded capture.

Record API limitations and version-specific behavior.

If a desired state cannot be observed reliably, represent it as unknown rather than fabricating a value.

## 3. Define the GUI State Model

Introduce or extend a state model that represents the observable state of each RenderDoc GUI instance.

The state model should distinguish at least two independent concepts.

### 3.1 GUI Connection State

Examples:

- Connected
- Disconnected
- Unresponsive
- Unknown

This state describes communication with the RenderDoc GUI extension.

### 3.2 Capture State

Examples:

- No capture loaded
- Loading
- Loaded
- Unloading
- Failed
- Unknown

Use only states that can be reliably determined using the available RenderDoc APIs.

Do not introduce artificial distinctions that cannot actually be observed.

A connected RenderDoc GUI does not necessarily have a loaded capture.

Similarly, a temporarily disconnected GUI must not automatically be interpreted as having unloaded its capture.

### 3.3 Suggested State Information

The state representation should support the following information where available:

```json
{
  "session_id": "renderdoc-session-1234",
  "process_id": 1234,
  "connection_state": "connected",
  "capture": {
    "state": "loaded",
    "path": "D:/Captures/frame_001.rdc"
  },
  "state_version": 42
}
```

This is a conceptual example, not a mandatory schema.

Adapt the actual representation to existing RenderEyeMCP models and naming conventions.

Additional capture metadata may be included if it is available and useful.

Do not add redundant or speculative metadata.

A session identifier must remain stable for the lifetime of its corresponding GUI session, without assuming that a process ID alone is globally unique across time.

## 4. Discover Captures Opened Outside RenderEyeMCP

Implement detection of captures opened by external applications or direct user interaction.

The implementation must not depend on an MCP-initiated capture-open operation.

Required workflows include:

### Scenario A — Capture Already Loaded

1. A developer opens a capture from Unity or Unreal Engine.
2. RenderDoc loads the capture.
3. The RenderDoc extension observes its current state.
4. An MCP client connects or requests the current state.
5. The agent receives the actual loaded capture information.

No additional capture-open operation should be required.

### Scenario B — Capture Changed Manually

1. A RenderDoc GUI currently has Capture A loaded.
2. The developer opens Capture B using the GUI.
3. RenderEyeMCP detects the state change.
4. Subsequent MCP queries return Capture B.

The system must not continue reporting Capture A as the current capture.

### Scenario C — Capture Closed

1. A RenderDoc GUI has a capture loaded.
2. The developer closes the capture.
3. RenderEyeMCP observes the transition.
4. MCP queries report that no capture is loaded.

Do not return a stale capture path as an active capture.

### Scenario D — Extension Connects After Capture Load

1. RenderDoc loads a capture before the extension establishes its IPC connection.
2. The extension connects to the Shared IPC Service.
3. The current state is discovered through a snapshot.
4. The Shared IPC Service receives the actual current state.

State discovery must not require observing the original capture-load event.

## 5. State Snapshot and Change Notifications

Implement a synchronization strategy using snapshots and change notifications where supported.

### 5.1 State Snapshots

The RenderDoc extension should be able to provide a snapshot of its current observable GUI state.

Snapshots should be available:

- When the extension connects to the Shared IPC Service.
- When IPC reconnects after an interruption.
- When an MCP request explicitly needs current state.
- When synchronization detects a possible inconsistency.

A snapshot must describe the actual GUI state at the time it is collected.

The Shared IPC Service must not infer the current capture solely from previous MCP operations.

### 5.2 State Change Notifications

If RenderDoc exposes reliable state-change callbacks, use them to notify the Shared IPC Service.

Potential events include:

- Capture load started.
- Capture loaded.
- Capture unloaded.
- Capture changed.
- Capture load failed.

Only implement events supported by reliable observations.

If callbacks are unavailable or insufficient, introduce lightweight polling.

Polling must:

- Avoid unnecessary work.
- Avoid interfering with RenderDoc GUI responsiveness.
- Avoid expensive capture processing.
- Avoid excessive IPC traffic.
- Be configurable only where there is a concrete operational need.

Do not build a complex event framework merely for this phase.

### 5.3 Synchronization Correctness

Ensure that:

- A new snapshot cannot be overwritten by an older event.
- Duplicate notifications are harmless.
- Reconnection can restore the latest observable state.
- Delayed messages from an obsolete connection cannot corrupt a new session.
- Invalid state transitions are handled safely.

Use a monotonically increasing state version or another appropriate ordering mechanism where necessary.

If ordering cannot be established across a reconnection, obtain a fresh snapshot instead of relying on old event sequences.

Avoid holding global locks while making blocking calls into RenderDoc or IPC.

## 6. Integrate with the Phase 6 Shared IPC Service

Extend the existing Shared IPC Service to expose synchronized GUI state.

Preserve the Phase 6 architecture and its multi-agent behavior.

The Shared IPC Service should be able to:

1. Identify registered RenderDoc GUI instances.
2. Associate reported state with the correct GUI session.
3. Store the latest known state for each session.
4. Distinguish connected and disconnected sessions.
5. Provide state snapshots to MCP clients.
6. Reject or ignore obsolete updates.
7. Recover state following IPC reconnection.

The RenderDoc GUI extension remains the authoritative source of observable GUI state.

The Shared IPC Service may maintain a cached state representation, but that cache must not become an independent source of truth.

### 6.1 Avoid Stale State

Handle:

- RenderDoc process termination.
- Extension disconnection.
- IPC service restart.
- Extension reconnection.
- GUI crashes.
- Process ID reuse.

Do not report a cached capture as definitely loaded when the corresponding GUI session is disconnected.

If a cached state is retained for diagnostics, expose it explicitly as stale or last-known state.

Prefer a clear unknown/disconnected result over false certainty.

### 6.2 Multiple RenderDoc Instances

Each RenderDoc GUI instance must maintain independent state.

Example:

```text
RenderDoc Instance A
  Capture: frame_001.rdc

RenderDoc Instance B
  Capture: frame_002.rdc

RenderDoc Instance C
  Capture: none
```

Queries targeting Instance A must not accidentally return information from Instance B.

Do not introduce a process-wide global `current_capture` value that ignores session identity.

## 7. MCP Tool Integration

Expose the observable GUI state through the existing MCP interface.

First inspect the current tools and reuse or extend them wherever appropriate.

Suggested capabilities:

### 7.1 List RenderDoc Sessions

Return the known RenderDoc GUI sessions and their connection/capture state.

Suggested tool name, if a suitable tool does not already exist:

`list_renderdoc_sessions`

The result should allow an agent to distinguish:

- A connected GUI with a loaded capture.
- A connected GUI without a loaded capture.
- A disconnected or otherwise unavailable GUI.

### 7.2 Get Session State

Return the state for a specific RenderDoc GUI session.

Suggested tool name:

`get_renderdoc_session_state`

Use the existing session identifier format.

If a session is unavailable, return a meaningful structured result rather than treating the absence of a capture as an IPC failure.

### 7.3 Get Current Capture

Provide a convenient way to determine which capture is currently loaded.

Suggested tool name:

`get_current_capture`

If the user or agent has explicitly selected a GUI session, preserve that selection.

If there is exactly one eligible RenderDoc GUI session, it may be selected automatically.

If multiple eligible sessions exist and the target is ambiguous, return the available sessions rather than silently selecting an arbitrary instance.

Do not equate "most recently registered" with "currently active" unless there is a reliable mechanism and an explicitly defined policy supporting that behavior.

### 7.4 Error and Empty-State Semantics

Distinguish:

- No RenderDoc GUI instances found.
- RenderDoc GUI connected, but no capture loaded.
- Capture currently loading.
- Target GUI session not found.
- Target GUI session disconnected.
- GUI state temporarily unavailable.
- Multiple possible target sessions.

Avoid presenting normal empty states as tool execution failures.

Keep responses concise and suitable for AI coding agents.

Preserve existing MCP response schemas wherever practical.

## 8. Preserve Multi-Agent Compatibility

Phase 6 established support for multiple independent MCP processes using the Shared IPC Service.

This functionality must remain intact.

Verify the following configuration:

```text
Claude Code ── MCP Process A ──┐
                               │
                               ├── Shared IPC Service
                               │           │
Codex ─────── MCP Process B ──┘           │
                                           │
                                    RenderDoc GUI
```

Both agents should observe the same authoritative GUI state.

Required behavior:

- Both agents can query concurrently.
- Neither agent needs to own the RenderDoc session.
- A state query does not modify the GUI.
- A capture change is visible to both agents.
- One MCP client disconnecting does not invalidate the other's session.
- State synchronization does not reintroduce the fixed IPC port conflict resolved in Phase 6.

Avoid implementing separate RenderDoc GUI state caches inside individual MCP processes unless they have explicit invalidation and synchronization semantics.

Prefer the existing shared infrastructure.

## 9. Threading and Performance

RenderDoc GUI operations may have thread-affinity or lifecycle constraints.

Investigate the relevant API requirements before introducing callbacks, background threads, or polling.

Requirements:

- Access RenderDoc state only from permitted execution contexts.
- Do not block the RenderDoc GUI thread on slow MCP operations.
- Avoid deadlocks between extension callbacks and IPC processing.
- Keep state snapshots lightweight.
- Avoid unnecessary render pipeline inspection.
- Make state reads safe when captures are being loaded or unloaded.

Do not introduce a high-frequency polling loop without a demonstrated need.

State synchronization should remain inexpensive even while multiple coding agents are connected.

## 10. Testing

Add automated tests where practical and document manual integration tests where RenderDoc GUI interaction is required.

### 10.1 Unit Tests

Cover:

- State model initialization.
- Capture loaded/unloaded transitions.
- Session identity handling.
- Duplicate state updates.
- Out-of-order state updates.
- Connection loss.
- Reconnection.
- Stale cache detection.
- Multiple session isolation.
- Unknown and unavailable state handling.

### 10.2 Integration Tests

Verify:

1. The RenderDoc extension registers with the Shared IPC Service.
2. A state snapshot is obtained on initial connection.
3. An already-loaded capture is detected.
4. Capture changes are reflected in MCP responses.
5. Capture closure is reflected in MCP responses.
6. IPC reconnection restores current state.
7. Multiple MCP clients receive consistent results.

### 10.3 Manual GUI Tests

Perform or document the following tests:

| Test | Expected result |
|---|---|
| Launch RenderDoc without a capture | Connected, no capture |
| Open `.rdc` manually | Loaded capture detected |
| Open Capture A, then Capture B | Current capture changes to B |
| Close the current capture | No capture loaded |
| Open capture from Unity | External capture recognized |
| Open capture from Unreal Engine | External capture recognized |
| Connect MCP after capture is loaded | Correct snapshot returned |
| Restart MCP process | Current GUI state remains discoverable |
| Restart Shared IPC Service | State recovers after reconnection |
| Open two RenderDoc instances | Independent capture states |
| Query using Claude Code and Codex | Consistent state across agents |

If Unity or Unreal Engine is not available in the test environment, document those tests as unverified.

Do not claim successful testing without actual execution.

### 10.4 Regression Tests

Ensure the following still work:

- Existing RenderDoc information retrieval.
- Existing IPC communication.
- Existing capture/session operations.
- Phase 6 multi-agent behavior.
- RenderDoc extension startup and shutdown.
- MCP server startup and shutdown.

## 11. Documentation

Update the relevant documentation to explain the new capability.

Include:

- How RenderEyeMCP discovers an already-open capture.
- How state is synchronized.
- How to query the currently loaded capture.
- How multiple RenderDoc GUI instances are represented.
- What happens when no capture is loaded.
- What happens when a GUI disconnects.
- Any RenderDoc API limitations.

Add a short example workflow:

```text
1. Open a Unity project.
2. Capture a frame using Unity's RenderDoc integration.
3. Open the capture in RenderDoc.
4. Ask an AI agent:

   "Which capture is currently loaded in RenderDoc?"

5. The agent queries RenderEyeMCP.
6. RenderEyeMCP returns the actual loaded capture.
```

The workflow should not require an MCP capture-open operation.

Document any configuration changes, but avoid adding mandatory configuration unless necessary.

## 12. Out of Scope

Do not implement the following as part of Phase 7:

- Automatic capture opening.
- Automatic capture closing.
- Automatic RenderDoc window switching.
- GUI focus manipulation.
- GUI automation.
- Capture ownership or locking by agents.
- New rendering analysis features.
- Changes to draw-call inspection functionality.
- A major IPC architecture redesign.
- A general-purpose event subscription framework.
- Unnecessary changes to installers or distribution infrastructure.

Existing capture-opening behavior must continue working, but improving it is not the objective of this phase.

This phase is focused on **read-only discovery and synchronization**.

## 13. Implementation Guidelines

Follow these principles throughout the implementation.

**Reuse existing architecture.**

Extend the current RenderDoc extension, Shared IPC Service, session registry, and MCP tools.

**Prefer observable facts over inferred state.**

A successful request to open a capture does not prove that it is currently loaded.

**Keep GUI state authoritative.**

Agent commands and cached state must not override the actual GUI state.

**Distinguish unavailable from empty.**

A disconnected GUI is not equivalent to a GUI without a capture.

**Preserve concurrency safety.**

Multiple agents must remain able to query the same RenderDoc GUI safely.

**Avoid unnecessary complexity.**

Do not introduce large frameworks for state management, messaging, or event processing when small changes to existing components are sufficient.

**Maintain backward compatibility.**

Do not unnecessarily rename or remove existing MCP tools, IPC messages, or configuration options.

**Do not mask unsupported APIs.**

When a feature cannot be implemented using supported RenderDoc APIs, document the limitation and provide a safe fallback where possible.

## 14. Deliverables

When implementation is complete, provide:

1. **Implementation Summary**
   - Modified components.
   - New or extended state models.
   - New or extended MCP tools.
   - Synchronization mechanism.

2. **RenderDoc API Findings**
   - APIs used.
   - Supported state observations.
   - Unsupported or version-dependent features.
   - Any fallback implementation.

3. **Compatibility Summary**
   - Impact on existing IPC behavior.
   - Impact on existing MCP tools.
   - Phase 6 multi-agent compatibility.

4. **Test Results**
   - Unit tests.
   - Integration tests.
   - Manual tests actually performed.
   - Tests not performed and why.

5. **Known Limitations**
   - State that cannot be observed reliably.
   - Remaining race conditions or lifecycle constraints.
   - Any supported RenderDoc version restrictions.

6. **Documentation Updates**
   - Updated files and new usage examples.

Do not describe unimplemented behavior as completed.

## 15. Acceptance Criteria

Phase 7 is complete when all of the following are satisfied:

- [ ] RenderEyeMCP can determine whether a connected RenderDoc GUI has a capture loaded.
- [ ] A capture opened manually or by a game engine can be discovered without an MCP open request.
- [ ] The loaded capture path is returned when the RenderDoc API reliably provides it.
- [ ] Capture changes and unloads are reflected in subsequent state queries.
- [ ] Initial connection discovers an already-loaded capture.
- [ ] Reconnection restores an accurate state snapshot.
- [ ] Multiple RenderDoc GUI instances are distinguishable.
- [ ] Disconnected sessions cannot be mistaken for actively loaded captures.
- [ ] Multiple AI agents can query state without interfering with each other.
- [ ] Existing Phase 6 IPC behavior remains functional.
- [ ] Automated tests cover state synchronization and session lifecycle behavior.
- [ ] Relevant documentation is updated.
- [ ] Any API limitations or unverified integration scenarios are explicitly documented.

## Final Goal

After Phase 7, a developer should be able to open a capture through Unity, Unreal Engine, or the RenderDoc GUI and immediately ask a connected AI coding agent:

**"What capture is currently open in RenderDoc?"**

The agent should be able to answer using RenderEyeMCP without opening the capture itself, guessing from file history, or assuming ownership of the RenderDoc GUI session.

RenderEyeMCP should observe the developer's existing workflow rather than requiring the developer to adapt their workflow to the AI agent.
