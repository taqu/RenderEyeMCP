# RenderEyeMCP — Phase 0 Implementation Instructions

## Objective

Implement **Phase 0: Foundation & Feasibility** of RenderEyeMCP.

RenderEyeMCP is a Model Context Protocol (MCP) server and RenderDoc Python extension designed to provide reliable `.rdc` capture discovery, RenderDoc GUI instance management, and window orchestration for coding agents such as Claude Code.

The purpose of Phase 0 is to establish a working project foundation, investigate RenderDoc integration capabilities, validate critical technical assumptions, and implement a minimal end-to-end proof of concept.

**Do not stop after writing documentation. Implement and test working code wherever the local environment permits.**

---

## 1. Project Constraints

Follow these requirements throughout implementation.

### Existing Environment

- `uv` is already installed.
- Use Python for the MCP server.
- Use `uv` for Python dependency management, environment management, and command execution.
- Target Windows as the primary development platform.
- Use the official MCP Python SDK.
- Use RenderDoc's official Python extension mechanism whenever possible.

### Compatibility

- Do not modify the existing engine.
- Do not modify RenderDoc source code.
- Do not require rebuilding RenderDoc.
- Do not interfere with existing RenderDoc GUI windows.
- Do not assume every RenderDoc instance was launched by RenderEyeMCP.
- Do not terminate unrelated processes.
- Do not assume that one process always corresponds to one capture or one window.

### Implementation Principles

- Prefer simple and maintainable implementations.
- Avoid introducing unnecessary infrastructure.
- Keep the MCP server independent from the RenderDoc GUI process.
- Separate platform-specific functionality from core logic.
- Use type annotations throughout the Python implementation.
- Provide structured logging and actionable error messages.
- Do not introduce GPU debugging or frame analysis functionality.
- Do not implement Phase 1–5 functionality prematurely.

When an API or operating-system behavior is uncertain, verify it experimentally rather than assuming it works.

---

## 2. Repository Inspection

Before making changes:

1. Inspect the existing repository structure.
2. Identify existing Python packages, configuration files, documentation, and tests.
3. Check whether any MCP server or RenderDoc extension implementation already exists.
4. Identify conventions that should be preserved.
5. Avoid replacing or deleting existing implementations without justification.

If the repository is empty, initialize a new Python project.

Use `uv` rather than manually creating and managing virtual environments.

Suggested commands:

```bash
uv init --package
uv add "mcp[cli]"
uv add --dev pytest ruff
uv sync
```

These commands are examples. Adapt them to the repository and installed environment.

Inspect the installed MCP SDK version and use APIs documented for that exact version. Do not mix incompatible examples from different SDK major versions.

---

## 3. Project Structure

Establish a modular project structure similar to:

```text
RenderEyeMCP/
├── pyproject.toml
├── uv.lock
├── README.md
├── .gitignore
│
├── src/
│   └── rendereye_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py
│       ├── config.py
│       ├── logging.py
│       │
│       ├── ipc/
│       │   ├── __init__.py
│       │   ├── protocol.py
│       │   ├── transport.py
│       │   └── connection.py
│       │
│       └── platform/
│           ├── __init__.py
│           └── windows.py
│
├── extensions/
│   └── rendereye/
│       ├── __init__.py
│       ├── extension.json
│       └── ipc_client.py
│
├── tests/
│   ├── test_server.py
│   ├── test_config.py
│   ├── test_ipc.py
│   └── test_protocol.py
│
└── docs/
    ├── architecture.md
    ├── renderdoc_integration.md
    ├── feasibility_report.md
    └── development.md
```

The structure is a guideline, not a strict requirement.

Adjust it based on the actual implementation.

The RenderDoc extension must remain deployable independently of the MCP server's Python virtual environment.

Do not assume that RenderDoc's embedded Python interpreter can import packages installed in the `uv` environment.

Prefer Python standard-library functionality for the extension whenever practical.

---

## 4. Task A — Minimal MCP Server

Implement a minimal, functional MCP server using the official Python MCP SDK.

### Requirements

- Use the standard MCP protocol.
- Support `stdio` transport.
- Use the current, installed SDK APIs.
- Provide a clean application entry point.
- Keep protocol output separate from diagnostic logging.
- Use stderr for diagnostic logs when running over stdio.
- Shut down cleanly.

Implement one diagnostic MCP tool:

`server_status`

It should return structured information containing at least:

- Server name
- Server version
- Operating system
- Python version
- RenderDoc detection status
- IPC listener status
- Extension connection status

Unknown or unverified values must be reported as unknown or unavailable rather than fabricated.

### Validation

Demonstrate that:

1. The server starts through `uv run`.
2. A real MCP client can initialize a session.
3. The client can list available tools.
4. The client can invoke `server_status`.
5. The response is valid and structured.
6. The server exits cleanly.

Prefer an automated MCP client smoke test.

Do not rely solely on directly calling the Python function behind an MCP tool.

---

## 5. Task B — RenderDoc Installation and Process Discovery

Investigate the RenderDoc installation available on the development machine.

### Requirements

- Detect whether RenderDoc is installed.
- Identify the installed RenderDoc version when possible.
- Locate `qrenderdoc.exe`.
- Support a configurable executable path.
- Detect currently running RenderDoc GUI processes.
- Collect process IDs and process start times when available.
- Investigate reliable mapping between processes and top-level windows.
- Distinguish confirmed RenderDoc processes from uncertain candidates.

Do not hardcode a particular installation directory.

Investigate the actual command-line arguments supported by the installed RenderDoc version.

### Launch Feasibility

Determine whether a capture can be opened using an external command such as:

```text
qrenderdoc.exe <capture-file>
```

This syntax is only a hypothesis and must be verified.

Do not assume that every invocation creates a new process or a new GUI window.

Test and document:

- Opening a capture when RenderDoc is not running.
- Opening a capture when RenderDoc is already running.
- Opening a second capture while another is open.
- Whether the invocation creates a new window or reuses an existing instance.
- How the launched process can be correlated with the resulting window.
- Whether command-line options influence the behavior.

Use only valid `.rdc` files supplied or explicitly approved for testing.

If no sample capture is available, provide a manual test procedure and clearly identify the test as not executed.

### Deliverable

Document the verified launch and process behavior in `docs/renderdoc_integration.md`.

A reusable Windows process-discovery helper may be implemented, but avoid building the complete session-management system.

---

## 6. Task C — RenderDoc Python Extension Proof of Concept

Investigate and implement a minimal RenderDoc Python extension.

### Research Requirements

Verify:

1. RenderDoc's extension discovery mechanism.
2. Extension installation directories.
3. The required extension metadata format.
4. Extension initialization and shutdown callbacks.
5. Relevant Python API availability.
6. How to access the active capture path.
7. Whether GUI state changes can be observed through callbacks.
8. Whether supported APIs expose GUI window identity.
9. Whether multiple GUI instances load independent extension instances.
10. Whether extensions can be loaded into already-running GUI processes.

Use the installed RenderDoc version and its matching documentation or source.

Do not assume that APIs available in one RenderDoc version are available in another.

### Implementation Requirements

Create a minimal extension that:

- Can be discovered by RenderDoc.
- Can be enabled through RenderDoc's extension manager.
- Logs successful initialization.
- Logs shutdown or unloading when supported.
- Reports its process ID.
- Reports its extension version.
- Attempts to retrieve the currently loaded capture path.
- Handles cases where no capture is loaded.
- Handles unsupported or missing APIs safely.

Do not crash RenderDoc when an expected API is unavailable.

If the extension registration API requires callbacks such as `register` or `unregister`, implement them according to the verified version-specific contract.

Do not invoke RenderDoc-managed registration callbacks manually.

### Validation

Manually or automatically verify:

1. The extension loads successfully.
2. The extension reports initialization.
3. The extension operates with no capture loaded.
4. The extension operates with a capture loaded.
5. The extension can be unloaded or RenderDoc can exit without errors.
6. Multiple RenderDoc windows behave as documented.

If a capability is unavailable, record the limitation and possible alternatives.

---

## 7. Task D — Local IPC Proof of Concept

Implement minimal bidirectional communication between the MCP server and the RenderDoc extension.

### Transport Selection

Evaluate at least:

- Windows named pipes
- Loopback TCP sockets

Select the transport based on:

- Compatibility with RenderDoc's embedded Python runtime
- Implementation complexity
- Reliability
- Support for multiple GUI instances
- Local security
- Reconnection feasibility
- Future cross-platform support

For Phase 0, prefer a simple transport that can be tested reliably.

Do not introduce external message brokers, databases, or network services.

### Minimum Protocol

Implement a small, versioned JSON message protocol.

Required message types:

- `hello`
- `hello_ack`
- `heartbeat` or equivalent health probe
- `get_status`
- `status_response`
- `error`

Include:

- Protocol version
- Request or correlation ID where appropriate
- Process ID
- Instance identity
- Extension version
- Connection status
- Loaded capture path, when available

An example handshake:

```json
{
  "type": "hello",
  "protocol_version": 1,
  "request_id": "req-001",
  "instance_id": "temporary-instance-id",
  "process_id": 12345,
  "extension_version": "0.1.0"
}
```

The example is illustrative. Refine the protocol as necessary.

### Security

- Restrict IPC access to the local machine.
- Do not expose an unrestricted TCP listener.
- Bind TCP listeners to loopback only.
- Use appropriate local authentication or connection validation.
- Never accept arbitrary Python code execution.
- Do not implement generic shell-command execution over IPC.
- Validate incoming message types and payloads.
- Enforce message size limits.
- Apply timeouts to network operations.
- Prevent uncontrolled reconnect loops.

### Reliability

The implementation must:

- Handle connection failure without crashing RenderDoc.
- Support multiple extension connections.
- Detect disconnected clients.
- Avoid blocking the RenderDoc GUI thread with long-running I/O.
- Shut down sockets, threads, and other resources safely.
- Keep IPC failures isolated from the MCP server's main protocol handling.

Use standard-library mechanisms inside the RenderDoc extension where possible.

### Validation

Demonstrate:

1. Starting the MCP server.
2. Loading the RenderDoc extension.
3. Establishing IPC communication.
4. Receiving an instance registration message.
5. Querying extension status.
6. Returning the result through the MCP server.
7. Disconnecting or closing RenderDoc.
8. Handling the disconnection gracefully.

If GUI testing is unavailable, implement a simulated extension client and test the protocol with it.

Clearly distinguish simulated tests from tests performed with real RenderDoc.

---

## 8. Task E — Configuration and Logging

Implement a minimal configuration mechanism.

Support the following settings where appropriate:

- RenderDoc executable path
- IPC transport
- IPC endpoint
- Connection timeout
- Log level
- Optional extension discovery or installation path

Avoid excessive configuration options.

Prefer explicit defaults and validation.

### Logging Requirements

- Use Python's standard logging facilities unless another dependency is justified.
- Use structured or consistently formatted log messages.
- Separate MCP protocol output from logs.
- Include instance and request identifiers when relevant.
- Avoid logging authentication secrets.
- Keep diagnostic logs suitable for troubleshooting process and IPC issues.

Document configuration examples in the README.

---

## 9. Task F — Tests and Development Tooling

Configure the development environment using `uv`.

Include:

- `pytest`
- `ruff`
- Appropriate Python type checking if useful

### Required Tests

Implement automated tests for:

- MCP server initialization
- `server_status` response
- Configuration parsing and validation
- IPC message serialization and deserialization
- Protocol version mismatch
- Invalid or oversized IPC messages
- IPC connection and disconnection
- Multiple simulated extension clients
- Missing RenderDoc installation
- Process-discovery error handling

Avoid tests that terminate unrelated processes.

Ensure unit tests can run without RenderDoc installed.

Place real RenderDoc integration tests behind explicit opt-in execution or document them as manual tests.

### Development Commands

Provide documented commands for:

- Installing dependencies
- Running the server
- Running tests
- Running lint checks
- Installing the extension
- Running integration tests

Use `uv run` for Python commands.

---

## 10. Documentation Deliverables

Create or update the following documents.

### README.md

Include:

- Project overview
- Phase 0 capabilities
- Prerequisites
- Development setup
- Server startup instructions
- Extension installation instructions
- Verification steps
- Current limitations

### docs/architecture.md

Describe:

- Component responsibilities
- MCP server boundaries
- Extension boundaries
- IPC communication flow
- Future capture and session registry boundaries
- Separation between stable logical IDs and OS identifiers

### docs/renderdoc_integration.md

Document:

- Tested RenderDoc version
- Python extension APIs verified
- Capture path identification results
- Process and window behavior
- Launch-command experiments
- Unsupported or uncertain capabilities
- Relevant API documentation or source references

### docs/feasibility_report.md

Include a capability matrix.

| Capability | Status | Evidence |
|---|---|---|
| RenderDoc installation detection | Verified / Partial / Blocked / Untested | Test result |
| External capture launch | ... | ... |
| Multiple GUI instances | ... | ... |
| Extension loading | ... | ... |
| Loaded capture identification | ... | ... |
| Process/window correlation | ... | ... |
| MCP-to-extension IPC | ... | ... |
| Multiple extension connections | ... | ... |
| Reconnection | ... | ... |

Do not mark a capability as verified without evidence.

Document blockers, implementation alternatives, and their implications for subsequent phases.

### docs/development.md

Include:

- Development commands
- Test commands
- Project structure
- Debugging procedures
- Environment assumptions

---

## 11. Phase 0 Scope Boundaries

Do not implement the complete Capture Registry planned for Phase 1.

Do not implement:

- Directory watching
- Latest capture ordering
- Persistent capture history
- Capture readiness detection
- Capture IDs and registry persistence

Do not implement the complete Session Manager planned for Phase 2.

Do not implement:

- Persistent Session IDs
- Full window lifecycle management
- Protected or pinned sessions
- Automatic session restoration
- General-purpose window automation
- Automatic closing of old windows

Do not implement GPU frame analysis.

Phase 0 may introduce interfaces and data types required for feasibility experiments, but production implementations belong to later phases.

---

## 12. Acceptance Criteria

Phase 0 is complete when the following criteria are satisfied.

### Foundation

- [ ] A valid `uv`-managed Python project exists.
- [ ] The MCP server starts successfully.
- [ ] A real MCP client can invoke `server_status`.
- [ ] Automated unit tests pass.
- [ ] Lint checks pass.

### RenderDoc Integration

- [ ] RenderDoc installation detection has been implemented and tested.
- [ ] RenderDoc process detection has been tested.
- [ ] Capture launch behavior has been investigated.
- [ ] A minimal Python extension has been implemented.
- [ ] Extension loading behavior has been verified where RenderDoc is available.
- [ ] Loaded capture identification has been tested or its limitation documented.

### IPC

- [ ] A local IPC transport has been selected and implemented.
- [ ] Protocol messages can be exchanged.
- [ ] Multiple clients are supported at the protocol level.
- [ ] Connection failures do not crash the server.
- [ ] IPC errors do not crash the RenderDoc extension.

### Documentation

- [ ] Architecture documentation exists.
- [ ] RenderDoc integration findings are documented.
- [ ] Feasibility report is complete.
- [ ] Development instructions are reproducible.
- [ ] Unverified capabilities are clearly identified.

### End-to-End Proof of Concept

The preferred validation sequence is:

```text
Claude Code / MCP Test Client
          |
          v
    RenderEyeMCP
      MCP Server
          |
          v
      Local IPC
          |
          v
   RenderDoc Extension
          |
          v
      RenderDoc GUI
          |
          v
   Current Capture Path
```

The MCP client must be able to request a status query that reaches the RenderDoc extension and returns information from the actual GUI process.

This is the primary Phase 0 success criterion.

If real RenderDoc integration is blocked by missing software, missing captures, or unsupported APIs, report Phase 0 as partially verified rather than complete.

---

## 13. Execution Instructions

Execute the implementation in the following order:

1. Inspect the repository and development environment.
2. Initialize or update the `uv` project.
3. Implement the minimal MCP server.
4. Verify the server with a real MCP client.
5. Investigate the installed RenderDoc version and integration APIs.
6. Implement the RenderDoc extension proof of concept.
7. Select and implement the local IPC transport.
8. Connect the MCP server and extension.
9. Test the communication flow.
10. Implement process and launch feasibility experiments.
11. Add unit and integration tests.
12. Complete documentation.
13. Review the implementation against the acceptance criteria.

Work autonomously using the available tools and repository.

Make reasonable technical decisions when requirements leave implementation details open.

Prefer practical verification over speculative architecture.

Do not introduce unrelated features or excessive abstractions.

Do not modify the existing engine or unrelated project files.

When testing requires potentially destructive process operations, avoid them unless explicitly authorized.

If a hardware-dependent test cannot be performed, continue implementing other components and record the limitation.

Do not claim successful validation of anything that was not actually executed.

---

## 14. Final Report

After implementation, provide a concise report containing:

1. **Implementation Summary** — What was implemented.
2. **Project Structure** — Important created or modified files.
3. **Environment** — Python, MCP SDK, OS, and RenderDoc versions.
4. **Verification Results** — Tests actually executed and their outcomes.
5. **RenderDoc Findings** — Confirmed integration capabilities.
6. **Technical Limitations** — Unverified APIs, blockers, and workarounds.
7. **Phase 0 Status** — Complete, partially verified, or blocked.
8. **Phase 1 Readiness** — What is ready and what must be resolved first.

**Prioritize a functional MCP-to-RenderDoc communication proof of concept over documentation-only completion.**

Do not begin Phase 1 implementation.
