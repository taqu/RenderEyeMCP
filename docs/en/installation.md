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
| `rendereye-mcp.exe` (MCP Bridge + IPC Service) | Windows: `%LOCALAPPDATA%\RenderEyeMCP\`<br>Linux: `~/.local/bin/` |
| RenderDoc extension `rendereye/` | Auto-detected RenderDoc plugins folder |
| Configuration file `.env` | Same folder as the executable |

Nothing is installed into RenderDoc's own directory, and RenderDoc itself is not bundled.

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

1. Copies `rendereye-mcp.exe` to `%LOCALAPPDATA%\RenderEyeMCP\`.
2. Auto-detects the RenderDoc plugins folder and copies the `extension/` files there.
3. Creates a default `.env` in `%LOCALAPPDATA%\RenderEyeMCP\` (not overwritten on
   subsequent runs).
4. Prints the MCP configuration snippet to use in your agent's config.

**RenderDoc not detected?** Pass the path explicitly:

```powershell
.\install.ps1 -RenderDocExtDir "C:\Program Files\RenderDoc\plugins"
```

**Updating?** Re-run with `-Force` to overwrite the existing binary:

```powershell
.\install.ps1 -Force
```

**Manual installation** (without the installer):

```powershell
$dest = "$env:LOCALAPPDATA\RenderEyeMCP"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item rendereye-mcp.exe $dest
# copy extension to your RenderDoc plugins\rendereye directory
Copy-Item -Recurse extension\ "$env:APPDATA\qrenderdoc\extensions\rendereye"
```

### Step 3 — Verify the binary

```powershell
& "$env:LOCALAPPDATA\RenderEyeMCP\rendereye-mcp.exe" version
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

The installer copies `rendereye-mcp` to `~/.local/bin/` (or `--install-dir DIR`),
auto-detects the RenderDoc plugins folder, copies the extension, and creates a default
`.env` next to the binary.

**RenderDoc not detected?**

```bash
./install.sh --renderdoc-ext-dir ~/.local/share/renderdoc/plugins
```

**Updating?**

```bash
./install.sh --force
```

### Step 3 — Add `~/.local/bin` to PATH (if needed)

If the installer warns that `~/.local/bin` is not in `$PATH`, add this to your shell
profile (`~/.bashrc` or `~/.zshrc`):

```bash
export PATH="$PATH:$HOME/.local/bin"
```

Then open a new terminal and verify:

```bash
rendereye-mcp version
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
   & "$env:LOCALAPPDATA\RenderEyeMCP\rendereye-mcp.exe" version
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

1. Download the new release archive and extract it.
2. Stop any running IPC service or coding agent sessions.
3. Re-run the installer with `-Force`:

   ```powershell
   .\install.ps1 -Force
   ```

4. Restart RenderDoc to load the updated extension.
5. Restart your coding agent.

Agent configuration files do not need changes as long as the executable path is the same.

## Uninstall

**Windows:**

```powershell
# Remove the executable and .env
Remove-Item -Recurse "$env:LOCALAPPDATA\RenderEyeMCP"

# Remove the RenderDoc extension (path may vary)
Remove-Item -Recurse "$env:APPDATA\qrenderdoc\extensions\rendereye"
```

**Linux:**

```bash
rm -f ~/.local/bin/rendereye-mcp ~/.local/bin/.env
rm -rf ~/.local/share/renderdoc/plugins/rendereye
```

## What was tested

| Method | Environment | Result |
|--------|-------------|--------|
| `install.ps1` | Windows 11, extracted release archive | Pass |
| `install.ps1 -Force` | Windows 11, re-run over existing installation | Pass |
| Manual copy | Windows 11 | Pass |
| `install.sh` | — | Code path validated; live RenderDoc not tested |
| Clean Windows machine / VM | — | **Not performed** |
| Linux end-to-end with RenderDoc | — | **Not performed** |
