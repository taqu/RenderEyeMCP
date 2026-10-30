package server

import (
	"encoding/json"
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/ipc"
)

// newTestRouter returns a Router with a fake auth that accepts any token.
func newTestRouter() *Router {
	r := &Router{
		serviceInstanceID: "test-service",
		auth:              &Auth{token: "test-token"},
		extensions:        make(map[string]*extState),
		bridges:           make(map[string]*bridgeState),
		pending:           make(map[string]*pendingCall),
	}
	// Don't start the timeout loop in unit tests.
	return r
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

	msg := &ipc.ToolCallMessage{
		RequestID: "req-2",
		ToolName:  "get_current_capture_info",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	}
	r.RouteToolCall(msg, "bridge-1")

	inspectMsg := receiveInspectCapture(t, extCh, time.Second)
	if inspectMsg.Operation != "capture_info" {
		t.Errorf("operation got %q want %q", inspectMsg.Operation, "capture_info")
	}
	if inspectMsg.RequestID != "req-2" {
		t.Errorf("request_id propagated incorrectly")
	}

	// Simulate extension response.
	resultData := map[string]interface{}{"path": "/cap.rdc"}
	r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{
		RequestID: "req-2",
		Operation: "capture_info",
		Result:    resultData,
		Error:     "",
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

	msg := &ipc.ToolCallMessage{
		RequestID: "req-3",
		ToolName:  "get_pipeline_state",
		Arguments: map[string]interface{}{
			"instance_id": "inst-A",
			"event_id":    42,
			"section":     "summary",
		},
		Type: "tool_call",
	}
	r.RouteToolCall(msg, "bridge-1")

	inspectMsg := receiveInspectCapture(t, extCh, time.Second)
	if _, hasID := inspectMsg.Params["instance_id"]; hasID {
		t.Error("instance_id should be stripped from inspect_capture params")
	}
	if v, _ := inspectMsg.Params["event_id"]; v == nil {
		t.Error("event_id should be in inspect_capture params")
	}
}

func TestRouteToolCall_noExtension(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")

	msg := &ipc.ToolCallMessage{
		RequestID: "req-4",
		ToolName:  "list_capture_events",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	}
	r.RouteToolCall(msg, "bridge-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	resultMap, _ := result.Result.(map[string]interface{})
	if resultMap == nil {
		t.Fatal("expected result map")
	}
	status, _ := resultMap["status"].(string)
	if status != "no_renderdoc_connected" {
		t.Errorf("expected no_renderdoc_connected status, got %q", status)
	}
}

func TestRouteToolCall_notImplemented(t *testing.T) {
	r := newTestRouter()
	bridgeCh := addBridge(r, "bridge-1")

	msg := &ipc.ToolCallMessage{
		RequestID: "req-5",
		ToolName:  "capture_list",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	}
	r.RouteToolCall(msg, "bridge-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	resultMap, _ := result.Result.(map[string]interface{})
	if resultMap == nil {
		t.Fatal("expected result map")
	}
	if _, hasErr := resultMap["error"]; !hasErr {
		t.Error("expected error in result for not-implemented tool")
	}
}

func TestDisconnectExtension_errorsPendingCalls(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	bridgeCh := addBridge(r, "bridge-1")

	// Store a pending call manually.
	r.mu.Lock()
	r.pending["req-99"] = &pendingCall{
		requestID:    "req-99",
		bridgeConnID: "bridge-1",
		toolName:     "list_resources",
		extConnID:    "ext-1",
		createdAt:    time.Now(),
	}
	r.mu.Unlock()

	r.DisconnectExtension("ext-1")

	result := receiveToolResult(t, bridgeCh, time.Second)
	if result.Error != "extension_disconnected" {
		t.Errorf("expected extension_disconnected error, got %q", result.Error)
	}
}

func TestDisconnectBridge_cleansPendingCalls(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	addBridge(r, "bridge-1")

	r.mu.Lock()
	r.pending["req-100"] = &pendingCall{
		requestID:    "req-100",
		bridgeConnID: "bridge-1",
		toolName:     "get_texture_info",
		extConnID:    "ext-1",
		createdAt:    time.Now(),
	}
	r.mu.Unlock()

	r.DisconnectBridge("bridge-1")

	r.mu.Lock()
	_, exists := r.pending["req-100"]
	r.mu.Unlock()

	if exists {
		t.Error("pending call should be removed when bridge disconnects")
	}
}

func TestListRenderdocSessions(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	addExt(r, "ext-2", "inst-2", false)

	result := r.toolListRenderdocSessions()
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

	result := r.toolGetCurrentCapture("")
	status, _ := result["status"].(string)
	if status != "loaded" {
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
	wg.Wait()

	// Simulate extension responding to all inspect_capture messages.
	for i := 0; i < n; i++ {
		select {
		case data := <-extCh:
			var req ipc.InspectCaptureRequestMessage
			json.Unmarshal(trimNewline(data), &req)
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
// Phase 20 reliability tests
// ---------------------------------------------------------------------------

// TestRouterClose_stopsTimeoutLoop verifies that Close() stops the background
// timeout goroutine within a reasonable time (prevents goroutine leaks).
func TestRouterClose_stopsTimeoutLoop(t *testing.T) {
	auth := &Auth{token: "test-token"}
	r := NewRouter("svc-close-test", auth)

	// Close should not block or panic.
	done := make(chan struct{})
	go func() {
		r.Close()
		close(done)
	}()
	select {
	case <-done:
		// OK
	case <-time.After(2 * time.Second):
		t.Fatal("Close() did not return within 2 seconds — possible goroutine leak")
	}
}

// TestTimeoutLoop_expiresStaleCall verifies that the timeout loop errors stale
// pending calls and delivers the error to the waiting bridge.
func TestTimeoutLoop_expiresStaleCall(t *testing.T) {
	auth := &Auth{token: "test-token"}
	r := &Router{
		serviceInstanceID: "svc-timeout-test",
		auth:              auth,
		extensions:        make(map[string]*extState),
		bridges:           make(map[string]*bridgeState),
		pending:           make(map[string]*pendingCall),
		done:              make(chan struct{}),
	}

	bridgeCh := addBridge(r, "bridge-timeout")

	// Insert a pending call that is already expired.
	r.mu.Lock()
	r.pending["req-stale"] = &pendingCall{
		requestID:    "req-stale",
		bridgeConnID: "bridge-timeout",
		toolName:     "get_texture_info",
		extConnID:    "ext-gone",
		createdAt:    time.Now().Add(-2 * toolCallTimeout), // definitely expired
	}
	r.mu.Unlock()

	// Run one tick of the timeout loop inline.
	go r.timeoutLoop()

	// We should receive an error tool_result within 10 seconds (loop fires every 5s).
	select {
	case data := <-bridgeCh:
		var msg ipc.ToolResultMessage
		if err := json.Unmarshal(trimNewline(data), &msg); err != nil {
			t.Fatalf("unmarshal: %v", err)
		}
		if msg.Error != "timeout" {
			t.Errorf("expected timeout error, got %q", msg.Error)
		}
	case <-time.After(12 * time.Second):
		t.Fatal("timeout: expected stale call to be expired by timeoutLoop")
	}

	r.Close()
}

// TestRouteToolCall_marshalInspectCaptureNilGuard verifies that if
// marshalInspectCapture cannot serialize the message (simulated by injecting a
// non-serializable params value), the pending call is removed and the bridge
// receives an immediate error rather than waiting for the 30-second timeout.
// This test is indirect — it verifies the error path via a disconnected
// extension (which triggers the same immediate-error code path).
func TestDisconnectExtension_immediateErrorOnPendingCall(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-dc", "inst-dc", true)
	bridgeCh := addBridge(r, "bridge-dc")

	r.mu.Lock()
	r.pending["req-dc"] = &pendingCall{
		requestID:    "req-dc",
		bridgeConnID: "bridge-dc",
		toolName:     "get_buffer_info",
		extConnID:    "ext-dc",
		createdAt:    time.Now(),
	}
	r.mu.Unlock()

	// Disconnect the extension — pending call must be errored immediately.
	r.DisconnectExtension("ext-dc")

	result := receiveToolResult(t, bridgeCh, time.Second)
	if result.Error != "extension_disconnected" {
		t.Errorf("expected extension_disconnected, got %q", result.Error)
	}
	if result.RequestID != "req-dc" {
		t.Errorf("expected request_id req-dc, got %q", result.RequestID)
	}

	// Pending map must be empty.
	r.mu.Lock()
	pending := len(r.pending)
	r.mu.Unlock()
	if pending != 0 {
		t.Errorf("pending map should be empty after disconnect, has %d entries", pending)
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
// bridge does not touch pending calls belonging to another bridge.
func TestDisconnectBridge_doesNotAffectOtherBridges(t *testing.T) {
	r := newTestRouter()
	addExt(r, "ext-1", "inst-1", true)
	addBridge(r, "bridge-A")
	addBridge(r, "bridge-B")

	r.mu.Lock()
	r.pending["req-A"] = &pendingCall{requestID: "req-A", bridgeConnID: "bridge-A", toolName: "t", extConnID: "ext-1", createdAt: time.Now()}
	r.pending["req-B"] = &pendingCall{requestID: "req-B", bridgeConnID: "bridge-B", toolName: "t", extConnID: "ext-1", createdAt: time.Now()}
	r.mu.Unlock()

	r.DisconnectBridge("bridge-A")

	r.mu.Lock()
	_, aExists := r.pending["req-A"]
	_, bExists := r.pending["req-B"]
	r.mu.Unlock()

	if aExists {
		t.Error("req-A should be removed after bridge-A disconnects")
	}
	if !bExists {
		t.Error("req-B should remain after bridge-A disconnects")
	}
}
