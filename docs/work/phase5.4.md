# RenderEyeMCP — Phase 5.2 Addendum: User Installation & Coding Agent MCP Configuration

## Objective

Redesign and implement the end-user installation and coding agent integration workflows for RenderEyeMCP.

The recommended installation method must use **`uv tool install`**, which installs RenderEyeMCP as an independent, persistent CLI application without requiring users to clone the repository, manually create a virtual environment, or manage Python dependencies.

The existing standard Python installation method must remain supported for users who do not want to install `uv`.

Development and testing instructions must be completely separated from end-user installation instructions.

The implementation must also provide a unified command-line interface for setting up RenderDoc integration and configuring major coding agents.

**Implement the installation and configuration functionality, not just the documentation.**

---

## 1. Installation Architecture

RenderEyeMCP must distinguish between three separate concerns.

### Application Installation

The Python application, its dependencies, and console entry points are managed by the selected Python package installer.

For `uv tool install`, allow `uv` to manage the application environment.

Do not manually copy the Python package into `%LOCALAPPDATA%\RenderEyeMCP\venv` when using `uv tool install`.

### Application Configuration and Data

Store persistent RenderEyeMCP configuration independently from the Python installation.

Default Windows location:

```text
%LOCALAPPDATA%\RenderEyeMCP\
├── .env
├── data\
└── logs\
```

Use appropriate user-local directories on Linux.

### RenderDoc Extension

Install the extension into the RenderDoc-supported user extension directory.

For Windows, investigate and verify:

```text
%APPDATA%\qrenderdoc\extensions\rendereye\
```

Do not install extension files into the Python environment.

Do not modify the RenderDoc executable or production engine.

### Important Principle

Application installation, application configuration, and RenderDoc extension installation must remain independent.

Reinstalling or upgrading the Python application must not erase persistent configuration or Capture Registry data.

---

## 2. Task A — Audit Existing Installation Mechanisms

Before implementing changes:

1. Inspect `pyproject.toml`.
2. Inspect the current CLI entry points.
3. Inspect all existing installation scripts.
4. Inspect the RenderDoc extension packaging.
5. Inspect existing `.env` initialization.
6. Inspect `RENDEREYE_ENV_FILE` registration.
7. Inspect the coding agent configuration generator.
8. Review README installation instructions.
9. Review Phase 5.1 and Phase 5.2 changes.
10. Run the existing test suite.

Identify functionality that can be reused.

### Problems to Eliminate

- Using `uv sync` as an end-user installation method.
- Assuming `uv sync` installs into the user application directory.
- Assuming external repository scripts exist after wheel installation.
- Requiring Git for installing a released package.
- Requiring manual virtual environment management for the recommended installation.
- Duplicating RenderEyeMCP configuration across coding agents.
- Hardcoding development installation paths.
- Depending on the current working directory for MCP startup.
- Providing installation commands that reference files not included in the distribution.

### Deliverable

An implementation plan identifying necessary modifications and reusable functionality.

---

## 3. Task B — Recommended Installation Using uv tool

Make `uv tool install` the recommended end-user installation method.

### Requirements

- Support installation from a released wheel.
- Support installation from a package index if the package is published there.
- Do not require a Git checkout.
- Do not require manual virtual environment creation.
- Do not require manually installing Python if `uv` can provision a compatible interpreter.
- Install a usable console entry point.
- Preserve installed application isolation.
- Support Windows and Linux.
- Do not rely on the development `.venv`.

### Recommended Command

For a locally downloaded wheel:

```powershell
uv tool install .\rendereye_mcp-1.0.0-py3-none-any.whl
```

Verify the actual wheel filename against the generated release artifact.

### Console Entry Point

Ensure the package declares an appropriate entry point.

For example:

```toml
[project.scripts]
rendereye-mcp = "rendereye_mcp.cli:main"
```

Adapt the module path to the repository's implementation.

Do not create conflicting entry points.

### PATH Handling

Document:

```powershell
uv tool update-shell
```

Explain that a new terminal may be necessary.

The installation and coding agent configuration must not depend on blindly assuming the command is already available through PATH.

Resolve and verify the installed executable location.

When configuring coding agents, prefer the absolute path to the installed RenderEyeMCP launcher.

### Verification

After installation, the following must work:

```powershell
rendereye-mcp --version
rendereye-mcp --help
```

The installed package must contain all modules and resources required by the setup commands.

### Deliverable

A verified, persistent `uv tool install` distribution.

---

## 4. Task C — Standard Python Installation Without uv

Keep a supported alternative using standard Python tools.

### Requirements

- Support `venv`.
- Support `pip`.
- Support wheel installation.
- Do not require `uv`.
- Do not require Git.
- Do not require editable installation.
- Use user-writable installation locations.

### Windows Example

```powershell
$installDir = Join-Path $env:LOCALAPPDATA "RenderEyeMCP"
$venv = Join-Path $installDir "venv"
$python = Join-Path $venv "Scripts\python.exe"

py -m venv $venv

& $python -m pip install .\rendereye_mcp-1.0.0-py3-none-any.whl
& $python -m rendereye_mcp setup
```

Verify that `python -m rendereye_mcp` supports the proposed CLI commands.

### Shared Functionality

Both installation methods must use the same application-level setup implementation.

Do not maintain separate setup logic for `uv` and `pip`.

### Deliverable

A standard Python installation method with functionality equivalent to the recommended `uv tool` installation.

---

## 5. Task D — Unified RenderEyeMCP CLI

Implement or consolidate the command-line interface.

### Required Commands

| Command | Purpose |
|---|---|
| `rendereye-mcp serve` | Start MCP server using stdio |
| `rendereye-mcp setup` | Configure RenderEyeMCP and RenderDoc integration |
| `rendereye-mcp setup-agent` | Configure a supported coding agent |
| `rendereye-mcp doctor` | Diagnose installation and connectivity |
| `rendereye-mcp uninstall-setup` | Remove RenderEye-managed integration safely |
| `rendereye-mcp --version` | Display installed version |

Use the existing CLI architecture where practical.

### MCP Entry Point Compatibility

Preserve existing MCP startup commands when possible.

Do not break existing coding agent configurations unnecessarily.

Ensure `serve`:

- Uses stdio transport.
- Writes protocol data only to stdout.
- Sends diagnostics to stderr or log files.
- Loads `.env` before Config initialization.
- Does not require the repository as the working directory.

### CLI Packaging

All commands must be included in the installed wheel.

Do not require users to execute:

```text
scripts/setup_env.py
scripts/install_extension.py
```

from a source checkout.

Those scripts may remain as development wrappers, but their functionality must be accessible from the installed application.

### Deliverable

One consistent CLI shared by all supported installation methods.

---

## 6. Task E — Unified Setup Command

Implement:

```powershell
rendereye-mcp setup
```

### Required Workflow

The setup command must:

1. Determine the user application configuration directory.
2. Create required directories.
3. Create `.env` if absent.
4. Preserve existing `.env` settings.
5. Detect RenderDoc.
6. Configure the RenderDoc executable path.
7. Install or update the RenderDoc extension.
8. Register `RENDEREYE_ENV_FILE`.
9. Validate installation components.
10. Display the resulting setup status.

### RenderDoc Discovery

Prefer the standard Windows installation candidate:

```text
C:\Program Files\RenderDoc\qrenderdoc.exe
```

Also support custom locations.

Do not overwrite a valid user-configured RenderDoc path.

### Configuration

Default Windows `.env`:

```text
%LOCALAPPDATA%\RenderEyeMCP\.env
```

Register only:

```text
RENDEREYE_ENV_FILE
```

as a persistent Windows User environment variable.

Do not register it at Machine scope.

Do not register individual RenderEye configuration settings as additional persistent environment variables.

### Server Environment Loading

The MCP server must:

1. Read `RENDEREYE_ENV_FILE`.
2. Load the referenced `.env` into `os.environ`.
3. Preserve existing process environment values.
4. Construct Config afterward.
5. Initialize services.
6. Start MCP.

### Extension Packaging

The extension must be available from the installed application distribution or a separately versioned, explicitly resolved release asset.

Prefer bundling the relatively small extension files as package resources so that `rendereye-mcp setup` works without a source checkout or second download.

Do not depend on files in the original wheel download directory.

### Setup Behavior

The command must be:

- Idempotent
- Safe during reinstallations
- Compatible with upgrades
- Non-destructive
- Independent of `uv`
- Usable from arbitrary working directories

### Interactive Behavior

If a user decision is necessary, request it in an appropriate terminal context.

Provide noninteractive options for automation.

Do not prompt for input when executing `rendereye-mcp serve` under MCP stdio.

### Deliverable

A complete first-run setup command.

---

## 7. Task F — Coding Agent Integration

Implement setup for the following agents:

1. Claude Code
2. OpenAI Codex CLI / IDE
3. Cursor
4. Visual Studio Code / GitHub Copilot
5. Gemini CLI

### Primary Goal

Users should be able to register RenderEyeMCP without manually locating MCP configuration files.

### Command Interface

Provide:

```powershell
rendereye-mcp setup-agent claude-code
rendereye-mcp setup-agent codex
rendereye-mcp setup-agent cursor
rendereye-mcp setup-agent vscode
rendereye-mcp setup-agent gemini
```

### Options

Support appropriate options such as:

```text
--scope user
--scope project
--project-path <path>
--dry-run
--force
--remove
```

Document supported scopes for each agent.

Reject unsupported combinations explicitly.

### Configuration Requirements

Every agent configuration must use:

- MCP server name: `rendereye`
- Transport: stdio
- Installed RenderEyeMCP executable
- Startup argument: `serve`

Example logical configuration:

```json
{
  "name": "rendereye",
  "command": "<absolute-path-to-rendereye-mcp>",
  "args": ["serve"]
}
```

This is a logical representation, not a universal agent configuration schema.

Generate the actual agent-specific format.

### Configuration Rules

- Use the installed executable's verified absolute path.
- Do not rely solely on PATH inheritance.
- Do not reference development `.venv` directories.
- Do not use `uv run`.
- Do not require `uv` when launching the MCP server.
- Do not embed RenderDoc paths into agent configuration.
- Do not duplicate `.env` contents into agent configuration.
- Preserve unrelated MCP servers.
- Preserve unrelated agent settings.
- Avoid duplicate `rendereye` entries.
- Use atomic writes where appropriate.
- Create backups before potentially risky changes.

### Environment Inheritance

Normally, the server discovers its `.env` through `RENDEREYE_ENV_FILE`.

For agent processes that do not inherit the updated user environment:

- Explain the required restart.
- Support explicit injection of only `RENDEREYE_ENV_FILE` where the agent permits it.
- Or provide a safe installed launcher that resolves the application configuration location.
- Do not embed all application settings in each agent configuration.

### Deliverable

Safe, automated MCP registration for all required agents.

---

## 8. Task G — Agent-Specific Configuration

Verify the current official MCP configuration specification for each supported agent before implementing generation.

### Claude Code

Support:

- User-level MCP registration
- Project-level registration
- stdio transport
- Tool discovery

Use the current supported CLI or configuration method.

Do not assume that every scope uses the same file location.

### OpenAI Codex

Support:

- Codex CLI
- Codex IDE integration
- User-level `config.toml`
- Project-level configuration where supported
- stdio MCP server definitions

Use the documented TOML configuration format.

Do not generate JSON for Codex configuration.

### Cursor

Support:

- User-level MCP configuration
- Project-level `.cursor/mcp.json`
- stdio MCP servers

Use the documented `mcpServers` structure.

### Visual Studio Code / GitHub Copilot

Support the appropriate current MCP configuration modes.

Distinguish:

**VS Code MCP configuration**

```text
.vscode/mcp.json
```

Typically uses a top-level `servers` object.

**Portable GitHub Copilot MCP configuration**

```text
.mcp.json
```

Uses a top-level `mcpServers` object.

Support the relevant current user-level locations as documented.

Do not treat these formats as interchangeable.

Select the appropriate format based on the intended Copilot or VS Code integration.

### Gemini CLI

Support:

- User-level settings
- Project-level `.gemini/settings.json`
- stdio MCP integration
- Existing settings preservation

Use the current documented `mcpServers` schema.

### Compatibility

Client configuration locations and schemas may change.

Keep agent-specific serialization isolated from the core application.

Provide clear errors when a client version or configuration mode is unsupported.

### Deliverable

Independently tested configuration adapters for each required agent.

---

## 9. Task H — Agent Setup Workflow

Make configuration straightforward for an ordinary user.

### Single-Agent Setup

Example:

```powershell
rendereye-mcp setup-agent claude-code
```

Expected behavior:

1. Detect the installed RenderEyeMCP executable.
2. Locate Claude Code configuration.
3. Identify the requested configuration scope.
4. Check existing MCP entries.
5. Generate the correct server configuration.
6. Preserve unrelated settings.
7. Save the configuration safely.
8. Validate the saved configuration.
9. Display restart or reload instructions.

### Interactive Agent Selection

Optionally allow:

```powershell
rendereye-mcp setup-agent
```

This may show an interactive selection of supported agents.

Do not make interactive selection mandatory.

### Multiple Agents

Optionally support:

```powershell
rendereye-mcp setup-agent --all
```

Only configure agents that are installed and have a supported configuration mechanism.

Do not create speculative configuration files for software that is not installed without explicit user request.

### Existing Configuration

If `rendereye` is already registered:

- Detect the existing entry.
- Compare it with the desired configuration.
- Avoid duplicate entries.
- Update only RenderEye-owned settings.
- Preserve unrelated configuration.
- Report whether anything changed.

### Dry Run

Example:

```powershell
rendereye-mcp setup-agent cursor --dry-run
```

Display:

- Target configuration file
- Proposed server entry
- Existing entry status
- Intended modifications

Do not write any files in dry-run mode.

### Deliverable

A predictable coding agent setup workflow with safe modification behavior.

---

## 10. Task I — Installation and Configuration Verification

Implement:

```powershell
rendereye-mcp doctor
```

### Application Checks

Verify:

- Installed application version
- CLI entry point
- Python runtime
- Configuration directory
- `.env` existence
- `RENDEREYE_ENV_FILE`
- RenderDoc executable
- RenderDoc extension installation
- IPC configuration

### Agent Checks

Allow:

```powershell
rendereye-mcp doctor --agent claude-code
rendereye-mcp doctor --agent codex
rendereye-mcp doctor --agent cursor
rendereye-mcp doctor --agent vscode
rendereye-mcp doctor --agent gemini
```

Verify:

- Agent detection
- Configuration file location
- Valid configuration syntax
- RenderEye server entry
- Executable existence
- Correct startup arguments
- MCP initialization where practical
- Tool discovery where practical

### Status

Use:

- PASS
- WARNING
- FAIL
- NOT_TESTED

Distinguish a valid configuration file from a confirmed live MCP connection.

### Deliverable

Reliable diagnostics for both application installation and agent integration.

---

## 11. Task J — Updates and Uninstallation

Support lifecycle operations for `uv tool` installations.

### Updating

Document installation of an updated release wheel using the supported `uv tool` replacement or reinstall mechanism.

Do not assume that `uv tool upgrade` discovers a new locally downloaded wheel automatically.

Re-run setup when necessary to update the RenderDoc extension.

### Configuration Preservation

Upgrading the Python application must preserve:

- `.env`
- Capture Registry
- Session Registry
- Protected session metadata
- User-defined capture directories
- Agent configuration

### Uninstalling

Support:

```powershell
rendereye-mcp uninstall-setup
```

This command should safely remove RenderEye-owned integration components.

Do not automatically delete:

- Capture files
- User databases
- Unrelated MCP configurations
- Other RenderDoc extensions

Document application removal using:

```powershell
uv tool uninstall rendereye-mcp
```

For standard pip installations, document removal of the dedicated virtual environment after integration cleanup.

### Agent Removal

Support:

```powershell
rendereye-mcp setup-agent claude-code --remove
```

Remove only the RenderEye MCP entry.

### Deliverable

Non-destructive update and uninstallation procedures.

---

## 12. Task K — README Reorganization

Redesign README installation documentation.

### Required Structure

```text
README.md
├── Overview
├── Features
├── Requirements
├── Installation
│   ├── Quick Install with uv
│   ├── Install without uv
│   └── Manual Installation
├── Initial Setup
├── Coding Agent Integration
├── Configuration
├── Usage
├── Updating
├── Uninstallation
└── Development
```

### Installation Section

Only include end-user installation methods.

### Development Section

Keep developer setup separate.

Use:

```powershell
git clone <repository-url>
cd RenderEyeMCP
uv sync
uv run pytest
```

Do not present `uv sync` as an end-user installation command.

### Quick Install Documentation

Use the simplest verified steps:

```powershell
uv tool install .\rendereye_mcp-1.0.0-py3-none-any.whl
rendereye-mcp setup
rendereye-mcp setup-agent claude-code
rendereye-mcp doctor
```

Clearly explain how to install `uv` and handle PATH configuration when necessary.

### Coding Agent Documentation

Provide separate pages for:

- Claude Code
- Codex
- Cursor
- VS Code / GitHub Copilot
- Gemini CLI

Each page must include both:

- Automatic setup using `setup-agent`
- Manual configuration

### Deliverable

User-oriented installation documentation separated from development instructions.

---

## 13. Task L — Release Packaging

Ensure the GitHub Releases distribution supports the new installation model.

### Python Distribution

The wheel must include:

- MCP server implementation
- CLI implementation
- Setup functionality
- Diagnostics
- Coding agent configuration adapters
- Required package resources
- RenderDoc extension installation resources, if bundled

### Package Resources

Do not assume files under the repository's `scripts/` or `extensions/` directories are available after wheel installation.

If setup requires these files, include them as package resources or provide a validated separate distribution mechanism.

### Release Assets

Maintain:

- Python wheel
- Source distribution
- RenderDoc extension archive
- Manual installation bundle
- Checksums

Do not package virtual environments or development dependencies.

### Release Validation

Test installation from the actual built wheel.

Do not rely only on editable source installations.

### Deliverable

Release artifacts that support all documented end-user commands.

---

## 14. Task M — Automated Tests

Add comprehensive installation and agent-configuration tests.

### uv Tool Tests

- Installation from a wheel
- Console entry point availability
- Running outside the repository
- PATH-independent executable resolution
- Application setup
- Application diagnostics
- Upgrade behavior

### pip Tests

- Dedicated virtual environment installation
- Module startup
- CLI startup
- Setup commands
- Agent configuration

### Setup Tests

- First installation
- Existing `.env`
- RenderDoc detected
- RenderDoc missing
- Extension installation
- Reinstallation
- Upgrade
- Custom installation directory
- Environment variable registration

### Agent Configuration Tests

For every supported agent:

- New configuration
- Existing configuration
- User scope
- Project scope
- Unsupported scope
- Existing RenderEye entry
- Unrelated MCP servers
- Invalid configuration
- Configuration merging
- Dry-run
- Removal
- Absolute executable paths
- Spaces and Unicode in paths

### MCP Tests

- Server initialization
- Tool discovery
- `server_status`
- `capture_list`
- Structured result handling
- Clean shutdown

### Test Safety

- Use temporary directories.
- Mock agent configuration locations.
- Do not modify developer configuration files in unit tests.
- Do not terminate real RenderDoc processes.
- Do not delete user captures.

### Real Integration

Where supported agents are installed, test actual MCP connections.

Report configuration-only validation separately from live connection verification.

### Deliverable

Automated tests demonstrating that installed distributions work independently of the source checkout.

---

## 15. Task N — Cross-Platform Requirements

Preserve Windows and Linux support.

### Windows

Verify:

- `uv tool install`
- Console entry point
- RenderDoc discovery
- User-level `.env`
- Extension installation
- Agent configuration
- Paths with spaces
- Unicode paths

### Linux

Verify where possible:

- `uv tool install`
- Console entry point
- Configuration directories
- RenderDoc discovery
- Extension installation
- Agent configuration
- Executable permissions
- Case-sensitive paths

### Platform Independence

Keep:

- MCP tools
- Capture Registry
- Session Manager
- Config parsing
- Agent configuration serialization

independent of operating-system-specific implementation details.

Do not claim Linux compatibility based only on Windows testing.

### Deliverable

Cross-platform installation support with explicitly documented verification status.

---

## 16. Definition of Done

The addendum is complete when:

- [ ] `uv tool install` works with the release wheel.
- [ ] Installed CLI works without a source checkout.
- [ ] End users do not need `uv sync`.
- [ ] Standard Python installation remains supported.
- [ ] Application configuration is independent of the Python environment.
- [ ] `rendereye-mcp serve` works.
- [ ] `rendereye-mcp setup` works.
- [ ] `rendereye-mcp doctor` works.
- [ ] `rendereye-mcp setup-agent` works.
- [ ] RenderDoc executable discovery works.
- [ ] RenderDoc extension installation works from the installed distribution.
- [ ] `.env` is generated and preserved.
- [ ] `RENDEREYE_ENV_FILE` is registered correctly.
- [ ] Claude Code configuration works.
- [ ] Codex configuration works.
- [ ] Cursor configuration works.
- [ ] VS Code / GitHub Copilot configuration works.
- [ ] Gemini CLI configuration works.
- [ ] Agent configurations use the installed executable.
- [ ] Existing agent settings are preserved.
- [ ] Agent configuration removal works.
- [ ] Upgrade procedures preserve user data.
- [ ] README separates Installation from Development.
- [ ] GitHub Release artifacts contain required resources.
- [ ] Automated tests pass.
- [ ] Real agent connections are verified where possible.
- [ ] Platform limitations are documented accurately.

---

## 17. Execution Instructions

Execute the implementation in this order:

1. Inspect the repository.
2. Run the existing test suite.
3. Audit current installation methods.
4. Verify console entry point packaging.
5. Implement or consolidate the CLI.
6. Implement `serve`.
7. Implement the unified `setup` command.
8. Integrate `.env` and RenderDoc discovery.
9. Package the RenderDoc extension for installed setup.
10. Implement `setup-agent`.
11. Implement agent-specific configuration adapters.
12. Implement configuration merging and safety checks.
13. Implement diagnostic commands.
14. Implement upgrade and removal support.
15. Verify `uv tool install` using the built wheel.
16. Verify pip installation in a clean environment.
17. Test agent configuration generation.
18. Test actual MCP connectivity where possible.
19. Update GitHub Release packaging.
20. Reorganize README.
21. Update agent documentation.
22. Run the complete regression suite.
23. Review all acceptance criteria.
24. Produce the final report.

Work autonomously using the existing repository and tools.

Do not stop after editing documentation.

Do not implement unrelated GPU debugging functionality.

Do not break existing MCP tools.

Do not automatically overwrite user configuration.

Do not modify the production engine.

Do not publish a GitHub Release without explicit authorization.

---

## 18. Final Report

After implementation, provide:

1. **Implementation Summary** — Installation and CLI changes.
2. **Files Changed** — Main implementation files and documentation.
3. **uv Tool Installation** — Actual installation and execution results.
4. **pip Installation** — Standard Python installation results.
5. **CLI Commands** — Implemented commands and behavior.
6. **RenderDoc Setup** — Executable detection and extension installation.
7. **Environment Configuration** — `.env` and `RENDEREYE_ENV_FILE`.
8. **Coding Agent Integrations** — Configuration and verification status for every required agent.
9. **Packaging** — Verified wheel and release bundle contents.
10. **Automated Tests** — Commands executed and results.
11. **Real Integration Tests** — Agent connections actually verified.
12. **Platform Compatibility** — Windows and Linux results.
13. **Known Limitations** — Remaining issues.
14. **Completion Status** — Complete, partially verified, or blocked.

Do not claim that an agent integration works unless actual testing supports that conclusion.

Do not publish release artifacts or create version tags without authorization.

**Primary Goal: Provide a simple, persistent, end-user-friendly RenderEyeMCP installation using `uv tool install`, followed by unified RenderDoc setup and reliable MCP configuration for major coding agents, while keeping development workflows separate.**
