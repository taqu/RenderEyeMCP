# RenderEyeMCP — Phase 5.1 Addendum: Manual Installation Support

## Objective

Extend the existing Phase 5.1 implementation to officially support **manual installation, configuration, verification, and uninstallation** of RenderEyeMCP.

The previous Phase 5.1 instructions introduced clean Windows installation, standard Python packaging, RenderDoc executable discovery, and integration with major coding agents.

This addendum introduces an additional installation method that does not require running the RenderEyeMCP installer.

Users must be able to install RenderEyeMCP through ordinary file copying, standard Python commands, and manual coding agent configuration.

**Manual installation must be treated as a first-class supported workflow, not merely an undocumented workaround.**

Do not replace or remove existing automatic installation or `uv`-based development workflows.

---

## 1. Installation Methods

RenderEyeMCP must support three installation methods.

### Automatic Installation

Use the provided installation scripts to configure the MCP server, RenderDoc extension, and coding agent.

### Manual Installation

Users manually:

1. Install the Python package using standard Python tooling.
2. Copy the RenderEye extension into the appropriate RenderDoc extension directory.
3. Configure their coding agent's MCP server entry.
4. Verify that RenderEyeMCP is running correctly.

No RenderEyeMCP-specific installation script should be required.

### Developer Installation

Use `uv` and the repository development workflow.

All three methods must result in equivalent core MCP functionality.

---

## 2. Task A — Manual MCP Server Installation

Document and verify installation without `uv`.

### Requirements

- Support standard Python.
- Support `pip`.
- Support Python `venv`.
- Support installation from a wheel.
- Support installation from a source checkout.
- Do not require Git when installing from a released distribution.
- Do not require administrator privileges for a user-local installation.
- Do not require modifying the system PATH.
- Do not depend on the current working directory at runtime.

### Example Windows Setup

```powershell
mkdir "$env:LOCALAPPDATA\RenderEyeMCP"

py -m venv "$env:LOCALAPPDATA\RenderEyeMCP\venv"

& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\python.exe" -m pip install .\rendereye_mcp-<version>-py3-none-any.whl
```

The wheel filename is illustrative.

Verify the actual package name and distribution filename.

If the installed Python does not expose the `py` launcher, document the equivalent `python` command.

### Runtime Verification

The installed MCP server should be launchable using:

```powershell
& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\python.exe" -m rendereye_mcp
```

Verify that the module entry point exists and correctly starts the MCP stdio server.

Do not write diagnostic logs to stdout.

### Manual File Copying

If a prepackaged Python runtime or portable distribution exists, document how it can be copied into a target directory.

Do not claim that an arbitrary Python virtual environment can be copied between machines reliably.

Python virtual environments may contain interpreter-specific paths, executable references, and dependencies that are not portable.

A wheel-based installation is the preferred manual installation method unless a genuinely relocatable standalone distribution has been implemented and tested.

### Deliverable

A documented and tested manual MCP server installation method.

---

## 3. Task B — Manual RenderDoc Extension Installation

Support installing the RenderEye Python extension by copying files.

### Windows

RenderDoc installation directory:

`C:\Program Files\RenderDoc\`

Do not assume that extensions must be installed inside this directory.

Use the user-level RenderDoc extension directory supported by the installed RenderDoc version.

An expected candidate is:

```text
%APPDATA%\qrenderdoc\extensions\
```

Verify the actual directory and extension discovery rules against the installed RenderDoc version.

### Manual Installation Layout

Provide a self-contained extension directory that can be copied as a unit.

Example:

```text
rendereye/
├── __init__.py
├── extension.json
├── ipc_client.py
├── gui_context.py
├── gui_dispatcher.py
└── state_observer.py
```

The file list is illustrative. Package the actual files required by the implementation.

### Installation Procedure

Document how to:

1. Locate the user-level RenderDoc extension directory.
2. Create the directory if necessary.
3. Copy the complete RenderEye extension folder.
4. Start or restart RenderDoc as required.
5. Open the extension manager.
6. Enable the RenderEye extension.
7. Verify extension initialization.
8. Verify connectivity with the MCP server.

Do not require modifying RenderDoc executable files.

### Linux

Document the supported Linux extension location.

An expected candidate is:

```text
~/.local/share/qrenderdoc/extensions/
```

Verify this against the installed RenderDoc version.

Do not assume identical paths across all distributions or installation formats.

### Extension Dependencies

The extension must not assume access to the MCP server's Python virtual environment.

Keep the extension self-contained wherever practical.

Use the standard library when possible.

If additional Python modules are required, include clear deployment instructions and verify compatibility with RenderDoc's embedded Python interpreter.

### Deliverable

A manually copyable RenderDoc extension package and verified installation instructions.

---

## 4. Task C — Manual Coding Agent Configuration

Provide manual MCP configuration instructions for every supported coding agent.

### Required Agents

- Claude Code
- OpenAI Codex
- Cursor
- GitHub Copilot / VS Code
- Gemini CLI

### Requirements

For each agent, document:

- MCP configuration file location
- User-level configuration method
- Project-level configuration method, when supported
- Correct configuration schema
- MCP server command
- MCP server arguments
- Working-directory behavior
- Connection verification
- Configuration removal

Verify the current configuration format for each agent.

Do not assume that all agents use the same configuration schema.

### Runtime Command

Agent configurations should reference the installed Python environment.

For example:

```text
C:\Users\<USERNAME>\AppData\Local\RenderEyeMCP\venv\Scripts\python.exe
```

With arguments:

```text
-m rendereye_mcp
```

Do not require `uv` in end-user MCP configurations.

Do not hardcode the developer's username or workstation paths.

### Configuration Examples

Provide complete examples with clearly identified placeholders.

Explain how to substitute the actual installation path.

Preserve unrelated MCP servers and agent settings.

### Verification

For each agent, document how to:

1. Register RenderEyeMCP.
2. Restart or reload the agent when required.
3. Confirm that RenderEyeMCP appears in its MCP server list.
4. Invoke `server_status`.
5. Invoke `capture_list`.
6. Diagnose connection failures.

### Deliverable

Complete manual setup documentation for all required coding agents.

---

## 5. Task D — Manual Configuration Files

Ensure that RenderEyeMCP can be configured without running an installation wizard or setup script.

### Requirements

- Provide a documented default configuration file.
- Provide a sample configuration.
- Support user-local configuration paths.
- Support environment-variable overrides where appropriate.
- Support a custom RenderDoc executable path.
- Support custom capture directories.
- Support configurable logging.
- Support IPC configuration without source-code modification.

### RenderDoc Discovery

Use:

`C:\Program Files\RenderDoc\qrenderdoc.exe`

as a preferred Windows discovery candidate.

Continue to support custom installation locations.

Do not require users to copy the RenderDoc executable path into every coding agent configuration.

Centralize RenderDoc configuration inside RenderEyeMCP.

### Configuration Preservation

Manual upgrades must not require overwriting the user's configuration.

Document how the application handles missing or outdated configuration settings.

### Deliverable

A configuration system usable without automatic setup tools.

---

## 6. Task E — Manual Installation Verification

Provide a verification checklist that users can perform without the automatic installer.

### Required Checks

1. The Python virtual environment exists.
2. Required Python dependencies are installed.
3. The MCP server starts successfully.
4. RenderDoc is discovered.
5. The RenderEye extension is installed.
6. The extension can load in RenderDoc.
7. The extension can communicate with the MCP server.
8. The selected coding agent can connect to the MCP server.
9. `server_status` works.
10. `capture_list` works.

### Diagnostics

If the existing `rendereye-mcp doctor` command is available, recommend it as an optional diagnostic tool.

However, the manual installation procedure must not depend on the automatic installer or setup-agent command.

### Failure Reporting

Distinguish:

- Missing Python
- Invalid virtual environment
- Missing dependencies
- RenderDoc not found
- Incorrect extension directory
- Extension not enabled
- IPC connection failure
- Incorrect MCP command
- Agent configuration error

Do not claim that copying the extension successfully proves MCP connectivity.

### Deliverable

A reproducible manual installation verification procedure.

---

## 7. Task F — Manual Updates and Uninstallation

Provide procedures for updating and uninstalling without using installation scripts.

### Manual Update

Document how to:

1. Stop the MCP server.
2. Preserve user configuration.
3. Preserve registry data.
4. Install the updated Python wheel.
5. Replace only RenderEye-owned extension files.
6. Restart RenderDoc when required.
7. Verify protocol compatibility.
8. Verify MCP connectivity.

Do not automatically delete Capture Registry or Session Registry databases.

### Manual Uninstallation

Document how to:

1. Remove RenderEyeMCP entries from coding agent configurations.
2. Stop the MCP server.
3. Remove the dedicated Python environment.
4. Remove the RenderEye extension directory.
5. Preserve user captures.
6. Preserve registry metadata by default unless the user explicitly chooses to delete it.

Do not remove other RenderDoc extensions.

Do not modify RenderDoc's installation directory unnecessarily.

### Deliverable

Safe manual update and uninstall instructions.

---

## 8. Task G — Distribution Package Layout

Prepare release assets that make manual installation straightforward.

### Recommended Artifacts

```text
RenderEyeMCP-v1.0.0/
├── python/
│   └── rendereye_mcp-<version>-py3-none-any.whl
│
├── renderdoc-extension/
│   └── rendereye/
│       ├── __init__.py
│       ├── extension.json
│       └── ...
│
├── examples/
│   ├── claude-code/
│   ├── codex/
│   ├── cursor/
│   ├── vscode/
│   └── gemini/
│
├── README.md
└── INSTALL-MANUAL.md
```

The structure is illustrative.

Use the actual wheel filename and extension file layout.

Do not introduce duplicate source implementations solely for packaging.

### Requirements

- Python wheel must install independently.
- Extension folder must be copyable independently.
- Configuration examples must contain no developer-specific absolute paths.
- Package contents must be versioned consistently.
- Avoid including unnecessary build artifacts.
- Avoid including capture files or Unity project data.
- Avoid bundling RenderDoc binaries.

### Deliverable

A manual-installation-friendly release package.

---

## 9. Task H — Testing

Add tests for manual installation support.

### Python Packaging

- Install from wheel using pip.
- Install without uv.
- Launch through the installed interpreter.
- Run from a different working directory.
- Test paths containing spaces.
- Test Unicode paths.

### Extension Packaging

- Verify required files exist.
- Verify extension metadata.
- Verify correct directory structure.
- Verify self-contained dependencies.
- Verify version compatibility.

### Agent Configuration

- Verify example configuration syntax.
- Verify startup commands.
- Verify paths containing spaces.
- Verify existing unrelated configuration is preserved.

### Upgrade and Uninstall

- Verify manual upgrade preserves configuration.
- Verify registry data remains available.
- Verify extension replacement affects only RenderEye files.
- Verify uninstallation does not delete `.rdc` files.

### Real Environment

When possible, execute the complete manual installation process in a clean Windows environment without uv.

Clearly distinguish simulated installation tests from actual clean-machine verification.

### Deliverable

Automated tests and an evidence-based manual installation report.

---

## 10. Task I — Documentation

Create:

`docs/installation-manual.md`

Update:

- `README.md`
- `docs/installation.md`
- `docs/development.md`
- `docs/troubleshooting.md`
- Coding agent setup guides
- Release documentation

### Documentation Requirements

Provide separate sections for:

- Windows manual installation
- Linux manual installation
- Manual RenderDoc extension installation
- Manual MCP configuration
- Manual verification
- Manual updates
- Manual uninstallation

The README must clearly distinguish:

1. Automatic installation
2. Manual installation
3. Developer installation using uv

Do not require users to read developer documentation to complete a manual installation.

---

## 11. Definition of Done

This Phase 5.1 addendum is complete when:

- [ ] RenderEyeMCP can be installed using standard Python and pip.
- [ ] No uv installation is required for end users.
- [ ] The RenderDoc extension can be installed by copying a folder.
- [ ] The extension can be enabled through RenderDoc.
- [ ] MCP server configuration can be performed manually.
- [ ] Major coding agents have manual configuration examples.
- [ ] The application works without running an installer script.
- [ ] Custom RenderDoc paths remain supported.
- [ ] Manual installation verification is documented.
- [ ] Manual upgrade procedures are documented.
- [ ] Manual uninstallation procedures are documented.
- [ ] User captures and registry data remain protected.
- [ ] Release assets support manual installation.
- [ ] Automated packaging tests pass.
- [ ] Existing Phase 0–5 tests remain passing.
- [ ] Real installation tests are executed where possible.

If actual clean-environment verification cannot be performed, report it as unverified.

---

## 12. Execution Instructions

1. Inspect the existing Phase 5.1 implementation.
2. Identify installation components already implemented.
3. Avoid duplicating existing functionality.
4. Verify the Python wheel installation workflow.
5. Prepare the manually copyable RenderDoc extension.
6. Create manual configuration examples for supported coding agents.
7. Verify RenderDoc executable discovery.
8. Implement or improve manual configuration support.
9. Prepare the manual distribution package.
10. Document manual installation, upgrade, and uninstallation.
11. Add packaging and configuration tests.
12. Execute real installation tests where possible.
13. Run the complete regression suite.
14. Update release documentation.
15. Report completion status and limitations.

Do not begin unrelated feature development.

Do not remove automatic installation support.

Do not remove uv-based development support.

Do not publish release artifacts without explicit authorization.

---

## 13. Final Report

After implementation, report:

1. **Implementation Summary**
2. **Files Added or Modified**
3. **Manual Python Installation Results**
4. **RenderDoc Extension Copy Installation Results**
5. **Coding Agent Configuration Examples**
6. **Distribution Package Contents**
7. **Automated Test Results**
8. **Clean Environment Verification**
9. **Manual Upgrade and Uninstallation**
10. **Known Limitations**
11. **Phase 5.1 Addendum Status**

Distinguish verified behavior from untested assumptions.

**Phase 5.1 Addendum Focus: Enable reliable RenderEyeMCP installation through standard Python tooling, manual RenderDoc extension copying, and manual MCP configuration without requiring an installer or uv.**
