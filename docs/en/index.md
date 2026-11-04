[English](index.md) | [日本語](../ja/index.md)

# RenderEyeMCP

**Let your AI coding agent look at the capture you already have open in RenderDoc.**

RenderEyeMCP is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server
that connects AI coding agents such as Claude Code and Codex to the
[RenderDoc](https://renderdoc.org/) GUI. You keep capturing and replaying frames in
RenderDoc exactly as you do today. The agent reads what RenderDoc is showing: the loaded
capture, the selected event, pipeline state, shaders, bound resources, buffers, render
targets, and pixel values.

It is designed for graphics and engine programmers who already use RenderDoc and want an
agent to help gather evidence while debugging rendering problems.

## Getting Started

| Guide | Description |
|-------|-------------|
| [Quick Start](quickstart.md) | Inspect a capture in five minutes |
| [Installation](installation.md) | Set up RenderEyeMCP on Windows or Linux |
| [Configuration](configuration.md) | Connect Claude Code, Codex, and other agents |

## Common Debugging Scenarios

| Scenario | Use it when |
|----------|-------------|
| [Inspect an open capture](examples/active-capture.md) | First contact: which capture, which API, which event |
| [Object not visible](examples/missing-object.md) | A draw call should produce something but nothing shows up |
| [Missing mesh or geometry](examples/missing-mesh.md) | Vertices are submitted but the mesh is missing or malformed |
| [Shader debugging](examples/shader-debugging.md) | A shader reads wrong values or produces unexpected output |
| [GPU performance bottleneck](examples/gpu-bottleneck.md) | GPU time is high; identify where it goes |
| [Pixel history investigation](examples/pixel-history.md) | A pixel has an unexpected colour; trace its write history |

See [all debugging scenarios](examples/README.md) for the complete list.

## Reference

| Document | Description |
|----------|-------------|
| [MCP Tools](tools.md) | Complete tool reference with parameters and return values |
| [Architecture](architecture.md) | How RenderEyeMCP works internally |
| [Troubleshooting](troubleshooting.md) | Common problems and solutions |
| [Advanced Debugging](advanced-debugging.md) | Multi-step debugging workflows |
| [GPU Performance Analysis](performance.md) | GPU counter collection and profiling guidance |
