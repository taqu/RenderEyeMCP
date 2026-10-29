# RenderEyeMCP v1.0.0 — Release notes (DRAFT)

**Status: draft — not released.** No tag or GitHub release has been created. See
[release readiness](release_readiness.md) for the open blockers.

## Highlights

RenderEyeMCP lets an AI coding agent inspect the capture you already have open in the
RenderDoc GUI — no need for the agent to reopen it.

- Discovers every RenderDoc window running the RenderEyeMCP extension, including windows
  opened by Unity or Unreal Engine, and the capture each one has loaded.
- Reads the event selected in RenderDoc: pipeline state, shaders and reflection,
  declared vs. bound resources, constant buffer values, buffers, render targets,
  PNG previews, exact pixel values and texture statistics. All inspection is read-only.
- One shared background service serves any number of MCP clients at once.
- `rendereye-mcp setup` installs the RenderDoc extension and configuration;
  `rendereye-mcp setup-agent` writes Claude Code and Codex configuration safely
  (targeted edits, backups); `rendereye-mcp doctor` diagnoses the installation.
- English and Japanese documentation with six debugging scenarios.

## Installation

Download `RenderEyeMCP-v1.0.0.zip`, then:

```powershell
uv tool install python\rendereye_mcp-1.0.0-py3-none-any.whl
rendereye-mcp setup
rendereye-mcp setup-agent claude-code   # or codex
```

Enable **RenderEyeMCP** under RenderDoc → Tools → Manage Extensions (*Always Load*) and
restart the agent. Full guide: `docs/en/installation.md` (日本語: `docs/ja/installation.md`).

| Artifact | Contents |
|----------|----------|
| `RenderEyeMCP-v1.0.0.zip` | Wheel, RenderDoc extension, agent config examples, EN/JA docs |
| `RenderEyeMCP-Extension-v1.0.0.zip` | RenderDoc extension only |
| `rendereye_mcp-1.0.0-py3-none-any.whl` / `.tar.gz` | Python package |
| `SHA256SUMS.txt` | Checksums |

## Supported environments

| | |
|---|---|
| Validated | Windows 11, RenderDoc 1.46, D3D12 captures, Claude Code, Codex |
| Expected to work, unverified | Windows 10; Vulkan, D3D11, OpenGL captures; Cursor, VS Code (Copilot), Gemini CLI |
| Experimental | Linux (unit tests only) |
| Unsupported | macOS; RenderDoc earlier than 1.46 |

Requires Python 3.11+ on the host (uv provides it automatically).

## Known limitations

- Inspection uses the event selected in the RenderDoc GUI; tools cannot change it.
- Depth/stencil state, rasterizer cull/fill mode and blend state are not exposed.
- No Pixel History, shader debugging, mesh output or GPU profiling.
- `read_buffer_data` reads at most 16 KiB per call; tool results are limited to 16 MiB.
- The automatically started service writes no log file; run
  `rendereye-mcp service run` in a terminal to see its log.
- Capture-file registry and managed-window tools (`capture_open`, `session_*`) were not
  validated live in this release.

## Changes since the Phase 5 baseline

- New active-capture inspection tools (Phases 7–11): GUI session discovery, capture and
  event inspection, pipeline state, resources and buffers, shaders and reflection,
  render targets, textures and pixels.
- Shared IPC service so several agents can use RenderEyeMCP at once (Phase 6).
- RenderDoc 1.46 compatibility fixes found by live testing: render/depth target
  descriptors, texture PNG export, histogram call.
- IPC message limit raised from 64 KB to 16 MiB; oversized replies return
  `result_too_large` instead of timing out.
- `get_pixel_value` accepts `coords` for batch reads through MCP.
- `RENDEREYE_CAPTURE_DIRS` uses `;` on Windows (`:` on Linux).
- `setup-agent` writes the executable of the installation you run it from.
- CLI output no longer crashes on non-UTF-8 consoles when redirected.
- `service status` detects stale state; `service stop` cleans up.
- Package metadata declares the MIT license.

## Breaking changes / migration

- **Multiple capture directories on Windows:** separate `RENDEREYE_CAPTURE_DIRS`
  entries with `;` instead of `:`. (The previous `:` separator never worked with drive
  letters.)
- **Update the extension:** run `rendereye-mcp setup` after upgrading and restart
  RenderDoc. The new service's 16 MiB message limit needs the matching extension.
- The user documentation moved to `docs/en/` and `docs/ja/`. Removed:
  `docs/installation.md`, `docs/installation-manual.md`, `docs/mcp_api.md`,
  `docs/troubleshooting.md`, `docs/architecture.md`, `docs/agents/*`.
