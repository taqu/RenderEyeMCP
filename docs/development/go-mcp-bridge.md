# Go MCP Bridge

Phase 18 introduces a Go MCP Bridge (`cmd/rendereye-mcp/`) that replaces the Python MCP Bridge while preserving full MCP interface compatibility.

## Architecture

```
Claude Code ── Go MCP Bridge ──┐
                               │
Codex ─────── Go MCP Bridge ──┼── Go Shared IPC Service
                               │     TCP 127.0.0.1:37020
RenderDoc ─── Python Extension ┘
```

The Go MCP Bridge is a thin stdio MCP server that:
1. Connects to the Go Shared IPC Service via TCP
2. Registers as a bridge using the Phase 6/17 IPC protocol
3. Forwards MCP tool calls as `tool_call` IPC messages
4. Returns `tool_result` responses to the MCP client

## Build Instructions

```bash
# Build for the current platform
go build -o rendereye-mcp ./cmd/rendereye-mcp/

# Windows
GOOS=windows GOARCH=amd64 go build -o rendereye-mcp.exe ./cmd/rendereye-mcp/

# Linux
GOOS=linux GOARCH=amd64 go build -o rendereye-mcp ./cmd/rendereye-mcp/

# macOS arm64
GOOS=darwin GOARCH=arm64 go build -o rendereye-mcp ./cmd/rendereye-mcp/
```

## Running

```bash
# Start as stdio MCP server (the default)
./rendereye-mcp
```

All logs go to **stderr**. stdout is reserved exclusively for MCP protocol messages.

## Configuration

| Environment variable     | Default       | Description                        |
|--------------------------|---------------|------------------------------------|
| `RENDEREYE_IPC_HOST`     | `127.0.0.1`   | IPC service host                   |
| `RENDEREYE_IPC_PORT`     | `37020`       | IPC service port                   |
| `RENDEREYE_LOG_LEVEL`    | `info`        | Log level: debug, info, warn, error |
| `RENDEREYE_ENV_FILE`     | `.env`        | Path to env file (overrides default)|

Variables may also be set in a `.env` file in the working directory (or at `RENDEREYE_ENV_FILE`). The env file does not override existing environment variables.

## Service Auto-Start

The Go MCP Bridge will attempt to auto-start `rendereye-ipc` if the IPC service is not running. It looks for the binary in the same directory as the `rendereye-mcp` executable.

If auto-start fails (binary not found, or service takes too long to start), a warning is logged and the bridge continues — allowing manually started services to be used.

## Tool Registration

The bridge registers all 58 MCP tools with exact descriptions and input schemas matching the Python MCP Bridge. Tools are forwarded to the IPC service via `tool_call` messages and results returned as JSON text content.

**Special handling**: `get_texture_image` returns `[ImageContent, TextContent]` when the IPC result contains `image_data` (base64 PNG). The base64 is decoded to raw bytes for the `ImageContent` block.

## MCP SDK

Uses the official Go MCP SDK `github.com/modelcontextprotocol/go-sdk v1.8.0` with stdio transport.

## Internal Package Structure

```
internal/bridge/
  client.go      — ServiceClient: TCP connection, handshake, concurrent tool call dispatch
  envfile.go     — .env file loading (RENDEREYE_ENV_FILE or ./.env)
  autostart.go   — Auto-start rendereye-ipc subprocess if not running
  register.go    — MCP server creation + all 58 tool registrations
  uuid.go        — UUID generation via crypto/rand
```

## Known Limitations

| Limitation                                                        | Notes              |
|-------------------------------------------------------------------|--------------------|
| Race detection not run in CI (CGO disabled in dev environment)    | Phase 17 note      |
| Real RenderDoc integration test requires a running RenderDoc      | Manual testing     |
| Claude Code and Codex validation requires running agents          | Manual testing     |
| No MCP contract snapshot tests yet                                | Phase 18 follow-up |

