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

## Graphics Debugging Examples

Each scenario starts from a real rendering problem. Use it as a prompt template or as
guidance for structuring your own investigation. See the [full scenario index](examples/README.md)
for a table of all scenarios and when to use them.

### Capture and Event Inspection

- [Inspect an already-open capture](examples/active-capture.md)
  — Confirm the agent can read the capture currently open in RenderDoc; identify the API, frame, and selected event.

### Missing or Incorrect Rendering

- [An object is not visible](examples/missing-object.md)
  — A draw call should produce geometry but nothing appears on screen.
- [Missing geometry](examples/missing-mesh.md)
  — Vertices are submitted but the mesh is absent or malformed; check vertex data and transformed positions.
- [Wrong texture or material values](examples/shader-resources.md)
  — A material shows the wrong texture, a placeholder, or unexpected constant values.
- [Black or wrong render target](examples/render-target.md)
  — A render target is black, oversaturated, or has unexpected colors.

### Render Targets, Pixels, and Depth

- [Incorrect pixel color](examples/pixel-history.md)
  — Trace the write history of a specific pixel to find which draw call last changed it and why.
- [Depth testing problems](examples/depth-debugging.md)
  — An object disappears behind something it should be in front of, or flickers (Z-fighting).
- [Depth test rejection](examples/depth-rejection.md)
  — Pixel History shows fragments present but consistently rejected by the depth test.

### Shader Debugging

- [Pixel shader debugging](examples/shader-debugging.md)
  — Only one fragment touches the suspect pixel; trace the bug inside the pixel shader.
- [Vertex shader debugging](examples/vertex-debugging.md)
  — Mesh vertices appear at wrong positions after transformation; step through the vertex shader.
- [Wrong compute shader output](examples/compute-dispatch.md)
  — A dispatch writes unexpected results (zeros, garbage, or a partially filled buffer).
- [Compute shader NaN](examples/compute-debugging.md)
  — A compute shader outputs NaN or Inf, corrupting downstream pixels.

### Geometry and Vertex Inspection

- [Incorrect vertex format](examples/vertex-layout.md)
  — Rendered geometry is distorted or garbled; suspect a mismatched vertex input layout.
- [Vertex transformation](examples/post-vs-inspection.md)
  — An object appears in the wrong position or clips unexpectedly; inspect pre- and post-VS positions.
- [Geometry performance](examples/geometry-performance.md)
  — An expensive draw call is identified; investigate whether the cost comes from excess geometry.

### GPU Performance Analysis

- [Find the most expensive draw calls](examples/expensive-drawcalls.md)
  — Rank draw calls by GPU time and inspect the pipeline of the heaviest one.
- [Compare GPU cost of render passes](examples/render-pass-performance.md)
  — Compare shadow, G-buffer, lighting, and post-processing passes to find the bottleneck pass.
- [Most expensive compute dispatches](examples/compute-performance.md)
  — Rank compute dispatches by GPU time and inspect the shader of the top offender.
- [Diagnose a GPU bottleneck](examples/gpu-bottleneck.md)
  — Collect pipeline statistics, shaders, render targets, and resource bindings for one draw call; produce a structured finding.

## Reference

| Document | Description |
|----------|-------------|
| [MCP Tools](tools.md) | Complete tool reference with parameters and return values |
| [Architecture](architecture.md) | How RenderEyeMCP works internally |
| [Troubleshooting](troubleshooting.md) | Common problems and solutions |
| [Advanced Debugging](advanced-debugging.md) | Multi-step debugging workflows |
| [GPU Performance Analysis](performance.md) | GPU counter collection and profiling guidance |
