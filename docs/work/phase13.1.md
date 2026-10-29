# Phase 13.1 — GPU Performance Analysis End-to-End Validation

## Objective

Create and execute a simple, reproducible end-to-end GPU performance analysis scenario using RenderEyeMCP and an AI coding agent.

The purpose is to validate that the GPU performance tools introduced in Phase 13 can be used together with the existing capture, event, pipeline, and shader inspection tools to investigate real rendering performance.

This is a validation and usability improvement task, not a new major feature development phase.

The scenario should demonstrate the complete workflow:

1. Discover the capture currently loaded in RenderDoc.
2. Discover available GPU performance counters.
3. Collect GPU timing measurements.
4. Identify expensive GPU events.
5. Inspect the most expensive event.
6. Correlate timing results with pipeline and shader information.
7. Generate a short performance analysis report.

**The primary success criterion is that a coding agent can execute the workflow using RenderEyeMCP without manual MCP tool orchestration by the developer.**

The developer should only need to open a capture in RenderDoc and provide a natural-language instruction to the agent.

---

## 1. Inspect the Existing Implementation

Before implementing the scenario, inspect the current repository.

Identify:

- Phase 13 GPU performance MCP tools.
- GPU counter discovery.
- Measurement lifecycle management.
- GPU timing retrieval.
- Performance summary generation.
- Event and draw-call inspection.
- Pipeline-state inspection.
- Shader inspection.
- Active capture discovery.
- Existing test infrastructure.
- Existing English and Japanese documentation.

Use the actual MCP tool names and parameter schemas.

Do not assume that the names proposed in the Phase 13 design document match the final implementation.

Do not create replacement implementations for existing functionality.

## 2. Scenario Scope

Implement one primary scenario:

**Find and investigate the most expensive GPU events in the currently loaded RenderDoc capture.**

The scenario must work with a capture opened manually or through a game engine.

Do not require the agent to reopen the capture.

### Required Capabilities

The scenario should use existing functionality to:

- Identify the loaded capture.
- Discover the GPU duration counter.
- Execute an explicit GPU measurement.
- Wait for measurement completion if asynchronous.
- Retrieve event timing results.
- Rank expensive events.
- Inspect the most expensive event.
- Retrieve relevant pipeline and shader information.
- Produce an evidence-based report.

### Optional Capabilities

Use these only when already implemented and available:

- Render pass timing aggregation.
- Pipeline statistics.
- Shader disassembly.
- Render target metadata.
- Resource binding inspection.
- Additional performance counters.

Optional capabilities must not prevent the primary scenario from completing.

---

## 3. Test Capture Requirements

Use a real RenderDoc capture.

Prefer an existing capture from the repository's test assets or the currently loaded RenderDoc GUI.

A suitable capture should contain:

- Multiple draw calls.
- A meaningful event hierarchy.
- At least one graphics pipeline.
- Shader bindings.
- GPU events eligible for timing measurements.

A capture with debug markers is preferable but not mandatory.

A compute dispatch is optional.

### 3.1 Do Not Require a New Test Application

Do not build a new graphics application solely for this scenario.

Reuse existing Unity, Unreal Engine, RenderDoc, or repository test assets where practical.

If no suitable capture is available, document the required preparation steps.

### 3.2 Capture Identity

Record the actual capture identity and relevant metadata.

Do not embed developer-specific absolute paths in reusable documentation.

Do not assume that a particular event ID will exist in every capture.

---

## 4. Coding Agent Execution Scenario

Create a reusable scenario document.

Suggested path:

`docs/en/examples/gpu-performance-end-to-end.md`

Also create the Japanese equivalent:

`docs/ja/examples/gpu-performance-end-to-end.md`

### 4.1 Developer Preparation

The developer should:

1. Start RenderDoc.
2. Open a capture containing several draw calls.
3. Confirm that RenderEyeMCP is connected to the coding agent.
4. Submit the performance analysis prompt.

No manual GPU counter collection should be required.

### 4.2 Primary Agent Prompt

Use the following prompt as the reference scenario:

> Analyze GPU performance in the capture currently open in RenderDoc.
>
> Collect GPU timing measurements and identify the 10 most expensive draw calls or compute dispatches.
>
> Inspect the most expensive event, including its pipeline state, shaders, render targets, and available pipeline statistics.
>
> Explain possible performance bottlenecks based on the collected evidence.
>
> Generate a concise Markdown report that clearly separates measured results from hypotheses.
>
> Do not modify the capture or change the current RenderDoc GUI selection.

The agent should determine the appropriate MCP tool sequence from the available tool descriptions.

Do not require the developer to manually specify individual MCP tool calls.

---

## 5. Expected Tool Workflow

The coding agent should perform the following sequence.

### Step 1 — Discover Active Capture

Query the existing RenderEyeMCP session and capture tools.

Verify that:

- A RenderDoc GUI session is available.
- A capture is loaded.
- The capture can be inspected.
- The target session is unambiguous.

If multiple captures are available, follow the existing session resolution rules.

Do not silently choose an arbitrary RenderDoc GUI instance.

### Step 2 — Discover GPU Counters

Query the available GPU performance counters.

Find the supported GPU duration counter.

Use the actual counter identifiers returned by RenderDoc.

Do not assume a fixed numeric counter ID.

If GPU duration is unavailable, record the limitation and terminate the timing portion of the scenario gracefully.

Do not generate simulated timing values.

### Step 3 — Collect GPU Timing

Execute the Phase 13 GPU counter collection operation.

Use an explicit measurement request.

If measurement is asynchronous:

1. Start the measurement.
2. Obtain the measurement ID.
3. Query its status using the supported interface.
4. Continue only after completion.

Use bounded waiting and existing timeout handling.

Do not start duplicate measurement jobs unnecessarily.

### Step 4 — Retrieve Expensive Events

Retrieve the timing results.

Rank eligible draw calls and compute dispatches by measured GPU duration.

Return the top 10 events, or fewer if insufficient results are available.

Preserve:

- Event ID.
- Event name.
- Event type.
- GPU duration.
- Timing unit.
- Parent debug marker or pass, when available.

Exclude marker-only or non-work events from a draw/dispatch ranking unless they are explicitly presented in a separate category.

Do not mix counters with different meanings or units.

### Step 5 — Inspect the Most Expensive Event

Identify the event with the highest measured GPU duration.

Use existing inspection tools to retrieve:

- Event information.
- Draw or dispatch parameters.
- Pipeline state.
- Bound shaders.
- Relevant shader reflection.
- Render target configuration, where applicable.

Retrieve pipeline statistics if available.

Do not require the agent to change the GUI's selected event.

Use explicit event targeting where supported.

If inspecting an arbitrary event would require unsafe GUI replay manipulation, skip that inspection and report the limitation.

### Step 6 — Analyze Performance

Use the collected information to investigate possible reasons for the event's GPU cost.

Potential observations include:

- Large vertex or index counts.
- High instance counts.
- High pixel shader invocation counts.
- Large render target dimensions.
- Expensive shader configurations.
- Multiple render targets.
- Multisampling.
- Depth or blending configuration.
- Large compute dispatch dimensions.

Do not automatically classify these characteristics as bottlenecks.

A large draw call or complex shader is not sufficient evidence of the actual hardware bottleneck.

Separate:

1. Measured facts.
2. Derived observations.
3. Possible explanations.
4. Information that cannot be determined from the available counters.

Do not invent performance measurements or hardware characteristics.

---

## 6. Performance Report

Generate a concise Markdown report.

Suggested output path:

`reports/gpu-performance-analysis.md`

Use the project's existing output convention if one is already established.

Avoid overwriting an existing report without an explicit policy.

### 6.1 Report Structure

Use the following format.

#### Capture Information

Include:

- Capture identity or path.
- Graphics API.
- Available GPU information.
- Measurement ID.
- Measurement status.
- Counters used.

#### GPU Timing Summary

Provide the top 10 measured events.

Example table:

| Rank | Event ID | Event Type | GPU Time |
|---|---|---|---|
| 1 | 580 | DrawIndexed | 1.42 ms |
| 2 | 720 | Dispatch | 1.08 ms |
| 3 | 451 | DrawIndexed | 0.82 ms |

These are illustrative values only.

The actual report must use real measurements.

#### Most Expensive Event

Summarize:

- Event ID and name.
- GPU duration.
- Draw or dispatch parameters.
- Pipeline configuration.
- Bound shaders.
- Relevant render target information.
- Available pipeline statistics.

#### Performance Observations

Describe the most important measured and derived findings.

#### Potential Bottlenecks

Provide plausible explanations supported by available evidence.

Clearly distinguish hypotheses from confirmed measurements.

#### Recommended Next Investigations

Suggest a small number of concrete follow-up investigations.

Avoid generic optimization advice unrelated to the collected data.

#### Measurement Limitations

Document:

- Unsupported counters.
- Missing data.
- Replay measurement limitations.
- Unverified assumptions.
- Any skipped inspection operations.

### 6.2 Report Accuracy

Do not present RenderDoc replay timings as original application frame times.

Do not infer frame FPS from incomplete GPU event measurements.

Do not sum event timings and label the result as total frame latency without valid measurement semantics.

---

## 7. Automated Scenario Validation

Where practical, add an integration or smoke-test entry point.

The test should validate the workflow through the actual MCP interface rather than bypassing MCP and directly invoking internal Python methods.

Prefer existing test infrastructure.

Do not introduce a large agent-benchmark framework.

### 7.1 Validation Levels

Separate two validation levels.

**Level A — MCP Tool Integration**

Verify that the required tools can be invoked successfully and return consistent results.

This may use a deterministic MCP client harness.

**Level B — Coding Agent Execution**

Verify that a real coding agent can execute the scenario from the natural-language prompt.

This should be performed with Claude Code or Codex where available.

Do not treat Level A as proof that Level B succeeded.

### 7.2 Required Assertions

Check that:

- The loaded capture is identified correctly.
- GPU duration counter discovery succeeds where supported.
- A measurement is completed.
- Returned counter values are real and well-formed.
- Timing results reference valid events.
- Ranking is sorted correctly.
- The most expensive event is inspected.
- The report contains actual measurements.
- Missing optional counters do not cause the workflow to fail.
- No unintended capture-open operation occurs.

### 7.3 GUI State Preservation

Record the selected event and relevant GUI state before execution.

After execution, verify that the scenario did not unexpectedly:

- Change the selected event.
- Open another capture.
- Close the current capture.
- Replace the active session.

Document any unavoidable effects of explicit GPU measurement.

### 7.4 Failure Handling

The scenario must handle:

- No capture loaded.
- No available GPU timing counter.
- Measurement failure.
- Counter collection timeout.
- Missing timing results.
- Capture changed during measurement.
- Unsupported arbitrary-event inspection.
- Agent tool-call failures.

Failures should produce useful diagnostics, not fabricated reports.

---

## 8. Documentation

Add the scenario to the existing English and Japanese documentation.

### 8.1 English Documentation

Explain:

- Purpose.
- Prerequisites.
- How to open a suitable capture.
- How to connect the coding agent.
- Copyable agent prompt.
- Expected workflow.
- Example report structure.
- Limitations.
- Troubleshooting.

### 8.2 Japanese Documentation

Provide equivalent Japanese instructions.

Use natural Japanese technical terminology.

Preserve MCP tool identifiers and commands.

### 8.3 README Integration

Add a link to the scenario from both:

- `README.md`
- `README.ja.md`

Place it in the existing examples or performance-analysis section.

Do not significantly expand the README with the full scenario.

---

## 9. Scope Restrictions

Do not implement:

- New GPU counters.
- Vendor-specific profiler integrations.
- CPU profiling.
- Real-time frame monitoring.
- Automated shader optimization.
- New pipeline-state inspection infrastructure.
- New rendering workloads unless absolutely necessary.
- A large benchmark framework.
- A new agent orchestration system.
- Major Shared IPC Service changes.
- Unrelated MCP tools.

Small fixes required to make the existing performance analysis tools work correctly are permitted.

Keep these changes focused and document them.

---

## 10. Acceptance Criteria

Phase 13.1 is complete when:

- [ ] A simple end-to-end GPU performance scenario is documented.
- [ ] English and Japanese scenario documentation are available.
- [ ] The scenario uses the actual MCP tools implemented in Phase 13.
- [ ] The developer can start the workflow using a single natural-language prompt.
- [ ] The agent can discover the currently loaded RenderDoc capture.
- [ ] Available GPU timing counters can be identified.
- [ ] GPU timing measurement can be executed where supported.
- [ ] The top 10 expensive draw calls or dispatches can be identified.
- [ ] The most expensive event can be inspected using existing tools.
- [ ] Pipeline and shader information can be correlated with measurements.
- [ ] The workflow generates a concise Markdown report.
- [ ] The report separates measured facts from hypotheses.
- [ ] Missing optional counters are handled gracefully.
- [ ] Existing GUI selection is not unexpectedly modified.
- [ ] The workflow does not reopen the capture.
- [ ] At least one actual MCP integration test is executed where a suitable RenderDoc environment is available.
- [ ] At least one real Coding Agent execution is performed where an agent environment is available.
- [ ] Unexecuted tests and environmental limitations are documented.
- [ ] Both READMEs link to the scenario.
- [ ] No unnecessary performance-analysis infrastructure is added.

Do not mark an unexecuted test as passed.

If GPU timing is unavailable in the test environment, report that limitation and preserve the scenario for an environment that supports the required counters.

---

## 11. Deliverables

Provide:

1. English GPU performance scenario documentation.
2. Japanese GPU performance scenario documentation.
3. A reusable natural-language Coding Agent prompt.
4. A Markdown performance report template or verified example.
5. A lightweight integration test where practical.
6. Actual execution results where available.
7. A list of issues discovered in the existing Phase 13 tools.
8. Focused fixes for blocking issues, where appropriate.

At completion, provide a short implementation and validation summary.

Distinguish:

- Implemented.
- Tested.
- Partially tested.
- Not tested.
- Blocked.

---

## Final Goal

A developer should be able to:

1. Open a capture in RenderDoc.
2. Connect Claude Code or Codex to RenderEyeMCP.
3. Enter one natural-language instruction:

**"Analyze the GPU performance of the current RenderDoc capture, find the most expensive events, inspect the worst one, and generate a short report."**

The agent should then use the existing RenderEyeMCP tools to collect GPU timings, identify expensive events, inspect relevant rendering state, and produce a report based on actual measurements.

The scenario should be simple enough for a new user to follow and reliable enough to serve as a regression test for future RenderEyeMCP releases.

**Phase 13.1 should validate that the GPU performance analysis functionality is useful in a real Coding Agent workflow before proceeding to Phase 14.**
