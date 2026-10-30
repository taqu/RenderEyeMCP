# Development Guide

This guide covers the developer workflow for the Go implementation.
For end-user installation, see [Installation](en/installation.md).

## Prerequisites

- **Go 1.22+** in PATH
- **RenderDoc 1.46+** installed (for manual extension testing)
- `uv` — only needed for RenderDoc extension development (`uv sync`, `uv run pytest`)

## Repository structure

```
cmd/rendereye-mcp/
    main.go              entry point; subcommand dispatch (default→bridge, service, version, help)

internal/
    bridge/
        autostart.go     launch "rendereye-mcp service" detached; wait for ready
        sysattr_windows.go   CREATE_NEW_PROCESS_GROUP (detach on Windows)
        sysattr_unix.go      Setsid: true (detach on Linux/macOS)
        client.go        TCP client that connects to IPC service
        mcp.go           MCP stdio transport; 58 tool handlers
    server/
        server.go        IPC service; TCP listener; connection accept loop
        connhandler.go   per-connection read/write; heartbeat; gui-state handlers
        router.go        pending-call map; request routing; timeout loop
        router_test.go   unit tests for router (goroutine lifecycle, routing, isolation)
        integration_test.go  full-stack IPC integration tests
    lifecycle/
        lock.go          per-machine advisory lock (prevents duplicate service)
    version/
        version.go       ldflags-injectable Version / GitCommit / BuildDate

extensions/rendereye/    (Python 3.8 stdlib only — for RenderDoc's embedded Python)
    __init__.py          register(version, pyrenderdoc) / unregister() entry points
    ipc_client.py        background-thread TCP client
    extension.json       RenderDoc extension metadata

tests/                   Python tests for the RenderDoc extension only
scripts/
    install.ps1          Windows installer
    install.sh           Linux/macOS installer
.github/workflows/
    release-go.yml       cross-platform release build matrix
```

## Build

```bash
# Development build
go build ./cmd/rendereye-mcp/

# Release build with version metadata
go build -ldflags "-X github.com/taqu/RenderEyeMCP/internal/version.Version=1.0.0 \
  -X github.com/taqu/RenderEyeMCP/internal/version.GitCommit=$(git rev-parse --short HEAD) \
  -X github.com/taqu/RenderEyeMCP/internal/version.BuildDate=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  ./cmd/rendereye-mcp/
```

## Tests

```bash
# All Go tests
go test ./...

# Verbose
go test -v ./...

# Race detector
go test -race ./...

# Go vet
go vet ./...
```

## Run the MCP Bridge (for debugging)

```bash
# Start MCP Bridge on stdio (this is what the agent starts)
./rendereye-mcp

# Start the IPC service in the foreground (for debugging)
./rendereye-mcp service

# Version
./rendereye-mcp version
```

Set `RENDEREYE_LOG_LEVEL=debug` for verbose output. Bridge and service logs go to stderr.
stdout is reserved for MCP JSON-RPC traffic.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | IPC service bind/connect address |
| `RENDEREYE_IPC_PORT` | `37020` | IPC service port |
| `RENDEREYE_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error` |

Variables are loaded from a `.env` file in the same directory as the executable, then
overridden by actual environment variables.

## Installing the RenderDoc extension (for development)

```powershell
# Windows — copy to RenderDoc user extensions folder
$dest = "$env:APPDATA\qrenderdoc\extensions\rendereye"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item -Recurse extensions\rendereye\* $dest
```

```bash
# Linux
mkdir -p ~/.local/share/renderdoc/plugins/rendereye
cp -r extensions/rendereye/. ~/.local/share/renderdoc/plugins/rendereye/
```

Then enable in RenderDoc → **Tools → Manage Extensions** → *Always Load*.

After changing extension code, re-copy and restart RenderDoc.

## RenderDoc extension development (Python)

The extension uses RenderDoc's embedded Python (3.8 in RenderDoc 1.46) and stdlib only.

```bash
# Install Python dev dependencies
uv sync

# Run extension unit tests
uv run pytest tests/ -v
```

Do not import any third-party package from within the extension. Keep it compatible with
Python 3.8.

## Cross-platform builds

The release workflow (`.github/workflows/release-go.yml`) builds for:

| OS | Architecture | Archive |
|----|-------------|---------|
| Windows | amd64 | `.zip` |
| Windows | arm64 | `.zip` |
| Linux | amd64 | `.tar.gz` |
| Linux | arm64 | `.tar.gz` |
| macOS | arm64 | `.tar.gz` |

Each archive contains: binary + `extension/` + installer script + README + LICENSE.

To replicate a release build locally:

```bash
GOOS=linux GOARCH=amd64 go build -o rendereye-mcp ./cmd/rendereye-mcp/
GOOS=windows GOARCH=amd64 go build -o rendereye-mcp.exe ./cmd/rendereye-mcp/
```

## Debugging the IPC protocol

Run the service in the foreground (`./rendereye-mcp service`) with
`RENDEREYE_LOG_LEVEL=debug` to see all connection events, message routing, and timeouts
on stderr. The bridge also logs at debug level when `RENDEREYE_LOG_LEVEL=debug` is set.

## RenderDoc API compliance notes

The extension dispatches all GUI work through
`Extensions().GetMiniQtHelper().InvokeOntoUIThread`. Never call `CaptureContext` methods
directly from the IPC worker thread. See [IPC protocol](ipc_protocol.md) and
[RenderDoc integration](renderdoc_integration.md) for details.
