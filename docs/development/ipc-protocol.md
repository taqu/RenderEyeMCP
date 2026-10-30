# IPC Protocol Reference (Development)

This document is the authoritative development reference.  See also `docs/ipc_protocol.md` for the user-facing summary.

## Transport

- **Protocol:** TCP
- **Address:** `127.0.0.1:37020` (loopback only)
- **Max connections:** 64

## Message Framing

- **Format:** Newline-delimited JSON (NDJSON)
- **Delimiter:** `\n` (LF, 0x0A)
- **Encoding:** UTF-8
- **Max message size:** 16 MiB (`MAX_MESSAGE_BYTES = 16 * 1024 * 1024`)
- **Read mechanism:** `asyncio.StreamReader.readline()` on the server side

Each message is a single compact JSON object followed by `\n`.  There is no length prefix.

## Serialization

```python
json.dumps(asdict(msg), separators=(",", ":")) + "\n"
```

- No whitespace between tokens.
- Python's `dataclasses.asdict()` is used; field order follows declaration order in the dataclass.
- `type` and `protocol_version` are `field(init=False)` but **are** included in `asdict()` output and therefore in the wire format.

## Protocol Version

`PROTOCOL_VERSION = 1`

Carried in `protocol_version` field of messages that include it (hello/hello_ack, register_instance/register_ack, service_info_response, bridge_register/bridge_register_ack).  There is currently no version negotiation; the server does not reject messages with different values.

## Request/Response Correlation

Most messages carry `request_id` (a UUID string set by the sender).  The responder echoes the same `request_id`.  The connection layer uses a `_pending_requests` dict to resolve futures keyed on `request_id`.

## Authentication

1. A 32-byte random value is generated on service startup and hex-encoded to 64 characters.
2. Written to `%TEMP%\rendereye_mcp_token.txt` (Windows) or `/tmp/rendereye_mcp_token.txt` (Unix).
3. Extensions include the token in `register_instance.auth_token`.
4. Bridges include the token in `bridge_register.auth_token`.
5. Validation uses `secrets.compare_digest` (constant-time).

## Operation Catalog

### Connection / Handshake

| Type | Direction | Fields |
|------|-----------|--------|
| `hello` | extension → service | `request_id`, `instance_id`, `process_id`, `extension_version`, `type`, `protocol_version` |
| `hello_ack` | service → extension | `request_id`, `server_version`, `type`, `protocol_version` |
| `register_instance` | extension → service | `request_id`, `instance_id`, `process_id`, `extension_version`, `renderdoc_version`, `auth_token`, `type`, `protocol_version` |
| `register_ack` | service → extension | `request_id`, `connection_id`, `server_version`, `type`, `protocol_version` |
| `service_info_request` | bridge → service | `request_id`, `client_type`, `type` |
| `service_info_response` | service → bridge | `request_id`, `service_name`, `service_version`, `service_pid`, `service_instance_id`, `type`, `protocol_version` |
| `bridge_register` | bridge → service | `request_id`, `bridge_id`, `process_id`, `bridge_version`, `auth_token`, `type`, `protocol_version` |
| `bridge_register_ack` | service → bridge | `request_id`, `bridge_connection_id`, `service_version`, `type`, `protocol_version` |
| `goodbye` | either → either | `reason`, `type` |
| `error` | service → client | `request_id`, `code`, `message`, `type` |

### Keep-alive

| Type | Direction | Fields |
|------|-----------|--------|
| `heartbeat` | extension → service | `request_id`, `type` |
| `heartbeat_ack` | service → extension | `request_id`, `type` |

### Status

| Type | Direction | Fields |
|------|-----------|--------|
| `get_status` | service → extension | `request_id`, `type` |
| `status_response` | extension → service | `request_id`, `process_id`, `instance_id`, `extension_version`, `capture_path`, `connected`, `type` |

### GUI State

| Type | Direction | Fields |
|------|-----------|--------|
| `gui_state_changed` | extension → service | `instance_id`, `revision`, `capture_loaded`, `capture_path`, `capture_state`, `type` |
| `get_gui_state` | service → extension | `request_id`, `type` |
| `gui_state_response` | extension → service | `request_id`, `instance_id`, `revision`, `capture_loaded`, `capture_path`, `capture_state`, `type` |
| `execute_gui_command` | service → extension | `request_id`, `command`, `params`, `type` |
| `gui_command_result` | extension → service | `request_id`, `command`, `success`, `outcome`, `error`, `state_revision`, `type` |

### Tool Execution

| Type | Direction | Fields |
|------|-----------|--------|
| `tool_call` | bridge → service | `request_id`, `bridge_connection_id`, `tool_name`, `arguments`, `type` |
| `tool_result` | service → bridge | `request_id`, `tool_name`, `result`, `error`, `type` |

### Capture Inspection

| Type | Direction | Fields |
|------|-----------|--------|
| `inspect_capture` | service → extension | `request_id`, `operation`, `params`, `type` |
| `inspect_capture_result` | extension → service | `request_id`, `operation`, `result`, `error`, `type` |

## Error Codes

| Code | Meaning |
|------|---------|
| `auth_failed` | Invalid or missing auth token |
| `parse_error` | JSON decode failed or unknown message type |
| `message_too_large` | Line exceeded `MAX_MESSAGE_BYTES` |
| `not_a_bridge` | `tool_call` received from a non-bridge connection |
| `unexpected_message` | Message type not valid for this connection role |
| `tool_executor_unavailable` | No tool executor is attached to the service |

## Timeout Behaviour

| State | Timeout |
|-------|---------|
| Unauthenticated | `READ_TIMEOUT = 10.0 s` |
| Authenticated (extension or bridge) | `READ_TIMEOUT_AUTHENTICATED = 60.0 s` |

Both are defined in `src/rendereye_mcp/ipc/connection.py`.

## Notification Semantics

`gui_state_changed` is fire-and-forget: the extension sends it and does not wait for a response.  The service silently ignores notifications with a `revision` value ≤ the currently stored revision (stale update suppression).

## Binary Data Handling

Binary data (e.g., texture images) is embedded as a base64-encoded string inside a JSON value.  Convention:

```json
{"data": "<base64>", "encoding": "base64", "size": <byte_count>}
```

The protocol has no dedicated binary framing; all binary content travels as JSON string values.  The 16 MiB message limit accommodates up to ~12 MiB of binary data after base64 overhead (~33%).

## Session and Capture Identity

- Each extension connection is identified by `instance_id` (set by the extension) and `connection_id` (assigned by the service at registration).
- Capture state is tracked per-connection via `revision`, `capture_loaded`, `capture_path`, and `capture_state`.
- Bridges are identified by `bridge_connection_id` (assigned by the service at registration).

## Known Limitations

- No version negotiation: protocol version 1 is the only supported version.
- No multiplexing: each TCP connection handles one logical session.
- No TLS: communication is loopback-only; TLS is not planned.
- Max connections (64) is not configurable at runtime.
