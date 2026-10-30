[English](troubleshooting.md) | [日本語](../ja/troubleshooting.md)

# Troubleshooting

Start with:

```powershell
rendereye-mcp version         # is the binary found and working?
netstat -ano | findstr :37020 # is the IPC service listening?
```

Then find the layer that fails: **agent ↔ MCP bridge** (stdio), **MCP bridge ↔ shared
service** (TCP), **service ↔ RenderDoc extension** (TCP), **extension ↔ replay**
(RenderDoc). The sections below follow that order.

## Installation problems

### `rendereye-mcp` is not recognized

- Windows: verify `%LOCALAPPDATA%\RenderEyeMCP\rendereye-mcp.exe` exists, or use the full
  path in the agent configuration.
- Linux: check that `~/.local/bin` is in `$PATH`.

### RenderDoc version is older than 1.46

The extension declares `minimum_renderdoc: 1.46`; older RenderDoc versions will not load
it. Update RenderDoc.

### Extension not detected by the installer

If `install.ps1` warns that the RenderDoc plugins directory was not found, pass it
explicitly:

```powershell
.\install.ps1 -RenderDocExtDir "C:\Program Files\RenderDoc\plugins"
```

Or copy the `extension/` folder from the release archive to your RenderDoc plugins
directory manually, then enable it under **Tools → Manage Extensions**.

## Connection problems

### The agent says the server failed to start

1. Check that the `command` path in the agent config exists.
2. Run the command directly to see any errors:

   ```powershell
   & "$env:LOCALAPPDATA\RenderEyeMCP\rendereye-mcp.exe" version
   ```

3. Claude Code: `claude --debug` shows the server's stderr. Codex: see its log output.

### Tools appear, but no RenderDoc session is found

`list_renderdoc_sessions` returns nothing, or `get_current_capture` says
`no_renderdoc_connected`:

1. Is the extension enabled? RenderDoc → **Tools → Manage Extensions** → RenderEyeMCP
   **Loaded** and **Always Load**. RenderDoc's log (`%TEMP%\RenderDoc\RenderDoc_*.log`)
   should contain `Automatically loading extension "rendereye"`.
2. Was the extension installed correctly? Re-run `install.ps1` and check for errors.
3. Wait up to 30 seconds — the extension reconnects with back-off.
4. Ports: if you changed `RENDEREYE_IPC_PORT`, RenderDoc must see the same value in its
   own environment (see [Configuration](configuration.md#environment-settings-env)).
5. A firewall or security tool blocking loopback TCP on port 37020.

### The shared service does not start

The agent reports `Shared service failed to start within 30s`:

- Another program may use port 37020. Check with:

  ```powershell
  netstat -ano | findstr :37020
  ```

- Run the service in the foreground to see its log:

  ```powershell
  $env:RENDEREYE_LOG_LEVEL = "debug"
  rendereye-mcp service
  ```

  Leave it running and start the agent; it connects to this running service.

### Several agents conflict

They should not: all agents share one service. Do not configure different ports per
agent. If one agent hangs, kill the `rendereye-mcp service` process and restart the
agents; the service will be started again automatically.

### Connection lost after RenderDoc restarts

Expected: the old session becomes `disconnected` (shown with `last_known_capture`) and
the new RenderDoc window registers as a new session with a new `instance_id`. Ask again,
or pass the new `instance_id`.

## Capture problems

### RenderDoc is connected but no capture is loaded

`status: no_capture_loaded` — open the capture in that RenderDoc window. With a large
capture you may briefly see `capture_loading`.

### A capture is open but the agent says there is none

- The capture is open in a RenderDoc window without the extension (for example a
  different RenderDoc installation). Check `list_renderdoc_sessions`.
- Two RenderDoc windows are connected and the agent picked the wrong one; ask it to
  list sessions and use the right `instance_id`.

### Multiple RenderDoc sessions are found

You get `status: ambiguous`. Tell the agent which one, e.g. *"Use the RenderDoc session
that has `my_scene.rdc` open."*

### Resource IDs stop working

IDs belong to the capture that was open when they were returned. After switching or
reopening captures, ask the agent to look them up again.

### The agent reports a different event than the one I selected

1. Ask: *"Call get_selected_event."* and compare `selected_event_id` with the EID in
   RenderDoc's Event Browser.
2. Make sure you clicked in the RenderDoc window that is connected (check the
   `process_id` in `list_renderdoc_sessions`).
3. If the IDs still differ, this is a known open issue observed once during validation;
   please report it with RenderDoc's version, how the capture was opened and the
   RenderEyeMCP log.

### `event_not_selected`

`get_pipeline_state` was called with an `event_id` other than the selected one. Select
that event in RenderDoc; RenderEyeMCP never changes the selection.

## Inspection problems

| Symptom | Cause / action |
|---------|----------------|
| `shader_not_bound` | The selected event has no shader at that stage (e.g. a marker or a depth-only draw). Select a draw call |
| `depth_stencil` returns only a note | Depth/stencil state is not exposed. Use RenderDoc's Pipeline State panel for compare function/write mask |
| `resource_not_found` | Wrong ID, or IDs from a previous capture |
| `range_too_large` from `read_buffer_data` | Max 16384 bytes per call; read in chunks with `offset` |
| `image_too_large` | Increase `max_dim` to `required_max_dim`, or pass `suggested_mip` |
| `result_too_large` | The answer exceeded 16 MiB; use a smaller mip or `max_dim` |
| `timeout` | RenderDoc is busy (long replay) or a modal dialog is open; close it and retry |
| `extension_error` / `unsupported` | RenderDoc raised an error; the `message` field explains. Report it with the RenderDoc version and graphics API |
| Unsupported graphics API | The tools use RenderDoc's API-neutral interface; only D3D12 was validated live. Report differences |
| Pixel values differ from the colors you see | Expected: RenderDoc's viewer applies range mapping and display conversion. `get_pixel_value` returns stored values (e.g. `R32_UINT` IDs or linear float depth) |
| A "black" render target | Check `get_texture_statistics`: max > 0 means data exists outside the displayed range |

## Diagnostic information

**Where logs go**

| Component | Log |
|-----------|-----|
| MCP bridge (`rendereye-mcp`) | stderr, captured by the agent (`claude --debug`, Codex logs) |
| Shared service | Not written to a file when auto-started. Run `rendereye-mcp service` in a terminal to see live output |
| RenderDoc extension and RenderDoc | `%TEMP%\RenderDoc\RenderDoc_*.log` |

Set `RENDEREYE_LOG_LEVEL=debug` in `.env` and restart the service for more detail.

**Telling the layers apart**

- Agent cannot start the server → configuration / MCP layer.
- `no_renderdoc_connected` → extension or IPC layer.
- `no_capture_loaded`, `shader_not_bound`, `resource_not_found` → normal answers about
  the capture.
- `extension_error`, `unsupported`, `timeout` → replay layer inside RenderDoc.

**For a bug report** include: OS version, RenderDoc version, `rendereye-mcp version`
output, coding agent and version, graphics API of the capture, the failing prompt or
tool call and its result, and relevant log excerpts.

## Security and privacy

Captures and logs can contain application paths, resource and shader names, shader
source, and rendered images of unreleased content. Review them before sharing, remove
anything sensitive, and never attach proprietary captures to a public issue without
permission. The IPC service listens on `127.0.0.1` only and requires a per-run token;
do not expose it to other machines.
