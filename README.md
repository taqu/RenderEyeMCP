[English](README.md) | [日本語](README.ja.md)

# RenderEyeMCP

**Let your AI coding agent look at the capture you already have open in RenderDoc.**

RenderEyeMCP is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server
that connects AI coding agents such as Claude Code and Codex to the
[RenderDoc](https://renderdoc.org/) GUI. You keep capturing and replaying frames in
RenderDoc exactly as you do today. The agent then reads what RenderDoc is showing: the
loaded capture, the event you selected, its pipeline state, shaders, bound resources,
buffers, render targets, and pixel values.

```text
Game engine / Unity / Unreal / .rdc file
      |  capture a frame
      v
RenderDoc GUI  (you select the draw call you care about)
      |  loaded capture + selected event
      v
rendereye-mcp (MCP Bridge)  ──┐
                              ├── rendereye-mcp service (Shared IPC Service)
rendereye-mcp (MCP Bridge)  ──┘         │
                                        │ TCP 127.0.0.1:37020
                          RenderDoc Python Extension
      |  MCP tools (58 total)
      v
AI coding agent  ->  evidence-based debugging assistance
```

RenderDoc stays the capture and replay application. RenderEyeMCP is a read-only bridge:
the agent does not reopen captures, and it never changes which event you have selected.

## What it can do

- **Find your RenderDoc session** — every running RenderDoc GUI with the extension loaded,
  the capture it has open, and whether it is connected.
- **Capture and events** — API, frame number, event counts, paged event lists, and the
  event currently selected in the GUI.
- **Pipeline state** — topology, vertex/index buffers, viewports and scissors, bound
  shaders, render targets, depth target, and resource bindings.
- **Shaders** — reflection (inputs, outputs, constant buffers, resources, samplers),
  declared-vs-bound resource correlation, paged disassembly, and embedded source.
- **Resources and buffers** — resource lists, texture/buffer metadata, bounded buffer
  reads with optional typed decoding.
- **Render targets and pixels** — bound targets, PNG previews of textures, exact typed
  pixel values, per-channel min/max and histograms.
- **Several agents at once** — multiple MCP Bridge processes share one background IPC
  Service, so Claude Code and Codex can inspect the same RenderDoc session simultaneously.

Limitations to know up front:

- Inspection always uses the event **selected in the RenderDoc GUI**. Select the draw or
  dispatch in RenderDoc first; the agent cannot move the selection.
- Only RenderDoc 1.46 on Windows has been validated live with D3D12. Other APIs and
  platforms are listed in [Supported platforms](#supported-platforms).

## Supported platforms

| Platform | Binary | MCP Bridge | IPC Service | RenderDoc Integration |
|----------|--------|------------|-------------|----------------------|
| Windows amd64 | ✓ | ✓ | ✓ | Validated (D3D12, RenderDoc 1.46) |
| Windows 10 | ✓ expected | expected | expected | Not validated |
| Linux amd64 | ✓ | ✓ | ✓ | Requires RenderDoc for Linux |
| macOS arm64 | ✓ compiled | expected | expected | RenderDoc not available |

Vulkan, D3D11, and OpenGL captures are expected to work through RenderDoc's API-neutral
interface but have not been validated live.

## Requirements

- **RenderDoc 1.46** or later. The extension declares 1.46 as its minimum version.
- An MCP-capable coding agent: **Claude Code** or **Codex** (both tested).
- No Python, pip, uv, or Go toolchain required for normal installation.

The RenderDoc Extension runs inside RenderDoc using RenderDoc's own embedded Python
runtime. No separate Python installation is needed.

## Quick installation (Windows)

1. Download `rendereye-mcp_<version>_windows_amd64.zip` from the
   [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) page.
2. Extract the archive.
3. Run the installer (or copy files manually — see [Installation](docs/en/installation.md)):

   ```powershell
   .\install.ps1
   ```

4. In RenderDoc, open **Tools → Manage Extensions**, select **RenderEyeMCP**, and enable
   **Always Load**.

5. Configure your coding agent. For Claude Code, add to `~/.claude.json`:

   ```json
   {
     "mcpServers": {
       "rendereye": {
         "command": "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
       }
     }
   }
   ```

6. Restart the coding agent.

Full installation instructions: [docs/en/installation.md](docs/en/installation.md).

## Quick usage

1. Open a capture in RenderDoc (*File → Open Capture* or capture from your engine).
2. Select a draw call in the Event Browser.
3. Ask your agent:

   > Inspect the capture currently open in RenderDoc. Identify the selected draw call and
   > summarize its pipeline state.

Step-by-step walkthrough: [Quick Start](docs/en/quickstart.md).

## Documentation

| Topic | English | 日本語 |
|-------|---------|--------|
| Installation | [installation.md](docs/en/installation.md) | [installation.md](docs/ja/installation.md) |
| Agent configuration | [configuration.md](docs/en/configuration.md) | [configuration.md](docs/ja/configuration.md) |
| Quick start | [quickstart.md](docs/en/quickstart.md) | [quickstart.md](docs/ja/quickstart.md) |
| Debugging scenarios | [examples/](docs/en/examples/README.md) | [examples/](docs/ja/examples/README.md) |
| Prompt examples | [prompts.md](docs/en/prompts.md) | [prompts.md](docs/ja/prompts.md) |
| MCP tool reference | [tools.md](docs/en/tools.md) | [tools.md](docs/ja/tools.md) |
| Troubleshooting | [troubleshooting.md](docs/en/troubleshooting.md) | [troubleshooting.md](docs/ja/troubleshooting.md) |
| Architecture | [architecture.md](docs/en/architecture.md) | [architecture.md](docs/ja/architecture.md) |

Developer material: [development guide](docs/development.md),
[IPC protocol](docs/ipc_protocol.md), [single binary architecture](docs/development/single-binary.md).

## Troubleshooting

**The agent cannot find a RenderDoc session:**

- Make sure the RenderEyeMCP extension is enabled in RenderDoc
  (**Tools → Manage Extensions**, *Always Load*).
- Restart the coding agent after enabling the extension.
- Check that RenderDoc has a capture open.

**The shared IPC service does not start:**

- The MCP Bridge starts the service automatically the first time. If it fails, run
  `rendereye-mcp service` in a separate terminal to check the error output.
- If port 37020 is in use by another program, set `RENDEREYE_IPC_PORT` to a free port
  in a `.env` file next to the executable.

Full troubleshooting: [Troubleshooting](docs/en/troubleshooting.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

```bash
# Go development
go test ./...
go vet ./...
go build ./cmd/rendereye-mcp/

# Python extension (RenderDoc extension only)
uv sync
uv run pytest tests/
```

## License

[MIT](LICENSE). RenderDoc is a separate project under its own license and is not bundled.
