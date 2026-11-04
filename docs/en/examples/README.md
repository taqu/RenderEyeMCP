[English](README.md) | [日本語](../../ja/examples/README.md)

# Debugging scenarios

Each scenario starts from a rendering problem and shows how to investigate it with a
coding agent and RenderEyeMCP. Use the prompts as templates, adapt them to your capture,
and treat the agent's conclusions as evidence to verify — not as final answers.

Every scenario shares the same structure:
**Problem → Preparation → Example prompt → Investigation workflow → Expected observations → Interpretation → Limitations → Related tools.**

**Validation status.** The tools used in every scenario were run against a real D3D12
capture in RenderDoc 1.46 (Windows 11). The scenarios themselves are guidance on how to
reason; they are not recordings of a single agent session.

---

## Capture and Event Inspection

| Scenario | Use it when |
|----------|-------------|
| [A. Inspect an already-open capture](active-capture.md) | First contact: confirm the agent reads the capture, identify the API, frame, and selected event |

---

## Missing or Incorrect Rendering

| Scenario | Use it when |
|----------|-------------|
| [B. An object is not visible](missing-object.md) | A draw call should produce geometry but nothing appears on screen |
| [G1. Missing geometry](missing-mesh.md) | Vertices are submitted but the mesh is absent or malformed |
| [C. Wrong texture or material values](shader-resources.md) | A material shows the wrong texture, a placeholder, or unexpected constants |
| [D. Black or wrong render target](render-target.md) | A render target is black, oversaturated, or has unexpected colors |

---

## Render Targets, Pixels, and Depth

| Scenario | Use it when |
|----------|-------------|
| [D1. Incorrect pixel color](pixel-history.md) | A pixel has the wrong color; trace which draw call last wrote it |
| [E. Depth testing problems](depth-debugging.md) | An object disappears behind something it should be in front of, or flickers (Z-fighting) |
| [D3. Depth test rejection](depth-rejection.md) | Pixel History shows fragments present but consistently rejected by the depth test |

---

## Shader Debugging

| Scenario | Use it when |
|----------|-------------|
| [D2. Pixel shader debugging](shader-debugging.md) | Only one fragment touches the suspect pixel; trace the bug inside the pixel shader |
| [D4. Vertex shader debugging](vertex-debugging.md) | Mesh vertices appear at wrong positions after transformation |
| [F. Wrong compute shader output](compute-dispatch.md) | A dispatch writes unexpected results (zeros, garbage, or a partially filled buffer) |
| [D5. Compute shader NaN](compute-debugging.md) | A compute shader outputs NaN or Inf, corrupting downstream pixels |

---

## Geometry and Vertex Inspection

| Scenario | Use it when |
|----------|-------------|
| [G2. Incorrect vertex format](vertex-layout.md) | Rendered geometry is distorted or garbled; suspect a mismatched vertex input layout |
| [G3. Vertex transformation](post-vs-inspection.md) | An object appears in the wrong position or clips unexpectedly; compare pre- and post-VS positions |
| [G4. Geometry performance](geometry-performance.md) | An expensive draw call is identified; investigate whether excess geometry is the cause |

---

## GPU Performance Analysis

| Scenario | Use it when |
|----------|-------------|
| [P1. Find the most expensive draw calls](expensive-drawcalls.md) | Rank draw calls by GPU time and inspect the pipeline of the heaviest one |
| [P2. Compare GPU cost of render passes](render-pass-performance.md) | Compare shadow, G-buffer, lighting, and post-processing passes to find the bottleneck |
| [P3. Most expensive compute dispatches](compute-performance.md) | Rank compute dispatches by GPU time and inspect the shader of the top offender |
| [P4. Diagnose a GPU bottleneck](gpu-bottleneck.md) | Collect pipeline statistics, shaders, render targets, and resource bindings; produce a structured finding |
