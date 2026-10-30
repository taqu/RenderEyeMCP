# Go Shared IPC Service

Phase 17 introduces a standalone Go implementation of the RenderEyeMCP Shared IPC Service that is wire-protocol compatible with the existing Python service.

## Architecture

```
Claude Code ── Python MCP Bridge ──┐
                                   │
Codex ─────── Python MCP Bridge ──┼── Go Shared IPC Service  (rendereye-ipc)
                                   │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ────┘
```

The service accepts two kinds of clients:

| Client | Registration | Role |
|---|---|---|
| Python MCP Bridge | `bridge_register` | Sends `tool_call`, receives `tool_result` |
| Python RenderDoc Extension | `hello` + `register_instance` | Receives `inspect_capture`, sends `inspect_capture_result` |

## Build Instructions

**Prerequisites:** Go 1.22 or later.

```bash
# Build for the current platform
go build ./cmd/rendereye-ipc/

# Windows
GOOS=windows GOARCH=amd64 go build -o rendereye-ipc.exe ./cmd/rendereye-ipc/

# Linux
GOOS=linux GOARCH=amd64 go build -o rendereye-ipc ./cmd/rendereye-ipc/

# macOS arm64
GOOS=darwin GOARCH=arm64 go build -o rendereye-ipc ./cmd/rendereye-ipc/
```

## Startup

```bash
# Start with defaults (127.0.0.1:37020)
./rendereye-ipc

# Override host/port
./rendereye-ipc -host 127.0.0.1 -port 37020

# Debug logging
./rendereye-ipc -log debug
```

## Runtime Configuration

| Environment variable | Default | Description |
|---|---|---|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | TCP bind address (never `0.0.0.0`) |
| `RENDEREYE_IPC_PORT` | `37020` | TCP port |
| `RENDEREYE_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error` |

Command-line flags (`-host`, `-port`, `-log`) take precedence over environment variables.

## Startup Coordination

On startup, the service:

1. Checks if the configured port is already open.  If so, it assumes another service instance is running and exits cleanly.
2. Acquires the cross-process startup lock (`Local\RenderEyeMCPServiceStartup` on Windows; flock on Linux/macOS).
3. Re-checks the port after acquiring the lock (another bridge may have started the service while waiting).
4. Binds the TCP listener.
5. Releases the startup lock.
6. Generates a fresh 32-byte random auth token and writes it to `%TEMP%\rendereye_mcp_token.txt`.
7. Writes the ready file `%TEMP%\rendereye_mcp_service.json` with `{"pid", "instance_id", "port", "host"}`.

## Shutdown

On `SIGINT` or `SIGTERM`:

1. Stops accepting new connections.
2. Removes the ready file.
3. Removes the auth token file.
4. Waits for active connections to finish.
5. Exits.

## Logging

Logs are written to **stderr** in logfmt (key=value) format.  Logged events include:

- Service startup / listener ready
- Client connected / disconnected
- Extension hello / registration
- Bridge registration
- Tool call routing (debug level)
- Routing errors and timeouts
- Graceful shutdown

## Service Selection (Migration)

During Phase 17, both Python and Go services are available.  Only one may run on the configured endpoint at a time.

**To use the Go service:**
1. Stop the Python service: `python -m rendereye_mcp service stop`
2. Start the Go service: `./rendereye-ipc`
3. Connect existing Python MCP Bridges and the RenderDoc Extension normally.

**To roll back to the Python service:**
1. Stop the Go service: send `SIGTERM` or `Ctrl-C`.
2. Start the Python service: `python -m rendereye_mcp service run`

No changes to the Python MCP Bridge or RenderDoc Extension are required.

## Protocol Compatibility

The Go service implements the same NDJSON wire protocol (Protocol Version 1) as the Python service:

- Transport: TCP loopback only (`127.0.0.1`)
- Framing: newline-delimited JSON (`\n`)
- Max message size: 16 MiB
- Read timeout: 10 s (unauthenticated), 60 s (authenticated)
- Max connections: 64

All 23 message types from Phase 16 are handled.

## Tool Routing

When the Go service receives a `tool_call` from a bridge it either:

**A) Handles internally** (using tracked extension state):
- `server_status`
- `list_renderdoc_sessions`
- `get_renderdoc_session_state`
- `get_current_capture`
- `instance_gui_state`

**B) Forwards to extension** as `inspect_capture` (Phase 8–15 inspection tools):

The routing path is:

```
Bridge → tool_call → Service → inspect_capture → Extension
Extension → inspect_capture_result → Service → tool_result → Bridge
```

The `instance_id` argument is used for extension selection and is stripped from the params forwarded to the extension.

**C) Returns a "not implemented" error** for tools that require the Python capture registry, session manager, or measurement/debug stores:
- `capture_list`, `capture_get`, `capture_latest`, `capture_rescan`, `capture_registry_status`
- `capture_open`
- `instance_list`
- `operation_get`
- `session_list`, `session_get`, `session_focus`, `session_close`, `session_protect`
- `collect_gpu_counters`, `get_gpu_measurement_status`, `get_gpu_timings`, `get_performance_summary`, `get_render_pass_performance`, `get_pipeline_statistics`
- `debug_pixel_shader`, `debug_vertex_shader`, `debug_compute_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`, `get_shader_debug_status`

These tools require infrastructure (databases, measurement stores, debug stores) that is implemented in the Python service and is planned for Phase 18.

## Running Unit Tests

```bash
go test ./internal/...

# Verbose output
go test -v ./internal/...

# Race detection (requires CGO)
CGO_ENABLED=1 go test -race ./internal/...
```

Tests cover:

- NDJSON framing (partial reads, oversized messages, round-trips)
- Protocol fixture conformance (all 29 golden fixtures from Phase 16)
- Router unit tests (tool routing, extension selection, disconnect cleanup)
- Server integration tests (end-to-end tool call routing, two-bridge isolation, auth, error handling)

## Known Limitations

| Limitation | Phase |
|---|---|
| Tools requiring Python registry/session DB return "not_implemented_in_go_service" | Phase 18 |
| Tools requiring measurement_store (`collect_gpu_counters`, etc.) return errors | Phase 18 |
| Shader debugging tools (`debug_pixel_shader`, etc.) return errors | Phase 18 |
| Race detection not verified (CGO disabled in current environment) | Phase 17 |
| Real RenderDoc GUI integration testing requires a running RenderDoc instance | Manual |

## Phase 18 Readiness

Phase 17 establishes:

- Full IPC wire protocol implementation in Go
- TCP server with concurrency-safe routing
- Extension and bridge lifecycle management
- Request/response correlation across connections
- GUI state tracking from extension notifications
- Cross-platform compilation (Windows, Linux, macOS)

Phase 18 (Go MCP Bridge) can proceed once this compatibility baseline is confirmed with real RenderDoc.  The Go service needs the following for full feature parity with the Python service:

- Capture registry (SQLite-backed)
- Session manager
- Instance/window discovery
- Operation tracker
- Measurement store
- Debug store
