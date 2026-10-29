# IPC Protocol Reference

## Transport

- **Protocol**: TCP
- **Address**: `127.0.0.1:37020` (loopback only — never binds to 0.0.0.0)
- **Framing**: Newline-delimited JSON (one JSON object per line, UTF-8)
- **Max message size**: 64 KB

## Authentication

The server generates a random 32-byte (64 hex char) token on startup and writes it to:
- Windows: `%TEMP%\rendereye_mcp_token.txt`
- Linux/macOS: `/tmp/rendereye_mcp_token.txt`
- Override via `RENDEREYE_TOKEN_PATH` environment variable

Extensions read this token and include it in the `register_instance` message. The server validates using constant-time comparison (`secrets.compare_digest`).

## Protocol Version

Current version: **1**

All messages with `protocol_version` carry this field. The server ignores unknown versions for forward compatibility.

## Message Types

### `hello` (extension → server)

Sent immediately after TCP connect.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"hello"` |
| `protocol_version` | int | Protocol version (1) |
| `request_id` | string | UUID for correlation |
| `instance_id` | string | Extension-assigned instance ID |
| `process_id` | int | RenderDoc process PID |
| `extension_version` | string | Extension version string |

### `hello_ack` (server → extension)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"hello_ack"` |
| `protocol_version` | int | Protocol version (1) |
| `request_id` | string | Echoed from `hello` |
| `server_version` | string | Server version string |

### `register_instance` (extension → server)

Sent after `hello_ack`. Authenticates and registers the connection.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"register_instance"` |
| `protocol_version` | int | Protocol version (1) |
| `request_id` | string | UUID for correlation |
| `instance_id` | string | Extension-assigned instance ID |
| `process_id` | int | RenderDoc process PID |
| `extension_version` | string | Extension version string |
| `renderdoc_version` | string | RenderDoc version string (or `"unknown"`) |
| `auth_token` | string | Token read from token file |

### `register_ack` (server → extension)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"register_ack"` |
| `protocol_version` | int | Protocol version (1) |
| `request_id` | string | Echoed from `register_instance` |
| `connection_id` | string | Server-assigned stable connection UUID |
| `server_version` | string | Server version string |

### `heartbeat` (extension → server)

Periodic keep-alive.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"heartbeat"` |
| `request_id` | string | UUID for correlation |

### `heartbeat_ack` (server → extension)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"heartbeat_ack"` |
| `request_id` | string | Echoed from `heartbeat` |

### `get_status` (server → extension)

Request current extension/capture status.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"get_status"` |
| `request_id` | string | UUID for correlation |

### `status_response` (extension → server)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"status_response"` |
| `request_id` | string | Echoed from `get_status` |
| `process_id` | int | RenderDoc process PID |
| `instance_id` | string | Extension instance ID |
| `extension_version` | string | Extension version |
| `capture_path` | string\|null | Currently loaded capture path |
| `connected` | bool | Whether extension is connected |

### `gui_state_changed` (extension → server)

Pushed by extension whenever GUI state changes (capture loaded/unloaded).

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"gui_state_changed"` |
| `instance_id` | string | Extension instance ID |
| `revision` | int | Monotonically increasing revision counter |
| `capture_loaded` | bool | Whether a capture is loaded |
| `capture_path` | string\|null | Currently loaded capture path |
| `capture_state` | string | `"loaded"` \| `"unloaded"` \| `"loading"` \| `"error"` \| `"unknown"` |

### `get_gui_state` (server → extension)

Requests a full GUI state snapshot.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"get_gui_state"` |
| `request_id` | string | UUID for correlation |

### `gui_state_response` (extension → server)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"gui_state_response"` |
| `request_id` | string | Echoed from `get_gui_state` |
| `instance_id` | string | Extension instance ID |
| `revision` | int | Current state revision |
| `capture_loaded` | bool | Whether a capture is loaded |
| `capture_path` | string\|null | Currently loaded capture path |
| `capture_state` | string | State string |

### `execute_gui_command` (server → extension)

Request extension to execute a GUI command.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"execute_gui_command"` |
| `request_id` | string | UUID for correlation |
| `command` | string | `"open_capture"` \| `"close_capture"` \| `"focus_window"` |
| `params` | dict | Command-specific parameters |

**Params by command:**
- `open_capture`: `{"path": "/path/to/capture.rdc"}`
- `close_capture`: `{}`
- `focus_window`: `{}` (unsupported via extension — handled by Windows API)

### `gui_command_result` (extension → server)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"gui_command_result"` |
| `request_id` | string | Echoed from `execute_gui_command` |
| `command` | string | Echoed command name |
| `success` | bool | Whether command succeeded |
| `outcome` | string | `"success"` \| `"failed"` \| `"unsupported"` \| `"unknown_outcome"` |
| `error` | string | Error message (empty on success) |
| `state_revision` | int | GUI state revision after command |

### `goodbye` (either → either)

Sent before intentional disconnection.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"goodbye"` |
| `reason` | string | Optional human-readable reason |

### `error` (server → extension)

Generic error response.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"error"` |
| `request_id` | string | Correlation ID (may be empty) |
| `code` | string | Machine-readable error code |
| `message` | string | Human-readable description |

**Error codes:**
- `parse_error` — invalid JSON or malformed message
- `message_too_large` — message exceeds 64 KB
- `auth_failed` — invalid auth token in `register_instance`
- `unexpected_message` — message type not expected from client

## Connection Lifecycle

```
Extension                          Server
   |                                  |
   |-- [TCP connect] ----------------->|
   |-- hello ------------------------->|
   |<-- hello_ack --------------------|
   |-- register_instance ------------>|
   |<-- register_ack (connection_id) -|
   |                                  |
   |   [Operational phase]            |
   |-- heartbeat -------------------->| (every 5s)
   |<-- heartbeat_ack ----------------|
   |-- gui_state_changed ------------>| (on state change)
   |<-- get_gui_state ---------------- (server polls)
   |-- gui_state_response ----------->|
   |<-- execute_gui_command ----------|
   |-- gui_command_result ----------->|
   |                                  |
   |-- goodbye ---------------------->| (before disconnect)
   |-- [TCP close] ------------------>|
```

## Request Correlation

Requests use `request_id` (UUID string) for correlation. Responses echo the same `request_id`. The server maintains a `_pending_requests` dict mapping request_id → Future.

`send_request(msg, timeout=5.0)` sends a message and awaits the response Future. If no response arrives within `timeout` seconds, `asyncio.TimeoutError` is raised.

## GUI State Revision Semantics

- Each extension runtime starts at revision 0
- Revision is incremented on every state change (capture loaded/unloaded)
- The server discards updates with `revision <= current_revision` (stale)
- Revision is per-extension-runtime (resets on reconnect)

## Timeout Semantics

- `READ_TIMEOUT = 10.0s` — server closes connection if no data received for 10 seconds
- `HEARTBEAT_INTERVAL = 5.0s` — extension sends heartbeat every 5 seconds
- `send_request timeout = 5.0s` — default timeout for request-response pairs
