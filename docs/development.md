# Development Guide

This guide covers the developer workflow using `uv`.
For end-user installation (including without `uv`), see [Installation](en/installation.md).

## Prerequisites

- Python 3.11+ in PATH
- [uv](https://docs.astral.sh/uv/) 0.9.26+
- RenderDoc installed (auto-detected from `C:\Program Files\RenderDoc\` or set `RENDEREYE_RENDERDOC_EXE`)

## Setup

```bash
# Clone the repo
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP

# Create venv and install all dependencies (including dev)
uv sync

# Verify the MCP server works
uv run python -m rendereye_mcp
```

## Project Structure

```
src/rendereye_mcp/
    __init__.py          version string
    __main__.py          entry point (python -m rendereye_mcp)
    server.py            MCPServer + all MCP tools
    config.py            Config dataclass + RENDEREYE_* env overrides (incl. CaptureConfig)
    logging_setup.py     stderr logging configuration

    ipc/
        __init__.py
        protocol.py      message dataclasses + serialize/deserialize
        transport.py     asyncio TCP server
        connection.py    per-client handler

    platform/
        __init__.py
        windows.py       RenderDoc exe/process discovery

    captures/
        __init__.py      exports CaptureRegistry, CaptureStorage, CaptureRecord, CaptureStatus
        models.py        CaptureRecord dataclass + CaptureStatus enum
        discovery.py     scan_directory() — yields .rdc paths
        readiness.py     check_readiness() — async stability check
        storage.py       CaptureStorage — SQLite backend with threading.Lock
        registry.py      CaptureRegistry — coordinator (scan, watch, reconcile)
        watcher.py       CaptureWatcher — watchdog filesystem events

extensions/rendereye/    (Python 3.6 stdlib only — for RenderDoc)
    __init__.py          register(version, pyrenderdoc) / unregister() entry points
    ipc_client.py        background-thread TCP client
    extension.json       RenderDoc extension metadata

tests/
    test_config.py       Config defaults, env overrides, validation
    test_protocol.py     IPC message serialize/deserialize round-trips
    test_ipc.py          asyncio IPC server integration tests
    test_server.py       MCPServer creation + server_status tool
    captures/
        test_discovery.py   scan_directory() — filesystem scanning
        test_readiness.py   check_readiness() — async stability
        test_storage.py     CaptureStorage — SQLite CRUD
        test_registry.py    CaptureRegistry — integration
        test_mcp_tools.py   MCP tool logic (capture_list, etc.)
```

## Common Commands

### Run the server

```bash
# stdio transport (for MCP client connection)
uv run rendereye-mcp
# or
uv run python -m rendereye_mcp
```

### Run tests

```bash
uv run pytest tests/ -v
```

### Lint

```bash
uv run ruff check src/ extensions/ tests/
uv run ruff check src/ extensions/ tests/ --fix   # auto-fix
```

### Environment variable overrides

```bash
RENDEREYE_IPC_PORT=37021 uv run python -m rendereye_mcp
RENDEREYE_LOG_LEVEL=DEBUG uv run python -m rendereye_mcp
RENDEREYE_RENDERDOC_EXE=C:/Tools/RenderDoc/qrenderdoc.exe uv run python -m rendereye_mcp

# Phase 1: Configure capture directories
RENDEREYE_CAPTURE_DIRS="C:/RenderDocCaptures" uv run python -m rendereye_mcp
RENDEREYE_CAPTURE_DIRS="C:/dir1;C:/dir2" uv run python -m rendereye_mcp   # ";" on Windows, ":" on Linux
RENDEREYE_CAPTURE_STABILITY_SECONDS=1.0 uv run python -m rendereye_mcp
```

## Installing the RenderDoc Extension

1. Build/copy the extension to RenderDoc's extension directory:

```powershell
$dest = "$env:APPDATA\qrenderdoc\extensions\rendereye"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item -Recurse extensions\rendereye\* $dest
```

2. Open RenderDoc → Tools → Manage Extensions → select "RenderEyeMCP" → Load, and tick
   Always Load. (`uv run rendereye-mcp setup` does step 1 for you.)

3. Start the shared service (or let an agent start it via `rendereye-mcp serve`). The
   extension reconnects automatically, so start order does not matter:
   ```bash
   uv run rendereye-mcp service run
   ```

4. After changing extension code, keep `extensions/rendereye/` and
   `src/rendereye_mcp/_extension_data/` identical (tests enforce this), re-copy, and
   restart RenderDoc.

## Debugging

- All logs from `rendereye_mcp.*` go to **stderr**.
- MCP protocol JSON-RPC messages go to **stdout**.
- Set `RENDEREYE_LOG_LEVEL=DEBUG` for verbose output.
- The extension logs to stderr from within RenderDoc (check RenderDoc's log console).

## Dependency Notes

| Package | Version | Purpose |
|---------|---------|---------|
| mcp[cli] | 2.3.0 | MCP SDK — `MCPServer` (was `FastMCP` in 1.x) |
| psutil | 7.2.2 | Process enumeration for RenderDoc detection |
| watchdog | 6.0.0 | Filesystem event monitoring (Phase 1) |
| pytest | 9.1.1 | Test runner |
| pytest-asyncio | 1.4.0 | Async test support |
| ruff | 0.17.2 | Linter |

> **Note:** The extension (`extensions/rendereye/`) uses **stdlib only** and must remain
> Python 3.6 compatible. Do not import any third-party package from within the extension.

## RenderDoc API compliance

Use the context supplied by `register(version, pyrenderdoc)`. Dispatch all GUI
work through MiniQt, including initial sampling. Keep wheel `_extension_data`
resources byte-identical to `extensions/rendereye` (renaming the entry point).
The regression suite checks parity. See [integration](renderdoc_integration.md)
and [compatibility](renderdoc_api_compatibility.md). Real GUI validation is required
before declaring the extension fully verified; mocks alone are insufficient.
