[English](README.md) | [日本語](../../ja/examples/README.md)

# Debugging scenarios

Each scenario starts from a visible rendering problem and provides copyable
natural-language prompts for your coding agent. Open a capture in RenderDoc, follow the
Preparation steps, and paste an example prompt into Claude Code, Codex, or another
MCP-compatible agent. RenderEyeMCP provides access to the capture data automatically.

## Basic inspection

| Scenario | Use it when |
|----------|-------------|
| [A. Inspect an already-open capture](active-capture.md) | First contact: which capture, which API, which event is selected |

## Missing or invisible objects

| Scenario | Use it when |
|----------|-------------|
| [B. An object is not visible](missing-object.md) | A draw call should produce something but nothing shows up |
| [G1. Missing geometry](missing-mesh.md) | Draw call exists but the mesh is invisible; check vertex data and transforms |

## Wrong colors and textures

| Scenario | Use it when |
|----------|-------------|
| [C. Wrong texture or material values](shader-resources.md) | A material samples the wrong texture or has unexpected constants |
| [D. Black or wrong render target](render-target.md) | A target is black, saturated, or has unexpected colors |
| [D1. Incorrect pixel color](pixel-history.md) | A specific pixel shows the wrong color; trace which draw is responsible |
| [D2. Pixel shader debugging](shader-debugging.md) | Pixel history shows one fragment touching the pixel but the shader output is wrong |

## Depth and geometry

| Scenario | Use it when |
|----------|-------------|
| [E. Depth testing problems](depth-debugging.md) | Objects disappear or are wrongly occluded |
| [D3. Depth test rejection](depth-rejection.md) | Fragments exist but are consistently rejected by the depth test |
| [G2. Incorrect vertex format](vertex-layout.md) | Geometry is distorted; suspect a vertex layout mismatch |
| [G3. Vertex transformation](post-vs-inspection.md) | Object is at the wrong position or clips unexpectedly |
| [D4. Vertex shader debugging](vertex-debugging.md) | Step through a vertex shader to find a wrong matrix or transform |

## Performance

| Scenario | Use it when |
|----------|-------------|
| [P1. Find the ten most expensive draw calls](expensive-drawcalls.md) | Identify which draw calls dominate GPU frame time |
| [P2. Compare GPU cost of render passes](render-pass-performance.md) | Compare shadow, G-buffer, lighting, and post-processing pass costs |
| [P3. Most expensive compute dispatches](compute-performance.md) | Find and analyze costly compute dispatches |
| [P4. Diagnose a GPU bottleneck](gpu-bottleneck.md) | Deep-dive one expensive draw call with pipeline statistics and bindings |
| [G4. Geometry performance](geometry-performance.md) | Check whether high draw-call cost comes from excessive geometry |

## Advanced debugging

| Scenario | Use it when |
|----------|-------------|
| [F. Wrong compute shader output](compute-dispatch.md) | A dispatch writes unexpected results |
| [D5. Compute shader NaN](compute-debugging.md) | A compute pass produces NaN/Inf that corrupts downstream results |

**Note.** The scenarios are guidance on how to reason about graphics problems using a coding agent. They are not recordings of a single agent session, and the conclusions an agent draws always need your review.
