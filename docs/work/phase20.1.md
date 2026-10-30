# Phase 20.1 Addendum — Go-Native Documentation Consolidation

## Objective

Update all active RenderEyeMCP documentation to describe the Go implementation as the official and primary implementation.

The documentation must present RenderEyeMCP as a Go-based MCP infrastructure with a RenderDoc Python Extension, rather than as a Python project that has been migrated to Go.

Do not create Python-to-Go migration guides.

## Requirements

### 1. README.md

Rewrite the root README.md to reflect the Go-native architecture.

The README should include:

- Project overview and purpose.
- Supported platforms and requirements.
- Installation using prebuilt GitHub Releases binaries.
- RenderDoc Extension installation.
- MCP configuration examples for Claude Code and Codex.
- Basic usage workflow.
- Multi-agent support.
- Troubleshooting.
- Links to detailed documentation.

Do not require Python, pip, uv, virtual environments, or a Go toolchain for normal installation.

Keep the README concise and approachable for new users.

### 2. Architecture Documentation

Document the current architecture:

```text
Claude Code ── rendereye-mcp ──┐
                               ├── rendereye-mcp service
Codex ─────── rendereye-mcp ──┘         │
                                       │ TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────────┘
```

Explain that:

- The MCP Bridge is implemented in Go.
- The Shared IPC Service is implemented in Go.
- Both modes are provided by the same executable.
- Each coding agent runs an independent MCP Bridge.
- Multiple Bridges share one independently running IPC Service.
- The RenderDoc Extension continues using RenderDoc's embedded Python API.
- Users do not need a separate Python environment.

### 3. Installation Documentation

Update installation instructions for Windows and Linux.

Document macOS only to the extent supported and verified.

Prioritize prebuilt release binaries.

Provide accurate installation and configuration examples based on the actual implementation.

Do not invent command-line flags, installation scripts, or supported platforms.

### 4. Developer Documentation

Update development instructions for the Go implementation.

Include:

- Go development prerequisites.
- Repository structure.
- Build commands.
- Unit and integration tests.
- MCP Bridge debugging.
- Shared IPC Service debugging.
- RenderDoc Extension development.
- Cross-platform validation.

Python development instructions should remain only where necessary for the RenderDoc Extension or explicitly maintained compatibility tests.

### 5. Remove Obsolete Documentation

Review all active documentation for obsolete references to:

- Python MCP Bridge installation.
- Python Shared IPC Service installation.
- uv-based user installation.
- pip-based user installation.
- Python virtual environments for MCP execution.
- Legacy Python entry points.
- Outdated architecture diagrams.
- Obsolete MCP configuration examples.

Remove or rewrite these references as appropriate.

Do not delete historical design records or test fixtures merely because they reference Python.

### 6. No Migration Documentation

Do not create:

- Python-to-Go migration guides.
- Legacy installation upgrade tutorials.
- Python rollback procedures for end users.
- Separate legacy Python user documentation.

The Go implementation is the primary documented implementation.

Internal compatibility and regression testing may remain where technically necessary.

### 7. English and Japanese Documentation

Maintain consistent English and Japanese documentation.

Both languages must describe the same installation requirements, architecture, commands, and supported capabilities.

Avoid maintaining conflicting instructions.

### 8. Documentation Validation

Verify:

- Every documented command against the actual CLI.
- Every referenced path and file.
- Release artifact names.
- MCP configuration examples.
- RenderDoc Extension installation steps.
- Platform support claims.
- Internal documentation links.

Do not claim functionality or platform support that has not been implemented or verified.

## Acceptance Criteria

1. A new user can install and configure RenderEyeMCP using the Go release artifacts without reading about the legacy Python infrastructure.
2. README.md accurately describes the current Go implementation.
3. All active installation and usage documentation is consistent.
4. The RenderDoc Python Extension is correctly documented.
5. No unnecessary Python-to-Go migration documentation is introduced.
6. Existing compatibility tests and historical development records remain intact where useful.
7. English and Japanese documentation are aligned.

## Constraints

- Do not change MCP Tool contracts.
- Do not change the IPC protocol.
- Do not change runtime behavior solely to simplify documentation.
- Do not remove required RenderDoc Extension Python dependencies.
- Do not publish a release as part of this task.

## Deliverables

- Updated README.md.
- Updated English and Japanese documentation.
- Updated architecture documentation.
- Updated installation and development guides.
- Removal or correction of obsolete active documentation.
- A summary of modified files and documentation validation results.
