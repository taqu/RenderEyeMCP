[English](performance.md) | [日本語](../ja/performance.md)

# GPU Performance Analysis

## Introduction

RenderEyeMCP exposes GPU performance counters through RenderDoc's replay infrastructure.
Analysis is **replay-based, not live**: the GPU re-executes the captured frame under
instrumentation, and counter values are recorded per draw call or dispatch. No live
application is involved after the capture is taken.

Because the GPU must replay the entire frame (or a portion of it) for every collection
run, measurement is an explicit, time-consuming operation. The seven Phase 13 tools are
designed around a **collect-once, analyze-many** pattern: you pay the replay cost once
and then query the stored results as many times as needed without touching the GPU again.

---

## Prerequisites

- RenderDoc is running with the RenderEyeMCP extension enabled.
- A capture (`.rdc` file) is open in RenderDoc. The extension cannot analyze a capture
  that is not loaded in the GUI.
- Verify readiness with `get_current_capture` before calling any performance tool.

---

## Step 1 — Discover available counters

Not every counter is available on every GPU, driver, or graphics API. Counter
availability is determined at runtime by RenderDoc querying the driver; it is never
hardcoded by the server.

```json
{ "tool": "list_gpu_counters" }
```

The response lists all counters the current GPU/driver combination exposes. Each entry
includes:

| Field | Meaning |
|---|---|
| `counter_id` | Opaque integer used in later calls |
| `name` | Human-readable name (e.g. `"GPU Duration"`) |
| `description` | What the counter measures |
| `unit` | `seconds`, `percentage`, `bytes`, `cycles`, … |
| `category` | Broad group: `timing`, `pipeline`, `memory`, … |

Counters in the `timing` category (unit `seconds` or `nanoseconds`) are the most
commonly useful starting point. Pipeline-statistics counters (vertex invocations, pixel
shader invocations, etc.) fall under the `pipeline` category.

If the list is empty the GPU or driver does not expose counters through the RenderDoc
API for the active capture's graphics API. This is a hardware/driver constraint, not a
server bug.

---

## Step 2 — Collect counter values

Collecting counters replays the frame on the GPU. This is an **explicit** operation; the
server never initiates a measurement on its own.

```json
{
  "tool": "collect_gpu_counters",
  "counter_ids": [1, 2, 5],
  "repeats": 3
}
```

| Parameter | Default | Notes |
|---|---|---|
| `counter_ids` | — | List of `counter_id` values from `list_gpu_counters`. Pass only the counters you need; requesting unused counters wastes replay time. |
| `repeats` | `1` | Run collection this many times (1–5) and average the results. Useful when individual measurements are noisy (thermal throttling, driver scheduler jitter). |

The tool returns a `measurement_id` immediately. For small captures the collection
finishes before the response arrives; for large captures the operation may still be
running. Use `get_gpu_measurement_status` to check.

The `measurement_id` is a stable string for the lifetime of the server process. It can
be shared between agents or stored in context for later analysis.

---

## Step 3 — Check measurement status

```json
{
  "tool": "get_gpu_measurement_status",
  "measurement_id": "meas_abc123"
}
```

Lifecycle states:

| State | Meaning |
|---|---|
| `pending` | Collection is queued but not started |
| `running` | GPU replay is in progress |
| `ready` | Results are available for analysis |
| `error` | Collection failed; `error_message` explains why |

Do not call analysis tools until status is `ready`.

---

## Step 4 — Analyze results

All analysis tools accept `measurement_id` and operate on the stored result set without
re-running the GPU.

### get_gpu_timings

Returns per-event timing values from the measurement.

```json
{
  "tool": "get_gpu_timings",
  "measurement_id": "meas_abc123",
  "sort_by": "duration_desc",
  "page": 0,
  "page_size": 50
}
```

Each result row contains `event_id`, `event_name`, `duration_seconds`, and any other
counters that were collected. Events for which the GPU did not return a value are
**absent** from the result set — they are not reported as zero.

Sorting options: `duration_desc` (default), `duration_asc`, `event_id_asc`.

### get_performance_summary

Ranks the top-N most expensive events by GPU duration.

```json
{
  "tool": "get_performance_summary",
  "measurement_id": "meas_abc123",
  "top_n": 10
}
```

This is the fastest way to identify hotspots. The response includes each event's
absolute duration and its percentage of the total measured GPU time.

### get_render_pass_performance

Aggregates results by debug marker hierarchy (e.g. `BeginEvent`/`EndEvent` groups).

```json
{
  "tool": "get_render_pass_performance",
  "measurement_id": "meas_abc123"
}
```

`aggregated_duration` for a pass is the **sum of leaf event durations** within that
group, not the GPU wall-clock elapsed time for the pass. The distinction matters when
events overlap or when some events inside the group were not measured (missing counters
are absent, not zero, so the aggregate may undercount).

Use this tool to compare the relative GPU cost of named render passes (shadow, G-buffer,
lighting, post-processing, etc.) at a glance.

### get_pipeline_statistics

Filters the result set to pipeline-statistics counters: vertex invocations, primitive
assembly, rasterized primitives, pixel shader invocations, compute thread invocations,
and similar hardware counters.

```json
{
  "tool": "get_pipeline_statistics",
  "measurement_id": "meas_abc123",
  "event_id": 1042
}
```

Omit `event_id` to get pipeline statistics for every measured event. Provide `event_id`
to focus on a single draw call or dispatch.

---

## Pagination and sorting

`get_gpu_timings` supports pagination for captures with thousands of events:

- `page` — zero-based page index (default `0`)
- `page_size` — results per page (default `50`, max `500`)
- `sort_by` — `duration_desc`, `duration_asc`, `event_id_asc`

`get_performance_summary` is already pre-sorted; no pagination is needed.

---

## Measurement variability and repeats

GPU timing measurements can vary between runs due to:

- Thermal throttling (the GPU clocks down after sustained load)
- Driver scheduler jitter on Windows
- Background GPU work from the OS compositor

The `repeats` parameter (1–5) runs the full collection multiple times and returns
averaged counter values. Use `repeats: 3` or higher when you see large variance between
consecutive measurements or when working with a laptop GPU prone to throttling.

Averaged measurements reduce noise but multiply collection time linearly.

---

## What the tools cannot tell you

| Question | Why not answerable |
|---|---|
| CPU time for a draw call | Replay measurements are GPU-only |
| Live frame time (ms/frame) | Analysis runs on a static capture, not a live app |
| Thermal or power consumption | RenderDoc does not expose power counters |
| Memory allocation patterns over time | Counter collection is per-event, not per-allocation |
| GPU utilization percentage across a session | Only the captured frame is replayed |

If you need CPU/GPU overlap or live frame time, use a separate profiling tool (e.g.
GPU vendor profiler, RenderDoc's own timeline view) alongside MCP analysis.

---

## Multi-agent usage

Measurements are stored server-side indexed by `measurement_id`. Multiple agents (or
multiple turns of the same agent) can query the same measurement concurrently without
re-running the GPU. Pass the `measurement_id` string in your context or conversation
thread to share results.

---

## Known limitations

- **Counter availability varies**: a counter present on one machine may be absent on
  another due to GPU model, driver version, or graphics API differences. Always call
  `list_gpu_counters` at the start of a session.
- **`aggregated_duration` is not wall-clock pass time**: it is the sum of leaf event
  durations. Overlapping events or incomplete coverage can make this figure differ from
  what a timeline profiler would show.
- **Missing counter values are absent, not zero**: if a counter was not returned for an
  event, that event does not appear for that counter. Do not interpret absence as "zero
  cost."
- **Collection time scales with capture complexity**: a frame with 10 000 events and
  heavy shaders may take tens of seconds to replay.

---

## Related tools

`list_gpu_counters`, `collect_gpu_counters`, `get_gpu_measurement_status`,
`get_gpu_timings`, `get_performance_summary`, `get_render_pass_performance`,
`get_pipeline_statistics` — see the [tool reference](tools.md#gpu-performance-analysis).
