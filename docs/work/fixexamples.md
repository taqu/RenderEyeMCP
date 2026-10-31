# RenderEyeMCP — Rewrite Use Case Examples as Natural-Language Prompts

## Objective

Rewrite the user-facing examples under:

- `docs/en/examples/`
- `docs/ja/examples/`

The examples currently contain investigation workflows expressed primarily as MCP Tool calls.

Although technically accurate, these workflows are not particularly useful to ordinary users.

RenderEyeMCP is designed to let developers investigate graphics problems by asking their coding agents to inspect RenderDoc captures.

**The documentation should teach users what to ask their coding agents, not how to manually orchestrate MCP Tools.**

Replace tool-oriented procedures with realistic, actionable natural-language prompts.

This is a documentation improvement task. Do not modify MCP Tools, the IPC protocol, or runtime implementation.

---

## 1. Documentation Philosophy

The examples should answer three questions:

1. What graphics problem am I investigating?
2. What should I ask my coding agent?
3. What results should I expect, and how should I interpret them?

Users should not need to understand:

- MCP Tool names.
- IPC operations.
- Tool input schemas.
- Internal request parameters.
- RenderDoc Python API calls.
- Internal execution sequences.

The coding agent is responsible for selecting and invoking the appropriate MCP Tools.

Avoid writing instructions such as:

```text
1. Call get_render_targets.
2. Call get_texture_statistics.
3. Call get_pixel_value.
4. Call get_texture_image.
```

Instead, provide a natural-language instruction describing the investigation goal:

> The render target written by the selected draw call appears black. Inspect its format, dimensions, and actual pixel values. Determine whether the target contains zero values, unexpected HDR values, or data that is being displayed incorrectly. Explain the likely causes and report the evidence.

The user should be able to copy this prompt directly into Claude Code, Codex, or another MCP-compatible coding agent.

---

## 2. Review All Existing Examples

Inspect all Markdown files under:

```text
docs/en/examples/
docs/ja/examples/
```

Identify:

- Existing use cases.
- Their intended graphics debugging problems.
- Required RenderDoc preparation.
- Existing investigation workflows.
- Expected observations.
- Interpretation guidance.
- Known limitations.

Preserve the original technical meaning of each example.

Do not replace specific graphics debugging scenarios with generic prompts.

Do not invent new RenderDoc capabilities.

Use the repository's current MCP Tool documentation to verify what each scenario can actually investigate.

The English and Japanese examples should cover the same scenarios and capabilities.

---

## 3. Recommended Example Structure

Use a consistent, user-oriented structure.

For English:

```markdown
# Scenario — Descriptive title

## Problem

Describe the visible graphics problem.

## Preparation

Explain what the user needs to do in RenderDoc.

## Example prompts

Provide natural-language prompts that can be copied
directly into a coding agent.

## What the agent should investigate

Describe the investigation objectives without naming
specific MCP Tools or their parameters.

## Expected results

Describe the kinds of findings the user may receive.

## How to interpret the results

Explain common causes and possible next steps.

## Limitations

Describe important capability limitations.
```

For Japanese, use corresponding natural headings:

```markdown
# シナリオ — タイトル

## 問題

## 準備

## プロンプト例

## 調査内容

## 期待される結果

## 結果の解釈

## 制限事項
```

Adapt the structure when a section does not contribute useful information.

Do not add empty sections merely for consistency.

---

## 4. Provide Practical, Copyable Prompts

Each scenario should contain at least one useful prompt.

Where appropriate, provide multiple prompts with different investigation depths.

### Quick Investigation

A short prompt for identifying the immediate problem.

### Detailed Investigation

A more specific prompt requesting technical evidence and possible causes.

### Follow-up Investigation

An optional prompt for investigating findings from the first analysis.

Do not force three prompts into every scenario if they would be repetitive.

### Example — Black Render Target

**Quick investigation:**

> The render target written by the selected draw call appears completely black. Investigate why and report the most likely causes.

**Detailed investigation:**

> Inspect the render target bound to the selected draw call. Check its format, dimensions, actual pixel values, and channel statistics. Determine whether the image is genuinely empty, contains HDR values outside the visible range, or is being interpreted incorrectly. Explain your conclusions using the captured data.

**Follow-up investigation:**

> The render target contains nonzero values but still appears black. Investigate whether its format, numeric range, or display conversion could explain the difference. Identify what additional evidence is needed to confirm the cause.

These prompts express debugging objectives without prescribing MCP Tool execution order.

The agent must decide which available Tools are appropriate.

---

## 5. Make Prompts Specific to Each Scenario

Avoid generic examples such as:

> Analyze this capture.

> Check the rendering.

> Find the problem.

Instead, include meaningful debugging context.

Examples of useful investigation objectives include:

- Explain why a draw call produces no visible geometry.
- Investigate a black or incorrectly colored render target.
- Identify unexpected shader resource bindings.
- Examine vertex attributes and index buffers.
- Compare the pipeline state of two draw calls.
- Investigate unexpectedly expensive rendering passes.
- Examine suspicious texture formats or buffer contents.
- Investigate abnormal depth or stencil behavior.

These are illustrative objectives, not instructions to create new scenarios.

Base the final examples on the actual documentation and supported capabilities.

### Important

Prompts should describe a desired result, not a sequence of API calls.

Prefer:

> Compare the vertex input and pipeline state of these two draw calls and explain the differences that could affect rendering.

Avoid:

> Execute get_mesh_info, get_pipeline_state, and get_shader_reflection for both events.

---

## 6. Preserve Useful Technical Explanations

Do not remove valuable graphics debugging knowledge merely because it is technical.

For example, the existing render-target documentation explains that:

- A black preview does not necessarily mean all pixel values are zero.
- HDR render targets may contain values above 1.0.
- Integer textures contain numeric data rather than ordinary colors.
- NaN and infinity may affect subsequent rendering.
- Capture contents reflect the selected event.

These explanations are useful and should remain.

However, move low-level MCP Tool invocation details out of the user-facing investigation workflow.

For example, details such as:

```text
max_dim
required_max_dim
hist_min
hist_max
coords
sample
```

should generally remain in the Tool reference documentation rather than the scenario prompts.

Only mention such parameters when they are genuinely necessary for a user to understand a limitation.

---

## 7. Keep Preparation Instructions Practical

Users may still need to perform actions in the RenderDoc GUI before asking the agent to investigate.

Keep those instructions clear and concise.

For example:

> Open the capture in RenderDoc and select the draw call that writes to the problematic render target.

Do not assume the coding agent can automatically perform GUI actions that are not supported by the current implementation.

Distinguish between:

- Actions the user must perform in RenderDoc.
- Investigation the coding agent can perform through RenderEyeMCP.

Do not promise automatic capture loading, event selection, or GUI manipulation unless the implementation supports those operations.

---

## 8. Describe Expected Results, Not Tool Responses

The examples should explain what useful information the agent can provide.

Prefer descriptions such as:

- Whether the render target contains meaningful data.
- Whether the resource format matches its intended use.
- Whether the selected draw call writes to the expected target.
- Whether shader resources are correctly bound.
- Which pipeline state differences may explain the problem.
- Which evidence supports a suspected cause.

Avoid presenting raw MCP response schemas as the primary expected output.

Technical values may still be used to illustrate meaningful findings.

For example:

> The agent may discover that an HDR target contains values significantly above 1.0, indicating that the apparent white image may result from display conversion rather than incorrect rendering.

The example should distinguish possible observations from guaranteed outcomes.

Do not invent actual results from captures that have not been inspected.

---

## 9. Preserve Capability Limitations

Review the current implementation before documenting capabilities.

Do not claim that a scenario can perform an operation that the current RenderEyeMCP implementation does not support.

For example, the attached render-target example states that Pixel History is unavailable.

Verify whether this limitation still applies to the current Go-based implementation and RenderDoc Extension.

If Pixel History is now supported, update the example accordingly.

If it remains unsupported, retain the limitation.

Apply the same verification to all other scenarios.

Do not copy outdated limitations without checking the current implementation.

Distinguish between:

- Unsupported RenderEyeMCP functionality.
- RenderDoc API limitations.
- GPU or driver capability limitations.
- Operations requiring additional user preparation.

---

## 10. English and Japanese Consistency

Update both language versions together.

Requirements:

- Preserve equivalent scenario coverage.
- Preserve equivalent investigation goals.
- Preserve equivalent capability limitations.
- Use natural language appropriate for each language.
- Avoid awkward literal translations.
- Maintain existing cross-language navigation links.
- Keep Markdown formatting consistent.

Japanese prompts should read like instructions a Japanese graphics programmer would naturally give to a coding agent.

English prompts should be concise, clear, and technically precise.

Do not mix English and Japanese within a prompt unless it is appropriate for technical terminology.

---

## 11. Keep Tool Documentation Separate

The `docs/en/examples/` and `docs/ja/examples/` directories are user-oriented use case collections.

Detailed MCP Tool documentation should remain in the appropriate Tool reference pages.

Do not duplicate complete Tool schemas or parameter descriptions inside scenario examples.

Existing links to Tool references may be retained where helpful, but they should be secondary.

A user should be able to understand and use a scenario without opening the Tool reference documentation.

---

## 12. Update Navigation and Index Pages

Inspect any documentation indexes, README links, or scenario tables that reference the examples.

Ensure that they describe the examples as practical coding-agent prompts rather than manual MCP Tool workflows.

Where appropriate, introduce the examples with a short explanation:

> These examples show how to investigate common graphics problems by describing the issue to your coding agent. Open a capture in RenderDoc, perform any listed preparation, and copy an example prompt into your agent. RenderEyeMCP provides access to the relevant capture data automatically.

Provide a natural Japanese equivalent.

Preserve existing working links.

---

## 13. Validation

After rewriting the examples:

1. Confirm that every existing scenario still has a useful example prompt.
2. Confirm that prompts do not directly instruct users to invoke MCP Tools.
3. Confirm that prompts are actionable with the current implementation.
4. Confirm that required RenderDoc preparation is documented.
5. Confirm that important technical interpretation guidance remains.
6. Confirm that unsupported capabilities are not promised.
7. Confirm that English and Japanese examples are consistent.
8. Verify Markdown links and navigation.
9. Check that Tool-specific parameter instructions have been removed from user-facing workflows.
10. Confirm that no runtime code or MCP Tool contracts have changed.

Review the examples from the perspective of a developer who understands graphics programming but has never used RenderEyeMCP.

The developer should be able to follow the instructions without knowing any MCP Tool names.

---

## Acceptance Criteria

The task is complete when:

- All existing examples under `docs/en/examples/` and `docs/ja/examples/` are rewritten as practical coding-agent use cases.
- Each scenario includes at least one copyable natural-language prompt.
- Tool-call sequences are no longer the primary investigation instructions.
- Existing technical explanations and important limitations are preserved.
- Prompts reflect actual RenderEyeMCP capabilities.
- English and Japanese documentation remain aligned.
- Existing documentation navigation works.
- No MCP server or RenderDoc Extension runtime changes are introduced.

## Deliverables

- Updated English scenario examples.
- Updated Japanese scenario examples.
- Updated documentation indexes where necessary.
- A concise summary of modified files.
- A report of any outdated capability descriptions discovered during the review.

## Execution Instructions

Inspect all existing examples before editing.

Use the current implementation and Tool reference documentation to verify supported functionality.

Rewrite the examples directly rather than merely proposing changes.

Prioritize practical developer instructions over internal implementation details.

Do not introduce new debugging features or unrelated documentation changes.

**The final examples should teach developers how to ask RenderEyeMCP useful graphics debugging questions, not how to manually operate its MCP interface.**
