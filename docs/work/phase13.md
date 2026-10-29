# Phase 13 — GPU Performance Analysis & Profiling

## Objective

Extend RenderEyeMCP with GPU performance measurement and analysis capabilities for captures already loaded in the RenderDoc GUI.

Phase 13 builds on the existing infrastructure:

- Phase 6 — Shared IPC Service and multi-agent support.
- Phase 7 — RenderDoc GUI state discovery and synchronization.
- Phase 8 — Active capture, event, and pipeline-state inspection.
- Phase 9 — GPU resource metadata and buffer inspection.
- Phase 10 — Shader inspection and reflection.
- Phase 11 — Render target, texture, and pixel inspection.
- Phase 12 — Release preparation and bilingual documentation.

The primary objective is to enable AI coding agents to identify expensive GPU events, analyze rendering-pass costs, inspect pipeline statistics, and correlate performance measurements with relevant rendering state.

Typical developer requests include:

- "Find the most expensive draw calls in this capture."
- "Which rendering pass consumes the most GPU time?"
- "Compare the GPU cost of the shadow and G-buffer passes."
- "Inspect the pipeline statistics for the selected draw call."
- "Investigate why this draw call is expensive."
- "Which compute dispatches consume the most GPU time?"

**RenderEyeMCP must expose reliable GPU measurements and provide the information needed for evidence-based performance analysis.**

It must not attempt to become a replacement for dedicated GPU profiling tools such as NVIDIA Nsight Graphics, AMD Radeon GPU Profiler, or Intel Graphics Performance Analyzers.

This phase focuses on the performance information available through RenderDoc.

---

## 1. Investigate the Existing Implementation

Before making changes, inspect the current repository.

Identify:

1. RenderDoc extension implementation.
2. Existing RenderDoc ReplayController integration.
3. Replay-thread scheduling mechanisms.
4. Phase 6 Shared IPC Service.
5. Phase 7 GUI session and capture state management.
6. Phase 8 event and action enumeration.
7. Debug marker and event hierarchy representation.
8. Existing performance-related tools or utilities.
9. MCP request handling and timeout mechanisms.
10. Existing long-running task infrastructure.
11. Existing result caching and serialization.
12. Existing tests and documentation.

Determine which capabilities can be reused.

Do not introduce duplicate event enumeration, capture identity, or replay-controller infrastructure.

### 1.1 Verify Existing Dependencies

Confirm that RenderEyeMCP can:

- Identify the currently loaded capture.
- Resolve the selected GUI session.
- Enumerate events and actions.
- Preserve event hierarchy.
- Identify draw calls and compute dispatches.
- Retrieve pipeline state for relevant events.
- Associate inspection results with capture identity.

Performance analysis must use the existing event and capture models wherever possible.

### 1.2 Establish Current Limitations

Identify limitations that affect GPU counter collection.

Examples include:

- ReplayController ownership.
- Replay-thread constraints.
- GUI state modifications.
- IPC timeouts.
- Unsupported graphics APIs.
- Hardware-dependent counters.
- Concurrent ReplayController access.

Document these limitations before implementing measurement operations.

---

## 2. Investigate RenderDoc GPU Counter APIs

Investigate the actual RenderDoc APIs supported by the installed version.

Relevant API concepts include:

- `ReplayController`
- `GPUCounter`
- `CounterDescription`
- `CounterResult`
- `CounterUnit`
- `ActionDescription`
- `EnumerateCounters()`
- `DescribeCounter()`
- `FetchCounters()`

Verify method signatures, data structures, enum values, and behavior against the installed RenderDoc version.

Do not assume all counters or measurement capabilities are available.

### 2.1 Counter Enumeration

Investigate how `EnumerateCounters()` reports supported counters.

Determine whether the available counters depend on:

- Graphics API.
- GPU vendor.
- GPU architecture.
- Graphics driver.
- Replay environment.
- RenderDoc version.
- Capture characteristics.

Do not hardcode a universal list of available counters.

### 2.2 Counter Descriptions

Investigate `DescribeCounter()` and determine how to retrieve:

- Counter identifier.
- Human-readable name.
- Description.
- Unit.
- Result type.
- Result byte width.
- Relevant interpretation information.

Preserve the units and types provided by RenderDoc.

Do not assume every counter is a floating-point value.

### 2.3 Counter Collection

Investigate `FetchCounters()`.

Determine:

- How counters are requested.
- How results are associated with event IDs.
- Whether collection requires one or more replay passes.
- Whether multiple counters can be collected together.
- Whether counters must be collected in separate groups.
- What happens when a counter is unsupported.
- Whether collecting counters changes replay state.
- Whether GPU synchronization is required.
- What happens during capture unload or replay shutdown.

Do not assume that counter collection is inexpensive or side-effect-free.

### 2.4 Hardware Counter Restrictions

Some hardware counters may not be available on every GPU.

Some counters may be mutually incompatible or require separate measurement passes.

Support these restrictions explicitly.

Do not assume all requested counters can be collected simultaneously.

### 2.5 Record API Findings

Document:

- Supported APIs.
- Available counter categories.
- Replay behavior.
- Threading requirements.
- Known compatibility restrictions.
- Unsupported or unavailable functionality.

Do not implement undocumented workarounds that manipulate GPU driver internals.

---

## 3. Define Measurement and Analysis Responsibilities

Separate GPU measurement from performance analysis.

### 3.1 Measurement Layer

The measurement layer is responsible for:

- Discovering available counters.
- Validating counter requests.
- Collecting counter values.
- Associating results with events.
- Preserving capture identity.
- Recording measurement metadata.
- Reporting collection failures.

### 3.2 Analysis Layer

The analysis layer is responsible for:

- Ranking expensive events.
- Summarizing counter results.
- Grouping events by render pass.
- Calculating applicable statistics.
- Comparing compatible measurements.
- Identifying unusual values.
- Presenting evidence suitable for coding agents.

The analysis layer should operate on previously collected measurement results.

**Do not automatically repeat GPU counter collection every time an agent requests a different summary.**

### 3.3 Reuse Collected Results

A typical workflow should be:

```text
Loaded RenderDoc Capture
          |
          v
Discover GPU Counters
          |
          v
Explicit Counter Collection
          |
          v
Measurement Result
          |
          +---- Event Ranking
          |
          +---- Pass Summary
          |
          +---- Pipeline Statistics
          |
          +---- Performance Analysis
          |
          +---- Export / Comparison
```

Keep measurement results separate from GUI state snapshots.

---

## 4. GPU Counter Discovery

Implement GPU counter discovery.

Suggested MCP tool:

`list_gpu_counters`

Reuse an existing tool if equivalent functionality already exists.

### 4.1 Required Information

Return available information such as:

- Counter ID.
- Counter name.
- Description.
- Unit.
- Value type.
- Counter category, when reliably identifiable.

Preserve RenderDoc counter identifiers.

### 4.2 Counter Categories

Where available, distinguish:

- GPU duration or timing.
- Input assembly statistics.
- Vertex processing statistics.
- Geometry processing statistics.
- Rasterization statistics.
- Fragment/pixel shader statistics.
- Compute statistics.
- Other hardware-specific metrics.

Do not infer counter categories from unreliable naming conventions.

### 4.3 Counter Capability Response

An illustrative response:

```json
{
  "capture_id": "capture-1234",
  "counters": [
    {
      "id": "GPU_DURATION",
      "name": "GPU Duration",
      "unit": "seconds",
      "value_type": "float64"
    },
    {
      "id": "INPUT_VERTICES",
      "name": "Input Vertices",
      "unit": "absolute",
      "value_type": "uint64"
    }
  ]
}
```

Counter IDs and names above are conceptual examples.

Use the actual identifiers and descriptions returned by RenderDoc.

### 4.4 No Available Counters

If no counters are available, return a structured capability result.

Do not report an empty list as evidence that the capture contains no GPU work.

Clearly distinguish unsupported counter collection from an empty capture.

---

## 5. Explicit GPU Measurement

Implement an explicit operation for collecting GPU counters.

Suggested MCP capability:

`collect_gpu_counters`

This operation differs from ordinary read-only inspection.

Counter collection may involve replay execution and GPU synchronization.

### 5.1 Explicit Invocation

Do not trigger GPU measurement implicitly from:

- Session discovery.
- Capture information retrieval.
- Event enumeration.
- Pipeline inspection.
- Shader inspection.
- Resource inspection.

A measurement operation must be explicitly requested.

### 5.2 Request Parameters

Support:

- Target GUI session.
- Capture identity.
- Requested counter IDs.
- Measurement options supported by RenderDoc.

Reuse the existing session resolution rules.

Validate every counter identifier against the available counters.

### 5.3 Measurement Scope

Investigate the scope supported by RenderDoc's counter collection API.

Do not assume that `FetchCounters()` can collect only a requested subset of events.

If RenderDoc collects counters for the entire capture, collect them once and apply event filtering in the analysis layer.

Avoid creating a custom replay implementation solely to restrict counter collection to selected events.

### 5.4 Measurement Identity

Assign each collection operation a unique measurement ID.

Associate the result with:

- Capture identity.
- GUI session identity.
- Selected counter set.
- Measurement start and completion timestamps.
- Relevant graphics API.
- Available GPU and driver information.
- Measurement status.

Include sufficient information to distinguish separate measurement runs.

### 5.5 Example Result

```json
{
  "measurement_id": "measurement-001",
  "capture_id": "capture-1234",
  "status": "completed",
  "counters": [
    {
      "counter_id": "GPU_DURATION",
      "unit": "seconds",
      "result_count": 780
    }
  ]
}
```

This example is conceptual.

Do not invent result counts or device metadata.

---

## 6. Measurement Lifecycle Management

GPU counter collection may take significantly longer than ordinary MCP queries.

Introduce a safe lifecycle for these operations.

### 6.1 Measurement States

Support states such as:

- Pending.
- Running.
- Completed.
- Failed.
- Cancelled.
- Invalidated.

Use existing long-running task infrastructure if available.

Do not create a separate task framework unnecessarily.

### 6.2 Synchronous and Asynchronous Execution

Investigate how long GPU measurements take in representative captures.

If synchronous requests are reliable within existing MCP and IPC timeouts, they may remain supported.

For potentially long operations, prefer a job-oriented interface.

Suggested capabilities:

- `collect_gpu_counters`
- `get_gpu_measurement_status`

The collection request may return a measurement ID before collection completes.

### 6.3 Progress Reporting

Report actual progress when reliably available.

If RenderDoc exposes no useful measurement progress, report the operation as running without fabricating a percentage.

### 6.4 Cancellation

Support safe cancellation where the architecture permits it.

Do not forcibly interrupt RenderDoc replay operations in ways that could corrupt the replay context.

If immediate cancellation is unsupported, cancellation may prevent further queued work and discard results after the current operation safely completes.

Clearly document the behavior.

### 6.5 Timeouts

Handle:

- Replay controller shutdown.
- GUI process termination.
- IPC disconnection.
- Capture unload.
- GPU counter collection failure.
- Measurement timeout.

Do not allow a failed measurement to block the Shared IPC Service indefinitely.

### 6.6 Resource Cleanup

Ensure measurement jobs release associated resources after completion or failure.

Do not retain abandoned jobs indefinitely.

---

## 7. Replay Safety and GUI Non-Interference

This is a critical Phase 13 requirement.

Counter collection may require replay execution and may affect shared replay state.

### 7.1 Replay Ownership

Investigate how RenderDoc coordinates GUI replay operations and counter collection.

Respect existing replay-thread scheduling.

Do not invoke `FetchCounters()` directly from arbitrary IPC threads.

### 7.2 GUI State Protection

Record relevant GUI state before counter collection where possible:

- Loaded capture identity.
- Selected event.
- Current replay event.
- Relevant replay context generation.

Determine whether supported counter collection can proceed without changing developer-visible GUI state.

### 7.3 Do Not Assume Read-Only Behavior

Unlike metadata queries, GPU measurement may perform additional GPU work.

Treat it as a potentially disruptive operation even if it does not modify the capture file.

### 7.4 Safe Execution Strategy

Prefer supported RenderDoc mechanisms that coordinate replay access.

Do not directly manipulate undocumented ReplayController internals.

Do not introduce a second replay controller unless required by an explicitly documented limitation.

If the existing GUI replay context cannot safely support measurement, investigate alternatives and document the tradeoffs before implementing them.

### 7.5 State Restoration

If RenderDoc's supported APIs guarantee safe restoration of replay state after measurement, verify that behavior through tests.

Do not assume that manually saving and restoring an event ID is sufficient to restore the complete GUI state.

If non-interfering measurement cannot be guaranteed, document the effect and require an explicit measurement request.

### 7.6 Concurrent Inspection

While measurement is running:

- Ordinary metadata queries should remain safe.
- Replay-dependent requests must be coordinated.
- Another measurement must not interfere with the current operation.
- No deadlocks should occur between IPC and replay threads.

Prefer a simple, bounded concurrency policy.

---

## 8. GPU Timing Analysis

Implement event-level GPU timing analysis.

This is a primary Phase 13 deliverable.

Suggested MCP tool:

`get_gpu_timings`

### 8.1 Timing Results

Use the actual GPU duration counter provided by RenderDoc where available.

Associate results with the correct RenderDoc event IDs.

Return timing values in documented units.

Prefer seconds as the canonical stored unit when matching RenderDoc, while allowing convenient presentation in milliseconds or microseconds.

### 8.2 Result Structure

An illustrative result:

```json
{
  "measurement_id": "measurement-001",
  "unit": "milliseconds",
  "events": [
    {
      "event_id": 450,
      "name": "DrawIndexed",
      "duration": 0.82
    },
    {
      "event_id": 451,
      "name": "DrawIndexed",
      "duration": 0.35
    }
  ]
}
```

The values are illustrative only.

### 8.3 Timing Scope

Document what the GPU duration counter measures.

Do not assume a GPU timestamp duration represents:

- CPU execution time.
- Actual application frame latency.
- GPU queue idle time.
- Complete frame presentation latency.
- Wall-clock execution time of the original game.

Counter semantics must follow RenderDoc's descriptions.

### 8.4 Missing Results

Some events may not have timing results.

Do not assign zero duration to missing measurements.

Distinguish:

- Measured zero.
- No counter result.
- Unsupported event.
- Measurement failure.

### 8.5 Result Filtering

Support filtering by:

- Event ID.
- Event type.
- Draw calls.
- Compute dispatches.
- Relevant event range.
- Minimum duration.

Do not require another GPU measurement for analysis-only filtering.

### 8.6 Pagination

Large captures may contain thousands of events.

Return bounded results.

Support sorting and pagination.

Avoid returning the entire timing table by default.

---

## 9. Expensive Event Ranking

Provide a convenient way to identify the most expensive measured GPU events.

Suggested MCP tool:

`get_performance_summary`

### 9.1 Top Events

Support ranking by a selected timing or numeric counter.

Useful options include:

- Top N expensive draw calls.
- Top N expensive compute dispatches.
- Top N events by a supported metric.

Use actual counter results.

Do not substitute heuristic estimates when measurements are unavailable.

### 9.2 Example Response

```json
{
  "measurement_id": "measurement-001",
  "metric": "gpu_duration",
  "unit": "milliseconds",
  "top_events": [
    {
      "event_id": 580,
      "name": "DrawIndexed",
      "value": 1.42
    },
    {
      "event_id": 720,
      "name": "Dispatch",
      "value": 1.08
    }
  ]
}
```

This example contains illustrative values.

### 9.3 Contextual Information

Where available, include:

- Event ID.
- Event name.
- Event category.
- Parent debug marker or pass.
- Draw/dispatch parameters.
- Capture identity.

Reuse Phase 8 event descriptions.

Do not duplicate entire pipeline state objects in ranking responses.

### 9.4 Further Investigation

Ensure ranked events can be inspected through existing Phase 8–11 tools.

The agent should be able to retrieve the expensive event's:

- Pipeline state.
- Bound shaders.
- Shader reflection.
- Resource bindings.
- Render target metadata.
- Buffer information.

### 9.5 Avoid Unsupported Conclusions

A long GPU duration does not automatically identify the underlying bottleneck.

Do not claim that a draw is expensive because of its pixel shader simply because it has a high execution time.

Performance summaries must distinguish measurements from hypotheses.

---

## 10. Render Pass Performance Analysis

Implement performance grouping based on the event hierarchy and available debug markers.

Suggested MCP tool:

`get_render_pass_performance`

### 10.1 Existing Event Hierarchy

Reuse the Phase 8 event/action hierarchy.

Relevant grouping information may include:

- Application debug markers.
- Nested marker regions.
- Render pass actions.
- Event hierarchy.
- Explicitly named groups.

Do not invent render passes from arbitrary event names unless clearly identified as heuristic grouping.

### 10.2 Pass Identity

Preserve:

- Parent marker or group ID.
- Group name.
- Child event IDs.
- Hierarchy depth.
- Capture identity.

Support nested groups.

### 10.3 Pass Timing

Investigate whether RenderDoc provides a direct duration measurement for the relevant group.

If not, distinguish derived aggregation from direct GPU timing.

For example, summing measured child durations may provide a useful approximation of the measured work attributed to a group.

However, it is not necessarily equivalent to the GPU elapsed wall-clock duration of that pass.

### 10.4 Avoid Double Counting

Do not sum both parent and child durations when they represent overlapping work.

Do not add nested marker summaries to their descendant events twice.

Define explicit aggregation semantics.

### 10.5 Queue and Overlap Limitations

Graphics APIs may support multiple GPU queues and overlapping work.

A sum of event durations does not necessarily represent total GPU frame latency.

Document cases where:

- Event timing intervals overlap.
- Queue-specific results cannot be distinguished.
- Marker regions lack explicit timing boundaries.
- Replay behavior differs from original execution.

Do not invent cross-queue synchronization information.

### 10.6 Pass-Level Output

Return useful information such as:

- Group name.
- Parent group ID.
- Number of measured events.
- Sum of applicable child event durations.
- Largest child event.
- Counter coverage.
- Aggregation method.
- Unmeasured event count.

Include the method used to calculate each summary.

### 10.7 Example

```json
{
  "measurement_id": "measurement-001",
  "passes": [
    {
      "name": "Shadow Pass",
      "event_count": 120,
      "aggregated_duration_ms": 3.8,
      "aggregation": "sum_of_leaf_event_durations"
    },
    {
      "name": "GBuffer Pass",
      "event_count": 240,
      "aggregated_duration_ms": 5.2,
      "aggregation": "sum_of_leaf_event_durations"
    }
  ]
}
```

The values are illustrative.

Do not label aggregated child event durations as exact pass elapsed time unless supported by direct measurement.

---

## 11. Pipeline Statistics

Expose supported pipeline statistics counters.

Suggested MCP tool:

`get_pipeline_statistics`

This may be implemented through the generic GPU counter retrieval API rather than a separate collection mechanism.

### 11.1 Relevant Statistics

Investigate available counters such as:

- Input vertices.
- Input primitives.
- Vertex shader invocations.
- Geometry shader invocations.
- Rasterizer invocations.
- Fragment/pixel shader invocations.
- Compute shader invocations.
- Other relevant pipeline metrics.

Use the actual counters exposed by RenderDoc.

Do not assume they are all available.

### 11.2 Event Association

Associate statistics with the correct measured event.

The agent should be able to query:

- Selected draw call.
- Explicit event ID.
- Measured event range.
- Existing pass grouping.

### 11.3 Correct Counter Semantics

Do not confuse:

- Vertex count and vertex shader invocations.
- Primitive count and rasterized fragments.
- Pixel shader invocations and final visible pixels.
- Compute dispatch group count and shader invocations.

Use counter descriptions to explain the actual meaning.

### 11.4 Derived Statistics

Simple derived ratios may be useful.

Examples:

- Pixel shader invocations per input primitive.
- Vertex shader invocations per input vertex.
- GPU duration per draw call.
- Measured work per pass.

Only calculate ratios when the underlying values are compatible and meaningful.

Handle zero denominators.

Mark derived statistics explicitly.

### 11.5 No Automatic Bottleneck Classification

Pipeline statistics can suggest possible inefficiencies.

They generally do not prove:

- Memory bandwidth saturation.
- Shader occupancy limitations.
- Cache bottlenecks.
- ALU saturation.
- Texture sampling latency.
- CPU submission bottlenecks.

Do not present unsupported conclusions as measured facts.

---

## 12. Measurement Repetition and Variability

Performance counters may vary between measurement runs.

Add repeated measurement support if feasible.

### 12.1 Repeated Collection

Allow an explicitly bounded number of measurement runs.

Do not repeat measurements automatically without user or agent intent.

### 12.2 Statistical Summary

For compatible repeated measurements, calculate:

- Minimum.
- Maximum.
- Mean.
- Median.
- Standard deviation, where useful.

Keep each raw measurement identifiable.

### 12.3 Counter Compatibility

Not every counter may support meaningful averaging.

Do not average incompatible measurements.

Use the counter's value type, unit, and semantic meaning to determine appropriate aggregation.

### 12.4 Measurement Variability

Document possible sources of variation:

- GPU clock changes.
- Thermal conditions.
- Power management.
- Concurrent GPU activity.
- Driver scheduling.
- Replay overhead.
- Hardware counter collection passes.

Do not claim the repeated measurements reproduce the original game's performance conditions.

### 12.5 Practical Limits

Repeated measurements can be expensive.

Set a conservative maximum repetition count.

Do not implement indefinite benchmark loops.

---

## 13. Measurement Result Storage

Support reuse of collected performance data.

### 13.1 In-Memory Results

At minimum, maintain a bounded measurement result store.

Each entry must include:

- Measurement ID.
- Capture identity.
- Counter definitions.
- Counter results.
- Measurement status.
- Relevant collection metadata.

### 13.2 Result Lifetime

Define how long results remain available.

Distinguish:

- Live measurement jobs.
- Completed measurement snapshots.
- Results invalidated for active-capture operations.
- Exported historical results.

A completed measurement may remain useful after capture unload if it is clearly identified as historical data.

Do not label historical measurements as current capture measurements.

### 13.3 Storage Limits

Enforce limits on:

- Number of retained measurements.
- Total memory usage.
- Number of counter results.
- Retention duration, if applicable.

Avoid indefinite accumulation of large results.

### 13.4 Avoid Unnecessary Replay

Analysis of existing measurement results should not require an active ReplayController.

This allows agents to inspect summaries without repeatedly using the GPU.

---

## 14. Export and Comparison

Add structured export support where practical.

### 14.1 JSON Export

Support exporting collected measurements to JSON.

Include:

- Measurement metadata.
- Counter descriptions.
- Event identifiers.
- Counter values.
- Units.
- Available event names and hierarchy information.
- Aggregation metadata.

Use a versioned schema.

Do not serialize internal RenderDoc objects directly.

### 14.2 Output Location

Use an explicit, safe output location or an existing project-supported artifact mechanism.

Do not write arbitrary files based on unvalidated paths.

Do not overwrite existing files silently.

### 14.3 Comparison

Provide basic comparison of two compatible measurement results if the core functionality is complete.

Potential comparisons include:

- Event durations.
- Pass aggregation.
- Counter values.
- Event count differences.
- Pipeline statistics differences.

### 14.4 Cross-Capture Comparison

Cross-capture event identity is not guaranteed.

Do not match events solely by numeric event ID.

Possible matching hints include:

- Debug marker hierarchy.
- Event name.
- Event type.
- Relative location in a pass.
- Relevant shader or pipeline metadata.

Treat such matching as potentially ambiguous.

Do not automatically claim that two events are equivalent because their names match.

### 14.5 Comparison Limitations

Document differences in:

- Hardware.
- Driver.
- Replay environment.
- Counter availability.
- Capture contents.
- Measurement method.

Do not compare incompatible counters as though they represented the same metric.

---

## 15. Performance Analysis Integration

Enable coding agents to correlate measurement results with rendering state.

This is the main value of Phase 13 beyond exposing raw counters.

### 15.1 Expensive Draw Call Investigation

Example workflow:

1. Collect GPU duration counters.
2. Identify the most expensive draw calls.
3. Retrieve draw-call parameters.
4. Inspect pipeline state.
5. Identify bound shaders.
6. Retrieve shader reflection or disassembly.
7. Inspect render target formats and dimensions.
8. Retrieve pipeline statistics if available.
9. Report observations and plausible performance hypotheses.

### 15.2 Shader Cost Investigation

Useful information may include:

- Shader stage configuration.
- Available shader disassembly.
- Input and output signatures.
- Resource declarations.
- Bound textures and buffers.
- Pipeline statistics.
- Measured GPU duration.

Do not estimate exact shader execution cost from instruction count alone.

Do not claim that shader reflection identifies hardware bottlenecks.

### 15.3 Render Target Cost Investigation

Correlate expensive rendering events with:

- Render target count.
- Render target resolution.
- Render target formats.
- Multisampling.
- Depth/stencil configuration.
- Blend configuration.

These properties may suggest possible bandwidth or rasterization costs.

They do not independently prove a bandwidth bottleneck.

### 15.4 Compute Performance Investigation

Correlate compute dispatch timing with:

- Dispatch group counts.
- Compute shader information.
- Bound storage buffers.
- Bound storage textures.
- Available compute statistics.

Do not infer hardware occupancy without suitable occupancy-related measurements.

### 15.5 Evidence-Based Conclusions

Performance findings should distinguish:

**Measured facts**

Values directly supported by GPU counters.

**Derived observations**

Calculations based on compatible measurement results.

**Hypotheses**

Possible explanations based on timing, pipeline configuration, and resource information.

**Unknowns**

Potential bottlenecks that cannot be established from available data.

Avoid overstating conclusions.

---

## 16. MCP Tool Design

Keep the MCP interface compact.

Suggested capabilities:

| Tool | Responsibility |
|---|---|
| `list_gpu_counters` | Discover supported GPU counters and their definitions |
| `collect_gpu_counters` | Start explicit GPU measurement |
| `get_gpu_measurement_status` | Inspect measurement lifecycle and completion |
| `get_gpu_timings` | Retrieve event-level GPU timing results |
| `get_pipeline_statistics` | Retrieve available pipeline statistics |
| `get_performance_summary` | Rank expensive events and summarize results |
| `get_render_pass_performance` | Aggregate results by pass or marker hierarchy |

Result export and comparison can be implemented through additional tools or existing project abstractions if justified.

Do not create separate MCP tools for every counter.

### 16.1 Separation of Measurement and Analysis

Measurement tools may execute replay operations.

Analysis tools should operate on previously collected results.

Make this distinction clear in MCP tool descriptions.

### 16.2 Existing Session Resolution

Reuse existing rules for selecting the active RenderDoc GUI session.

Do not introduce a separate global profiling session.

### 16.3 Parameter Consistency

Use existing conventions for:

- Session ID.
- Capture identity.
- Event ID.
- Counter ID.
- Measurement ID.
- Result limits.
- Sorting.
- Pagination.

### 16.4 Output Size

All event lists and statistical results must be bounded.

Provide explicit limits and truncation information.

---

## 17. Shared IPC and Multi-Agent Concurrency

Preserve Phase 6 Shared IPC behavior.

### 17.1 Centralized Measurement Coordination

A measurement must execute against the appropriate RenderDoc GUI session.

Use a shared coordination mechanism to prevent conflicting replay operations.

Do not allow each MCP process to independently perform counter collection against the same replay context without coordination.

### 17.2 Measurement Exclusivity

If RenderDoc requires exclusive replay access for counter collection, enforce that requirement.

Prefer one active measurement per affected replay context.

Do not introduce a global lock that unnecessarily blocks unrelated RenderDoc GUI sessions.

### 17.3 Multiple Agents

Consider:

1. Claude Code requests GPU timing.
2. Codex requests pipeline statistics.
3. Both target the same capture.
4. The user changes the selected event.

Requirements:

- Requests remain associated with the correct capture.
- Measurement results are not mixed.
- Concurrent measurements are coordinated.
- Completed results can be shared safely.
- Ordinary analysis queries do not rerun measurement unnecessarily.

### 17.4 Request Deduplication

Identical concurrent measurement requests may optionally share an in-progress job if the counter set, capture identity, and measurement options are equivalent.

Do not deduplicate requests when doing so would violate explicit repeated-measurement intent.

### 17.5 Disconnect Handling

Handle MCP client disconnection without corrupting shared measurement state.

Define whether a running measurement continues or is cancelled safely when its requesting client disconnects.

Document the policy.

### 17.6 Locking

Avoid holding Shared IPC Service locks while waiting for replay-thread operations.

Prevent deadlocks between:

- IPC worker threads.
- Replay thread.
- GUI thread.
- Measurement lifecycle management.

---

## 18. Performance and Resource Limits

GPU profiling should not destabilize RenderDoc.

### 18.1 Bounded Measurements

Enforce limits on:

- Requested counters.
- Concurrent measurement jobs.
- Repetition count.
- Retained measurement results.
- Response size.
- Job queue size.

### 18.2 Replay Cost

Counter collection may require several replay passes.

Avoid automatically requesting every available hardware counter.

Prefer a small, relevant counter set.

### 18.3 Default Counter Set

Consider using GPU duration as the default timing measurement when supported.

Do not assume a duration counter is always available.

### 18.4 Failure Recovery

Ensure a failed profiling operation does not leave the extension or Shared IPC Service permanently blocked.

### 18.5 No Unbounded Background Work

Do not introduce continuous profiling or an indefinite GPU monitoring loop.

Measurements should be finite and explicitly requested.

---

## 19. Error Handling

Use structured errors consistent with existing MCP conventions.

Handle:

- No RenderDoc GUI connected.
- No capture loaded.
- Capture changed.
- Replay controller unavailable.
- GPU counter collection unsupported.
- Requested counter unavailable.
- Unsupported counter combination.
- Counter result missing.
- Counter collection failed.
- Measurement already running.
- Measurement cancelled.
- Measurement timeout.
- Measurement ID not found.
- Incompatible comparison results.
- Event ID not found.
- Pass aggregation unavailable.
- GUI disconnected.
- IPC failure.

Do not return zero values for failed or missing measurements.

Do not fabricate GPU counter values.

---

## 20. Testing

Implement automated and real RenderDoc tests where possible.

### 20.1 Unit Tests

Cover:

- Counter enumeration serialization.
- Counter type and unit preservation.
- Counter request validation.
- Event ID association.
- Measurement identity.
- Measurement lifecycle transitions.
- Measurement failure handling.
- Timing conversion.
- Event ranking.
- Sorting and pagination.
- Missing counter results.
- Nested marker aggregation.
- Double-count prevention.
- Derived statistics.
- Zero denominators.
- Repeated measurement statistics.
- Result caching.
- Cache invalidation.
- Export serialization.
- Comparison compatibility.
- Concurrent request handling.

### 20.2 Deterministic Timing Fixtures

Use synthetic counter results for unit testing.

Verify that event rankings and aggregations are calculated correctly.

For example:

```text
Pass A
  Draw 1: 0.4 ms
  Draw 2: 0.6 ms

Pass B
  Draw 3: 1.2 ms
  Draw 4: 0.3 ms
```

The derived leaf-event duration sums should be:

```text
Pass A: 1.0 ms
Pass B: 1.5 ms
```

These values are useful for validating aggregation logic.

They must not be presented as actual GPU measurements.

### 20.3 Integration Tests

Verify:

1. Available counters can be enumerated.
2. Counter descriptions include valid units and types.
3. Counter collection can be initiated.
4. Returned counter values are associated with the correct events.
5. GPU timing results can be retrieved.
6. Expensive events are ranked correctly.
7. Debug marker grouping works.
8. Pipeline statistics are available where supported.
9. Missing counters are handled safely.
10. Capture unload during measurement is handled.
11. Multiple MCP clients can access measurement results.
12. Concurrent measurement requests are coordinated.

### 20.4 Real RenderDoc Testing

Use representative captures from available graphics APIs.

Test:

- A capture containing several graphics draw calls.
- A capture containing compute dispatches.
- A capture with nested debug markers.
- A capture with a large event count.
- A capture where some counters are unavailable.

Compare the collected results with RenderDoc's own performance counter presentation where available.

Do not assume that two independent timing runs produce identical numeric values.

### 20.5 GUI Non-Interference Test

Before profiling, record:

- Loaded capture.
- Selected event.
- Replay event.
- Relevant GUI state.

Run GPU counter collection.

Verify the actual observed behavior.

If the GUI state changes, investigate whether this is expected and supported by the RenderDoc API.

Do not silently claim non-interference.

### 20.6 Multi-Agent Test

Use Claude Code and Codex where available.

Test:

1. Agent A starts GPU measurement.
2. Agent B queries measurement status.
3. Agent B retrieves completed results.
4. Agent A requests event ranking.
5. Agent B inspects an expensive event's pipeline state.
6. Both receive consistent capture and event identities.

Also test disconnection and capture switching during measurement.

### 20.7 Regression Tests

Ensure Phases 6–12 continue working.

In particular:

- Shared IPC Service remains stable.
- Active capture discovery remains correct.
- Event inspection remains functional.
- Shader inspection remains functional.
- Texture inspection remains functional.
- Existing MCP tool contracts remain compatible.

Do not report tests as passed unless they were executed.

---

## 21. Documentation

Update English and Japanese documentation introduced in Phase 12.

### 21.1 Documentation Structure

Suggested files:

```text
docs/
  en/
    performance.md
    examples/
      gpu-bottleneck.md
      expensive-drawcalls.md
      render-pass-performance.md
      compute-performance.md

  ja/
    performance.md
    examples/
      gpu-bottleneck.md
      expensive-drawcalls.md
      render-pass-performance.md
      compute-performance.md
```

Adapt to the existing documentation structure.

### 21.2 Required Content

Document:

- GPU counter availability.
- GPU timing measurement.
- Explicit measurement behavior.
- Measurement lifecycle.
- Pipeline statistics.
- Draw-call ranking.
- Pass-level aggregation.
- Counter units.
- Measurement variability.
- Replay overhead.
- Supported graphics APIs.
- Known hardware limitations.
- Multi-agent measurement behavior.

### 21.3 Example A — Find Expensive Draw Calls

Developer prompt:

> Analyze GPU performance in the currently loaded RenderDoc capture. Find the ten most expensive draw calls and summarize their pipeline configurations.

Expected workflow:

1. Discover supported GPU timing counters.
2. Collect timing results.
3. Rank draw calls.
4. Inspect the most expensive events.
5. Retrieve pipeline and shader information.
6. Report measured timing and possible causes.

### 21.4 Example B — Compare Rendering Passes

Developer prompt:

> Compare the GPU cost of the shadow, G-buffer, lighting, and post-processing passes in this capture.

Expected workflow:

1. Collect GPU duration measurements.
2. Identify the relevant debug marker hierarchy.
3. Aggregate measured events without double counting.
4. Report each grouping's aggregation method.
5. Identify expensive events within each pass.

Explain that event-duration sums do not necessarily equal exact pass elapsed time.

### 21.5 Example C — Analyze a Compute Dispatch

Developer prompt:

> Find the most expensive compute dispatches and inspect their shaders, dispatch dimensions, and output resource bindings.

Expected workflow:

1. Collect timing counters.
2. Rank compute dispatches.
3. Retrieve dispatch dimensions.
4. Inspect compute shaders.
5. Inspect resource bindings.
6. Report potential sources of computational cost.

### 21.6 Example D — Investigate a Slow Draw Call

Developer prompt:

> This draw call takes a long time on the GPU. Inspect its pipeline statistics, shaders, render targets, and resource bindings. Suggest likely performance bottlenecks, separating measured evidence from hypotheses.

Expected workflow:

1. Retrieve the measured GPU duration.
2. Retrieve available pipeline statistics.
3. Inspect shader configuration.
4. Inspect render target configuration.
5. Inspect resource bindings.
6. Explain what measurements support.
7. Identify what would require further profiling.

### 21.7 Documentation Language

Maintain equivalent English and Japanese documentation.

Preserve technical identifiers and command syntax.

Do not document unimplemented features as available.

---

## 22. Out of Scope

Do not implement:

- CPU profiling.
- Real-time application frame-time monitoring.
- FPS measurement from live application execution.
- GPU clock monitoring.
- GPU temperature or power telemetry.
- VRAM allocation tracking.
- Hardware occupancy estimation without supported counters.
- Cache-miss analysis without supported counters.
- Memory bandwidth saturation analysis without supported counters.
- Vendor-specific profiling integrations.
- NVIDIA Nsight automation.
- AMD Radeon GPU Profiler automation.
- Intel GPA automation.
- Shader execution tracing.
- Shader debugging.
- Pixel History.
- Geometry visualization.
- Automated shader optimization.
- Continuous profiling agents.
- Major replay architecture redesign.

Do not create a custom GPU profiler when RenderDoc already exposes suitable counter collection functionality.

---

## 23. Implementation Principles

**Use RenderDoc's existing counter APIs.**

Do not implement low-level hardware counter collection independently.

**Separate measurement from analysis.**

Expensive GPU measurement should not run for every summary request.

**Make profiling explicit.**

Do not silently execute GPU replay during ordinary information retrieval.

**Preserve counter semantics.**

Use accurate types, units, and descriptions.

**Do not fabricate unavailable measurements.**

Missing counters are not zero-valued counters.

**Preserve event and capture identity.**

Never mix measurements from different captures without explicit comparison logic.

**Avoid double counting.**

Nested render pass and debug marker aggregation must be mathematically well-defined.

**Respect replay ownership.**

Use supported RenderDoc execution contexts and synchronization.

**Preserve multi-agent compatibility.**

Multiple agents must not perform conflicting replay operations.

**Keep outputs bounded.**

Large captures must remain manageable for MCP clients.

**Distinguish facts from hypotheses.**

Performance measurements should support, not replace, engineering judgment.

---

## 24. Deliverables

At completion, provide the following.

### A. Implementation Summary

- Modified components.
- New or extended MCP tools.
- GPU counter discovery implementation.
- Measurement lifecycle implementation.
- Timing analysis.
- Pipeline statistics.
- Render pass aggregation.
- Result storage and export.

### B. RenderDoc API Findings

- Available counter APIs.
- Supported counters.
- Counter units and types.
- Replay-thread requirements.
- Measurement side effects.
- Hardware and graphics API limitations.

### C. Performance Analysis

- Measurement overhead observations.
- Result retrieval latency.
- Memory consumption.
- Maximum supported result sizes.
- Multi-agent concurrency behavior.

### D. Test Report

- Unit tests executed.
- Integration tests executed.
- Manual GUI tests executed.
- Graphics APIs tested.
- Hardware used for validation.
- Known failures.
- Unverified scenarios.

### E. Documentation

- English performance documentation.
- Japanese performance documentation.
- Practical debugging examples.
- MCP tool reference updates.
- Known limitations.

---

## 25. Acceptance Criteria

Phase 13 is complete when:

- [ ] RenderEyeMCP can enumerate supported GPU performance counters.
- [ ] Counter descriptions include correct units and value types.
- [ ] Unsupported counters are handled explicitly.
- [ ] GPU counter collection is an explicit operation.
- [ ] Measurement execution respects RenderDoc replay-thread requirements.
- [ ] Measurement jobs have identifiable lifecycle states.
- [ ] Measurement failures and disconnections do not leave the service blocked.
- [ ] GPU timing values can be retrieved for supported events.
- [ ] Counter values are associated with the correct event IDs.
- [ ] Expensive draw calls and compute dispatches can be ranked.
- [ ] Timing summaries can be generated without repeating GPU measurement.
- [ ] Debug marker and render pass grouping is supported.
- [ ] Nested aggregation avoids double counting.
- [ ] Pass aggregation methods are clearly identified.
- [ ] Pipeline statistics can be retrieved where supported.
- [ ] Missing measurements are not silently treated as zero.
- [ ] Counter semantics are preserved in all responses.
- [ ] Measurement results preserve capture and event identity.
- [ ] Measurement result storage is bounded.
- [ ] Multiple MCP clients can safely access measurement results.
- [ ] Conflicting replay measurements are coordinated.
- [ ] GUI non-interference is validated or limitations are documented.
- [ ] Performance summaries distinguish measurements from derived results and hypotheses.
- [ ] Existing Phase 6–12 functionality remains operational.
- [ ] Automated tests cover counter handling, ranking, aggregation, and lifecycle management.
- [ ] Real RenderDoc captures are used to validate supported measurement paths.
- [ ] English and Japanese documentation are updated.
- [ ] Practical Coding Agent performance-debugging examples are provided.

If a criterion depends on unsupported hardware counters or RenderDoc APIs, document the limitation and report the corresponding capability as unavailable or partially implemented.

Do not claim full GPU profiling support without validating the actual measurement capabilities.

---

## Final Goal

After Phase 13, developers should be able to ask an AI coding agent:

**"Analyze the GPU performance of the capture currently open in RenderDoc. Identify the most expensive rendering passes and draw calls, inspect their shaders and pipeline states, and explain possible bottlenecks."**

The agent should be able to:

1. Discover available GPU performance counters.
2. Start an explicit GPU measurement.
3. Retrieve the measurement results.
4. Identify expensive events.
5. Aggregate performance data by rendering pass.
6. Inspect relevant pipeline state and shader information.
7. Correlate measured costs with rendering configuration.
8. Produce an evidence-based performance analysis.

The workflow must use the existing RenderDoc GUI capture and the established RenderEyeMCP architecture.

**Phase 13 should transform RenderEyeMCP from a rendering-state inspection interface into a useful foundation for AI-assisted GPU performance investigation, without attempting to replace specialized hardware profilers.**
