# Release readiness — v1.0.0 (Phase 12)

Audit date: 2026-10-29. Version in `pyproject.toml`, `__init__.py` and `extension.json`:
**1.0.0**. No tag and no GitHub release exist yet.

**Classification: Not ready — blocking issues remain** (see [Blockers](#blockers)).
The validation evidence is in [release_testing.md](release_testing.md).

## Feature inventory

Source of truth for the user documentation. "Live" means exercised against RenderDoc
1.46 on Windows 11 with a real D3D12 capture during Phase 12.

### Implemented and tested (unit tests + live)

| Area | Tools / commands |
|------|------------------|
| GUI session discovery | `list_renderdoc_sessions`, `get_current_capture` (incl. `session_not_found` and multi-session listing with a disconnected session) |
| Capture metadata and events | `get_current_capture_info`, `list_capture_events` (`flags_filter`, paging), `get_capture_event`, `get_selected_event` |
| Pipeline state | `get_pipeline_state` all sections; `event_not_selected` / `invalid_section` errors |
| Resources and buffers | `list_resources`, `get_texture_info`, `get_buffer_info`, `read_buffer_data` (hex, `decode_layout`, `range_too_large`) |
| Shaders | `list_shaders`, `get_shader_info`, `get_shader_reflection`, `get_shader_bindings`, `get_shader_disassembly`, `get_shader_debug_info` (graphics and compute) |
| Render targets and pixels | `get_render_targets`, `get_texture_image` (MCP image content), `get_pixel_value` (single and `coords` batch, `out_of_bounds`), `get_texture_statistics` (incl. histogram) |
| MCP stdio end to end | `rendereye-mcp serve` → shared service → extension; 38 tools listed |
| Installation | `uv tool install` (source and wheel), `pip` into a fresh venv, `setup` (twice, `.env` preserved), `doctor`, `service status/stop` |
| Agent configuration | `setup-agent claude-code` and `codex`: real Claude Code (`claude mcp get` → Connected) and real Codex (`codex mcp list`) load the generated config |

### Implemented, tested by unit/integration tests only

| Area | Notes |
|------|-------|
| `get_renderdoc_session_state`, `get_resource_info` | Same code paths as live-tested tools |
| Several agents at once (shared service) | `tests/test_multi_client.py`; not exercised with two real agents simultaneously |
| Capture registry (`capture_*`) and managed sessions (`capture_open`, `session_*`, `instance_*`, `operation_get`) | Real-RenderDoc scenarios A–J in the Phase 5 record were never run |
| `setup-agent cursor`, `vscode`, `gemini` | Fixture tests only |
| Linux | CI unit tests; no live RenderDoc |
| Vulkan, D3D11, OpenGL captures | API-neutral code paths; not live |

### Partially implemented

| Area | Gap |
|------|-----|
| `get_pipeline_state` `depth_stencil` | Returns a note only; no compare function, write mask or stencil state |
| `get_pipeline_state` `rasterizer` | Viewports and scissors only; no cull/fill/blend state |
| Input layout | Buffers and topology only; attribute layout must be inferred from the VS input signature |
| `list_capture_events` names | Generic `Event N` names in the list; real API call names come from `get_selected_event` / `get_capture_event` |
| Diagnostics | An automatically started shared service writes no log file (`service run` in a terminal is the workaround) |
| Linux setup | Prints an `export` line; nothing persists `RENDEREYE_ENV_FILE` automatically |

### Not implemented

Pixel History, shader debugging/stepping, mesh/post-transform geometry, GPU timing or
profiling, changing the selected event from a tool.

### Unsupported

macOS (no RenderDoc GUI), RenderDoc earlier than 1.46, exposing the IPC service beyond
`127.0.0.1`.

## Defects found and fixed in Phase 12

| Defect | Impact | Fix | Verified |
|--------|--------|-----|----------|
| `get_render_targets`, `output_merger`, `summary.has_depth_target` read `resourceId`/`mip`/`slice` from RenderDoc 1.46 `Descriptor` objects | Every color and depth target reported unbound | Use `resource`/`firstMip`/`firstSlice` | Live |
| `get_texture_image` assigned a `Subresource` to `TextureSave.slice` | Always `save_error` | Use `slice.sliceIndex` / `sample.sampleIndex` | Live |
| `get_texture_statistics` called `GetHistogram` with 5 arguments | Histogram always failed | 6-argument 1.46 signature | Live |
| IPC message limit 64 KB on every hop; oversized extension replies silently dropped | PNG previews could not be delivered; requests timed out after 30 s | 16 MiB limit with matching stream limits; oversized replies become `result_too_large` errors on both sides | Live (2.25 MB image) + tests |
| `image_too_large` suggested `mip=0` when no mip fits | Misleading hint | `suggested_mip: null` + `required_max_dim` | Live + test |
| `get_pixel_value` MCP signature lacked `coords` | Batch reads impossible through MCP | Parameter exposed and forwarded | Live through MCP + tests |
| `RENDEREYE_CAPTURE_DIRS` split on `:` | Windows paths (`C:\...`) broken | Split on `os.pathsep` | Test |
| `setup-agent` preferred the first `rendereye-mcp` on `PATH` | Wrong executable written into agent configs when invoked by path or with two installs | Prefer the invoked script and the running environment | Live + tests |
| CLI crashed with `UnicodeEncodeError` on cp932 consoles when output was redirected | `--help`, `setup`, `doctor` unusable in logs/CI on Japanese Windows | `errors="backslashreplace"` on stdout/stderr | Test |
| `service status` trusted a stale ready file; `service stop` left it behind | Misleading "running" | Port check; `stop` removes the file | Live + test |
| 106 ruff findings | CI lint job would fail | Fixed | `ruff check` clean |
| Claude Code real-client test expected `Connected` for an unapproved project server and crashed decoding output on cp932 | Local test failure | Pre-approve in the isolated config; UTF-8 decoding | Test passes with real Claude Code |
| No license metadata in the wheel | Package metadata incomplete | `license = "MIT"`, `license-files`, project URLs | Wheel metadata |

## Blockers

1. **GUI selection sync needs a manual re-test.** In one live session, after the user
   clicked a draw call, the extension kept reporting the post-load `Present` event while
   RenderDoc's own Python shell reported the clicked event. With selection set through
   `SetEventID`, the extension reported the right event, and the extension holds the same
   `CaptureContext` object as the shell. The cause is not identified. Re-test: open a
   capture, click several draw calls, call `get_selected_event` after each.
2. **CI has not run on the Phase 12 changes.** Push the branch and require the CI
   workflow to pass on Windows and Ubuntu.
3. **No clean-machine installation.** Install from the release ZIP on a fresh Windows
   VM (no Python, no uv beforehand), enable the extension, configure Claude Code, and run
   the quick start.

## Known non-blocking limitations

Linux, Vulkan/D3D11/OpenGL, Cursor/VS Code/Gemini, managed-window tools, and running two
real agents at once are unverified; depth/stencil and rasterizer state are partial;
the auto-started service has no log file. These are documented in the user guides.

## Licensing and redistribution

- Project license: MIT (`LICENSE`), now declared in package metadata.
- Runtime dependencies: `mcp`, `psutil`, `python-dotenv`, `watchdog`, `tomlkit` — installed
  from PyPI, not bundled.
- RenderDoc binaries, RenderDoc Python modules and capture files are **not** bundled.
- The release ZIP contains the wheel, the extension source, example configs and
  documentation only.
