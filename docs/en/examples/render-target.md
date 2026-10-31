[English](render-target.md) | [日本語](../../ja/examples/render-target.md)

# Scenario D — Black or wrong render target

## Problem

A render target looks black, saturated, or has unexpected colors.

## Preparation

Select a draw call that writes to the target (or the last draw of the pass you suspect).

## Example prompts

**Quick investigation:**
> Inspect the render target bound to the selected draw call. Show its contents, check the
> format and dimensions, and inspect representative pixel values.

**Detailed investigation:**
> The render target for the selected draw call looks black. Check the bound render target:
> confirm its format and dimensions, read its per-channel statistics (minimum and maximum
> values across the whole texture), sample pixel values at the center and corners, and
> get a preview image. Based on those values, explain whether the target contains no
> data, HDR values outside the displayable range, NaN/Inf, or something else.

## What the agent should investigate

- The bound color targets and depth target: resource IDs, formats, sizes, mip level and slice
- Per-channel statistics (min/max) across the entire target, to distinguish true zero from HDR values outside display range
- Pixel values at representative coordinates (center, corners, areas where content is expected)
- A preview image if the target is a standard color format

## Expected results

- Format and size, e.g. `R16G16B16A16_FLOAT`, 1920×1080
- Statistics such as `max.float = [0.0, 0.0, 0.0, 1.0]` (genuinely empty color) or
  `max.float = [24.3, 18.1, 9.7, 1.0]` (HDR values far above 1.0)
- Exact pixel values in `float`, `uint` and `sint` form

## How to interpret the results

**A black image does not mean the values are zero.**

- Float targets (HDR, lighting buffers) often hold values far above 1.0 or tiny values
  near 0. A display mapping may show them as white or black. Use statistics and pixel
  values for conclusions, not the preview.
- Integer targets (`R32_UINT` IDs, `R8_UINT` masks) contain numbers, not colors; a
  preview of them is not meaningful. Read the `uint` values.
- If min = max = 0 for all channels, nothing was written by the selected event (or
  before it): check the draw (Scenario B), blending, or that the right target is bound.
- NaN/Inf values (`"nan"`/`"inf"` in results) propagate through post-processing and
  often turn a whole image black.
- Contents reflect the selected event. Select a later event to see later writes.

## Limitations

- The PNG is RenderDoc's display conversion of one mip/slice, not exact data.
- Large textures produce large PNGs; the result must fit 16 MiB. Use a smaller mip if
  you get `result_too_large`.
- MSAA: `get_pixel_value` takes a `sample` index; the image and statistics use the
  default resolve behavior of RenderDoc.
- Pixel History (which draw wrote a pixel) is not implemented.

## Related tools

`get_render_targets`, `get_texture_info`, `get_texture_statistics`, `get_pixel_value`,
`get_texture_image` — see
[Render targets, textures and pixels](../tools.md#render-targets-textures-and-pixels).
