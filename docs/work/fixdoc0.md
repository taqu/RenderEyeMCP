# RenderEyeMCP — Simplify Windows Installation for Go Distribution

## Objective

Simplify the Windows installation process for the Go-based RenderEyeMCP distribution.

The Go implementation is a standalone native executable and no longer requires a Python environment or installation into a separate application directory.

Update `install.ps1`, `README.md`, and related installation documentation to support a portable distribution model.

This task covers two primary changes:

1. Correct the RenderDoc Extension installation directory.
2. Remove the unnecessary executable installation/copy step.

Preserve existing runtime functionality, MCP compatibility, and multi-agent support.

---

## 1. Correct RenderDoc Extension Installation Directory

### Current Problem

The existing `install.ps1` attempts to locate the RenderDoc Extension directory using paths such as:

```powershell
"$env:ProgramFiles\RenderDoc\plugins\amd\renderdoc"
"$env:ProgramFiles\RenderDoc\plugins"
"$env:LOCALAPPDATA\RenderDoc\plugins"
```

These paths should not be used as default destinations for the RenderDoc Python Extension.

### Required Behavior

Use the per-user RenderDoc extension directory:

```text
%APPDATA%\qrenderdoc\extensions\
```

The RenderEyeMCP extension should be installed under:

```text
%APPDATA%\qrenderdoc\extensions\rendereye\
```

In PowerShell:

```powershell
if ([string]::IsNullOrWhiteSpace($RenderDocExtDir)) {
    $RenderDocExtDir = Join-Path $env:APPDATA "qrenderdoc\extensions"
}

$ExtDst = Join-Path $RenderDocExtDir "rendereye"
```

### Implementation Requirements

- Use `$env:APPDATA`, not `$env:LOCALAPPDATA`.
- Do not search RenderDoc's installation directory to locate the extension destination.
- Create the extension directory if it does not exist.
- Preserve the existing `-RenderDocExtDir` override, if provided.
- Preserve the extension's required directory structure and files.
- Make repeated installation safe.
- Handle missing extension source files and copy failures explicitly.
- Do not require administrator privileges for a normal per-user installation.
- Do not modify RenderDoc's program files.

Verify the actual extension package layout before implementing the copy operation. Avoid accidentally creating an extra nested `rendereye` directory.

After installation, instruct users to restart RenderDoc and enable or load the extension through RenderDoc's extension management interface if necessary.

Do not claim that copying the extension automatically enables it unless that behavior is verified.

---

## 2. Remove Executable Installation and Copying

### Current Problem

The existing installer copies:

```text
rendereye-mcp.exe
```

from the extracted release archive into a separate `$InstallDir`.

This was useful for the earlier Python-based distribution model but is unnecessary for the standalone Go executable.

### Required Behavior

Treat RenderEyeMCP as a portable application.

Users should be able to:

1. Download the appropriate GitHub Releases archive.
2. Extract it into a permanent directory of their choice.
3. Run `install.ps1` to install the RenderDoc Extension.
4. Configure their coding agent to launch `rendereye-mcp.exe` directly from the extracted directory.

Do not copy `rendereye-mcp.exe` to another directory.

### Implementation Requirements

Remove the executable installation logic that:

- Creates `$InstallDir` for the executable.
- Copies `rendereye-mcp.exe` into `$InstallDir`.
- Prompts to overwrite an existing executable in `$InstallDir`.
- Uses `$Force` specifically to control executable overwriting.
- Assumes the executable is installed under `%LOCALAPPDATA%\RenderEyeMCP`.

Preserve `$Force` only if it remains useful for other installer operations.

Use the directory containing `install.ps1` as the release root:

```powershell
$ScriptDir = $PSScriptRoot
$ExeSrc = Join-Path $ScriptDir "rendereye-mcp.exe"
$ExtSrc = Join-Path $ScriptDir "extension"
```

Verify that the executable exists and resolve its absolute path:

```powershell
if (-not (Test-Path $ExeSrc -PathType Leaf)) {
    Write-Fail "rendereye-mcp.exe not found in $ScriptDir"
    exit 1
}

$ExePath = (Resolve-Path $ExeSrc).Path
```

Optionally validate the executable using the existing supported CLI version command.

Do not introduce new CLI flags or commands solely for installation validation.

The installer must not relocate, rename, or modify the executable.

### Portable Distribution Layout

Preserve the actual release archive structure, with a layout conceptually equivalent to:

```text
RenderEyeMCP/
├── rendereye-mcp.exe
├── install.ps1
└── extension/
    └── ...
```

The installation script should only perform operations that are actually necessary, primarily installing the RenderDoc Extension and providing configuration guidance.

---

## 3. Update MCP Configuration Instructions

### README.md

Update the installation section to explain that RenderEyeMCP runs directly from the extracted directory.

Remove the hardcoded executable location:

```text
C:\Users\<you>\AppData\Local\RenderEyeMCP\rendereye-mcp.exe
```

Replace it with an example based on the user's chosen extraction directory.

For Claude Code:

```json
{
  "mcpServers": {
    "rendereye": {
      "command": "C:\\path\\to\\RenderEyeMCP\\rendereye-mcp.exe"
    }
  }
}
```

Explain that:

- The executable is not copied during installation.
- An absolute executable path is recommended.
- The extracted directory must be retained after configuration.
- Moving or deleting that directory requires updating the MCP configuration.
- The executable does not require a separate Python environment.
- The Shared IPC Service continues to be managed according to the existing Go implementation.

Preserve the correct configuration instructions for other supported coding agents, including Codex.

Do not assume that all coding agents use identical configuration formats.

### Installer Output

At the end of `install.ps1`, display the absolute path of the executable and a usable MCP configuration example.

Generate the configuration using the actual resolved executable path rather than a hardcoded user profile directory.

For example:

```powershell
$config = @{
    mcpServers = @{
        rendereye = @{
            command = $ExePath
        }
    }
}

Write-Host ($config | ConvertTo-Json -Depth 5)
```

Ensure that Windows path escaping is handled correctly.

Do not automatically modify coding-agent configuration files as part of this task.

---

## 4. Update Installation Documentation

Review and update all active installation documentation, including:

- Root `README.md`.
- English installation guide.
- Japanese installation guide.
- Any Windows quick-start documentation.
- Other documentation containing hardcoded executable installation paths.

The documentation must consistently describe the portable Go distribution model.

### Updated User Workflow

```text
Download GitHub Release
        |
        v
Extract to a permanent directory
        |
        v
Run install.ps1
        |
        +-- Install RenderDoc Extension
        |
        +-- Display MCP configuration
        |
        v
Configure coding agent
        |
        v
Open RenderDoc and load the extension
        |
        v
Use RenderEyeMCP
```

Remove obsolete instructions involving:

- Copying the Go executable into a separate installation directory.
- Installing a Python MCP package.
- Creating Python virtual environments for MCP execution.
- Using `pip` or `uv` for normal Go distribution installation.
- Assuming `%LOCALAPPDATA%\RenderEyeMCP` is the executable location.

Keep Python-related documentation where it is still necessary for RenderDoc Extension development.

Do not create Python-to-Go migration documentation.

---

## 5. Update Uninstallation Instructions

Since the executable is no longer copied elsewhere, update the uninstall documentation accordingly.

The basic procedure should be:

1. Stop coding agents using RenderEyeMCP.
2. Stop the Shared IPC Service if it remains running.
3. Remove RenderEyeMCP entries from coding-agent MCP configurations.
4. Remove the RenderDoc Extension from the per-user extension directory.
5. Delete the extracted RenderEyeMCP directory.

Do not assume that deleting the executable automatically terminates an independently running Shared IPC Service.

Do not delete unrelated RenderDoc extensions or user data.

If an existing uninstall script assumes the old `$InstallDir` layout, update it consistently with the new portable distribution model.

---

## 6. Preserve Existing Functionality

This task is an installation and documentation cleanup.

Do not modify:

- MCP Tool names or schemas.
- IPC protocol framing or serialization.
- Shared IPC Service routing behavior.
- Multi-agent concurrency behavior.
- RenderDoc capture/session management.
- RenderDoc Extension runtime logic.
- Go MCP Bridge runtime behavior.

Avoid unrelated refactoring.

Do not introduce a new package manager, installer framework, system service, or background process.

---

## 7. Validation

Perform the following checks.

### Installer Validation

Verify that:

- `install.ps1` works when executed from an arbitrary extracted release directory.
- The executable remains in its original location.
- The RenderDoc Extension is copied to the correct per-user directory.
- Missing extension directories are created automatically.
- The `-RenderDocExtDir` override still works.
- Repeated installation succeeds.
- Missing files and permission failures produce useful error messages.
- No administrator privileges are required for the default installation.
- No obsolete executable installation directory is created.

### Configuration Validation

Verify that:

- The generated MCP configuration references the actual executable location.
- Windows paths are escaped correctly in JSON.
- The documented Claude Code configuration is valid.
- The documented Codex configuration matches its supported format.
- Moving the extracted directory does not silently leave invalid documentation or configuration assumptions.

### Documentation Validation

Verify that:

- English and Japanese installation documentation agree.
- README.md describes the portable distribution model.
- No active installation guide incorrectly requires Python, pip, uv, or a Go toolchain for normal users.
- No obsolete `%LOCALAPPDATA%\RenderEyeMCP` executable path remains in active user instructions.
- RenderDoc Extension activation instructions are accurate.
- Release artifact names and directory structures match the actual build output.

Use automated validation where practical. If full Windows or RenderDoc integration testing is unavailable, clearly report which checks were not performed.

---

## Acceptance Criteria

The task is complete when:

1. `install.ps1` installs the RenderDoc Extension under `%APPDATA%\qrenderdoc\extensions\rendereye` by default.
2. RenderDoc installation-directory discovery is no longer used to choose the extension destination.
3. `rendereye-mcp.exe` is never copied to a separate installation directory.
4. MCP clients execute the Go binary directly from the extracted release directory.
5. The installer displays the resolved executable path and appropriate configuration guidance.
6. README.md and English/Japanese installation documentation reflect the new installation model.
7. Uninstallation instructions are consistent with the portable distribution.
8. Existing MCP, IPC, RenderDoc integration, and multi-agent functionality remain unchanged.
9. Validation results and any remaining limitations are reported.

## Deliverables

- Updated `install.ps1`.
- Updated `README.md`.
- Updated English and Japanese installation guides.
- Updated uninstall instructions or scripts, where applicable.
- Updated installer tests, where applicable.
- A concise summary of changed files and validation results.

Do not publish a release or create a release tag as part of this task.
