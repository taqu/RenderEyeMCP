[English](compute-debugging.md) | [日本語](../../ja/examples/compute-debugging.md)

# Scenario D5 — Compute Shader NaN

## Problem

A compute shader producing a post-processing result outputs NaN or Inf values, causing
corrupted pixels downstream. You need to find the exact instruction that first generates
the NaN and identify the variable responsible.

## Preparation

1. RenderDoc is running with the RenderEyeMCP extension enabled.
2. A capture is loaded and the dispatch event containing the compute shader is known or
   selected in the GUI.

## Example prompts

**Quick investigation:**
> The compute dispatch at event 550 is producing NaN in its output buffer. Step through
> thread (0,0,0) in workgroup (0,0,0) to find the first NaN-generating instruction.

**Detailed investigation:**
> Debug the compute shader at event 550. Step through thread (0,0,0) in workgroup (0,0,0)
> and scan all execution steps to find the first one that generates NaN or Inf. For that
> step, show me all variable values. Then check the same shader in a thread from a
> non-border region to confirm whether the NaN is limited to specific inputs.

## What the agent should investigate

- Collect a shader debug trace for the specified compute thread and workgroup
- Scan all execution steps for the first step that produces NaN or Inf values
- Inspect the variable values at and just before that step to identify the input that causes the problem
- Compare with a thread in a different area of the dispatch to determine whether the NaN is isolated to specific pixel regions

## Expected results

The agent should identify the specific step number where NaN first appears and name the variable involved. For example: step 47, variable `log_lum` becomes `Inf` because `log(luminance + epsilon)` evaluates to `log(0.0)` when both `luminance` and `epsilon` are zero. Subsequent arithmetic on `-Inf` produces `NaN`.

A root cause table similar to this indicates a complete investigation:

| Step | Variable | Value | Observation |
|---|---|---|---|
| 10 | `luminance` | 0.0 | Correct for black pixel |
| 46 | `epsilon`   | 0.0 | Should be ~1e-6 but is zero |
| 47 | `log_lum`   | Inf | `log(0 + 0) = -Inf` |
| 48 | `tone_factor`| NaN | Downstream arithmetic on Inf |

Fix: ensure `epsilon` is initialized to a non-zero constant before the `log` call.
This is typically a constant buffer upload bug — the uniform was not set or was zeroed.

## How to interpret the results

The first NaN step is the root cause; all NaN flags on later steps are consequences.
Read the variable values *before* the NaN step to find the input combination that
produced the problematic result. Zero-epsilon guarding for transcendental functions
(`log`, `sqrt`, `rcp`) is the most common source of this class of bug. Check whether
the constant buffer that should contain the epsilon value is correctly uploaded each frame.

## Limitations

- Only the requested thread is debugged. Shared memory, barriers, and wave operations
  are not observable from a single-thread view.
- If NaN first appears beyond `max_steps` (default 200, max 500), increase `max_steps`
  or use a thread closer to the origin of the problem.
- Returns `error: debug_compute_unsupported` if the API or driver does not support
  compute shader debugging (common on older OpenGL drivers).
- The `DebugStore` retains at most 10 traces; the oldest is evicted on overflow.

## Related tools

`debug_compute_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`,
`get_shader_debug_status`, `get_bound_resources` —
[Advanced Debugging guide](../advanced-debugging.md) and
[Tool reference](../tools.md#advanced-debugging-pixel-history--shader-debug).
