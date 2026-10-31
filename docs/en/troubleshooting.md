[English](troubleshooting.md) | [日本語](../ja/troubleshooting.md)

# Troubleshooting

Start with:

```powershell
rendereye-mcp doctor                      # installation, .env, RenderDoc, extension, service
rendereye-mcp doctor --agent claude-code  # also checks that agent's configuration
rendereye-mcp service status              # is the shared service listening?
```

Then find the layer that fails: **agent ↔ MCP server** (stdio), **MCP server ↔ shared
service** (TCP), **service ↔ RenderDoc extension** (TCP), **extension ↔ replay**
(RenderDoc). The sections below follow that order.

## Installation problems

### `rendereye-mcp` is not recognized

- uv: run `uv tool update-shell`, then open a new terminal.
- pip/venv: call the full path,
  `& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\rendereye-mcp.exe"`.

### `RenderDoc not found` during setup

Setup only checks `%ProgramFiles%\RenderDoc` and `%ProgramFiles(x86)%\RenderDoc`. Set the
path in `.env` (`RENDEREYE_RENDERDOC_EXE=D:\Tools\RenderDoc\qrenderdoc.exe`). Inspecting a
capture you opened yourself does not depend on this setting.

### RenderDoc version is older than 1.46

The extension declares `minimum_renderdoc: 1.46`; older RenderDoc versions will not load
it. Update RenderDoc.

### `RENDEREYE_ENV_FILE` is not set / points elsewhere

Run `rendereye-mcp setup` again, then open a new terminal **and restart the agent**.
Processes started before setup do not see the new user variable.

### Python errors when installing

RenderEyeMCP needs Python 3.11+. With uv this is handled automatically. With pip, check
`python --version` inside the venv.

### `UnicodeEncodeError` in command output

Fixed in this release for the `rendereye-mcp` command. If you script RenderEyeMCP
modules directly on a non-UTF-8 console (for example cp932), set
`PYTHONIOENCODING=utf-8`.

## Connection problems

### The agent says the server failed to start

1. Check the `command` path in the agent config exists (`Test-Path <path>`).
2. `rendereye-mcp doctor --agent <agent>`.
3. Claude Code: `claude --debug` shows the server's stderr. Codex: see its log output.
4. Configured with `setup-agent` from a different installation? Re-run `setup-agent`
   with the `rendereye-mcp` you actually use (add `--force` to replace the entry).

### Tools appear, but no RenderDoc session is found

`list_renderdoc_sessions` returns nothing, or `get_current_capture` says
`no_renderdoc_connected`:

1. Is the extension enabled? RenderDoc → **Tools → Manage Extensions** → RenderEyeMCP
   **Loaded** and **Always Load**. RenderDoc's log (`%TEMP%\RenderDoc\RenderDoc_*.log`)
   should contain `Automatically loading extension "rendereye"`.
2. Was the extension installed for this user? `doctor` shows its folder.
3. Wait up to 30 seconds — the extension reconnects with back-off.
4. Ports: if you changed `RENDEREYE_IPC_PORT`, RenderDoc must see the same value in its
   own environment (see [Configuration](configuration.md#environment-settings-env)).
5. A firewall or security tool blocking loopback TCP on port 37020.

### The shared service is unavailable

`rendereye-mcp service status` says `not running`, or the agent reports
`Shared service failed to start within 30s`:

- Another program may use port 37020. Check with
  `netstat -ano | findstr :37020`.
- Run the service in the foreground to see its log:

  ```powershell
  rendereye-mcp service stop
  $env:RENDEREYE_LOG_LEVEL = "DEBUG"
  rendereye-mcp service run
  ```

  Leave it running and start the agent; it connects to this service.
- `status` reporting a *stale ready file* means a previous service ended without cleaning
  up. `rendereye-mcp service stop` removes it.

### Several agents conflict

They should not: all agents share one service. Do not configure different ports per
agent. If one agent hangs, `rendereye-mcp service stop` and restart the agents.

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
| MCP server (`rendereye-mcp serve`) | stderr, captured by the agent (`claude --debug`, Codex logs) |
| Shared service | Not written to a file when started automatically. Run `rendereye-mcp service run` in a terminal to see it (above) |
| RenderDoc extension and RenderDoc | `%TEMP%\RenderDoc\RenderDoc_*.log` |

Set `RENDEREYE_LOG_LEVEL=DEBUG` in `.env` (then `rendereye-mcp service stop` and
restart the agent) for more detail.

**Telling the layers apart**

- Agent cannot start the server → configuration / MCP layer.
- `no_renderdoc_connected` → extension or IPC layer.
- `no_capture_loaded`, `shader_not_bound`, `resource_not_found` → normal answers about
  the capture.
- `extension_error`, `unsupported`, `timeout` → replay layer inside RenderDoc.

**For a bug report** include: OS version, RenderDoc version, `rendereye-mcp --version`,
coding agent and version, graphics API of the capture, `rendereye-mcp doctor` output,
the failing prompt or tool call and its result, and relevant log excerpts.

## Security and privacy

Captures and logs can contain application paths, resource and shader names, shader
source, and rendered images of unreleased content. Review them before sharing, remove
anything sensitive, and never attach proprietary captures to a public issue without
permission. The IPC service listens on `127.0.0.1` only and requires a per-run token;
do not expose it to other machines.
