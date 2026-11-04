package server

import (
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/ipc"
)

// call runs a service tool directly and returns its result map.
func callTool(t *testing.T, r *Router, bridgeCh chan []byte, name string, args map[string]interface{}) map[string]interface{} {
	t.Helper()
	r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "rq-" + name, ToolName: name, Arguments: args, Type: "tool_call"}, "bridge-1")
	res := receiveToolResult(t, bridgeCh, 5*time.Second)
	m, _ := res.Result.(map[string]interface{})
	if m == nil {
		t.Fatalf("%s: non-object result %v (error %q)", name, res.Result, res.Error)
	}
	return m
}

func counterExt(t *testing.T, r *Router, values [][]float64) (*fakeExtension, *int) {
	t.Helper()
	extCh := addExt(r, "ext-1", "inst-1", true)
	path := "/captures/a.rdc"
	r.extensions["ext-1"].capPath = &path
	fake := &fakeExtension{}
	var mu sync.Mutex
	run := 0
	fake.serve(t, r, extCh, func(req ipc.InspectCaptureRequestMessage) map[string]interface{} {
		switch req.Operation {
		case "fetch_gpu_counters":
			mu.Lock()
			v := values[run%len(values)]
			run++
			mu.Unlock()
			results := []interface{}{}
			for i, x := range v {
				results = append(results, map[string]interface{}{"event_id": float64(10 + i*10), "counter_id": 1.0, "value": x})
				results = append(results, map[string]interface{}{"event_id": float64(10 + i*10), "counter_id": 7.0, "value": float64(100 * (i + 1))})
			}
			return map[string]interface{}{
				"_capture_path": path,
				"results":       results,
				"counter_descriptions": []interface{}{
					map[string]interface{}{"counter_id": 1.0, "name": "GPU Duration", "unit": "Seconds", "result_type": "Double"},
					map[string]interface{}{"counter_id": 7.0, "name": "Vertex Shader Invocations", "unit": "Absolute", "result_type": "UInt"},
				},
				"counters_fetched": []interface{}{1.0, 7.0},
				"counters_invalid": []interface{}{99.0},
			}
		case "event_tree":
			return map[string]interface{}{"_capture_path": path, "events": []interface{}{
				map[string]interface{}{"event_id": 1.0, "name": "Shadow", "action_type": "marker_begin", "children": []interface{}{
					map[string]interface{}{"event_id": 10.0, "name": "Draw A", "action_type": "drawcall", "children": []interface{}{}},
					map[string]interface{}{"event_id": 20.0, "name": "Draw B", "action_type": "drawcall", "children": []interface{}{}},
				}},
				map[string]interface{}{"event_id": 2.0, "name": "Lighting", "action_type": "marker_begin", "children": []interface{}{
					map[string]interface{}{"event_id": 30.0, "name": "Dispatch", "action_type": "dispatch", "children": []interface{}{}},
					map[string]interface{}{"event_id": 40.0, "name": "Unmeasured", "action_type": "drawcall", "children": []interface{}{}},
				}},
			}}
		}
		return map[string]interface{}{"error": "unsupported_operation", "operation": req.Operation}
	})
	return fake, &run
}

func TestCollectGPUCounters_repeatsAveragedAndAnalysed(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")
	_, runs := counterExt(t, r, [][]float64{{0.002, 0.004, 0.010}, {0.004, 0.006, 0.020}})

	res := callTool(t, r, bridgeCh, "collect_gpu_counters", map[string]interface{}{"counter_ids": []interface{}{1.0, 7.0, 99.0}, "repeats": 2.0})
	if res["status"] != "completed" || res["repeats"] != 2.0 {
		t.Fatalf("collect failed: %v", res)
	}
	if *runs != 2 {
		t.Errorf("expected 2 FetchCounters runs, got %d", *runs)
	}
	if res["capture_path"] != "/captures/a.rdc" || res["result_count"] != 6.0 {
		t.Errorf("unexpected collect summary: %v", res)
	}
	if inv, _ := res["counters_invalid"].([]interface{}); len(inv) != 1 || inv[0] != 99.0 {
		t.Errorf("counters_invalid not propagated: %v", res["counters_invalid"])
	}
	id, _ := res["measurement_id"].(string)
	if len(id) != 8 {
		t.Fatalf("measurement_id %q", id)
	}

	status := callTool(t, r, bridgeCh, "get_gpu_measurement_status", map[string]interface{}{"measurement_id": id})
	if status["status"] != "completed" || status["result_count"] != 6.0 {
		t.Errorf("status: %v", status)
	}

	timings := callTool(t, r, bridgeCh, "get_gpu_timings", map[string]interface{}{"measurement_id": id})
	if timings["counter_id"] != 1.0 || timings["counter_name"] != "GPU Duration" || timings["total"] != 3.0 {
		t.Fatalf("timings: %v", timings)
	}
	evs, _ := timings["events"].([]interface{})
	first, _ := evs[0].(map[string]interface{})
	if first["event_id"] != 30.0 || first["value"] != 0.015 { // (0.010+0.020)/2, value_desc
		t.Errorf("averaged/sorted timings wrong: %v", evs)
	}

	summary := callTool(t, r, bridgeCh, "get_performance_summary", map[string]interface{}{"measurement_id": id, "top_n": 2.0})
	if summary["top_n"] != 2.0 || summary["total_events_measured"] != 3.0 {
		t.Errorf("summary: %v", summary)
	}

	stats := callTool(t, r, bridgeCh, "get_pipeline_statistics", map[string]interface{}{"measurement_id": id, "event_id": 20.0})
	if stats["total"] != 1.0 {
		t.Fatalf("pipeline stats: %v", stats)
	}
	stat := stats["statistics"].([]interface{})[0].(map[string]interface{})
	if stat["counter_id"] != 7.0 || stat["value"] != 200.0 || stat["counter_name"] != "Vertex Shader Invocations" {
		t.Errorf("integral averaging or naming wrong: %v", stat)
	}

	passes := callTool(t, r, bridgeCh, "get_render_pass_performance", map[string]interface{}{"measurement_id": id})
	if passes["pass_count"] != 2.0 {
		t.Fatalf("render passes: %v", passes)
	}
	top := passes["passes"].([]interface{})[0].(map[string]interface{})
	if top["name"] != "Lighting" || top["event_count"] != 1.0 || top["unmeasured_event_count"] != 1.0 {
		t.Errorf("pass aggregation wrong: %v", top)
	}
}

func TestRenderPassPerformance_listEventsFallback(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")
	extCh := addExt(r, "ext-1", "inst-1", true)
	fake := &fakeExtension{}
	fake.serve(t, r, extCh, func(req ipc.InspectCaptureRequestMessage) map[string]interface{} {
		switch req.Operation {
		case "event_tree": // an extension that predates event_tree
			return map[string]interface{}{"error": "unsupported_operation", "operation": "event_tree"}
		case "list_events":
			return map[string]interface{}{"_capture_path": "/c.rdc", "has_more": false, "events": []interface{}{
				map[string]interface{}{"event_id": 1.0, "name": "Pass", "action_type": "marker_begin", "depth": 0.0},
				map[string]interface{}{"event_id": 2.0, "name": "Draw", "action_type": "drawcall", "depth": 1.0},
			}}
		}
		return nil
	})
	r.measure.put(&measurementRecord{
		id: "m1", status: "completed", capturePath: "/c.rdc", instanceID: "inst-1",
		counterIDs: []int{1}, results: []counterResult{{EventID: 2, CounterID: 1, Value: 0.5}}, createdAt: time.Now(),
	})
	res := callTool(t, r, bridgeCh, "get_render_pass_performance", map[string]interface{}{"measurement_id": "m1"})
	p := res["passes"].([]interface{})
	if len(p) != 1 || p[0].(map[string]interface{})["aggregated_duration"] != 0.5 {
		t.Errorf("fallback aggregation failed: %v", res)
	}
}

func TestCollectGPUCounters_validationAndErrors(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")
	if res := callTool(t, r, bridgeCh, "collect_gpu_counters", map[string]interface{}{}); res["error"] != "missing_counter_ids" {
		t.Errorf("expected missing_counter_ids, got %v", res)
	}
	if res := callTool(t, r, bridgeCh, "collect_gpu_counters", map[string]interface{}{"counter_ids": []interface{}{1.0}}); res["status"] != "no_renderdoc_connected" {
		t.Errorf("expected no_renderdoc_connected, got %v", res)
	}
	if res := callTool(t, r, bridgeCh, "get_gpu_timings", map[string]interface{}{"measurement_id": "nope"}); res["error"] != "measurement_not_found" {
		t.Errorf("expected measurement_not_found, got %v", res)
	}
}

// TestCollectGPUCounters_timeoutAndExtensionError checks that a hung
// FetchCounters returns a structured timeout (no measurement stored) and that
// an extension error is passed through unchanged.
func TestCollectGPUCounters_timeoutAndExtensionError(t *testing.T) {
	r := newTestRouter()
	r.timeoutOverride = 50 * time.Millisecond
	bridgeCh := addBridge(r, "bridge-1")
	extCh := addExt(r, "ext-1", "inst-1", true)
	go func() {
		for range extCh { // never answers
		}
	}()
	res := callTool(t, r, bridgeCh, "collect_gpu_counters", map[string]interface{}{"counter_ids": []interface{}{1.0}})
	if res["error"] != failTimeout {
		t.Errorf("expected timeout, got %v", res)
	}
	if n := len(r.measure.records); n != 0 {
		t.Errorf("timed-out collection must not store a measurement (have %d)", n)
	}

	r2 := newTestRouter()
	bridge2 := addBridge(r2, "bridge-1")
	ext2 := addExt(r2, "ext-1", "inst-1", true)
	(&fakeExtension{}).serve(t, r2, ext2, func(ipc.InspectCaptureRequestMessage) map[string]interface{} {
		return map[string]interface{}{"error": "no_valid_counters", "invalid_counter_ids": []interface{}{5.0}}
	})
	if res := callTool(t, r2, bridge2, "collect_gpu_counters", map[string]interface{}{"counter_ids": []interface{}{5.0}}); res["error"] != "no_valid_counters" {
		t.Errorf("extension error not propagated: %v", res)
	}
}

func TestCaptureChangeInvalidatesStoredResults(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", false)
	a, b := "/a.rdc", "/b.rdc"
	r.UpdateGuiState("ext-1", 1, true, &a, "loaded")
	r.measure.put(&measurementRecord{id: "m1", status: "completed", capturePath: a, instanceID: "inst-1", createdAt: time.Now()})
	r.measure.put(&measurementRecord{id: "m2", status: "completed", capturePath: a, instanceID: "other", createdAt: time.Now()})
	r.debug.put(&debugRecord{id: "d1", status: "ready", capturePath: a, instanceID: "inst-1", createdAt: time.Now()})

	r.UpdateGuiState("ext-1", 2, true, &b, "loaded")

	if m, _ := r.measure.get("m1"); m.status != "invalidated" {
		t.Errorf("m1 should be invalidated, got %q", m.status)
	}
	if m, _ := r.measure.get("m2"); m.status != "completed" {
		t.Errorf("m2 belongs to another instance and must stay completed, got %q", m.status)
	}
	if d, _ := r.debug.get("d1"); d.status != "invalidated" {
		t.Errorf("d1 should be invalidated, got %q", d.status)
	}
	bridgeCh := addBridge(r, "bridge-1")
	if res := callTool(t, r, bridgeCh, "get_shader_debug_trace", map[string]interface{}{"debug_id": "d1"}); res["error"] != "debug_not_ready" {
		t.Errorf("invalidated trace must not be served: %v", res)
	}
}

func TestShaderDebug_storeTraceAndVariables(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")
	extCh := addExt(r, "ext-1", "inst-1", true)
	fake := &fakeExtension{}
	var gotParams map[string]interface{}
	var mu sync.Mutex
	fake.serve(t, r, extCh, func(req ipc.InspectCaptureRequestMessage) map[string]interface{} {
		mu.Lock()
		gotParams = req.Params
		mu.Unlock()
		return map[string]interface{}{
			"_capture_path": "/a.rdc", "stage": "pixel", "event_id": 42.0, "step_count": 3.0, "truncated": false,
			"initial_vars": map[string]interface{}{"uv": map[string]interface{}{"name": "uv", "value": 0.0}},
			"steps": []interface{}{
				map[string]interface{}{"changes": []interface{}{map[string]interface{}{"after": map[string]interface{}{"name": "r0", "value": 1.0}}}},
				map[string]interface{}{"changes": []interface{}{map[string]interface{}{"after": map[string]interface{}{"name": "r0", "value": 2.0}}}},
				map[string]interface{}{"changes": []interface{}{map[string]interface{}{"after": map[string]interface{}{"name": "r1", "value": 9.0}}}},
			},
		}
	})

	res := callTool(t, r, bridgeCh, "debug_pixel_shader", map[string]interface{}{"x": 3.0, "y": 4.0, "instance_id": "inst-1"})
	id, _ := res["debug_id"].(string)
	if len(id) != 12 || res["step_count"] != 3.0 || res["event_id"] != 42.0 {
		t.Fatalf("debug_pixel_shader: %v", res)
	}
	if fake.last() != "debug_pixel" {
		t.Errorf("expected debug_pixel operation, got %q", fake.last())
	}
	mu.Lock()
	if gotParams["x"] != 3.0 || gotParams["primitive"] != -1.0 || gotParams["instance_id"] != nil {
		t.Errorf("unexpected params forwarded: %v", gotParams)
	}
	mu.Unlock()

	trace := callTool(t, r, bridgeCh, "get_shader_debug_trace", map[string]interface{}{"debug_id": id, "first_step": 1.0, "count": 1.0})
	if trace["returned_steps"] != 1.0 || trace["total_steps"] != 3.0 || trace["has_more"] != true {
		t.Errorf("trace paging: %v", trace)
	}
	vars := callTool(t, r, bridgeCh, "get_shader_debug_variables", map[string]interface{}{"debug_id": id, "step": 1.0})
	v := vars["variables"].(map[string]interface{})
	if v["r0"].(map[string]interface{})["value"] != 2.0 || v["uv"] == nil || v["r1"] != nil {
		t.Errorf("variable reconstruction wrong: %v", v)
	}
	filtered := callTool(t, r, bridgeCh, "get_shader_debug_variables", map[string]interface{}{"debug_id": id, "step": 9.0, "variable_names": []interface{}{"r1"}})
	if fv := filtered["variables"].(map[string]interface{}); len(fv) != 1 || fv["r1"] == nil || filtered["step"] != 2.0 {
		t.Errorf("filter/clamp wrong: %v", filtered)
	}
	st := callTool(t, r, bridgeCh, "get_shader_debug_status", map[string]interface{}{"debug_id": id})
	if st["status"] != "ready" || st["x"] != 3.0 {
		t.Errorf("status: %v", st)
	}
	all := callTool(t, r, bridgeCh, "get_shader_debug_status", map[string]interface{}{})
	if all["count"] != 1.0 {
		t.Errorf("list: %v", all)
	}
}

func TestStoresAreBounded(t *testing.T) {
	ms := newMeasurementStore(2)
	base := time.Now()
	for i, id := range []string{"a", "b", "c"} {
		ms.put(&measurementRecord{id: id, createdAt: base.Add(time.Duration(i) * time.Second)})
	}
	if _, ok := ms.get("a"); ok {
		t.Error("oldest measurement should be evicted")
	}
	ds := newDebugStore(1)
	ds.put(&debugRecord{id: "x", createdAt: base})
	ds.put(&debugRecord{id: "y", createdAt: base.Add(time.Second)})
	if ids := ds.ids(); len(ids) != 1 || ids[0] != "y" {
		t.Errorf("debug store eviction wrong: %v", ids)
	}
}

// TestCollectGPUCounters_bridgeDisconnectStopsRepeats verifies cancellation:
// once the bridge disconnects no further FetchCounters runs are issued.
func TestCollectGPUCounters_bridgeDisconnectStopsRepeats(t *testing.T) {
	r := newTestRouter()
	addBridge(r, "bridge-1")
	extCh := addExt(r, "ext-1", "inst-1", true)
	done := make(chan struct{})
	go func() {
		r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "rq", ToolName: "collect_gpu_counters",
			Arguments: map[string]interface{}{"counter_ids": []interface{}{1.0}, "repeats": 5.0}}, "bridge-1")
		close(done)
	}()
	receiveInspectCapture(t, extCh, time.Second) // first run in flight
	r.DisconnectBridge("bridge-1")
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("collect_gpu_counters did not stop after bridge disconnect")
	}
	select {
	case extra := <-extCh:
		t.Errorf("no further runs expected after cancellation, got %s", extra)
	default:
	}
}

// TestCancelToolCall_stopsCollection verifies the tool_cancel path: a client
// cancel stops a multi-run collection and no tool_result is sent.
func TestCancelToolCall_stopsCollection(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")
	extCh := addExt(r, "ext-1", "inst-1", true)
	done := make(chan struct{})
	go func() {
		r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "rq-cancel", ToolName: "collect_gpu_counters",
			Arguments: map[string]interface{}{"counter_ids": []interface{}{1.0}, "repeats": 3.0}}, "bridge-1")
		close(done)
	}()
	receiveInspectCapture(t, extCh, time.Second)
	if r.CancelToolCall("bridge-1", "other-request") {
		t.Error("cancelling an unknown request must report false")
	}
	if !r.CancelToolCall("bridge-1", "rq-cancel") {
		t.Fatal("expected the in-flight call to be found")
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("cancelled call did not return")
	}
	select {
	case extra := <-extCh:
		t.Errorf("no further FetchCounters run expected, got %s", extra)
	case msg := <-bridgeCh:
		t.Errorf("no tool_result expected after cancel, got %s", msg)
	case <-time.After(50 * time.Millisecond):
	}
	if n := pendingCount(r); n != 0 {
		t.Errorf("pending requests leaked: %d", n)
	}
}
