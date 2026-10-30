# RenderEyeMCP — Development Roadmap

## Vision

**RenderEyeMCP enables AI coding agents to inspect and debug graphics captures directly through RenderDoc.**

The project integrates RenderDoc with MCP-compatible coding agents, including Claude Code and Codex.

Its goal is to make graphics debugging more accessible and efficient by allowing developers to investigate rendering problems through natural-language requests.

RenderEyeMCP does not replace RenderDoc, implement its own GPU debugger, or perform autonomous graphics optimization.

Instead, it exposes RenderDoc's existing inspection and debugging capabilities to coding agents through a reliable MCP interface.

## Core Principles

1. **RenderDoc remains the source of truth.** Use captures already loaded in the RenderDoc GUI.
2. **Preserve the developer's workflow.** Do not unnecessarily modify GUI selection or replay state.
3. **Support multiple coding agents.** Independent MCP clients must safely share the same RenderDoc environment.
4. **Reuse RenderDoc APIs.** Avoid independently implementing GPU debugging functionality.
5. **Keep installation simple.** Normal users should not need to manage Python environments, virtual environments, or developer toolchains.
6. **Prioritize stability.** Disconnections, capture changes, and replay failures must be handled safely.
7. **Support multiple platforms.** Maintain Windows as a primary target while improving Linux and other platform compatibility where RenderDoc supports them.
8. **Separate data retrieval from analysis.** RenderEyeMCP provides reliable debugging evidence; coding agents interpret it.

---

## Architecture

### Original Python Infrastructure

```text
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Python Shared IPC Service
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The Shared IPC Service is an independent daemon process.

### Target Go Infrastructure

```text
Claude Code ── rendereye-mcp ──┐
                               │
Codex ─────── rendereye-mcp ──┼── rendereye-mcp service
                               │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

The Go MCP Bridge and Shared IPC Service use a single executable with separate operating modes.

They remain independent processes.

The RenderDoc Extension continues using RenderDoc's Python API.

This architecture eliminates the requirement for a user-managed Python environment for the MCP and IPC infrastructure.

---

## Development Phases

### Stage 1 — Foundation and Initial Integration

| Phase | Title | Objectives |
|---|---|---|
| 0 | Project Foundation | Establish project structure, development environment, and basic integration architecture |
| 1 | RenderDoc Extension Foundation | Implement the initial RenderDoc extension and API access |
| 2 | MCP Server Foundation | Expose basic RenderDoc functionality through MCP |
| 3 | IPC Integration | Establish communication between the MCP server and RenderDoc |
| 4 | Core Integration | Extend basic inspection capabilities and validate end-to-end communication |
| 5 | Installation and Distribution | Improve Windows installation, configuration, and packaging |
| 5.1 | Installation Improvements | Simplify installation on clean Windows environments and configure coding agents |
| 5.2 | GitHub Actions Releases | Introduce automated release artifact generation |
| 5.5 | Documentation and Usability | Improve README, setup instructions, and user guidance |

**Milestone:** RenderEyeMCP can connect a coding agent to RenderDoc and provide a usable installation and debugging workflow.

### Stage 2 — Shared IPC and RenderDoc Inspection

| Phase | Title | Objectives |
|---|---|---|
| 6 | Shared IPC Service | Introduce a standalone shared daemon supporting multiple independent MCP processes |
| 7 | GUI State Discovery | Detect RenderDoc sessions, loaded captures, and GUI state |
| 8 | Event and Pipeline Inspection | Inspect draw calls, compute dispatches, event hierarchies, and pipeline state |
| 9 | GPU Resource Inspection | Retrieve texture and buffer metadata and bounded buffer contents |
| 10 | Shader Inspection | Retrieve shader information, reflection, bindings, and disassembly |
| 11 | Render Target and Pixel Inspection | Inspect render targets, texture images, and pixel values |

**Milestone:** Coding agents can investigate rendering state in captures already opened in RenderDoc.

The Shared IPC Service must maintain correct routing and isolation when multiple coding agents are connected.

### Stage 3 — Advanced Debugging and Release Preparation

| Phase | Title | Objectives |
|---|---|---|
| 12 | Release Preparation | Prepare bilingual documentation, installation validation, and practical debugging examples |
| 13 | GPU Performance Analysis | Collect GPU timing counters, pipeline statistics, and render-pass performance summaries |
| 13.1 | Performance E2E Validation | Validate real coding-agent performance analysis using an existing capture |
| 14 | Geometry and Mesh Inspection | Inspect vertex/index buffers, input layouts, Post-VS geometry, and mesh statistics |
| 15 | Pixel History and Shader Debugging | Inspect pixel modifications, shader execution traces, and variable states |
| 15.1 | PyPI Trusted Publishing | Add isolated PyPI and TestPyPI publishing workflows using OIDC |

Phase 15.1 requires separate GitHub Actions workflows:

```text
.github/workflows/
  publish-testpypi.yml
  publish-pypi.yml
```

Test tags such as `v0.1.0-test.1` publish to TestPyPI using a PEP 440-compatible version such as `0.1.0.dev1`.

Production tags such as `v0.1.0` publish to PyPI.

**Milestone:** RenderEyeMCP exposes the major RenderDoc inspection and debugging capabilities needed for practical AI-assisted graphics debugging.

Advanced features must respect RenderDoc capability availability and replay-thread requirements.

---

## Stage 4 — Migration from Python Infrastructure to Go

The primary objective of this stage is to eliminate installation complexity while preserving MCP compatibility and multi-agent reliability.

### Phase 16 — IPC Protocol Contract & Compatibility Tests

Document and validate the existing Python IPC protocol before migration.

Key deliverables:

- IPC protocol specification.
- Message framing and serialization contract.
- Session and request routing semantics.
- Binary payload compatibility.
- Golden protocol fixtures.
- Python compatibility tests.
- Minimal Go IPC probe.
- Cross-language interoperability tests.

The Python implementation remains authoritative during this phase.

**Completion condition:** Go can communicate correctly with the existing Python Shared IPC Service, and the protocol is sufficiently documented and tested for replacement.

### Phase 17 — Go Shared IPC Service

Replace the standalone Python Shared IPC Service with a compatible Go daemon.

Preserve:

- Existing TCP endpoint.
- Existing IPC protocol.
- Python MCP Bridge compatibility.
- Python RenderDoc Extension compatibility.
- Multi-client request routing.
- Session and capture identity.
- Service startup and lifecycle behavior.

Keep the Python service available for rollback.

**Completion condition:** Two Python MCP Bridges and the existing RenderDoc Extension can operate correctly through the Go Shared IPC Service.

### Phase 18 — Go MCP Bridge

Replace the Python MCP Bridge with a Go implementation using the official MCP Go SDK.

Key deliverables:

- Go MCP stdio server.
- Complete migration of implemented MCP tools.
- Compatible Tool names and descriptions.
- Compatible input and output schemas.
- Correct text, image, and structured results.
- Shared Go IPC client integration.
- MCP contract snapshot tests.
- Python/Go differential tests.
- Claude Code and Codex integration tests.

Do not modify the RenderDoc Extension or IPC protocol to accommodate the new MCP Bridge.

**Completion condition:** The Go MCP Bridge can replace the Python Bridge without changing coding-agent workflows.

### Phase 19 — Single Binary & Cross-Platform Distribution

Combine the Go MCP Bridge and Go Shared IPC Service into one executable with multiple operating modes.

Required behavior:

```text
rendereye-mcp          # MCP Bridge
rendereye-mcp service  # Shared IPC Service
```

Each coding agent launches its own Bridge process. The Bridges reuse one independently running Shared IPC Service.

Key deliverables:

- Service discovery and automatic startup.
- Concurrent startup race prevention.
- Native Windows and Linux binaries.
- macOS binary support with clearly documented RenderDoc limitations.
- RenderDoc Extension packaged with releases.
- Installation and upgrade scripts.
- GitHub Releases build automation.
- Checksums and artifact validation.
- English and Japanese installation documentation.

Existing PyPI and TestPyPI publishing workflows remain separate from Go binary release automation.

**Completion condition:** A user can install RenderEyeMCP and configure a coding agent without installing Python, uv, pip, or Go.

### Phase 20 — Reliability Hardening, Migration & Compatibility

Prepare the Go implementation to become the official default distribution.

Primary workstreams:

- Service startup, shutdown, and restart reliability.
- Multi-agent concurrency and request isolation.
- Capture/session lifecycle safety.
- Timeout and cancellation handling.
- Replay-dependent operation coordination.
- Goroutine, socket, and memory leak prevention.
- RenderDoc version compatibility.
- Windows and Linux integration testing.
- Cross-platform installation and upgrade validation.
- Python-to-Go migration and rollback.
- Regression testing and release quality gates.
- English and Japanese documentation updates.

Evaluate deprecation of the legacy Python MCP Bridge and Python Shared IPC Service only after the Go implementation has passed the required compatibility and reliability tests.

The RenderDoc Python Extension remains supported.

**Completion condition:** The Go implementation is reliable enough to become the recommended default, with documented platform support and a safe migration path.

---

## Long-Term Maintenance

After Phase 20, development priorities shift from major feature expansion to maintaining a stable, compatible, easy-to-install graphics debugging tool.

### Priority 1 — Reliability

- Prevent service and client lifecycle regressions.
- Maintain multi-agent safety.
- Improve recovery from failures.
- Preserve capture and replay state.
- Prevent resource leaks and deadlocks.

### Priority 2 — Platform Compatibility

- Maintain high-quality Windows support.
- Improve native Linux support.
- Validate other platforms according to RenderDoc availability.
- Keep installation and upgrade procedures straightforward.

### Priority 3 — RenderDoc Compatibility

- Support relevant RenderDoc updates.
- Detect API and feature availability.
- Adapt the Python Extension to upstream API changes.
- Avoid protocol or MCP Tool contract breakage.

### Priority 4 — User Experience

- Improve diagnostics and troubleshooting.
- Maintain practical coding-agent debugging examples.
- Keep English and Japanese documentation accurate.
- Reduce configuration and installation steps.

### Priority 5 — Feature Expansion

Introduce additional GPU debugging functionality when RenderDoc exposes useful new APIs or when a clearly justified user requirement can be satisfied through existing capabilities.

Do not implement an independent GPU debugger or profiler merely to expand the feature list.

---

## Non-Goals

RenderEyeMCP is not intended to:

- Replace the RenderDoc GUI.
- Reimplement RenderDoc's ReplayController.
- Implement a proprietary GPU debugger.
- Become a standalone hardware profiler.
- Automatically repair shaders or rendering bugs.
- Bundle a dedicated AI reasoning engine.
- Depend on cloud services for IPC or capture inspection.
- Require users to install a Python or Go development environment.
- Guarantee full RenderDoc functionality on unsupported operating systems.

---

## Release and Compatibility Policy

The project should maintain the following requirements:

**Stable MCP Interface**

Avoid unnecessary changes to existing Tool names, schemas, and result semantics.

**Stable IPC Protocol**

Use compatibility tests to identify unintended breaking changes.

**Versioned Release Artifacts**

Distribute traceable native binaries with consistent version metadata.

**Separate Publishing Destinations**

Maintain independent PyPI, TestPyPI, and GitHub Releases publishing paths.

**Verified Platform Claims**

Distinguish successful compilation from tested runtime and RenderDoc integration.

**Backward-Compatible Migration**

Keep legacy Python infrastructure available during the supported transition period.

**No Automatic Production Publishing During Development**

Release preparation and validation do not imply authorization to publish a production release.

---

## Project Milestones

| Milestone | Related phases | Outcome |
|---|---|---|
| M1 — Initial Integration | 0–5.5 | RenderDoc and MCP connection established |
| M2 — Multi-Agent Foundation | 6–7 | Shared IPC and active capture discovery |
| M3 — Core Inspection | 8–11 | Event, pipeline, shader, resource, and pixel inspection |
| M4 — Advanced Debugging | 12–15.1 | Performance, geometry, shader debugging, documentation, and publishing preparation |
| M5 — Go Infrastructure | 16–18 | Compatible Go Shared IPC Service and MCP Bridge |
| M6 — Native Distribution | 19 | Single executable and simplified cross-platform installation |
| M7 — Stable Go Adoption | 20 | Reliability validation, migration readiness, and maintenance policy |

Milestone definitions describe intended capabilities, not proof of implementation or testing.

Track actual completion status separately from the roadmap.

---

## Final Target

RenderEyeMCP should become a reliable, cross-platform-friendly companion to RenderDoc that allows developers to investigate graphics problems through their preferred coding agents.

The desired user workflow is:

1. Install RenderDoc.
2. Download and install RenderEyeMCP.
3. Configure Claude Code, Codex, or another MCP-compatible agent.
4. Open a graphics capture in RenderDoc.
5. Ask the agent to inspect the capture and investigate a problem.

The user should not need to manage Python virtual environments, manually start IPC daemons, or export debugging data between applications.

**The long-term development focus is stability, ease of installation, multi-agent compatibility, and continued support for RenderDoc's evolving APIs.**
