[English](depth-rejection.md) | [日本語](../../ja/examples/depth-rejection.md)

# Scenario D3 — Depth Test Rejection

## Problem

An object is invisible even though it should be in front of everything else. Pixel
History shows its fragments are present but consistently rejected by the depth test.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded.
3. You know a pixel coordinate where the missing object should appear.

## Example prompts

**Quick investigation:**
> The UI overlay at pixel (960, 540) is not visible. Pixel History shows its draw call
> produces fragments but they are all rejected. Find out why.

**Detailed investigation:**
> Pixel (960, 540) should show a white UI overlay but it remains dark. Use pixel history
> to find all fragments that touched this pixel. Identify which draw produces the
> fragments that get rejected, what rejection reason is reported, and what color the
> shader would have output. Then compare the pipeline state of the rejected draw with
> the draw that last successfully wrote the pixel, focusing on their depth settings.

**Follow-up investigation (optional):**
> Repeat the same pixel history check at pixel (980, 540) to confirm whether the same
> pattern repeats across the overlay.

## What the agent should investigate

- Pixel history at the affected coordinate — which draw calls touched the pixel and which ones passed or failed
- For any rejected fragments, the rejection reason (depth test, stencil test, shader discard, etc.) and what the shader would have output if it had passed
- The depth/stencil pipeline state of the draw whose fragments are rejected — particularly whether depth testing is enabled, the depth comparison function, and whether depth writes are enabled
- How the depth convention used by the rejected draw compares to the depth value already in the buffer at that pixel

## Expected results

A pixel history will show a chain of modifications. For a UI overlay bug, the expected finding is that the last scene geometry draw (e.g. event 305) wrote depth correctly, and the overlay draw (e.g. event 420) produces correct shader output but its fragments are depth-rejected because the overlay renders at z = 1.0 (far plane) while the scene already wrote z = 0.82 at this pixel, and the depth function is LESS.

## How to interpret the results

| `rejection_reason` | Meaning | Common causes |
|---|---|---|
| `depth_test` | Depth comparison failed | Wrong depth function, incorrect z value, premature depth write |
| `stencil_test` | Stencil comparison failed | Stencil mask mismatch, wrong reference value |
| `shader_discard` | Shader called `discard` / `clip` | Alpha test, out-of-range UV, explicit culling |
| `backface_cull` | Back face removed | Wrong winding order, flipped normals |
| `scissor` | Outside scissor rectangle | Scissor rect misconfigured |
| `sample_mask` | Excluded by MSAA sample mask | MSAA configuration mismatch |
| `unknown` | Reason not determined | Check other pipeline stages |

For a UI overlay being rejected by `depth_test`: the fix is to set `depth_enable = false` (or `depth_func = ALWAYS`) for the UI draw call pass.

## Limitations

- Pixel History is GPU-replay based; avoid calling it in a tight loop.
- If depth rejection is expected (e.g., correct occlusion), use `passed: true` to find
  the last fragment that actually wrote the pixel.

## Related tools

`get_pixel_history`, `get_pipeline_state`, `get_bound_resources`, `get_resource_info` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
