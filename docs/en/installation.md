[English](installation.md) | [日本語](../ja/installation.md)

# Install RenderEyeMCP

This page installs the `rendereye-mcp` binary, the RenderDoc extension, and the
configuration file. Connecting a coding agent is covered in
[Configuration](configuration.md).

- [What gets installed](#what-gets-installed)
- [Requirements](#requirements)
- [Install on Windows](#install-on-windows)
- [Install on Linux](#install-on-linux)
- [Enable the RenderDoc extension](#enable-the-renderdoc-extension)
- [Verify the installation](#verify-the-installation)
- [Update](#update)
- [Uninstall](#uninstall)
- [What was tested](#what-was-tested)

## What gets installed

| Piece | Where |
|-------|-------|
| `rendereye-mcp.exe` (MCP Bridge + IPC Service) | Stays in the directory where you extracted the archive |
| RenderDoc extension `rendereye/` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `~/.local/share/qrenderdoc/extensions/rendereye/` |
| Configuration file `.env` | Same folder as the archive (next to `rendereye-mcp.exe`) |

The executable is **not** copied to another location. Keep the extracted directory
in place and point your coding agent's MCP configuration directly at `rendereye-mcp.exe`
there. Moving or deleting the extracted directory requires updating the agent configuration.

Nothing is installed into RenderDoc's own program directory, and RenderDoc itself is not bundled.

## Requirements

- **RenderDoc 1.46** or later. The extension declares 1.46 as its minimum version.
- An MCP-capable coding agent: **Claude Code** or **Codex**.
- No Python, pip, uv, or Go toolchain required.

## Install on Windows

### Step 1 — Download the release archive

Download `rendereye-mcp_<version>_windows_amd64.zip` from the
[GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) page and extract it.

### Step 2 — Run the installer

Open PowerShell in the extracted folder and run:

```powershell
.\install.ps1
```

The installer:

1. Verifies that `rendereye-mcp.exe` is present in the same directory.
2. Copies the `extension/` files to `%APPDATA%\qrenderdoc\extensions\rendereye\`.
3. Creates a default `.env` next to the executable (not overwritten on subsequent runs).
4. Prints the MCP configuration snippet to use in your agent's config.

**Custom extension directory?** Pass it explicitly:

```powershell
.\install.ps1 -RenderDocExtDir "C:\custom\path\to\extensions"
```

**Updating?** Re-run with `-Force` to overwrite the existing extension:

```powershell
.\install.ps1 -Force
```

**Manual extension installation** (without the installer):

```powershell
$extDst = "$env:APPDATA\qrenderdoc\extensions\rendereye"
New-Item -ItemType Directory -Force -Path $extDst
Copy-Item -Recurse extension\* $extDst
```

### Step 3 — Verify the binary

```powershell
.\rendereye-mcp.exe version
```

Expected output: `rendereye-mcp v<version> ...`

Continue with [Enable the RenderDoc extension](#enable-the-renderdoc-extension).

## Install on Linux

### Step 1 — Download the release archive

Download `rendereye-mcp_<version>_linux_amd64.tar.gz` from the
[GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) page and extract it:

```bash
tar -xzf rendereye-mcp_<version>_linux_amd64.tar.gz
cd rendereye-mcp_<version>_linux_amd64
```

### Step 2 — Run the installer

```bash
./install.sh
```

The installer verifies `rendereye-mcp` is present, copies the extension to
`~/.local/share/qrenderdoc/extensions/rendereye/`, and creates a default `.env` next to
the executable.

**Custom extension directory?**

```bash
./install.sh --renderdoc-ext-dir ~/.local/share/qrenderdoc/extensions
```

**Updating?**

```bash
./install.sh --force
```

### Step 3 — Verify the binary

```bash
./rendereye-mcp version
```

Linux RenderDoc integration has not been validated live; the installer follows the
implemented code paths.

## Enable the RenderDoc extension

RenderDoc does not load user extensions until you enable them once:

1. Start RenderDoc.
2. Open **Tools → Manage Extensions**.
3. Select **RenderEyeMCP** in the list and enable **Always Load**.

With *Always Load* set, the extension starts with every RenderDoc window.

The extension connects to the IPC service on `127.0.0.1:37020`. The service is started
automatically by the MCP Bridge when your coding agent launches `rendereye-mcp`. If
RenderDoc starts first, the extension retries in the background (back-off up to 30
seconds), so start order does not matter.

## Verify the installation

Work through these in order:

1. **Binary works**

   ```powershell
   .\rendereye-mcp.exe version
   ```

   Expect a version line such as `rendereye-mcp v1.0.0 ...`

2. **MCP server starts and the agent sees the tools** — follow
   [Configuration → Verify](configuration.md#verify-the-connection). For example,
   `claude mcp get rendereye` should report `Connected`.

3. **RenderDoc is discovered** — start RenderDoc (extension enabled) and ask the agent:

   > List the RenderDoc sessions RenderEyeMCP can see.

   The answer should include a session with `connection_state: connected`.

4. **An already-loaded capture can be inspected** — open an `.rdc` file, select a draw
   call, and ask:

   > What capture is open in RenderDoc, and which event is selected?

A process that merely starts is not proof that everything is connected; step 3 is the
first point where the extension, the service, and the MCP bridge are all involved.

## Update

1. Download the new release archive and extract it to a directory.
2. Stop any running IPC service or coding agent sessions.
3. Run the installer with `-Force` to update the extension:

   ```powershell
   .\install.ps1 -Force
   ```

4. Update the `command` path in your agent's MCP configuration if you extracted to a
   new directory.
5. Restart RenderDoc to load the updated extension.
6. Restart your coding agent.

If you extracted the new version to the same directory, the agent configuration does not
need to change.

## Uninstall

**Windows:**

1. Stop any coding agents using RenderEyeMCP and wait for the IPC service to exit.
2. Remove the RenderEyeMCP entry from your agent's MCP configuration.
3. Remove the RenderDoc extension:

   ```powershell
   Remove-Item -Recurse "$env:APPDATA\qrenderdoc\extensions\rendereye"
   ```

4. Delete the extracted RenderEyeMCP directory (contains `rendereye-mcp.exe` and
   `.env`).

**Linux:**

1. Remove the RenderDoc extension:

   ```bash
   rm -rf ~/.local/share/qrenderdoc/extensions/rendereye
   ```

2. Delete the extracted RenderEyeMCP directory.

## What was tested

| Method | Environment | Result |
|--------|-------------|--------|
| `install.ps1` | Windows 11, extracted release archive | Pass |
| `install.ps1 -Force` | Windows 11, re-run over existing installation | Pass |
| Manual copy | Windows 11 | Pass |
| `install.sh` | — | Code path validated; live RenderDoc not tested |
| Clean Windows machine / VM | — | **Not performed** |
| Linux end-to-end with RenderDoc | — | **Not performed** |
