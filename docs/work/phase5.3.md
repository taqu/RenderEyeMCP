# RenderEyeMCP — Phase 5.2 Addendum: Installer-Managed Environment Configuration

## Objective

Implement a centralized environment configuration system for RenderEyeMCP.

The installer must create a default `.env` file inside the RenderEyeMCP installation directory, automatically detect RenderDoc when possible, and register the configuration file location through a single user-level environment variable:

`RENDEREYE_ENV_FILE`

The MCP server must load this file into `os.environ` before constructing its application configuration.

This configuration mechanism must work consistently across supported coding agents without requiring agent-specific copies of RenderEyeMCP settings.

**Implement and test the complete installation, startup, upgrade, and uninstallation behavior. Do not stop at documentation or example scripts.**

---

## 1. Core Design

Use the following architecture:

```text
RenderEyeMCP Installer
    |
    +-- Install Python package
    |
    +-- Install RenderDoc Extension
    |
    +-- Detect RenderDoc executable
    |
    +-- Generate or update .env
    |       |
    |       +-- Default settings
    |       +-- Detected RenderDoc path
    |       +-- Preserved user settings
    |
    +-- Register User Environment Variable
            |
            +-- RENDEREYE_ENV_FILE
                        |
                        v
              Coding Agent Process
                        |
                        v
                  MCP Server
                        |
                        v
                Load .env File
                        |
                        v
                  os.environ
                        |
                        v
               Create Config Object
                        |
                        v
             Initialize Components
                        |
                        v
                  Start MCP
```

### Design Principles

1. Keep application configuration centralized.
2. Do not require separate RenderEyeMCP configuration values for each coding agent.
3. Use only one persistent environment variable to locate the configuration file.
4. Prefer user-level installation and configuration.
5. Preserve existing environment variables.
6. Preserve user configuration during upgrades.
7. Support installations without `uv`.
8. Maintain compatibility with manual installation.
9. Preserve Linux portability.
10. Avoid machine-specific assumptions in shared runtime code.

---

## 2. Task A — Installation Directory

Use the existing Phase 5.1 installation directory conventions.

### Windows

Default installation directory:

```text
%LOCALAPPDATA%\RenderEyeMCP\
```

Recommended layout:

```text
RenderEyeMCP/
├── .env
├── venv/
├── data/
│   ├── captures.db
│   └── sessions.db
└── logs/
```

Adapt this layout to the existing application architecture.

Do not duplicate existing registry or session databases.

### Configuration File Location

The default configuration path should be:

```text
%LOCALAPPDATA%\RenderEyeMCP\.env
```

Resolve this to an absolute path during installation.

Do not store an unexpanded `%LOCALAPPDATA%` expression as the environment variable value.

### Custom Installation Directories

If the installer supports a custom installation path, place `.env` in that selected directory.

The registered environment variable must point to the actual installed configuration file.

### Linux

Preserve an equivalent user-local configuration mechanism.

Use appropriate Linux user configuration conventions and avoid introducing Windows-specific logic into the MCP server core.

---

## 3. Task B — Default .env Generation

The installer must create a default `.env` file when one does not already exist.

### Default Configuration

Provide a version-controlled template:

`.env.example`

Example:

```dotenv
# RenderEyeMCP configuration

# RenderDoc executable.
# Automatically populated when detected.
RENDEREYE_RENDERDOC_PATH=

# Logging
RENDEREYE_LOG_LEVEL=INFO
```

Extend this template with existing application configuration settings where appropriate.

Do not invent configuration keys that are not supported by the existing Config implementation.

### First Installation

During initial installation:

1. Resolve the installation directory.
2. Check whether `.env` already exists.
3. Load the default template.
4. Detect the RenderDoc executable.
5. Populate the RenderDoc setting when detection succeeds.
6. Write `.env` using UTF-8 encoding.
7. Validate the resulting file.
8. Register `RENDEREYE_ENV_FILE`.

### Missing RenderDoc

If RenderDoc is not found:

- Continue installing RenderEyeMCP.
- Leave the RenderDoc path unset.
- Display a warning.
- Explain how to configure the path later.
- Do not invent an executable path.
- Do not mark RenderDoc integration as verified.

### File Encoding

Use UTF-8 consistently.

Avoid writing a UTF-8 BOM unless the configuration parser has been verified to handle it.

Support paths containing spaces, Unicode characters, and non-ASCII usernames.

### Configuration Comments

Preserve useful comments in `.env.example`.

Do not add secrets or machine-specific paths to version-controlled templates.

### Deliverable

A default `.env` template and reliable first-installation configuration generation.

---

## 4. Task C — Automatic RenderDoc Detection

Integrate existing RenderDoc executable discovery into the installer.

### Preferred Windows Candidate

Check:

```text
C:\Program Files\RenderDoc\qrenderdoc.exe
```

Use the appropriate Windows Program Files environment or known-folder resolution mechanism rather than assuming that the system drive is always `C:`.

### Discovery Priority

Use the existing verified discovery implementation.

Prefer:

1. Explicitly configured valid RenderDoc path
2. Existing valid user configuration
3. Standard RenderDoc installation directories
4. Verified installation metadata
5. PATH-based executable discovery

Do not silently select an arbitrary executable when multiple incompatible installations exist.

### Validation

Before writing a detected path:

- Confirm the executable exists.
- Confirm it is a file.
- Confirm it is the expected RenderDoc GUI executable.
- Verify compatibility where practical.
- Handle access-denied errors.
- Handle paths containing spaces and Unicode characters.

### Updating .env

When a valid installation is discovered, set:

```dotenv
RENDEREYE_RENDERDOC_PATH="C:\Program Files\RenderDoc\qrenderdoc.exe"
```

Ensure that the generated value can be parsed correctly by the selected dotenv parser.

Do not use a generic string replacement that may corrupt quoting, comments, or unrelated settings.

### Multiple Installations

If multiple RenderDoc installations are detected:

- Prefer an existing valid user selection.
- Otherwise use a documented deterministic selection policy.
- Report ambiguity when automatic selection is unsafe.
- Do not silently switch between installations during upgrades.

### Deliverable

Installer-integrated RenderDoc discovery that updates only the appropriate configuration setting.

---

## 5. Task D — Register RENDEREYE_ENV_FILE

Register the configuration file location using the Windows user environment scope.

### Required Variable

```text
RENDEREYE_ENV_FILE
```

Example resolved value:

```text
C:\Users\<USERNAME>\AppData\Local\RenderEyeMCP\.env
```

The username placeholder is illustrative. The installer must compute the actual absolute path.

### Windows Registration

Use the equivalent of:

```powershell
[Environment]::SetEnvironmentVariable(
    "RENDEREYE_ENV_FILE",
    $envFile,
    "User"
)
```

Do not register the variable at Machine scope.

Do not require administrator privileges solely for environment variable registration.

### Current Process

Also set:

```powershell
$env:RENDEREYE_ENV_FILE = $envFile
```

This allows subsequent installer subprocesses to use the new configuration immediately.

### Existing Variable

Before modifying an existing user-level `RENDEREYE_ENV_FILE`:

1. Read its current value.
2. Resolve the existing path.
3. Determine whether it belongs to the current RenderEyeMCP installation.
4. Preserve valid custom configurations.
5. Avoid silently redirecting another installation.
6. Require an explicit migration or replacement decision when ownership is ambiguous.

### No Other Persistent Variables

Do not create separate persistent user or machine environment variables for:

- RenderDoc executable path
- Capture directories
- IPC endpoints
- Logging configuration
- Registry storage locations

These settings belong in `.env`.

Existing process-level environment variable overrides must remain supported.

### Environment Propagation

Windows applications that are already running may retain their previous environment.

After registration:

- Apply the variable to the current installer process.
- Notify the operating system of environment changes using supported mechanisms where appropriate.
- Explain that already-running coding agents or IDEs may need to restart.
- Verify registration through the User environment scope.
- Do not assume that every newly launched child process automatically inherits the updated registry value from an old parent process.

### Deliverable

Reliable user-level environment variable registration without administrator privileges.

---

## 6. Task E — MCP Server Environment Bootstrap

Implement environment loading before application configuration initialization.

### Requirements

1. Read `RENDEREYE_ENV_FILE` from the process environment.
2. Resolve and validate the specified path.
3. Load `.env` into `os.environ`.
4. Preserve already-existing environment variables.
5. Create the application Config only after loading.
6. Initialize registry, session, IPC, and MCP components afterward.
7. Preserve all existing MCP entry points.

### Python Dependency

Use `python-dotenv` if it is not already installed.

Add it as a normal runtime dependency.

Do not make it an optional development-only dependency.

### Suggested Bootstrap Implementation

```python
import os
from pathlib import Path

from dotenv import load_dotenv


def initialize_environment() -> Path | None:
    env_path = os.environ.get("RENDEREYE_ENV_FILE")

    if not env_path:
        return None

    path = Path(env_path).expanduser()

    if not path.is_absolute():
        raise ValueError(
            "RENDEREYE_ENV_FILE must be an absolute path"
        )

    if not path.is_file():
        raise FileNotFoundError(
            f"Environment file not found: {path}"
        )

    load_dotenv(
        dotenv_path=path,
        override=False,
    )

    return path
```

This is an illustrative implementation.

Adapt it to existing application error handling and platform behavior.

### Startup Order

```text
main()
  |
  +-- initialize_environment()
  |
  +-- create_config()
  |
  +-- initialize_capture_registry()
  |
  +-- initialize_session_manager()
  |
  +-- initialize_ipc()
  |
  +-- start_mcp_server()
```

### Import-Time Initialization

Avoid creating environment-dependent Config instances at module import time.

Configuration construction must occur after environment initialization.

If existing modules eagerly initialize configuration, refactor only the necessary startup boundaries.

### Error Handling

If `RENDEREYE_ENV_FILE` is explicitly defined but points to a missing or unreadable file:

- Return a clear startup error.
- Do not silently load another arbitrary `.env`.
- Do not silently fall back to a different configuration.
- Do not emit errors to MCP stdout.

If `RENDEREYE_ENV_FILE` is absent:

- Preserve the existing documented fallback or default configuration behavior.
- Do not automatically load unrelated project `.env` files.

### Deliverable

Deterministic environment bootstrap shared by all supported MCP launch methods.

---

## 7. Task F — Configuration Precedence

Implement and document the following priority:

| Priority | Source |
|---|---|
| Highest | Existing process environment |
| Medium | `.env` selected by `RENDEREYE_ENV_FILE` |
| Lowest | Application Config defaults |

### Existing Environment Variables

Use `override=False` when loading dotenv values.

If a coding agent explicitly provides:

```text
RENDEREYE_LOG_LEVEL=DEBUG
```

that value must take precedence over the `.env` value.

### Configuration File Selection

If `RENDEREYE_ENV_FILE` is set, use only that selected `.env` file.

Do not merge an unrelated project-local `.env` automatically.

### Missing Optional Configuration

An unset `RENDEREYE_ENV_FILE` must not prevent direct source development or ordinary default configuration startup unless the application's existing contract explicitly requires a configuration file.

### Consistency

Ensure that:

- Direct CLI execution
- Python module execution
- Installed console entry point
- Claude Code
- Codex
- Cursor
- VS Code / Copilot
- Gemini CLI

all use the same environment bootstrap logic.

### Deliverable

Consistent configuration resolution independent of the calling MCP client.

---

## 8. Task G — Reinstallation and Upgrade Behavior

Existing `.env` files must be preserved.

### First Installation

If no `.env` exists:

- Create it from `.env.example`.
- Detect RenderDoc.
- Populate the detected executable path.
- Register the environment variable.

### Reinstallation

If `.env` exists:

- Do not replace the entire file.
- Preserve custom settings.
- Preserve comments where practical.
- Preserve unknown keys.
- Validate existing settings.
- Update only settings that must be migrated.

### RenderDoc Path

If `RENDEREYE_RENDERDOC_PATH` contains a valid path, preserve it.

If it is unset or invalid:

- Attempt RenderDoc discovery.
- Fill an unset value when a valid executable is found.
- For an invalid nonempty user value, report the problem and require an explicit repair decision before replacement.

### Template Updates

If a new version introduces configuration keys:

- Add missing keys when necessary.
- Preserve existing values.
- Avoid reformatting unrelated lines.
- Do not remove unknown configuration entries without a documented migration.

### Atomic Updates

Write configuration changes safely:

1. Read the existing file.
2. Create the updated content.
3. Validate the result.
4. Write a temporary file in the same directory.
5. Flush and close the file.
6. Atomically replace the destination where supported.
7. Preserve file permissions where appropriate.

Create a backup before nontrivial migrations.

### Rollback

If installation fails after changing `.env` or environment registration, restore the previous installation state where practical.

Do not leave a newly registered `RENDEREYE_ENV_FILE` pointing to a nonexistent configuration file after a failed first installation.

### Deliverable

Idempotent installation and upgrade behavior that preserves user configuration.

---

## 9. Task H — Uninstallation Behavior

Update the uninstaller to handle the registered environment variable safely.

### Requirements

- Read the registered user-level `RENDEREYE_ENV_FILE`.
- Determine whether it points to the installation being removed.
- Remove the environment variable only when it matches the managed installation.
- Do not remove environment variables belonging to another installation.
- Do not modify Machine-scope environment variables.
- Preserve `.rdc` capture files.
- Preserve unrelated coding agent configuration entries.

### User Configuration

Preserve `.env` by default when retaining user application data.

If the user explicitly requests complete configuration removal, remove only RenderEye-owned configuration data.

Do not delete arbitrary files referenced by `RENDEREYE_ENV_FILE`.

### Safety

If ownership cannot be established, leave the environment variable unchanged and report the reason.

### Deliverable

Non-destructive uninstallation with conditional environment-variable cleanup.

---

## 10. Task I — Coding Agent Integration

Update supported coding agent setup workflows to use centralized configuration.

### Supported Agents

- Claude Code
- OpenAI Codex
- Cursor
- GitHub Copilot / VS Code
- Gemini CLI

### Agent Configuration

Each MCP configuration should normally specify only:

- MCP server name
- Executable command
- Required startup arguments

Do not duplicate RenderDoc paths or other application configuration values across agent settings.

### Example

The agent launches:

```text
<RenderEyeMCP Python executable> -m rendereye_mcp
```

RenderEyeMCP then resolves:

```text
RENDEREYE_ENV_FILE
    |
    v
<installation-directory>\.env
```

### Environment Inheritance

Test whether each supported agent inherits the user-level environment variable.

If an agent fails to inherit the updated environment due to its launch context:

- Explain the restart requirement.
- Offer an explicit environment-variable entry or wrapper-based fallback.
- Do not duplicate the entire `.env` content into the agent configuration.
- Keep centralized configuration as the default design.

### Verification

Confirm that two different coding agents can launch RenderEyeMCP and resolve the same `.env` file without separate RenderDoc path settings.

### Deliverable

Simplified multi-agent configuration using a centralized `.env` file.

---

## 11. Task J — Manual Installation Compatibility

Manual installation must remain supported.

### Manual Setup

Document how a user can:

1. Install the Python wheel using pip.
2. Copy the RenderDoc Extension manually.
3. Create `.env` from `.env.example`.
4. Set their RenderDoc executable path.
5. Register `RENDEREYE_ENV_FILE` manually.
6. Configure a coding agent.
7. Verify server startup.

### Manual Environment Registration

Provide PowerShell instructions using User scope.

Do not require administrator privileges.

### Development Workflow

Keep `uv` development support.

Development environments must not be forced to register a global user environment variable.

Developers may set `RENDEREYE_ENV_FILE` temporarily for a terminal session or test invocation.

### Deliverable

Compatibility with automatic, manual, and developer installation methods.

---

## 12. Task K — Diagnostics

Extend the existing diagnostics command.

### Required Checks

- `RENDEREYE_ENV_FILE` is defined or intentionally absent.
- The configured path is absolute.
- The selected `.env` exists.
- The file is readable.
- The file parses correctly.
- The selected RenderDoc executable exists.
- The executable is compatible where verifiable.
- Config values are successfully initialized.
- MCP startup works.
- IPC initialization works.

### Diagnostic Output

Report the active configuration source.

Example:

```text
RenderEyeMCP Configuration

Environment file:
  C:\Users\<USERNAME>\AppData\Local\RenderEyeMCP\.env

Environment source:
  RENDEREYE_ENV_FILE

RenderDoc:
  Found

Configuration:
  Valid
```

Do not expose secrets or dump all environment variables.

### Error Messages

Provide actionable messages for:

- Missing environment file
- Invalid path
- Permission denied
- Invalid dotenv syntax
- Invalid RenderDoc executable
- Conflicting configuration
- Environment variable not inherited
- Configuration validation failure

### Deliverable

Diagnostic support for centralized environment configuration.

---

## 13. Task L — Automated Tests

Implement isolated automated tests.

### Environment Bootstrap Tests

- No `RENDEREYE_ENV_FILE`
- Valid explicit `.env`
- Missing explicit `.env`
- Unreadable `.env`
- Invalid environment file path
- Preexisting environment variable
- `.env` default value
- Environment precedence
- Config initialization order
- Multiple application entry points
- Unicode paths
- Paths containing spaces

### Installer Tests

- First installation
- Existing `.env`
- Reinstallation
- Upgrade
- RenderDoc detected
- RenderDoc missing
- Invalid existing RenderDoc path
- Custom installation directory
- User environment variable registration
- Existing custom environment variable
- Failed installation rollback

### Configuration Tests

- Template generation
- Comment preservation
- Unknown-key preservation
- Default value generation
- Missing-key migration
- Invalid value handling
- Atomic update
- UTF-8 encoding

### Uninstallation Tests

- Environment variable matches installation
- Environment variable belongs to another installation
- Configuration retained
- Complete configuration removal explicitly requested
- Missing installation directory

### MCP Integration Tests

- Direct module execution
- Installed console entry point
- stdio MCP initialization
- `server_status`
- Config created after environment loading
- Existing Phase 0–5 functionality
- Startup from unrelated working directories

### Test Isolation

Do not modify the developer's real User or Machine environment variables during ordinary automated tests.

Mock environment registration or use isolated test processes.

Do not overwrite real user `.env` files.

### Deliverable

Automated tests covering the complete environment configuration lifecycle.

---

## 14. Documentation

Update:

- `README.md`
- `docs/installation.md`
- `docs/installation-manual.md`
- `docs/development.md`
- `docs/troubleshooting.md`
- Coding agent integration guides
- Release packaging documentation

### Required Documentation

Explain:

1. Where `.env` is stored.
2. How the installer generates it.
3. How RenderDoc is detected.
4. How `RENDEREYE_ENV_FILE` is registered.
5. Why User scope is preferred over Machine scope.
6. How server startup loads the file.
7. Configuration precedence.
8. How to edit `.env` manually.
9. How to use a custom `.env` path.
10. How upgrades preserve settings.
11. How uninstallation handles the environment variable.
12. Why running coding agents may require restarting.

### Example File

Include `.env.example` in the release distribution.

Exclude real user `.env` files from source control and release artifacts.

Ensure the example does not contain secrets or developer-specific paths.

---

## 15. Definition of Done

This addendum is complete when:

- [ ] Installer creates `.env` in the RenderEyeMCP installation directory.
- [ ] A version-controlled `.env.example` exists.
- [ ] Default settings are generated correctly.
- [ ] RenderDoc is automatically detected when available.
- [ ] The detected RenderDoc path is written correctly.
- [ ] Missing RenderDoc does not prevent package installation.
- [ ] Only `RENDEREYE_ENV_FILE` is registered persistently.
- [ ] The variable is registered at Windows User scope.
- [ ] Machine environment variables remain untouched.
- [ ] Server loads `.env` before Config initialization.
- [ ] Existing environment values take precedence.
- [ ] Explicit missing `.env` paths produce clear errors.
- [ ] Reinstallation preserves user settings.
- [ ] Upgrade preserves user settings.
- [ ] Custom RenderDoc paths are not silently overwritten.
- [ ] Configuration updates are safe and validated.
- [ ] Uninstallation handles environment registration safely.
- [ ] Major coding agents use the centralized configuration.
- [ ] Manual installation remains supported.
- [ ] `uv` remains optional for end users.
- [ ] Linux portability is preserved.
- [ ] Automated tests pass.
- [ ] Existing Phase 0–5 functionality remains operational.
- [ ] Documentation is updated.

---

## 16. Execution Instructions

Execute the implementation in the following order:

1. Inspect the existing repository and installer.
2. Review the current Config implementation.
3. Identify existing `.env` or dotenv handling.
4. Add or update `.env.example`.
5. Implement environment bootstrap.
6. Ensure Config initialization occurs after bootstrap.
7. Integrate RenderDoc discovery into installation.
8. Implement `.env` generation.
9. Implement safe configuration merging and preservation.
10. Register `RENDEREYE_ENV_FILE` at Windows User scope.
11. Handle existing environment-variable conflicts.
12. Integrate environment handling into upgrades.
13. Integrate safe cleanup into uninstallation.
14. Update coding agent configuration generation.
15. Preserve manual installation.
16. Extend diagnostics.
17. Add automated tests.
18. Run the complete regression suite.
19. Test real installation and server startup where possible.
20. Update documentation.
21. Review acceptance criteria.
22. Produce a final report.

Work autonomously using the existing repository and development tools.

Do not rewrite unrelated functionality.

Do not introduce unnecessary dependencies.

Do not modify the production engine.

Do not modify RenderDoc source code.

Do not duplicate application configuration across individual coding agents.

Do not overwrite user-customized `.env` files.

Do not publish a GitHub Release without explicit authorization.

---

## 17. Final Report

After implementation, provide:

1. **Implementation Summary** — Environment configuration changes.
2. **Files Changed** — Installer, bootstrap, configuration, tests, and documentation.
3. **Installation Behavior** — First install and upgrade.
4. **RenderDoc Detection** — Discovery method and observed results.
5. **Environment Registration** — Scope, value, and conflict handling.
6. **Server Bootstrap** — Actual initialization sequence.
7. **Configuration Precedence** — Verified behavior.
8. **Coding Agent Integration** — Configuration inheritance and verification.
9. **Manual Installation** — Compatibility status.
10. **Test Results** — Commands and actual outcomes.
11. **Known Limitations** — Remaining platform-specific or environment propagation issues.
12. **Completion Status** — Complete, partially verified, or blocked.

Do not claim successful tests that were not executed.

Do not begin unrelated feature development.

**Primary Goal: RenderEyeMCP must use one installer-managed `.env` file, referenced through a single user-level `RENDEREYE_ENV_FILE` variable, consistently across all supported coding agents and server startup methods.**
