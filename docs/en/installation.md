[English](installation.md) | [日本語](../ja/installation.md)

# Install RenderEyeMCP

This page installs RenderEyeMCP, the RenderDoc extension and the configuration file.
Connecting a coding agent is covered in [Configuration](configuration.md).

- [What gets installed](#what-gets-installed)
- [Prerequisites](#prerequisites)
- [Install on Windows](#install-on-windows)
- [Install on Linux](#install-on-linux)
- [Enable the RenderDoc extension](#enable-the-renderdoc-extension)
- [Verify the installation](#verify-the-installation)
- [Update](#update)
- [Uninstall](#uninstall)
- [What was tested](#what-was-tested)

## What gets installed

| Piece | Where | Created by |
|-------|-------|-----------|
| `rendereye-mcp` command (MCP server, shared service, setup tools) | Your Python tool environment | `uv tool install` or `pip` |
| Configuration file `.env` | Windows: `%LOCALAPPDATA%\RenderEyeMCP\.env`<br>Linux: `$XDG_CONFIG_HOME/rendereye_mcp/.env` (default `~/.config/rendereye_mcp/.env`) | `rendereye-mcp setup` |
| RenderDoc extension `rendereye` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `$XDG_DATA_HOME/qrenderdoc/extensions/rendereye/` (default `~/.local/share/...`) | `rendereye-mcp setup` |
| `RENDEREYE_ENV_FILE` user environment variable (points to `.env`) | Windows: user environment (registry)<br>Linux: you add it to your shell profile | `rendereye-mcp setup` (Windows) |

Nothing is installed into RenderDoc's own directory, and RenderDoc itself is not bundled.

## Prerequisites

- **RenderDoc 1.46** installed. The extension declares 1.46 as its minimum version.
- **Python 3.11 or later**. With `uv` you do not need to install Python yourself.
- **[uv](https://docs.astral.sh/uv/)** (recommended), or plain `python -m venv` + `pip`.
- Git, only if you install from a source checkout.

> **Release status:** no public release has been published yet. The commands below use
> either a source checkout or a wheel file (`rendereye_mcp-<version>-py3-none-any.whl`).
> When a release is published, its ZIP contains the wheel in `python/`.

## Install on Windows

### Option A — uv (recommended)

```powershell
# Install uv if needed, then open a new terminal
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# From a source checkout
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
uv tool install .

# ...or from a wheel file
uv tool install .\rendereye_mcp-1.0.0-py3-none-any.whl
```

If `rendereye-mcp` is not found afterwards, run `uv tool update-shell` and open a new
terminal. Check it with:

```powershell
rendereye-mcp --version
```

### Option B — pip in a virtual environment (no uv)

```powershell
$installDir = "$env:LOCALAPPDATA\RenderEyeMCP"
py -3.11 -m venv "$installDir\venv"      # any Python 3.11+ works; plain `python` is fine too
& "$installDir\venv\Scripts\python.exe" -m pip install .\rendereye_mcp-1.0.0-py3-none-any.whl
& "$installDir\venv\Scripts\rendereye-mcp.exe" --version
```

In the following steps, replace `rendereye-mcp` with
`& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\rendereye-mcp.exe"`.

### Run setup

```powershell
rendereye-mcp setup
```

`setup` does four things:

1. Creates `%LOCALAPPDATA%\RenderEyeMCP\.env` from the bundled template. **An existing
   `.env` is never overwritten**; setup prints `Existing .env preserved`.
2. Looks for RenderDoc at `%ProgramFiles%\RenderDoc\qrenderdoc.exe` and
   `%ProgramFiles(x86)%\RenderDoc\qrenderdoc.exe` and writes the path to
   `RENDEREYE_RENDERDOC_EXE`. A value you already set is kept.
3. Copies the RenderDoc extension to `%APPDATA%\qrenderdoc\extensions\rendereye\`
   (re-running setup updates it).
4. Registers `RENDEREYE_ENV_FILE` as a user environment variable.

**RenderDoc in a custom location?** If setup prints `RenderDoc not found`, edit the
`.env` file and set the full path, for example:

```dotenv
RENDEREYE_RENDERDOC_EXE=D:\Tools\RenderDoc\qrenderdoc.exe
```

This path is only used by `server_status`/`doctor` checks and by the optional
`capture_open` tool. Inspecting a capture you opened yourself does not need it.

**Open a new terminal** (and restart any running coding agent or IDE) so that
`RENDEREYE_ENV_FILE` is visible. Then continue with
[Enable the RenderDoc extension](#enable-the-renderdoc-extension).

## Install on Linux

Linux is not validated with a live RenderDoc yet; the steps below follow the implemented
code paths.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # if needed
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
uv tool install .
rendereye-mcp setup
```

`setup` detects `qrenderdoc` in `/usr/bin`, `/usr/local/bin` or `~/.local/bin`, installs
the extension under `~/.local/share/qrenderdoc/extensions/rendereye/`, and prints an
`export RENDEREYE_ENV_FILE=...` line. Add that line to your shell profile, then open a new
terminal and restart your agent.

## Enable the RenderDoc extension

RenderDoc does not load user extensions until you enable them once:

1. Start RenderDoc.
2. Open **Tools → Manage Extensions**.
3. Select **RenderEyeMCP** in the list, click **Load**, and tick **Always Load**.

With *Always Load* set, the extension starts with every RenderDoc window, including
windows opened by Unity or Unreal Engine.

The extension connects to the RenderEyeMCP shared service on `127.0.0.1:37020`. The
service is started automatically by the first coding agent that launches
`rendereye-mcp serve`. If RenderDoc starts first, the extension retries in the background
(back-off up to 30 seconds), so the order does not matter.

## Verify the installation

Work through these in order. Each step checks something the previous one does not.

1. **Installation and configuration**

   ```powershell
   rendereye-mcp doctor
   ```

   Expect `[✓]` for Version, Executable, `.env` file, `RENDEREYE_ENV_FILE`, RenderDoc
   executable and RenderDoc extension. A warning for *Shared service* is normal when no
   agent is running.

2. **MCP server starts and the agent sees the tools** — follow
   [Configuration → Verify](configuration.md#verify-the-connection). For example,
   `claude mcp get rendereye` should report `Connected`.

3. **Shared service is running** — after the agent has started:

   ```powershell
   rendereye-mcp service status
   ```

   Expect `Service: running` and `Listening: 127.0.0.1:37020`.

4. **RenderDoc is discovered** — start RenderDoc (extension enabled) and ask the agent:

   > List the RenderDoc sessions RenderEyeMCP can see.

   The answer should include a session with `connection_state: connected`.

5. **An already-loaded capture can be inspected** — open an `.rdc` file, select a draw
   call, and ask:

   > What capture is open in RenderDoc, and which event is selected?

A process that merely starts is not proof that everything is connected; step 4 is the
first point where the extension, the service and the MCP server are all involved.

## Update

```powershell
cd RenderEyeMCP; git pull; uv tool install --force .   # source checkout
uv tool install --force .\rendereye_mcp-<new>-py3-none-any.whl   # wheel
rendereye-mcp service stop     # restart the shared service on the new version
rendereye-mcp setup            # refreshes the RenderDoc extension; keeps your .env
```

Restart RenderDoc so it loads the updated extension, and restart your coding agent.
Agent configuration files do not need changes as long as the executable path is the same.

## Uninstall

```powershell
rendereye-mcp setup-agent claude-code --remove   # repeat per agent you configured
rendereye-mcp service stop
rendereye-mcp uninstall-setup                    # removes the extension and RENDEREYE_ENV_FILE
uv tool uninstall rendereye-mcp                  # or delete the venv directory
```

`uninstall-setup` keeps `%LOCALAPPDATA%\RenderEyeMCP\` (your `.env`) and the database
under `%APPDATA%\rendereye_mcp\`. Delete those folders manually to remove everything.

## What was tested

| Method | Environment | Result |
|--------|-------------|--------|
| `uv tool install .` (source) | Windows 11, uv 0.12, isolated tool dir | Pass |
| `uv tool install <wheel>` | Windows 11, wheel built with `uv build` | Pass |
| `pip install <wheel>` in a fresh venv | Windows 11, Python 3.12.6, no uv | Pass |
| `rendereye-mcp setup` (twice) | Windows 11, isolated `%LOCALAPPDATA%`/`%APPDATA%`; registry write stubbed | Pass: `.env` created then preserved, RenderDoc detected, 6 extension files installed |
| `uv tool install --force .` (update), `uninstall-setup` | Windows 11, isolated directories | Pass: extension removed, `.env` kept |
| `pip install <wheel>` in a clean venv | CI: Windows and Ubuntu, Python 3.11/3.12 | Runs in CI |
| Clean Windows machine / VM | — | **Not performed.** Tests ran on a development machine with isolated directories |
| Linux end-to-end with RenderDoc | — | **Not performed** |
