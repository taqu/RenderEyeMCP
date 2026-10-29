\# RenderEyeMCP — Development Roadmap



\## 1. Project Overview



\*\*RenderEyeMCP\*\* is an MCP server and RenderDoc extension that enables coding agents such as Claude Code to reliably discover, open, track, and manage RenderDoc frame captures (`.rdc`) and GUI windows.



The project focuses on \*\*capture lifecycle management and reliable RenderDoc GUI orchestration\*\*, rather than GPU frame analysis.



\### Primary Goals



1\. Automatically discover newly generated `.rdc` files.

2\. Reliably identify the latest completed capture.

3\. Open and manage multiple RenderDoc GUI windows independently.

4\. Track relationships between captures, sessions, processes, and windows.

5\. Preserve existing debugging sessions when opening new captures.

6\. Expose these operations through a compact MCP interface.

7\. Integrate without modifying existing engine-side RenderDoc capture or launch logic.



\### Non-Goals for v1.0



\- Draw call and pipeline state analysis

\- Shader, texture, and buffer inspection

\- GPU debugging and automatic problem diagnosis

\- Capture content comparison or image diffing

\- Engine-side integration changes

\- Remote or multi-machine orchestration

\- General-purpose desktop automation



\---



\## 2. Architecture



The initial architecture consists of three main components.



\### MCP Server



Responsible for:



\- Exposing MCP tools to coding agents

\- Discovering and indexing captures

\- Managing sessions and process identities

\- Managing RenderDoc instances and windows

\- Coordinating requests with the RenderDoc extension

\- Handling errors, reconnections, and state recovery



\### RenderDoc Extension



Responsible for:



\- Reporting RenderDoc GUI state

\- Identifying the capture loaded in each instance

\- Executing supported GUI operations

\- Communicating with the MCP server through local IPC



The extension should use RenderDoc's official Python extension APIs wherever possible.



\### Capture Registry



Responsible for:



\- Tracking discovered `.rdc` files

\- Resolving the latest valid capture

\- Maintaining capture and session metadata

\- Detecting deleted, moved, and incomplete captures



The registry is managed by the MCP server and does not require a separate service.



\### Design Principles



\- \*\*Non-invasive:\*\* Do not modify existing engine code.

\- \*\*Non-destructive:\*\* Never close unrelated or protected GUI windows automatically.

\- \*\*Identity-based:\*\* Prefer stable capture and session IDs over process IDs or window handles.

\- \*\*Recoverable:\*\* Reconcile state after process crashes, server restarts, or IPC disconnections.

\- \*\*Agent-friendly:\*\* Return compact, structured, actionable results.

\- \*\*Local-first:\*\* Restrict process control and IPC to the local development environment.



\---



\## 3. Development Phases



\### Phase 0 — Foundation \& Feasibility



\*\*Goal:\*\* Establish the project foundation and validate the RenderDoc integration approach.



Tasks:



\- \[ ] Define repository structure and module boundaries.

\- \[ ] Select the implementation language and MCP SDK.

\- \[ ] Establish the target Windows and RenderDoc version baseline.

\- \[ ] Define configuration format and logging conventions.

\- \[ ] Investigate RenderDoc Python extension lifecycle and supported APIs.

\- \[ ] Verify how the existing engine starts RenderDoc.

\- \[ ] Prototype launching `qrenderdoc.exe` with a specific `.rdc` file.

\- \[ ] Prototype detection of running RenderDoc processes and their windows.

\- \[ ] Verify whether a running extension can report the currently loaded capture.

\- \[ ] Validate local IPC between the MCP server and RenderDoc extension.

\- \[ ] Document limitations when attaching to already-running RenderDoc instances.



\*\*Deliverable:\*\* Minimal MCP server, extension proof of concept, and validated integration design.



\*\*Exit Criteria:\*\* A test client can communicate with a running RenderDoc extension and identify its process and loaded capture.



\### Phase 1 — Capture Discovery \& Registry



\*\*Goal:\*\* Reliably discover and track `.rdc` files without changing the engine.



Tasks:



\- \[ ] Support configurable capture directories.

\- \[ ] Scan existing `.rdc` files on startup.

\- \[ ] Detect newly created captures through filesystem monitoring.

\- \[ ] Periodically rescan to recover missed filesystem events.

\- \[ ] Verify file readiness before exposing a capture as usable.

\- \[ ] Handle partially written files and delayed writes.

\- \[ ] Track file size, timestamps, paths, and discovery sequence.

\- \[ ] Assign stable Capture IDs.

\- \[ ] Resolve the latest valid capture.

\- \[ ] Handle deleted, renamed, and moved files.

\- \[ ] Support multiple capture directories.

\- \[ ] Provide deterministic ordering and pagination.

\- \[ ] Persist capture metadata across MCP server restarts.

\- \[ ] Add automated tests for discovery and registry behavior.



\*\*Deliverable:\*\* A reliable Capture Registry with latest-capture resolution.



\*\*Exit Criteria:\*\* The system correctly discovers new captures and resolves the latest completed `.rdc`, including after restart, without treating incomplete files as ready.



\### Phase 2 — RenderDoc Instance \& Session Management



\*\*Goal:\*\* Manage multiple RenderDoc instances and GUI windows through stable identifiers.



Tasks:



\- \[ ] Define Capture, Instance, Window, and Session data models.

\- \[ ] Discover RenderDoc processes and windows.

\- \[ ] Distinguish managed and unmanaged RenderDoc instances.

\- \[ ] Assign stable Session IDs.

\- \[ ] Track Session ID → Instance ID → Window ID relationships.

\- \[ ] Associate loaded captures with sessions.

\- \[ ] Open captures in new RenderDoc instances.

\- \[ ] Reuse existing sessions when explicitly requested.

\- \[ ] Focus a selected RenderDoc window.

\- \[ ] Close a selected managed session safely.

\- \[ ] Support protected or pinned sessions.

\- \[ ] Avoid duplicate openings when reuse is requested.

\- \[ ] Handle process termination and unexpected crashes.

\- \[ ] Recover or reconcile session state after server restart.

\- \[ ] Add integration tests for simultaneous RenderDoc instances.



\*\*Deliverable:\*\* Multi-instance and multi-window session manager.



\*\*Exit Criteria:\*\* Two or more different captures can remain open simultaneously, and each managed window can be independently identified, focused, and closed without affecting unrelated windows.



\### Phase 3 — RenderDoc Extension \& IPC Integration



\*\*Goal:\*\* Establish authoritative GUI state synchronization and reliable command execution.



Tasks:



\- \[ ] Implement extension initialization and shutdown.

\- \[ ] Implement local IPC connection and authentication.

\- \[ ] Register instances through a startup handshake.

\- \[ ] Report loaded capture paths and window identity.

\- \[ ] Report capture load/unload events.

\- \[ ] Implement requested GUI actions through supported APIs.

\- \[ ] Implement request IDs, timeouts, and error responses.

\- \[ ] Reconnect after IPC disconnections.

\- \[ ] Synchronize instance and session states after reconnection.

\- \[ ] Handle extension version and protocol compatibility.

\- \[ ] Provide extension installation instructions or an installer.

\- \[ ] Verify behavior across the supported RenderDoc versions.



\*\*Deliverable:\*\* Reliable bidirectional communication between MCP Server and RenderDoc GUI.



\*\*Exit Criteria:\*\* The MCP server can query the actual GUI state and control each connected, managed RenderDoc instance without relying solely on OS window heuristics.



\### Phase 4 — MCP Tools \& Agent Workflow



\*\*Goal:\*\* Expose capture and session management through a stable, agent-friendly MCP API.



\#### Capture Tools



\- \[ ] `capture\_list` — List known captures.

\- \[ ] `capture\_latest` — Resolve the latest valid capture.

\- \[ ] `capture\_get` — Get capture metadata.

\- \[ ] `capture\_open` — Open a capture and return its session.



\#### Session Tools



\- \[ ] `session\_list` — List active and known sessions.

\- \[ ] `session\_get` — Get session details.

\- \[ ] `session\_focus` — Focus the selected GUI window.

\- \[ ] `session\_close` — Close a managed session.



\#### Operational Tools



\- \[ ] `server\_status` — Report server, watcher, and extension health.



\#### API Requirements



\- \[ ] Use structured JSON-compatible responses.

\- \[ ] Define consistent error codes.

\- \[ ] Support explicit capture and session identifiers.

\- \[ ] Support `latest` as a capture selector.

\- \[ ] Define `new\_window`, `reuse`, and explicit `replace` opening modes.

\- \[ ] Resolve `latest` once per request to avoid race conditions.

\- \[ ] Define clear semantics for protected sessions.

\- \[ ] Keep tool outputs concise.

\- \[ ] Avoid destructive implicit behavior.

\- \[ ] Provide MCP configuration examples for Claude Code.



\*\*Deliverable:\*\* Functional RenderEyeMCP tool interface.



\*\*Exit Criteria:\*\* Claude Code can discover the latest capture, open it, list available sessions, focus the correct RenderDoc window, and close only the intended managed session.



\### Phase 5 — Reliability, Testing \& Release



\*\*Goal:\*\* Make RenderEyeMCP suitable for everyday graphics debugging workflows.



Tasks:



\- \[ ] Test simultaneous creation of multiple `.rdc` files.

\- \[ ] Test incomplete, inaccessible, and corrupted capture files.

\- \[ ] Test multiple RenderDoc GUI windows.

\- \[ ] Test duplicate filenames across capture directories.

\- \[ ] Test RenderDoc process crashes.

\- \[ ] Test MCP server restart and session reconciliation.

\- \[ ] Test extension disconnection and reconnection.

\- \[ ] Test process ID and window handle reuse.

\- \[ ] Verify protected and unmanaged windows are never closed accidentally.

\- \[ ] Verify behavior when a capture is deleted while open.

\- \[ ] Add structured diagnostics and troubleshooting commands.

\- \[ ] Document installation, configuration, and supported platforms.

\- \[ ] Add Claude Code integration examples.

\- \[ ] Prepare versioned releases and a minimal distribution package.

\- \[ ] Complete end-to-end regression tests.



\*\*Deliverable:\*\* RenderEyeMCP v1.0.



\*\*Exit Criteria:\*\* The primary workflows remain reliable under repeated capture creation, multiple-window usage, restarts, and common failure conditions.



\---



\## 4. Release Milestones



| Milestone | Phase | Outcome |

|---|---|---|

| M0 | Foundation | Integration feasibility confirmed |

| M1 | Capture Registry | Latest `.rdc` discovery works |

| M2 | Session Management | Multiple GUI instances manageable |

| M3 | Extension Integration | Reliable GUI state synchronization |

| M4 | MCP Integration | Claude Code controls captures and sessions |

| M5 | v1.0 Release | Tested and documented release |



Phases are ordered by dependency, but some development may overlap. In particular, the Phase 3 IPC prototype should begin during Phase 0 to avoid discovering critical integration limitations late in development.



\---



\## 5. v1.0 Acceptance Scenarios



\### Scenario A — Open Latest Capture



1\. The engine generates a new `.rdc`.

2\. RenderEyeMCP discovers it.

3\. The capture becomes ready after validation.

4\. Claude Code invokes `capture\_open` with `latest`.

5\. RenderEyeMCP opens it and returns a Session ID.



\*\*Expected:\*\* The correct, completed capture opens successfully.



\### Scenario B — Compare Two Captures Manually



1\. A previous capture is already open in Session A.

2\. The engine generates a new capture.

3\. Claude Code opens the latest capture in a new window.

4\. Session B is created.

5\. Both RenderDoc windows remain available.

6\. Claude Code can focus either session.



\*\*Expected:\*\* Existing debugging context is preserved.



\### Scenario C — Avoid Closing the Wrong Window



1\. Three RenderDoc instances exist.

2\. One instance is unmanaged.

3\. Another session is protected.

4\. Claude Code requests closure of a specific managed session.



\*\*Expected:\*\* Only the explicitly selected, unprotected session is closed.



\### Scenario D — Recover from Restart



1\. Multiple RenderDoc windows are open.

2\. The MCP server restarts.

3\. The server reloads the capture registry.

4\. Connected extensions re-register their instances.

5\. Session state is reconciled.



\*\*Expected:\*\* Running windows are not unexpectedly closed, and recoverable session associations are restored.



\---



\## 6. Future Extension Notes



The following capabilities are outside the v1.0 scope and do not have committed implementation phases.



\- \*\*Capture Comparison:\*\* Compare metadata, GPU events, pipeline states, and resources between captures.

\- \*\*Automated Graphics Debugging:\*\* Allow coding agents to investigate rendering problems using RenderDoc Replay APIs.

\- \*\*Existing RenderDoc MCP Interoperability:\*\* Pass managed capture paths and session context to specialized GPU analysis MCP servers.

\- \*\*Capture Metadata Enrichment:\*\* Associate captures with builds, Git commits, test cases, and engine execution contexts.

\- \*\*Automated Regression Workflows:\*\* Integrate capture management with automated rendering tests and CI pipelines.

\- \*\*Workspace Management:\*\* Save and restore groups of captures and debugging layouts.



These features should be considered only after the capture and session management foundation is stable.



\---



\## 7. Definition of Done — v1.0



RenderEyeMCP v1.0 is complete when:



\- \[ ] `.rdc` files are automatically discovered without engine modifications.

\- \[ ] The latest completed capture can be reliably identified.

\- \[ ] Captures have stable identities and queryable metadata.

\- \[ ] Multiple RenderDoc windows can coexist safely.

\- \[ ] Managed sessions can be independently identified and controlled.

\- \[ ] Existing and protected debugging sessions are preserved.

\- \[ ] GUI state can be synchronized through the RenderDoc extension.

\- \[ ] Claude Code can perform all core workflows through MCP.

\- \[ ] Common crashes and disconnections are handled gracefully.

\- \[ ] Installation, configuration, and troubleshooting are documented.



\*\*v1.0 Focus: Reliable capture discovery, lifecycle management, and RenderDoc GUI orchestration for coding agents.\*\*

