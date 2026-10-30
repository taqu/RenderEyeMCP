# IPC Architecture

## Process Roles

| Process | Role |
|---------|------|
| **Shared IPC Service** | Single long-lived Python process (`rendereye_mcp service`). Owns the TCP server on `127.0.0.1:37020`. Routes tool calls from bridges to extensions. |
| **MCP Bridge** | One bridge process per MCP client (Claude, Cursor, etc.). Connects as a bridge client, forwards tool calls, returns results. |
| **RenderDoc Extension** | One extension per running RenderDoc instance. Connects as an extension client, owns the live RenderDoc session. |

## Connection Topology

```
 MCP Client (Claude/Cursor)
        |
        | stdio / HTTP (MCP protocol)
        v
 +------------------+
 |   MCP Bridge     |  bridge_register → bridge_register_ack
 |  (Python proc)   |  tool_call → tool_result
 +------------------+
        |
        | TCP 127.0.0.1:37020
        v
 +------------------+       TCP 127.0.0.1:37020
 |  Shared IPC      |<----------------------------> RenderDoc Extension
 |  Service         |  hello → hello_ack
 |  (Python proc)   |  register_instance → register_ack
 +------------------+  inspect_capture → inspect_capture_result
                        heartbeat / gui_state_changed
```

## Shared Service Lifecycle

1. **Startup:** Service binds TCP `127.0.0.1:37020` and acquires a single-owner lock (named mutex on Windows; file lock on Unix).
2. **Ready file:** Writes `%TEMP%\rendereye_mcp_service.json` (or `/tmp/...`) containing `{"pid":N,"instance_id":"...","port":37020,"host":"127.0.0.1"}`.
3. **Token file:** Writes `%TEMP%\rendereye_mcp_token.txt` with the 64-hex-char auth token.
4. **Running:** Accepts up to 64 concurrent TCP connections.  Each connection is handled by `ClientConnection.run()` in an asyncio task.
5. **Shutdown:** Removes the ready file.  Closes all open connections.

## Multi-Agent Routing

Multiple MCP bridges can be registered simultaneously.  Each bridge gets a unique `bridge_connection_id` at registration.  When a bridge sends a `tool_call`, the service selects the best available extension connection (e.g., by `instance_id` or session state) and dispatches the `inspect_capture` or equivalent request.  The result travels back as `inspect_capture_result` → `tool_result`.

## Service Autostart Mechanism

The MCP bridge checks for the service ready file on startup.  If absent (or the PID is dead), it launches the service as a subprocess and waits for the ready file to appear before proceeding.  See `src/rendereye_mcp/bootstrap.py`.

## Single-Service Ownership

Only one service process may run at a time per user session:

- **Windows:** Named mutex `Local\RenderEyeMCP_Service_<username>` — first process to acquire it becomes the owner; subsequent attempts exit immediately.
- **Unix/macOS:** Exclusive file lock on the ready file path.

## Component Responsibility Table

| Component | Owns TCP bind | Owns auth token | Routes tool calls | Sends gui_state_changed |
|-----------|:---:|:---:|:---:|:---:|
| Shared IPC Service | Yes | Yes | Yes | No |
| MCP Bridge | No | No | No | No |
| RenderDoc Extension | No | No | No | Yes |
