[English](shader-resources.md) | [日本語](../../ja/examples/shader-resources.md)

# Scenario C — Wrong texture or material values

## Problem

A material shows the wrong texture, a default/placeholder texture, or unexpected values
(wrong tint, roughness, UV scale).

## Preparation

Select the draw call that renders the material.

## Example prompt

> Inspect the pixel shader used by the selected draw call. List its texture and sampler
> bindings, identify the actual bound resources, and check the relevant material
> constants.

## Investigation workflow

1. `list_shaders` — confirm a pixel shader is bound and get its ID.
2. `get_shader_reflection` (`stage: Pixel`, `section: resources`, then `cbuffers`) —
   what the shader *declares*: texture/sampler names and slots, constant buffer variables
   with byte offsets and types.
3. `get_shader_bindings` (`stage: Pixel`) — for each declaration, whether something is
   *actually bound* and its `resource_id`; for constant buffers also `byte_offset` and
   `byte_size`.
4. `get_texture_info` / `get_resource_info` on each bound texture — name, size, format,
   mip count.
5. `read_buffer_data` on each constant buffer, starting at its `byte_offset`, with a
   `decode_layout` built from the reflected variables (e.g. `float32` × 4 per `float4`).
6. Optional: `get_texture_image` to look at a bound texture.

## Expected observations

- A list pairing declared names (e.g. `AlbedoMap` at t0) with bound resources and their
  names (e.g. `/textures/rock_albedo`).
- `bound: false` / `resource_id: null` for anything missing.
- Decoded constant values next to their reflected names, for example
  `BaseColorTint = [1.0, 0.5, 0.5, 1.0]`.

## Interpretation

- **Unbound declaration** → the engine did not set that slot; the GPU reads a null or
  stale descriptor.
- **Bound, but the name/size/format is unexpected** (e.g. a 4×4 default texture, an
  `R8_UNORM` where color is expected) → the wrong asset or a fallback was bound.
- **Constants look wrong** (zeros, NaN, very large) → check the engine code that fills
  the buffer, and whether the offset used matches the reflected layout.

These are observations about one draw call. Whether a value is *wrong* depends on what
your material should contain — give the agent the expected values when you know them.

## Limitations

- Sampler state details (filtering, addressing) are limited to the reflected
  declarations.
- Values are read at the selected event; resources updated later in the frame show
  their state at that point.
- Constant buffers with complex packing (arrays, structs, matrices) need a
  `decode_layout` that reflects the packing rules; the agent must build it from the
  reflected offsets.
- Reading is limited to 16384 bytes per call and 100 decoded elements.

## Related tools

`list_shaders`, `get_shader_info`, `get_shader_reflection`, `get_shader_bindings`,
`get_texture_info`, `get_resource_info`, `read_buffer_data`, `get_texture_image` —
see [Shaders and reflection](../tools.md#shaders-and-reflection).
