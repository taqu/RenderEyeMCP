[English](prompts.md) | [日本語](../ja/prompts.md)

# Prompt examples

Copyable prompts, grouped by what you are trying to find out. Each one works on the
capture and event **currently selected in RenderDoc**, so select the right event first.

## Good prompts

- describe what you **observe** ("the character is missing", "the target is black");
- refer to the **selected** RenderDoc event instead of guessing IDs;
- ask for **evidence**: values, bindings, formats;
- do **not** assume the cause;
- do **not** ask for things the tools cannot do (Pixel History, stepping through a
  shader, profiling, changing the selection).

Adding *"Separate what you observed from what you suspect."* to any prompt helps.

## Connection check

> List the available RenderDoc sessions.

> What capture is currently loaded in RenderDoc?

> Show the selected draw call and its pipeline state.

## General inspection

> Inspect the currently selected draw call in RenderDoc and summarize the important
> pipeline state.

## Resource binding

> Check which textures and buffers are bound to the selected pixel shader and identify
> any missing bindings.

## Constant buffers

> Inspect the constant buffers used by the selected draw call and show the relevant
> transformation and material parameters.

(The agent combines `get_shader_reflection` for variable names and offsets with
`read_buffer_data` for values.)

## Render target

> Show the current render target and inspect the pixel values around the suspicious
> area.

Give coordinates if you have them: *"…around x=640, y=360."*

## Compute dispatch

> Inspect the selected compute dispatch and examine the output buffer values.

## Navigating a capture

> List the dispatches in this capture with their group counts.

> List the first 50 draw calls and tell me which ones use more than 10,000 indices.

## Prompts that will not work (yet)

| Request | Why |
|---------|-----|
| "Select event 1200 and inspect it." | Selection is never changed by RenderEyeMCP; select it in RenderDoc |
| "Show the pixel history of (100, 200)." | Pixel History is not implemented |
| "Step through the pixel shader for this pixel." | Shader debugging is not implemented |
| "Which pass is slowest?" | No GPU timing/profiling tools |
| "What is the depth compare function?" | Depth/stencil state is not exposed |
