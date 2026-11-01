[English](installation.md) | [日本語](../ja/installation.md)

# Install RenderEyeMCP

This page installs the RenderEyeMCP binary and its RenderDoc extension.
Connecting a coding agent is covered in [Configuration](configuration.md).

- [What gets installed](#what-gets-installed)
- [Prerequisites](#prerequisites)
- [Install on Windows](#install-on-windows)
- [Install on Linux](#install-on-linux)
- [Enable the RenderDoc extension](#enable-the-renderdoc-extension)
- [Verify the installation](#verify-the-installation)
- [Update](#update)
- [Uninstall](#uninstall)

## What gets installed

| Piece | Where |
|-------|-------|
| `rendereye-mcp.exe` (MCP Bridge + Shared IPC Service) | Wherever you extract the archive |
| RenderDoc extension `rendereye` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `~/.local/share/qrenderdoc/extensions/rendereye/` |

Nothing is installed into RenderDoc's own directory.
No Python, pip, or uv is required to run RenderEyeMCP.

## Prerequisites

- **RenderDoc 1.46** or later installed.
- A coding agent that supports MCP over stdio (Claude Code, Codex, Cursor, etc.).

## Install on Windows

1. Download the latest `rendereye-mcp_<version>_windows_amd64.zip` from the
   [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) page.

2. Extract the archive to a permanent directory, for example:

   ```text
   C:\Tools\RenderEyeMCP\
   ```

   After extraction the directory contains:

   ```text
   rendereye-mcp.exe
   install.ps1
   extensions\
   README.md
   LICENSE
   ```

3. Open PowerShell in that directory and run the installer:

   ```powershell
   .\install.ps1
   ```

   The installer copies the RenderDoc extension to
   `%APPDATA%\qrenderdoc\extensions\rendereye\` and prints the
   coding-agent configuration snippet to use.

   Use `.\install.ps1 -Force` to overwrite an existing extension installation.

4. Configure your coding agent using the snippet printed by the installer.
   See [Configuration](configuration.md) for full examples.

## Install on Linux

1. Download the latest `rendereye-mcp_<version>_linux_amd64.tar.gz` from the
   [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) page.

2. Extract the archive to a permanent directory:

   ```bash
   mkdir -p ~/tools/rendereye-mcp
   tar -xzf rendereye-mcp_*_linux_amd64.tar.gz -C ~/tools/rendereye-mcp --strip-components=1
   ```

3. Run the installer:

   ```bash
   cd ~/tools/rendereye-mcp
   ./install.sh
   ```

   The installer copies the RenderDoc extension to
   `~/.local/share/qrenderdoc/extensions/rendereye/` and prints the
   coding-agent configuration snippet.

   Use `./install.sh --force` to overwrite an existing installation.

4. Make the binary executable if the archive did not preserve permissions:

   ```bash
   chmod +x ~/tools/rendereye-mcp/rendereye-mcp
   ```

## Enable the RenderDoc extension

RenderDoc does not load user extensions until you enable them once:

1. Start RenderDoc.
2. Open **Tools → Manage Extensions**.
3. Select **RenderEyeMCP** in the list, click **Load**, and tick **Always Load**.

With *Always Load* set, the extension starts with every RenderDoc window, including
windows opened by Unity or Unreal Engine.

The extension connects to the RenderEyeMCP IPC service on `127.0.0.1:37020`.
The service starts automatically when the coding agent first invokes the binary,
so you do not need to start it manually.

## Verify the installation

1. **Binary works:**

   ```powershell
   C:\Tools\RenderEyeMCP\rendereye-mcp.exe version
   ```

   Expected output includes the version number and build date.

2. **Extension is installed:**

   Check that `%APPDATA%\qrenderdoc\extensions\rendereye\` exists and contains
   `__init__.py`, `extension.json`, and the other extension files.

3. **Agent sees the tools** — after configuring the agent, ask it:

   > List the MCP tools available from the rendereye server.

   The response should include tools like `get_current_capture` and `list_renderdoc_sessions`.

4. **RenderDoc is connected** — start RenderDoc with the extension enabled,
   open a capture, and ask the agent:

   > List the RenderDoc sessions RenderEyeMCP can see.

   The answer should include a session with `connection_state: connected`.

## Update

1. Download the new release archive.
2. Extract it, replacing the previous directory contents.
3. Run `install.ps1` (or `install.sh`) again to update the RenderDoc extension.
4. Restart RenderDoc so it loads the updated extension.

Agent configuration does not change as long as the binary path is the same.

## Uninstall

1. Remove the RenderDoc extension directory:
   - Windows: delete `%APPDATA%\qrenderdoc\extensions\rendereye\`
   - Linux: delete `~/.local/share/qrenderdoc/extensions/rendereye/`

2. Remove the `rendereye` entry from your agent's MCP configuration file.

3. Delete the extracted archive directory.
