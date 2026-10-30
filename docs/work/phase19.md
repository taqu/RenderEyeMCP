# Phase 19 — Single Binary & Cross-Platform Distribution

## Objective

Simplify RenderEyeMCP installation and distribution by combining the Go MCP Bridge and Go Shared IPC Service into a **single executable with multiple operating modes**, while preserving their existing independent-process architecture.

Phase 19 builds on:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 16 — IPC Protocol Contract & Compatibility Tests.
- Phase 17 — Go Shared IPC Service Migration.
- Phase 18 — Go MCP Bridge Migration.

At the end of Phase 18, the expected architecture is:

```text
Claude Code ── Go MCP Bridge A ──┐
                                │
Codex ─────── Go MCP Bridge B ──┼── Go Shared IPC Service
                                │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

Phase 19 must preserve this architecture while replacing the separately distributed Go executables with one executable supporting both roles.

The target architecture is:

```text
Claude Code ── rendereye-mcp ──┐
                               │
Codex ─────── rendereye-mcp ──┼── rendereye-mcp service
                               │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

Each coding agent launches its own MCP Bridge process.

The Shared IPC Service remains a separate process, but it is started using the same executable.

The primary user-facing goal is:

**Install RenderDoc, install RenderEyeMCP, configure a coding agent, and start debugging without installing or managing Python, uv, pip, Go, or a virtual environment.**

Preserve the existing Python RenderDoc Extension and its access to RenderDoc's embedded Python environment.

Do not rewrite the Extension in Go.

---

## 1. Inspect Existing Implementation

Before making changes, investigate the actual repository.

Identify:

1. Phase 17 Go Shared IPC Service entry point.
2. Phase 18 Go MCP Bridge entry point.
3. Shared Go modules and packages.
4. IPC protocol implementation.
5. Service startup and discovery.
6. Single-service ownership and startup coordination.
7. Client registration and reconnection.
8. Existing configuration behavior.
9. RenderDoc Extension installation and loading.
10. Current Python installation and distribution mechanisms.
11. Current Go build procedures.
12. Existing GitHub Actions workflows.
13. Current GitHub Releases packaging.
14. Existing installer scripts.
15. English and Japanese documentation.
16. Existing CI tests and release validation.

Establish the current behavior before modifying architecture.

Do not assume the original roadmap accurately describes every implemented component.

### 1.1 Verify Phase 17 and Phase 18 Readiness

Confirm that:

- The Go Shared IPC Service is functional.
- The Go MCP Bridge is functional.
- The Python RenderDoc Extension can communicate with the Go service.
- MCP Tool definitions and results remain compatible.
- Multiple Go Bridges can use the same service.
- Existing protocol tests pass.
- Real RenderDoc integration tests have been executed where an appropriate environment is available.

Document any outstanding migration issues.

Do not use Phase 19 packaging work to hide unresolved Phase 17 or Phase 18 incompatibilities.

### 1.2 Establish a Baseline

Record:

- Current executable names.
- Current startup commands.
- Default IPC endpoint.
- Configuration variables.
- Service lifecycle behavior.
- Installation directory assumptions.
- Existing package contents.
- Supported platforms.

This baseline will be used to verify that single-binary packaging does not change existing functionality.

---

## 2. Single Executable Architecture

Combine the Go MCP Bridge and Shared IPC Service into one executable.

### 2.1 Required Operating Modes

The executable must support at least:

**Default mode — MCP Bridge**

```shell
rendereye-mcp
```

This mode starts the MCP stdio server used by coding agents.

**Service mode — Shared IPC Service**

```shell
rendereye-mcp service
```

This mode starts the independent Shared IPC Service.

On Windows:

```powershell
rendereye-mcp.exe
rendereye-mcp.exe service
```

The command names are illustrative. Preserve the actual established executable name where appropriate.

### 2.2 Separate Processes

The executable must not run the Shared IPC Service inside each MCP Bridge process.

The required model is:

```text
Process A: rendereye-mcp        (MCP Bridge)
Process B: rendereye-mcp        (MCP Bridge)
Process C: rendereye-mcp service
```

Process C is shared by Processes A and B.

### 2.3 Reuse Existing Go Implementations

Do not duplicate service or Bridge logic in the combined entry point.

Prefer a thin application dispatcher that invokes the existing packages.

An illustrative project structure:

```text
go/
  cmd/
    rendereye-mcp/
      main.go

  internal/
    app/
      ...
    mcpbridge/
      ...
    ipcservice/
      ...
    ipcclient/
      ...
    protocol/
      ...
    config/
      ...
```

Use existing repository structure where possible.

### 2.4 CLI Dispatch

Default execution must enter MCP Bridge mode.

The `service` subcommand must enter Shared IPC Service mode.

Additional commands may include:

- `version`
- `help`
- `doctor`

Implement only those that provide a clear user or maintenance benefit.

Do not add a large command-line framework unnecessarily.

### 2.5 Protocol-Clean stdout

In default MCP mode, stdout must contain only valid MCP protocol traffic.

Do not print:

- Startup banners.
- Version messages.
- Service startup diagnostics.
- Configuration summaries.
- Log output.

Write diagnostics to stderr or an appropriate log file.

The same requirement applies when the Bridge automatically launches the service.

---

## 3. Shared IPC Service Discovery

The MCP Bridge must discover and use the existing Shared IPC Service.

### 3.1 Default Endpoint

Preserve the existing default endpoint:

```text
127.0.0.1:37020
```

Continue supporting configured alternative endpoints according to the existing implementation.

### 3.2 Connection-First Behavior

When a Bridge starts:

1. Attempt to connect to an existing service.
2. Verify the service using the established IPC protocol.
3. Reuse the service if it is compatible and ready.
4. Start a service only if no suitable service is available and automatic startup is permitted.
5. Wait for readiness using bounded retries.
6. Register the Bridge with the service.

Do not start a new service unconditionally.

### 3.3 Service Identity

A successful TCP connection alone does not prove that the listener is RenderEyeMCP.

Use the existing protocol's identity or readiness mechanism where available.

If the protocol lacks reliable identification, investigate a backward-compatible solution consistent with Phase 16.

Do not terminate another process merely because it occupies the configured port.

### 3.4 Explicit Service Mode

The `service` command must also be suitable for direct execution during development and diagnostics.

It must not require a running MCP Bridge.

---

## 4. Concurrent Startup and Single-Service Ownership

This is a critical requirement.

Multiple coding agents may launch RenderEyeMCP at nearly the same time.

### 4.1 Required Scenario

```text
Claude Code ── Bridge A ──┐
                          ├── One Shared IPC Service
Codex ─────── Bridge B ──┘
```

Both Bridges may initially observe that no service is running.

The implementation must avoid two competing service processes.

### 4.2 Preserve Phase 6 Behavior

Investigate the existing startup election or ownership mechanism.

Reuse it where possible.

Do not regress the Phase 6 solution to competing IPC listeners.

### 4.3 Atomic Ownership

Use an appropriate coordination mechanism so competing startup attempts resolve safely.

Potential mechanisms include:

- Atomic endpoint binding.
- OS-specific process locks.
- Existing lock-file ownership.
- Existing service-election logic.

Choose according to the actual architecture.

Do not rely on a check-then-start sequence without protection against races.

### 4.4 Race Resolution

If one process wins ownership:

- The winning service starts normally.
- Other attempted service processes terminate safely.
- Their Bridges connect to the winning service.
- No existing healthy service is killed.

### 4.5 Service Readiness

A successful process spawn does not mean the service is ready.

Wait for actual IPC readiness.

Use bounded retry behavior.

Do not block MCP startup indefinitely.

### 4.6 Startup Failure

Handle:

- Executable missing.
- Permission denied.
- Port conflict.
- Unsupported service protocol.
- Invalid configuration.
- Service crash during startup.
- Service not becoming ready.

Return useful diagnostics without corrupting MCP stdout.

---

## 5. Service Process Lifecycle

The Shared IPC Service must remain independent of individual MCP Bridge lifetimes.

### 5.1 Starting the Service

Use the current executable path to launch service mode.

Do not rely on:

- The current working directory.
- PATH containing the executable.
- A developer-specific absolute path.
- Python or uv commands.

Resolve the executable path using an appropriate platform-supported mechanism.

### 5.2 Process Detachment

Investigate correct subprocess behavior on each operating system.

The service must not be unintentionally terminated when its launching Bridge exits.

Account for:

- Windows process handles and Job Objects.
- POSIX process groups and sessions.
- Signal propagation.
- Parent process termination.
- stdin/stdout/stderr inheritance.

Do not assume that a detached process behaves identically on Windows, Linux, and macOS.

### 5.3 No Unnecessary External Supervisor

Do not require users to configure:

- Windows Services.
- systemd services.
- launchd services.

These may be optional future deployment mechanisms.

Default installation should work without them.

### 5.4 Bridge Termination

When one Bridge exits:

- Close its IPC connection.
- Release Bridge resources.
- Preserve the shared service for other clients.
- Do not terminate RenderDoc.

### 5.5 Service Lifetime

Investigate existing daemon shutdown behavior.

Preserve established semantics where possible.

Decide and document whether the service:

- Remains active until explicitly stopped.
- Exits after a bounded idle period.
- Follows another existing lifecycle policy.

Do not introduce unexplained automatic termination.

### 5.6 Service Restart

If the service stops unexpectedly:

- Connected Bridges must detect disconnection.
- Reconnection behavior must follow the established policy.
- The service must be restartable without stale ownership state.
- Capture/session state must be resynchronized.

Avoid implementing a new general-purpose process supervisor unless required.

### 5.7 Explicit Shutdown

If the project already has a safe service shutdown mechanism, preserve it.

Do not introduce a command that can arbitrarily terminate an unrelated process.

---

## 6. Configuration and Installation Paths

Preserve existing configuration semantics.

### 6.1 Existing Environment Support

Investigate and retain relevant settings, including:

```text
RENDEREYE_ENV_FILE
```

Verify the current configuration-loading behavior.

### 6.2 Configuration File

If the project uses a `.env` file, preserve support for it.

An illustrative installation:

```text
RenderEyeMCP/
  rendereye-mcp.exe
  .env
  extension/
    ...
```

Do not require the installation directory to be writable at runtime.

### 6.3 Configuration Precedence

Preserve the current precedence among:

- Command-line arguments.
- Process environment variables.
- Explicit environment file.
- Default configuration values.

Document the actual precedence.

### 6.4 Path Resolution

Support:

- Paths with spaces.
- Unicode paths.
- User installation directories.
- System installation directories.
- Non-default RenderDoc installation paths.

Avoid hardcoded assumptions such as a particular developer's drive or username.

### 6.5 Windows RenderDoc Location

Retain support for the common default path:

```text
C:\Program Files\RenderDoc\
```

Do not require RenderDoc to be installed there.

### 6.6 Service Environment

When the Bridge launches service mode, pass the required configuration environment explicitly and safely.

Do not assume all relevant settings will be inherited correctly without verification.

---

## 7. RenderDoc Extension Packaging

The RenderDoc Extension remains Python-based.

The Go migration must not change its responsibility for accessing RenderDoc APIs.

### 7.1 Extension Inventory

Inspect the existing Extension and determine:

- Required Python files.
- Required resource files.
- Extension entry point.
- Registration mechanism.
- Supported RenderDoc versions.
- Existing installation procedure.
- External Python package dependencies, if any.

### 7.2 No User-Managed Python Requirement

The intended installation must not require a separate Python runtime for the MCP Bridge or Shared IPC Service.

If the RenderDoc Extension can run entirely using RenderDoc's embedded Python environment, preserve that behavior.

If external Python dependencies are required, investigate whether they can be eliminated or packaged without requiring users to manage Python.

Do not claim a Python-free installation until this is verified.

### 7.3 Include the Extension

Official release archives must contain all files needed for the Extension.

Do not publish a Go executable alone if the user would then need to obtain Extension sources manually.

### 7.4 Installation

Reuse the existing supported Extension installation mechanism.

Where practical, provide a simple installation script that:

1. Detects an existing RenderDoc installation.
2. Determines the appropriate Extension destination.
3. Installs the required files.
4. Preserves existing user configuration.
5. Reports the result.

Do not modify arbitrary RenderDoc directories based on guesses.

### 7.5 Permissions

Handle installation locations requiring elevated privileges appropriately.

Do not silently request administrator privileges when a supported per-user installation mechanism is available.

### 7.6 Extension Updates

Define how upgrading RenderEyeMCP updates the Extension.

Avoid leaving incompatible old Extension files behind.

Document whether restarting RenderDoc is required.

### 7.7 Compatibility

Verify the Extension connects to the combined executable's service mode without IPC changes.

---

## 8. Windows Distribution

Windows is the primary supported platform.

### 8.1 Target Architectures

Provide Windows binaries for supported architectures.

At minimum, evaluate:

```text
windows/amd64
windows/arm64
```

Only publish an architecture as supported when its runtime behavior is sufficiently verified.

### 8.2 Executable

Produce a native Windows executable:

```text
rendereye-mcp.exe
```

It must not require Go or Python to run the MCP Bridge and Shared IPC Service.

### 8.3 Distribution Archive

An illustrative archive layout:

```text
rendereye-mcp_0.1.0_windows_amd64.zip
  rendereye-mcp.exe
  extension/
    ...
  install.ps1
  README.md
  LICENSE
```

Use the actual license and package version from the repository.

Do not assume a license value without verifying it.

### 8.4 Installation Script

Provide an optional PowerShell installer that:

- Finds the current archive contents.
- Installs the executable into a predictable location.
- Installs or configures the RenderDoc Extension.
- Generates necessary configuration files.
- Preserves existing settings.
- Reports the executable path.
- Explains coding-agent configuration.

The script must not require Python, uv, or pip.

### 8.5 Manual Installation

Maintain a manual installation path.

Users should not be forced to run an installer script.

Document where to place the executable and Extension files.

### 8.6 Upgrade Behavior

Repeated installation should be safe.

Do not overwrite user-managed configuration without approval or a compatible merge strategy.

### 8.7 Uninstallation

Document how to remove installed files.

Avoid deleting unrelated RenderDoc or coding-agent configuration.

---

## 9. Linux Distribution

Prepare and validate native Linux distribution.

### 9.1 Target Architectures

Evaluate:

```text
linux/amd64
linux/arm64
```

### 9.2 Runtime Independence

Prefer binaries without additional nonstandard runtime dependencies where feasible.

Investigate whether CGO is necessary.

Do not force `CGO_ENABLED=0` if a required dependency cannot operate without CGO.

### 9.3 Packaging

An illustrative archive:

```text
rendereye-mcp_0.1.0_linux_amd64.tar.gz
  rendereye-mcp
  extension/
    ...
  install.sh
  README.md
  LICENSE
```

### 9.4 Installation

Provide installation instructions covering:

- Executable placement.
- Executable permissions.
- Configuration files.
- RenderDoc Extension installation.
- Coding-agent MCP configuration.

### 9.5 Linux Paths

Use Linux-appropriate configuration and installation paths.

Do not assume Windows directory layouts.

### 9.6 Runtime Validation

Where Linux RenderDoc is available, validate:

- Extension loading.
- Shared IPC Service startup.
- Capture discovery.
- Basic inspection.
- Multi-agent operation.

Do not claim full Linux support based only on successful cross-compilation.

---

## 10. macOS Distribution

Investigate and support macOS to the extent justified by the actual RenderDoc environment.

### 10.1 Target Architectures

Evaluate:

```text
darwin/amd64
darwin/arm64
```

### 10.2 Go Executable Support

The Go MCP Bridge and Shared IPC Service should compile and run independently of RenderDoc where possible.

### 10.3 RenderDoc Compatibility

Investigate whether the required RenderDoc GUI, Python Extension, and Replay APIs are available and usable on macOS.

Do not assume that native Go binaries imply full RenderEyeMCP functionality on macOS.

### 10.4 Support Classification

Distinguish:

- Go binary builds successfully.
- MCP Bridge starts.
- IPC Service operates.
- RenderDoc Extension is available.
- Full capture inspection works.

Publish or label macOS artifacts based on validated capability levels.

If RenderDoc integration is unavailable, do not advertise a fully functional macOS RenderEyeMCP release.

### 10.5 Distribution Requirements

Investigate executable permissions, quarantine, code signing, and notarization requirements where relevant.

Do not claim the binary is signed or notarized unless the actual release process performs those steps.

Do not introduce mandatory proprietary developer-account requirements merely to complete basic Go compilation.

---

## 11. Unified Versioning

Use one project version for the combined executable and release artifacts.

### 11.1 Version Information

Embed relevant build metadata such as:

- Project version.
- Git revision.
- Build target.
- Build date, where useful.
- Protocol compatibility information, where available.

Do not expose sensitive build paths.

### 11.2 Version Command

Provide:

```shell
rendereye-mcp version
```

The output should identify the installed build without starting MCP mode.

### 11.3 Protocol Compatibility

The combined executable contains both Bridge and Service implementations, but the RenderDoc Extension may be updated independently.

Document relevant compatibility expectations.

Do not introduce an arbitrary incompatible protocol version solely because the executable format changed.

### 11.4 Version Source

Reuse the existing release versioning mechanism where practical.

Do not introduce competing version sources for Go binaries and Python Extension files.

### 11.5 Deterministic Builds

Use reproducible or traceable build inputs where practical.

Ensure that the version displayed by the executable matches the distribution archive.

---

## 12. GitHub Actions Release Pipeline

Add or update GitHub Actions to build platform-specific release artifacts.

### 12.1 Existing Workflow Review

Inspect:

```text
.github/workflows/
```

Identify existing:

- Go test workflows.
- Release workflows.
- PyPI publishing workflows.
- TestPyPI publishing workflows.
- Installer build workflows.

Do not replace unrelated workflows unnecessarily.

### 12.2 Preserve PyPI Workflow Separation

The project previously established separate workflows:

```text
publish-testpypi.yml
publish-pypi.yml
```

Keep their publishing destinations independent.

Do not merge PyPI publishing into the Go binary release workflow.

### 12.3 Go Binary Release

Prefer a separate workflow for GitHub Releases distribution.

For example:

```text
.github/workflows/release-go.yml
```

Use existing naming conventions where appropriate.

### 12.4 Build Matrix

Build supported combinations of:

- Windows.
- Linux.
- macOS, where appropriate.
- Relevant CPU architectures.

### 12.5 Build and Package

For every supported target:

1. Check out the tagged source.
2. Set up the supported Go toolchain.
3. Run applicable tests.
4. Build the combined executable.
5. Verify version information.
6. Include Extension resources.
7. Include appropriate installation scripts.
8. Package the release archive.
9. Generate checksums.
10. Upload the artifact for publication.

### 12.6 Release Safety

Do not create or publish a production GitHub Release automatically during Phase 19 implementation without explicit authorization.

Support local packaging and CI artifact validation before official publication.

### 12.7 Artifact Integrity

Generate SHA-256 checksums for release archives.

Use established GitHub Actions security practices and the repository's action-pinning policy.

Avoid broad write permissions for ordinary build jobs.

### 12.8 Native Testing

Where feasible, run binaries on native runners rather than relying only on cross-compilation.

### 12.9 Artifact Contents

Validate that archives contain the expected executable, Extension resources, and documentation.

Do not publish incomplete release archives.

---

## 13. Installation Experience

The primary objective of Phase 19 is installation simplicity.

### 13.1 Target User Workflow

A Windows user should be able to:

1. Download the appropriate release archive.
2. Extract it or run a provided installer.
3. Install the RenderDoc Extension.
4. Register the executable with a coding agent.
5. Open a RenderDoc capture.
6. Ask the coding agent to inspect it.

No Python environment setup should be required.

### 13.2 Minimize Configuration

Use sensible defaults for:

- IPC endpoint.
- Service discovery.
- Service autostart.
- Local logging.
- Extension integration.

Require explicit configuration only when necessary.

### 13.3 No Persistent Service Setup Required

Users should not need to manually start the Shared IPC Service every time they use RenderEyeMCP.

The MCP Bridge must handle service discovery and startup according to the established lifecycle policy.

### 13.4 Diagnostics

Provide useful diagnostics for:

- RenderDoc not installed.
- Extension not installed.
- Extension not loaded.
- Shared IPC Service unavailable.
- IPC port occupied by another program.
- Configuration errors.
- Version incompatibility.

A lightweight `doctor` command is acceptable if it materially improves setup troubleshooting.

It must not launch RenderDoc or modify user configuration unless explicitly requested.

### 13.5 Idempotence

Repeated installation must not corrupt an existing working installation.

Preserve user-managed configuration.

---

## 14. Coding Agent Configuration

Document the native executable configuration for each supported coding agent.

### 14.1 Claude Code

Provide tested instructions for registering the executable as an MCP stdio server.

Use the actual supported Claude Code configuration format.

### 14.2 Codex

Provide tested instructions for registering the executable with Codex.

Use the actual supported Codex configuration format.

### 14.3 Other MCP Clients

Document generic stdio configuration.

Do not claim support for a particular client without appropriate verification.

### 14.4 Example

An illustrative MCP configuration:

```json
{
  "mcpServers": {
    "rendereye": {
      "command": "C:\\Tools\\RenderEyeMCP\\rendereye-mcp.exe"
    }
  }
}
```

This is a conceptual example.

Adapt the configuration to each actual coding agent.

### 14.5 No Environment Setup

The user-facing MCP command must not require:

```text
python
pip
uv
go run
```

Use the installed executable directly.

### 14.6 Multi-Agent Configuration

Two agents should be able to register the same executable path.

Each launches an independent Bridge process, and both connect to one Shared IPC Service.

---

## 15. Migration from Python Installations

Existing RenderEyeMCP users may have Python-based installations.

Provide a non-destructive migration path.

### 15.1 Detect Existing Installation

Investigate existing:

- Python MCP entry points.
- Virtual environments.
- `.env` files.
- Installed Extension versions.
- Coding-agent configurations.
- Shared IPC Service processes.

### 15.2 Preserve Configuration

Avoid deleting or overwriting existing user configuration.

### 15.3 Bridge Migration

Update coding-agent MCP configurations to use the Go executable.

Provide clear manual instructions and automate only where safe.

Do not silently modify all installed coding agents.

### 15.4 Service Migration

Do not run the old Python Shared IPC Service and new Go Shared IPC Service simultaneously on the same endpoint.

Ensure a controlled switch.

### 15.5 Extension Compatibility

Verify that the existing Extension can communicate with the Go service.

Where an Extension update is required, document it.

### 15.6 Rollback

Document how to return temporarily to the Python installation.

Do not remove the Python implementation during Phase 19.

### 15.7 Existing PyPI Users

Keep existing PyPI publishing and installation behavior intact unless explicitly changed by a separate migration decision.

Do not make the release pipeline depend on deleting or deprecating the Python package.

---

## 16. Security Considerations

Single-binary distribution must not weaken existing security properties.

### 16.1 Loopback Binding

Keep the IPC Service bound to the intended local interface by default.

Do not expose the service publicly.

### 16.2 Local Client Security

Review existing assumptions about local IPC clients.

Loopback TCP alone does not prove that a connecting process is trusted.

Document supported trust boundaries.

### 16.3 Process Launch

Do not execute arbitrary commands from unvalidated IPC messages.

When spawning service mode, use the known executable path and controlled arguments.

### 16.4 Installation Scripts

Installation scripts must:

- Operate on expected files.
- Avoid unrelated directory deletion.
- Use safe path handling.
- Preserve user configuration.
- Avoid unnecessary elevation.

### 16.5 Release Integrity

Publish checksums.

Document how users can verify downloaded archives.

### 16.6 Secrets

Do not embed credentials or publishing tokens in distributed binaries or archives.

### 16.7 Logs

Avoid recording sensitive capture payloads by default.

---

## 17. Automated Testing

Extend existing tests to cover single-binary execution.

### 17.1 CLI Tests

Verify:

- Default mode starts the MCP Bridge.
- `service` starts the IPC Service.
- `version` reports correct metadata.
- Invalid arguments are handled predictably.
- MCP stdout remains protocol-clean.

### 17.2 Startup Tests

Verify:

- Bridge connects to an existing service.
- Bridge starts a missing service.
- Bridge waits for readiness.
- Two Bridges start simultaneously.
- Only one service becomes active.
- Service startup failure is reported clearly.

### 17.3 Lifecycle Tests

Verify:

- One Bridge exits without terminating the service.
- Another Bridge continues operating.
- Service restart is handled.
- Stale startup ownership is cleaned up.
- Unexpected service termination is detected.

### 17.4 Protocol Tests

Reuse Phase 16 protocol fixtures and Phase 17 compatibility tests.

Single-binary packaging must not modify the wire protocol.

### 17.5 MCP Tests

Reuse Phase 18 MCP contract and Tool compatibility tests.

No Tool should change behavior because of packaging.

### 17.6 Archive Tests

For each artifact, verify:

- Expected executable exists.
- Expected Extension files exist.
- Executable version is correct.
- Required documentation exists.
- Archive paths are valid.
- Checksums are correct.

### 17.7 Installation Tests

Where possible, install into a clean environment.

Verify:

- Installation succeeds.
- Executable launches.
- Configuration loads.
- Extension files are in the expected location.
- Reinstallation is safe.
- Uninstallation instructions are accurate.

### 17.8 Platform Tests

Run native tests where possible.

Distinguish compilation success from actual integration success.

---

## 18. End-to-End RenderDoc Testing

Use real RenderDoc captures to validate the distribution.

### 18.1 Clean Windows Installation

Perform a test without relying on a developer's Python virtual environment.

Test:

1. Install RenderDoc.
2. Install RenderEyeMCP from the release archive.
3. Install the Extension.
4. Configure Claude Code or Codex.
5. Open a capture.
6. Discover the capture.
7. Retrieve an event.
8. Inspect pipeline state and resources.

The test environment must not depend on repository-local Python tooling.

### 18.2 Two-Agent Test

Connect Claude Code and Codex simultaneously.

Verify:

- Two Bridge processes.
- One Shared IPC Service.
- Correct session discovery.
- Correct request routing.
- No port conflicts.
- Independent client shutdown.

### 18.3 Advanced Operations

Where implemented, test representative:

- Texture inspection.
- GPU performance collection.
- Geometry inspection.
- Pixel History.
- Shader debugging.

Do not claim these capabilities are tested merely because the MCP Bridge connects.

### 18.4 Linux Integration

Where available, perform the corresponding installation and capture inspection tests on Linux.

### 18.5 macOS Validation

Report exactly what is supported and what is blocked by RenderDoc availability or platform-specific restrictions.

### 18.6 No Developer Environment Assumptions

The final release should not require:

- Running commands from the repository.
- A checked-out source tree.
- Python packages installed by the developer.
- Go installed on the machine.
- Hardcoded local paths.

---

## 19. Cross-Platform Support Matrix

Maintain a clear support matrix.

Suggested format:

| Platform | Binary | IPC | MCP | RenderDoc Integration | Status |
|---|---|---|---|---|---|
| Windows amd64 | Test | Test | Test | Test | Verified when passed |
| Windows arm64 | Test | Test | Test | Test | Based on actual results |
| Linux amd64 | Test | Test | Test | Test | Based on actual results |
| Linux arm64 | Test | Test | Test | Test | Based on actual results |
| macOS amd64 | Test | Test | Test | Investigate | Capability-limited |
| macOS arm64 | Test | Test | Test | Investigate | Capability-limited |

Populate the final matrix using actual test results.

Do not label a target fully supported merely because the executable compiles.

---

## 20. Bilingual Documentation

Update English and Japanese documentation.

Suggested files:

```text
README.md
README.ja.md

docs/
  en/
    installation.md
    configuration.md
    quickstart.md
    troubleshooting.md

  ja/
    installation.md
    configuration.md
    quickstart.md
    troubleshooting.md
```

Adapt to existing documentation organization.

### 20.1 README

The README should prominently explain:

- What RenderEyeMCP does.
- Required RenderDoc installation.
- Native executable download.
- Simple installation.
- Coding-agent setup.
- Basic usage.
- Supported platforms.

### 20.2 Installation

Provide instructions for:

- Windows.
- Linux.
- macOS, within actual support limits.
- Manual installation.
- Optional installation scripts.
- Upgrading.
- Uninstalling.

### 20.3 Quick Start

A new user should be able to follow:

1. Install RenderDoc.
2. Install RenderEyeMCP.
3. Configure a coding agent.
4. Open a capture.
5. Ask the agent to inspect it.

### 20.4 Architecture

Explain the single-binary, multiple-process architecture.

Avoid claiming the system runs entirely in one process.

### 20.5 Troubleshooting

Cover:

- Service does not start.
- Port is already occupied.
- Extension not found.
- RenderDoc not detected.
- No capture available.
- Coding agent cannot connect.
- Invalid configuration.
- Version mismatch.

### 20.6 Python Migration

Explain how existing Python users can migrate without losing configuration.

### 20.7 Documentation Accuracy

Only document supported, tested behavior as available.

Maintain equivalent English and Japanese instructions.

---

## 21. Implementation Order

Follow this sequence.

### Step 1 — Existing Implementation Review

Verify Phase 17 and Phase 18 behavior and inspect installation infrastructure.

### Step 2 — Unified CLI Entry Point

Combine the existing Go Bridge and Service behind one executable.

### Step 3 — Service Discovery

Implement connection-first service reuse.

### Step 4 — Service Autostart

Launch the same executable in service mode where required.

### Step 5 — Concurrent Startup Safety

Validate two simultaneous Bridge launches and single-service ownership.

### Step 6 — Lifecycle Hardening

Handle process detachment, shutdown, restart, and cleanup.

### Step 7 — Configuration

Preserve existing configuration behavior and path handling.

### Step 8 — Extension Packaging

Include required RenderDoc Extension files.

### Step 9 — Windows Distribution

Create and validate the Windows archive and installation instructions.

### Step 10 — Linux Distribution

Create and validate Linux artifacts where supported.

### Step 11 — macOS Investigation

Build and test supported components, document RenderDoc integration limits.

### Step 12 — Release Automation

Add cross-platform builds, packaging validation, and checksums.

### Step 13 — Clean Installation Testing

Validate installation without Python, uv, pip, or Go.

### Step 14 — Multi-Agent E2E Testing

Verify simultaneous Claude Code and Codex operation.

### Step 15 — Documentation and Migration

Finalize bilingual documentation and rollback instructions.

Do not introduce the release workflow before verifying the combined executable works locally.

---

## 22. Scope Restrictions

Do not implement:

- New RenderDoc debugging features.
- New GPU analysis tools.
- New MCP Tool APIs.
- IPC protocol redesign.
- RenderDoc Extension rewrite in Go.
- A new transport protocol.
- A mandatory system service.
- A background auto-update daemon.
- Automatic Python installation removal.
- Mandatory cloud infrastructure.
- A new package manager.
- Vendor-specific GPU integrations.
- Major UI development.

Do not remove the existing Python implementation during this phase.

Do not merge PyPI and TestPyPI publishing workflows.

---

## 23. Acceptance Criteria

Phase 19 is complete when:

- [ ] One Go executable supports both MCP Bridge and Shared IPC Service modes.
- [ ] Default execution starts the MCP stdio server.
- [ ] Explicit service mode starts the standalone IPC Service.
- [ ] Bridge and Service remain separate processes.
- [ ] The existing IPC protocol remains compatible.
- [ ] Existing MCP Tool contracts remain compatible.
- [ ] An existing Shared IPC Service is reused.
- [ ] A missing service can be started automatically where configured.
- [ ] Concurrent Bridge startup results in one active service.
- [ ] Port conflicts are handled safely.
- [ ] An unrelated process on the IPC port is not terminated.
- [ ] Service readiness is checked before client registration.
- [ ] Bridge shutdown does not terminate other Bridges or the shared service.
- [ ] Service restart behavior is verified.
- [ ] Configuration and environment-file behavior remain compatible.
- [ ] MCP stdout contains only protocol messages.
- [ ] The executable runs without user-managed Python, uv, pip, or Go.
- [ ] Required RenderDoc Extension resources are included in release packaging.
- [ ] Extension installation is documented and tested.
- [ ] Windows release artifacts are generated.
- [ ] Linux release artifacts are generated for validated targets.
- [ ] macOS support is accurately classified.
- [ ] GitHub Actions build and validate release archives.
- [ ] SHA-256 checksums are generated.
- [ ] Clean installation is tested on Windows.
- [ ] Reinstallation and upgrade behavior are verified.
- [ ] Existing Python installations have a documented migration and rollback path.
- [ ] Existing PyPI and TestPyPI workflows remain separate.
- [ ] Claude Code can use the combined executable.
- [ ] Codex can use the combined executable.
- [ ] Two coding agents can operate simultaneously.
- [ ] Real RenderDoc capture inspection works through the distributed build.
- [ ] Existing Phase 16–18 tests remain passing.
- [ ] English documentation is updated.
- [ ] Japanese documentation is updated.
- [ ] Platform support claims match actual validation results.
- [ ] Known limitations are documented.
- [ ] No production release is published without explicit authorization.

If a platform or feature cannot be tested, report it as unverified.

Do not mark cross-platform integration complete based only on compilation.

---

## 24. Deliverables

### A. Single Go Executable

Provide:

- Unified executable entry point.
- MCP Bridge mode.
- Shared IPC Service mode.
- Service discovery.
- Automatic startup.
- Multi-process lifecycle handling.

### B. Distribution Infrastructure

Provide:

- Windows build.
- Linux build.
- macOS builds where appropriate.
- Release archives.
- Checksums.
- GitHub Actions release workflow.
- Archive validation tests.

### C. Installation

Provide:

- Windows installation script or equivalent.
- Linux installation script or equivalent.
- Manual installation instructions.
- RenderDoc Extension installation.
- Configuration setup.
- Upgrade and uninstall documentation.

### D. Testing

Provide:

- CLI tests.
- Startup race tests.
- Service lifecycle tests.
- IPC compatibility tests.
- MCP compatibility tests.
- Installation tests.
- Multi-agent integration tests.
- Platform-specific test results.

### E. Documentation

Provide:

- English quick start.
- Japanese quick start.
- Platform-specific installation instructions.
- Configuration reference.
- Troubleshooting guide.
- Python-to-Go migration guide.

### F. Completion Report

Summarize:

- Implemented changes.
- Generated release artifacts.
- Tests executed.
- Supported operating systems.
- Unverified platforms.
- Known limitations.
- Remaining migration work.
- Phase 20 recommendations.

---

## Final Goal

After Phase 19, a Windows developer should be able to:

1. Install RenderDoc.
2. Download the RenderEyeMCP release.
3. Install or copy the required files.
4. Configure Claude Code or Codex to launch `rendereye-mcp.exe`.
5. Open a capture in RenderDoc.
6. Ask the coding agent to inspect it.

The coding agent launches an independent MCP Bridge process.

The Bridge automatically connects to or starts the Shared IPC Service, which is implemented by the same executable running in a separate process.

Multiple coding agents share the service without port conflicts.

The RenderDoc Extension continues to access RenderDoc's Replay APIs through its existing Python integration.

No separate Python environment, uv installation, or Go toolchain is required for normal use.

**Phase 19 is successful when RenderEyeMCP becomes a straightforward native installation while preserving its established multi-agent and RenderDoc integration architecture.**

The next phase, Phase 20, should focus on reliability hardening, migration completion, compatibility maintenance, and deciding when the legacy Python MCP infrastructure can be deprecated.
