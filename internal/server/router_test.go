package server

import (
	"context"
	"encoding/json"
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/ipc"
)

// newTestRouter returns a Router with a fake auth that accepts any token and
// no registry/session subsystems.
func newTestRouter() *Router {
	return NewRouter("test-service", &Auth{token: "test-token"})
}

// addExt registers a mock extension in the router and returns its send channel.
func addExt(r *Router, connID, instanceID string, capLoaded bool) chan []byte {
	ch := make(chan []byte, sendQueueSize)
	r.mu.Lock()
	r.extensions[connID] = &extState{
		connID:     connID,
		instanceID: instanceID,
		connected:  true,
		capLoaded:  capLoaded,
		send:       ch,
	}
	r.mu.Unlock()
	return ch
}

// addBridge registers a mock bridge in the router and returns its send channel.
func addBridge(r *Router, connID string) chan []byte {
	ch := make(chan []byte, sendQueueSize)
	r.mu.Lock()
	r.bridges[connID] = &bridgeState{connID: connID, send: ch}
	r.mu.Unlock()
	return ch
}

// receiveToolResult reads one message from ch and asserts it is a tool_result.
func receiveToolResult(t *testing.T, ch chan []byte, timeout time.Duration) ipc.ToolResultMessage {
	t.Helper()
	select {
	case data := <-ch:
		var msg ipc.ToolResultMessage
		if err := json.Unmarshal(trimNewline(data), &msg); err != nil {
			t.Fatalf("unmarshal tool_result: %v (data=%q)", err, data)
		}
		if msg.Type != "tool_result" {
			t.Fatalf("expected tool_result, got type=%q", msg.Type)
		}
		return msg
	case <-time.After(timeout):
		t.Fatalf("timeout waiting for tool_result")
		return ipc.ToolResultMessage{}
	}
}

// receiveInspectCapture reads one message from ch and asserts it is inspect_capture.
func receiveInspectCapture(t *testing.T, ch chan []byte, timeout time.Duration) ipc.InspectCaptureRequestMessage {
	t.Helper()
	select {
	case data := <-ch:
		var msg ipc.InspectCaptureRequestMessage
		if err := json.Unmarshal(trimNewline(data), &msg); err != nil {
			t.Fatalf("unmarshal inspect_capture: %v (data=%q)", err, data)
		}
		if msg.Type != "inspect_capture" {
			t.Fatalf("expected inspect_capture, got type=%q", msg.Type)
		}
		return msg
	case <-time.After(timeout):
		t.Fatalf("timeout waiting for inspect_capture")
		return ipc.InspectCaptureRequestMessage{}
	}
}

func trimNewline(b []byte) []byte {
	if len(b) > 0 && b[len(b)-1] == '\n' {
		return b[:len(b)-1]
	}
	return b
}

// startForwardedCall launches a forwarded tool call and returns once the
// extension has received the inspect_capture request.
func startForwardedCall(t *testing.T, r *Router, extCh chan []byte, bridgeConnID, reqID, tool string) ipc.InspectCaptureRequestMessage {
	t.Helper()
	go r.RouteToolCall(&ipc.ToolCallMessage{RequestID: reqID, ToolName: tool, Arguments: map[string]interface{}{}, Type: "tool_call"}, bridgeConnID)
	return receiveInspectCapture(t, extCh, time.Second)
}

func pendingCount(r *Router) int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.pending)
}

func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for !cond() {
		if time.Now().After(deadline) {
			t.Fatalf("timed out waiting for %s", what)
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// ---------------------------------------------------------------------------

func TestRouteToolCall_internalTool(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")

	msg := &ipc.ToolCallMessage{
		RequestID:          "req-1",
		BridgeConnectionID: "bridge-1",
		ToolName:           "server_status",
		Arguments:          map[string]interface{}{},
		Type:               "tool_call",
	}
	r.RouteToolCall(msg, "bridge-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	if result.RequestID != "req-1" {
		t.Errorf("got request_id %q want %q", result.RequestID, "req-1")
	}
	if result.Error != "" {
		t.Errorf("unexpected error: %s", result.Error)
	}
}

func TestRouteToolCall_inspectionForwarded(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	bridgeCh := addBridge(r, "bridge-1")

	inspectMsg := startForwardedCall(t, r, extCh, "bridge-1", "req-2", "get_current_capture_info")
	if inspectMsg.Operation != "capture_info" {
		t.Errorf("operation got %q want %q", inspectMsg.Operation, "capture_info")
	}
	if inspectMsg.RequestID != "req-2" {
		t.Errorf("request_id propagated incorrectly")
	}

	// Simulate extension response.
	r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{
		RequestID: "req-2",
		Operation: "capture_info",
		Result:    map[string]interface{}{"path": "/cap.rdc"},
		Type:      "inspect_capture_result",
	})

	toolResult := receiveToolResult(t, bridgeCh, time.Second)
	if toolResult.RequestID != "req-2" {
		t.Errorf("request_id mismatch on tool_result")
	}
	if toolResult.ToolName != "get_current_capture_info" {
		t.Errorf("tool_name mismatch: got %q", toolResult.ToolName)
	}
	if toolResult.Error != "" {
		t.Errorf("unexpected error: %s", toolResult.Error)
	}
}

func TestRouteToolCall_instanceIDStripped(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-A", true)
	addBridge(r, "bridge-1")

	go r.RouteToolCall(&ipc.ToolCallMessage{
		RequestID: "req-3",
		ToolName:  "get_pipeline_state",
		Arguments: map[string]interface{}{
			"instance_id": "inst-A",
			"event_id":    42,
			"section":     "summary",
		},
		Type: "tool_call",
	}, "bridge-1")

	inspectMsg := receiveInspectCapture(t, extCh, time.Second)
	if _, hasID := inspectMsg.Params["instance_id"]; hasID {
		t.Error("instance_id should be stripped from inspect_capture params")
	}
	if v := inspectMsg.Params["event_id"]; v == nil {
		t.Error("event_id should be in inspect_capture params")
	}
}

func TestRouteToolCall_noExtension(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")

	r.RouteToolCall(&ipc.ToolCallMessage{
		RequestID: "req-4",
		ToolName:  "list_capture_events",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	}, "bridge-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	resultMap, _ := result.Result.(map[string]interface{})
	if resultMap == nil {
		t.Fatal("expected result map")
	}
	if status, _ := resultMap["status"].(string); status != "no_renderdoc_connected" {
		t.Errorf("expected no_renderdoc_connected status, got %q", status)
	}
}

func TestRouteToolCall_unknownTool(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")

	r.RouteToolCall(&ipc.ToolCallMessage{
		RequestID: "req-5",
		ToolName:  "no_such_tool",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	}, "bridge-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	resultMap, _ := result.Result.(map[string]interface{})
	if resultMap == nil {
		t.Fatal("expected result map")
	}
	if resultMap["error"] != errUnknownTool {
		t.Errorf("expected error=%s, got %v", errUnknownTool, resultMap["error"])
	}
}

func TestDisconnectExtension_errorsPendingCalls(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	bridgeCh := addBridge(r, "bridge-1")

	req := startForwardedCall(t, r, extCh, "bridge-1", "req-99", "list_resources")
	r.DisconnectExtension("ext-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	if result.Error != failDisconnected {
		t.Errorf("expected extension_disconnected error, got %q", result.Error)
	}
	if result.RequestID != "req-99" || req.RequestID != "req-99" {
		t.Errorf("request_id mismatch: tool_result %q, inspect %q", result.RequestID, req.RequestID)
	}
	if n := pendingCount(r); n != 0 {
		t.Errorf("pending map should be empty after disconnect, has %d entries", n)
	}
}

func TestDisconnectBridge_cleansPendingCalls(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	addBridge(r, "bridge-1")

	startForwardedCall(t, r, extCh, "bridge-1", "req-100", "get_texture_info")
	r.DisconnectBridge("bridge-1")

	waitFor(t, "pending call removal", func() bool { return pendingCount(r) == 0 })
	waitFor(t, "in-flight release", func() bool {
		r.mu.Lock()
		defer r.mu.Unlock()
		return len(r.inflight) == 0
	})
}

func TestListRenderdocSessions(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	addExt(r, "ext-2", "inst-2", false)

	result := r.toolListRenderdocSessions(context.Background(), &toolCall{args: map[string]interface{}{}})
	sessions, _ := result["sessions"].([]map[string]interface{})
	if len(sessions) != 2 {
		t.Errorf("expected 2 sessions, got %d", len(sessions))
	}
}

func TestGetCurrentCapture_singleLoaded(t *testing.T) {
	r := newTestRouter()
	path := "/test/capture.rdc"
	r.mu.Lock()
	r.extensions["ext-1"] = &extState{
		connID:     "ext-1",
		instanceID: "inst-1",
		connected:  true,
		capLoaded:  true,
		capPath:    &path,
		capState:   "loaded",
		revision:   5,
		send:       make(chan []byte, sendQueueSize),
	}
	r.mu.Unlock()

	result := r.toolGetCurrentCapture(context.Background(), &toolCall{args: map[string]interface{}{}})
	if status, _ := result["status"].(string); status != "loaded" {
		t.Errorf("expected status=loaded, got %q", status)
	}
}

func TestConcurrentToolCalls(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	bridgeCh := addBridge(r, "bridge-1")

	const n = 20
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		reqID := "req-concurrent-" + string(rune('a'+i))
		go func(rid string) {
			defer wg.Done()
			r.RouteToolCall(&ipc.ToolCallMessage{
				RequestID: rid,
				ToolName:  "list_capture_events",
				Arguments: map[string]interface{}{},
				Type:      "tool_call",
			}, "bridge-1")
		}(reqID)
	}

	// Simulate extension responding to all inspect_capture messages.
	for i := 0; i < n; i++ {
		select {
		case data := <-extCh:
			var req ipc.InspectCaptureRequestMessage
			json.Unmarshal(trimNewline(data), &req) //nolint:errcheck
			r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{
				RequestID: req.RequestID,
				Operation: req.Operation,
				Result:    map[string]interface{}{"events": []interface{}{}},
				Type:      "inspect_capture_result",
			})
		case <-time.After(2 * time.Second):
			t.Fatalf("timeout waiting for inspect_capture %d", i)
		}
	}

	// Collect all tool_results.
	for i := 0; i < n; i++ {
		receiveToolResult(t, bridgeCh, 2*time.Second)
	}
	wg.Wait()
}

func TestSelectExtension_preferLoaded(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-noload", "inst-1", false)
	addExt(r, "ext-loaded", "inst-2", true)

	ext := r.selectExtension("")
	if ext == nil {
		t.Fatal("expected extension, got nil")
	}
	if ext.connID != "ext-loaded" {
		t.Errorf("expected ext-loaded, got %q", ext.connID)
	}
}

func TestSelectExtension_byInstanceID(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-A", false)
	addExt(r, "ext-2", "inst-B", true)

	ext := r.selectExtension("inst-A")
	if ext == nil {
		t.Fatal("expected extension for inst-A")
	}
	if ext.instanceID != "inst-A" {
		t.Errorf("got instanceID %q want inst-A", ext.instanceID)
	}
}

// ---------------------------------------------------------------------------
// Reliability: timeouts, cancellation, synchronisation
// ---------------------------------------------------------------------------

// TestRouterClose_cancelsInflightCalls verifies that Close() aborts calls
// waiting on an extension instead of leaving them blocked.
func TestRouterClose_cancelsInflightCalls(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	addBridge(r, "bridge-1")

	done := make(chan struct{})
	go func() {
		r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "req-close", ToolName: "list_shaders", Arguments: map[string]interface{}{}}, "bridge-1")
		close(done)
	}()
	receiveInspectCapture(t, extCh, time.Second)
	r.Close()
	r.Close() // idempotent
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("RouteToolCall did not return after Close()")
	}
	if n := pendingCount(r); n != 0 {
		t.Errorf("pending map should be empty after Close, has %d", n)
	}
}

// TestPerCallTimeout verifies that an unanswered forwarded call returns the
// legacy timeout result as soon as its own deadline expires, and that a late
// reply is dropped.
func TestPerCallTimeout(t *testing.T) {
	r := newTestRouter()
	r.timeoutOverride = 50 * time.Millisecond
	extCh := addExt(r, "ext-1", "inst-1", true)
	bridgeCh := addBridge(r, "bridge-timeout")

	startForwardedCall(t, r, extCh, "bridge-timeout", "req-stale", "get_texture_info")
	msg := receiveToolResult(t, bridgeCh, time.Second)
	if msg.Error != failTimeout {
		t.Errorf("expected timeout error, got %q", msg.Error)
	}
	if m, _ := msg.Result.(map[string]interface{}); m["error"] != failTimeout {
		t.Errorf("expected result.error=timeout, got %v", msg.Result)
	}
	if n := pendingCount(r); n != 0 {
		t.Errorf("pending map should be empty after timeout, has %d", n)
	}

	r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{RequestID: "req-stale", Result: map[string]interface{}{}})
	select {
	case extra := <-bridgeCh:
		t.Errorf("late reply must not produce a second tool_result: %s", extra)
	case <-time.After(50 * time.Millisecond):
	}
}

// TestUpdateGuiState_staleRevisionIgnored verifies that lower revisions are
// discarded to prevent out-of-order state overwriting a newer state.
func TestUpdateGuiState_staleRevisionIgnored(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-rev", "inst-rev", false)

	path1 := "/cap1.rdc"
	r.UpdateGuiState("ext-rev", 10, true, &path1, "loaded")

	// A stale update with revision 5 should be ignored.
	path2 := "/cap2.rdc"
	r.UpdateGuiState("ext-rev", 5, false, &path2, "none")

	r.mu.Lock()
	ext := r.extensions["ext-rev"]
	r.mu.Unlock()

	if ext.revision != 10 {
		t.Errorf("revision should remain 10, got %d", ext.revision)
	}
	if ext.capPath == nil || *ext.capPath != "/cap1.rdc" {
		t.Errorf("capPath should remain /cap1.rdc, got %v", ext.capPath)
	}
}

// TestDisconnectBridge_doesNotAffectOtherBridges verifies that removing one
// bridge does not touch calls belonging to another bridge.
func TestDisconnectBridge_doesNotAffectOtherBridges(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	addBridge(r, "bridge-A")
	bridgeB := addBridge(r, "bridge-B")

	startForwardedCall(t, r, extCh, "bridge-A", "req-A", "list_shaders")
	reqB := startForwardedCall(t, r, extCh, "bridge-B", "req-B", "list_shaders")

	r.DisconnectBridge("bridge-A")
	waitFor(t, "bridge-A call cancellation", func() bool { return pendingCount(r) == 1 })

	r.mu.Lock()
	_, bExists := r.pending[reqB.RequestID]
	r.mu.Unlock()
	if !bExists {
		t.Fatal("req-B should remain after bridge-A disconnects")
	}
	r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{RequestID: reqB.RequestID, Result: map[string]interface{}{"ok": true}})
	if res := receiveToolResult(t, bridgeB, time.Second); res.RequestID != "req-B" || res.Error != "" {
		t.Errorf("bridge-B got %+v", res)
	}
}

// TestResolveExtension_ambiguous verifies that several loaded sessions yield
// status=ambiguous (with candidates) rather than no_renderdoc_connected.
func TestResolveExtension_ambiguous(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	addExt(r, "ext-2", "inst-2", true)
	bridgeCh := addBridge(r, "bridge-1")

	r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "req-amb", ToolName: "list_shaders", Arguments: map[string]interface{}{}}, "bridge-1")
	res := receiveToolResult(t, bridgeCh, time.Second)
	m, _ := res.Result.(map[string]interface{})
	if m["status"] != "ambiguous" {
		t.Fatalf("expected status=ambiguous, got %v", m)
	}
	if s, _ := m["sessions"].([]interface{}); len(s) != 2 {
		t.Errorf("expected 2 candidate sessions, got %v", m["sessions"])
	}
}

// TestResolveExtension_disconnectedInstance verifies the explicit-instance
// disconnected case.
func TestResolveExtension_disconnectedInstance(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	r.DisconnectExtension("ext-1")
	if _, errRes := r.resolveExtension("inst-1"); errRes["status"] != "session_disconnected" {
		t.Errorf("expected session_disconnected, got %v", errRes)
	}
}

// TestRouteInspectCaptureResultFrom_wrongExtensionIgnored verifies that one
// extension cannot answer a request sent to another.
func TestRouteInspectCaptureResultFrom_wrongExtensionIgnored(t *testing.T) {
	r := newTestRouter()
	extCh := addExt(r, "ext-1", "inst-1", true)
	addExt(r, "ext-2", "inst-2", false)
	bridgeCh := addBridge(r, "bridge-1")

	go r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "req-x", ToolName: "list_shaders", Arguments: map[string]interface{}{"instance_id": "inst-1"}}, "bridge-1")
	req := receiveInspectCapture(t, extCh, time.Second)

	r.RouteInspectCaptureResultFrom("ext-2", &ipc.InspectCaptureResultMessage{RequestID: req.RequestID, Result: map[string]interface{}{"forged": true}})
	if n := pendingCount(r); n != 1 {
		t.Fatalf("forged reply must not resolve the call (pending=%d)", n)
	}
	r.RouteInspectCaptureResultFrom("ext-1", &ipc.InspectCaptureResultMessage{RequestID: req.RequestID, Result: map[string]interface{}{"genuine": true}})
	res := receiveToolResult(t, bridgeCh, time.Second)
	if m, _ := res.Result.(map[string]interface{}); m["genuine"] != true {
		t.Errorf("expected genuine reply, got %v", res.Result)
	}
}
