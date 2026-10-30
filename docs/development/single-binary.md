# Single Binary Distribution (Phase 19)

Phase 19 combines the Go MCP Bridge and Go Shared IPC Service into one executable (`rendereye-mcp`) while preserving their separate-process architecture.

## Architecture

```
Claude Code ── rendereye-mcp (bridge) ──┐
                                        │
Codex ─────── rendereye-mcp (bridge) ──┼── rendereye-mcp service
                                        │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ─────────┘
```

Each coding agent launches `rendereye-mcp` as an MCP Bridge process. The bridge auto-starts `rendereye-mcp service` if no IPC service is running. Both roles are served by the same binary; they always run as separate OS processes.

## Operating Modes

| Command                      | Mode              | Description |
|------------------------------|-------------------|-------------|
| `rendereye-mcp`              | MCP Bridge        | stdio MCP server (default; used by coding agents) |
| `rendereye-mcp service`      | Shared IPC Service| TCP IPC service on 127.0.0.1:37020 |
| `rendereye-mcp version`      | Version info      | Prints version metadata |
| `rendereye-mcp help`         | Help              | Prints usage |

## Service Discovery and Auto-Start

When a bridge process starts, it:

1. Attempts a TCP connection to the configured IPC endpoint (default `127.0.0.1:37020`).
2. If successful, uses the existing service.
3. If not, launches `<current-exe> service` as a detached subprocess.
4. Waits up to 10 s for the service ready file (`%TEMP%\rendereye_mcp_service.json`).
5. Retries the IPC connection up to 3 times.

## Concurrent Startup Safety

Multiple bridges may start simultaneously. The service startup sequence uses the Phase 17 `internal/lifecycle` startup lock:

1. Each competing service process performs a fast port check.
2. The first acquires the OS-level startup lock (lock file).
3. Subsequent processes wait or exit cleanly after observing the port is now open.
4. The winning process releases the lock immediately before binding the port.

This prevents two services from racing to bind 127.0.0.1:37020.

## Process Detachment

The bridge spawns the service using platform-specific `SysProcAttr`:

| Platform | Mechanism |
|----------|-----------|
| Windows  | `CREATE_NEW_PROCESS_GROUP` — service not killed by Ctrl+C sent to bridge |
| Linux/macOS | `Setsid: true` — service in a new session, survives bridge exit |

The service subprocess inherits stderr (for logging) but not stdin or stdout.

## Version Embedding

Version metadata is injected at build time via ldflags:

```bash
go build -ldflags "-s -w \
  -X github.com/taqu/rendereye-mcp/internal/version.Version=1.0.0 \
  -X github.com/taqu/rendereye-mcp/internal/version.GitCommit=abc1234 \
  -X github.com/taqu/rendereye-mcp/internal/version.BuildDate=2026-10-31T00:00:00Z" \
  ./cmd/rendereye-mcp/
```

Version source of truth: `pyproject.toml` (shared with the Python package).

## Build Instructions

```bash
# Development build
go build ./cmd/rendereye-mcp/

# Windows release
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "..." -o rendereye-mcp.exe ./cmd/rendereye-mcp/

# Linux release
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "..." -o rendereye-mcp ./cmd/rendereye-mcp/

# macOS arm64
GOOS=darwin GOARCH=arm64 CGO_ENABLED=0 go build -ldflags "..." -o rendereye-mcp ./cmd/rendereye-mcp/
```

## Release Archive Layout

```
rendereye-mcp_1.0.0_windows_amd64.zip
  rendereye-mcp.exe
  extension/
    __init__.py
    extension.json
    gui_context.py
    gui_dispatcher.py
    ipc_client.py
    state_observer.py
  install.ps1
  README.md
  LICENSE

rendereye-mcp_1.0.0_linux_amd64.tar.gz
  rendereye-mcp
  extension/
    ...
  install.sh
  README.md
  LICENSE
```

## Configuration

All Phase 18 environment variables remain supported:

| Variable              | Default     | Description |
|-----------------------|-------------|-------------|
| `RENDEREYE_IPC_HOST`  | `127.0.0.1` | IPC service host |
| `RENDEREYE_IPC_PORT`  | `37020`     | IPC service port |
| `RENDEREYE_LOG_LEVEL` | `info`      | Log level: debug, info, warn, error |
| `RENDEREYE_ENV_FILE`  | `.env`      | Path to .env file |

Variables may also be set in a `.env` file next to the executable (or at `RENDEREYE_ENV_FILE`). Env file does not override already-set variables.

## Platform Support Matrix

| Platform       | Binary | IPC | MCP Bridge | RenderDoc | Status |
|----------------|--------|-----|------------|-----------|--------|
| Windows amd64  | ✓      | ✓   | ✓          | Primary   | Primary target |
| Windows arm64  | ✓ compiled | requires testing | requires testing | requires testing | Not yet validated |
| Linux amd64    | ✓      | ✓   | ✓          | Where RenderDoc available | Supported |
| Linux arm64    | ✓ compiled | requires testing | requires testing | requires testing | Not yet validated |
| macOS arm64    | ✓ compiled | requires testing | requires testing | RenderDoc unavailable | Go binary only |
| macOS amd64    | ✓ compiled | requires testing | requires testing | RenderDoc unavailable | Go binary only |

## Known Limitations

| Limitation | Notes |
|------------|-------|
| Windows arm64 not validated | Cross-compiled only |
| Linux arm64 not validated | Cross-compiled only |
| macOS RenderDoc integration | RenderDoc does not support macOS |
| Race detection not run in CI | CGO disabled in current environment |
| Real RenderDoc integration test requires manual testing | No CI environment with RenderDoc |
| No multi-agent E2E validation in CI | Manual testing required |

## GitHub Actions Release Workflow

`.github/workflows/release-go.yml` builds release archives for all supported targets. It triggers on tags matching `v*` or `workflow_dispatch` with `publish: true`.

It does **not** automatically publish a production GitHub Release unless explicitly authorized — set `publish: true` in `workflow_dispatch` or push a version tag.

## Migration from Python Installation

Existing Python MCP Bridge users can switch by:

1. Replacing the coding-agent MCP command from `python -m rendereye_mcp` to `./rendereye-mcp`.
2. Keeping the existing RenderDoc Extension (unchanged; still Python-based).
3. Keeping the existing `.env` file if present.

The Go binary reads the same `.env` variables as the Python bridge.

To roll back: restore the original MCP command in the coding-agent configuration.

The Python package (`rendereye-mcp` on PyPI) remains available and is not deprecated in Phase 19.
