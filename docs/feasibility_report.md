# Phase 0 Feasibility Report

## Capability Matrix

| Capability | Status | Notes |
|------------|--------|-------|
| MCP server starts (stdio transport) | **Verified** | `uv run python -m rendereye_mcp` → responds to `initialize` |
| MCP SDK version | **Verified** | mcp 2.3.0 (`MCPServer`, not `FastMCP`) |
| `server_status` tool | **Verified** | Returns all 8 required fields; tested |
| RenderDoc exe detection | **Verified** | Found at `C:/Program Files/RenderDoc/qrenderdoc.exe` |
| IPC TCP transport (asyncio) | **Verified** | Binds 127.0.0.1:37020; tested with multiple clients |
| IPC hello/heartbeat protocol | **Verified** | Full round-trip tested |
| IPC client disconnect detection | **Verified** | Connection count decrements on EOF |
| Config env-var overrides (RENDEREYE_*) | **Verified** | All fields tested |
| Config validation | **Verified** | Invalid values raise ValueError |
| 64 KB message size limit | **Verified** | Enforced in both serialize and deserialize |
| Python 3.6 extension (stdlib-only) | **Implemented** | Not yet tested inside RenderDoc |
| RenderDoc `renderdoc` Python API | **Unverified** | API injected at runtime; cannot test offline |
| Extension directory discovery | **Partial** | `%APPDATA%\qrenderdoc\extensions\` documented; not yet created |
| Capture path retrieval | **Unverified** | API call written defensively; needs RenderDoc to test |
| psutil process enumeration | **Verified** | psutil 7.2.2 installed; `get_running_renderdoc_processes()` implemented |
| Graceful extension load/unload | **Implemented** | `register()` / `unregister()` entry points defined |
| IPC reconnect with backoff | **Implemented** | 5 retries with exponential backoff in extension client |

## Component Readiness

### MCP Server — Ready
- Starts cleanly from `uv run python -m rendereye_mcp`
- Responds correctly to MCP `initialize` message
- `server_status` tool returns full status JSON
- 56/56 tests pass
- 0 ruff lint errors

### IPC Transport — Ready
- asyncio TCP server on 127.0.0.1:37020
- Multiple concurrent clients supported
- 10-second read timeout enforced
- 64 KB message size limit enforced
- Disconnect detection working

### RenderDoc Extension — Implemented, Pending RenderDoc Test
- Python 3.6 compatible stdlib-only code
- Defensive API usage (all `renderdoc` calls in try/except)
- Background thread IPC client with reconnect
- Cannot be tested until loaded inside `qrenderdoc.exe`

## Risks and Blockers

| Risk | Severity | Mitigation |
|------|----------|------------|
| RenderDoc Python API surface unknown | Medium | Defensive imports; fallback to no-op |
| Extension directory must be created manually | Low | Document installation steps |
| RenderDoc Python 3.6 has no `dataclasses` | N/A | Extension uses plain classes only |
| Port 37020 may be in use | Low | Config supports RENDEREYE_IPC_PORT override |
| Windows Firewall may block loopback | Very Low | Loopback traffic typically exempt |

## Phase 0 Conclusion

The MCP server infrastructure is fully functional and tested.
The RenderDoc extension is structurally complete but requires manual testing
inside a running RenderDoc instance to verify the Python API integration.
All automated tests pass; no ruff lint issues remain.
