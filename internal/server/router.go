package server

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"runtime"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/ipc"
)

// sendQueueSize is the capacity of each connection's outbound message channel.
const sendQueueSize = 64

// toolCallTimeout is how long we wait for an inspect_capture_result before
// returning an error tool_result to the bridge.
const toolCallTimeout = 30 * time.Second

// toolToOperation maps MCP tool names to the operation string sent in
// inspect_capture messages.  Only entries that differ from the tool name
// are listed; all others use the tool name directly.
var toolToOperation = map[string]string{
	// Phase 8
	"get_current_capture_info": "capture_info",
	"list_capture_events":      "list_events",
	"get_capture_event":        "get_event",
	"get_selected_event":       "selected_event",
	"get_pipeline_state":       "pipeline_state",
	// Phase 14
	"get_draw_geometry_info":  "draw_geometry_info",
	"get_vertex_input_layout": "vertex_input_layout",
	"get_mesh_indices":        "mesh_indices",
	"get_mesh_vertices":       "mesh_vertices",
	"get_post_vs_geometry":    "post_vs_geometry",
	"get_mesh_statistics":     "mesh_statistics",
	// Phase 15
	"get_pixel_history": "pixel_history",
}

// inspectionTools is the set of tool names that are forwarded to the extension
// via an inspect_capture message.  All other tool names are either handled
// internally or rejected.
var inspectionTools = map[string]bool{
	// Phase 8
	"get_current_capture_info": true,
	"list_capture_events":      true,
	"get_capture_event":        true,
	"get_selected_event":       true,
	"get_pipeline_state":       true,
	// Phase 9
	"list_resources":    true,
	"get_resource_info": true,
	"get_texture_info":  true,
	"get_buffer_info":   true,
	"read_buffer_data":  true,
	// Phase 10
	"list_shaders":           true,
	"get_shader_info":        true,
	"get_shader_reflection":  true,
	"get_shader_bindings":    true,
	"get_shader_disassembly": true,
	"get_shader_debug_info":  true,
	// Phase 11
	"get_render_targets":     true,
	"get_texture_image":      true,
	"get_pixel_value":        true,
	"get_texture_statistics": true,
	// Phase 13
	"list_gpu_counters": true,
	// Phase 14
	"get_draw_geometry_info":  true,
	"get_vertex_input_layout": true,
	"get_mesh_indices":        true,
	"get_mesh_vertices":       true,
	"get_post_vs_geometry":    true,
	"get_mesh_statistics":     true,
	// Phase 15
	"get_pixel_history": true,
}

// ---------------------------------------------------------------------------
// Connection state types
// ---------------------------------------------------------------------------

// extState holds per-connection state for a registered RenderDoc extension.
type extState struct {
	connID      string
	instanceID  string
	processID   int
	extVersion  string
	rdocVersion string
	connected   bool
	revision    int
	capLoaded   bool
	capPath     *string
	capState    string
	send        chan []byte // outbound messages; closed on disconnect
}

func (e *extState) toGuiSessionDict() map[string]interface{} {
	entry := map[string]interface{}{
		"instance_id":       e.instanceID,
		"process_id":        e.processID,
		"renderdoc_version": e.rdocVersion,
		"state_version":     e.revision,
	}
	if e.connected {
		entry["connection_state"] = "connected"
		entry["capture"] = map[string]interface{}{
			"state": e.capState,
			"path":  e.capPath,
		}
		entry["last_known_capture"] = nil
	} else {
		entry["connection_state"] = "disconnected"
		entry["capture"] = nil
		if e.revision > 0 {
			entry["last_known_capture"] = map[string]interface{}{
				"state": e.capState,
				"path":  e.capPath,
			}
		} else {
			entry["last_known_capture"] = nil
		}
	}
	return entry
}

// bridgeState holds per-connection state for a registered MCP bridge.
type bridgeState struct {
	connID   string
	bridgeID string
	send     chan []byte
}

// pendingCall records a tool_call forwarded to an extension, awaiting
// the matching inspect_capture_result.
type pendingCall struct {
	requestID    string
	bridgeConnID string
	toolName     string
	extConnID    string
	createdAt    time.Time
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

// Router is the central coordinator for all client connections and message
// routing.  It is safe for concurrent use.
type Router struct {
	serviceInstanceID string
	auth              *Auth
	mu                sync.Mutex
	extensions        map[string]*extState    // connID → ext
	bridges           map[string]*bridgeState // connID → bridge
	pending           map[string]*pendingCall // requestID → pending tool call

	// done is closed by Close() to stop background goroutines.
	done chan struct{}
}

// NewRouter creates a Router and starts its background timeout goroutine.
// Call Close() to stop the goroutine when the Router is no longer needed.
func NewRouter(serviceInstanceID string, auth *Auth) *Router {
	r := &Router{
		serviceInstanceID: serviceInstanceID,
		auth:              auth,
		extensions:        make(map[string]*extState),
		bridges:           make(map[string]*bridgeState),
		pending:           make(map[string]*pendingCall),
		done:              make(chan struct{}),
	}
	go r.timeoutLoop()
	return r
}

// Close stops the Router's background goroutines.  It must be called exactly
// once when the Router is no longer needed to prevent goroutine leaks.
func (r *Router) Close() {
	close(r.done)
}

// ---------------------------------------------------------------------------
// Extension registration / state
// ---------------------------------------------------------------------------

// RegisterExtension stores an authenticated extension connection in the router.
func (r *Router) RegisterExtension(connID, instanceID string, processID int, extVersion, rdocVersion string, sendCh chan []byte) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.extensions[connID] = &extState{
		connID:      connID,
		instanceID:  instanceID,
		processID:   processID,
		extVersion:  extVersion,
		rdocVersion: rdocVersion,
		connected:   true,
		send:        sendCh,
	}
	slog.Info("extension registered", "conn_id", connID, "instance_id", instanceID, "pid", processID)
}

// UpdateGuiState updates cached capture state from a gui_state_changed or gui_state_response.
func (r *Router) UpdateGuiState(connID string, revision int, capLoaded bool, capPath *string, capState string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	ext, ok := r.extensions[connID]
	if !ok {
		return
	}
	if revision <= ext.revision {
		return // stale
	}
	ext.revision = revision
	ext.capLoaded = capLoaded
	ext.capPath = capPath
	ext.capState = capState
}

// DisconnectExtension marks an extension as disconnected and cleans up pending
// tool calls that were routed to it.
func (r *Router) DisconnectExtension(connID string) {
	r.mu.Lock()
	var erroredCalls []*pendingCall
	if ext, ok := r.extensions[connID]; ok {
		ext.connected = false
	}
	for reqID, call := range r.pending {
		if call.extConnID == connID {
			delete(r.pending, reqID)
			erroredCalls = append(erroredCalls, call)
		}
	}
	bridgeMap := r.bridges
	r.mu.Unlock()

	for _, call := range erroredCalls {
		r.mu.Lock()
		bridge := bridgeMap[call.bridgeConnID]
		r.mu.Unlock()
		if bridge != nil {
			sendToolResultError(bridge.send, call.toolName, call.requestID, "extension_disconnected")
		}
	}
	slog.Info("extension disconnected", "conn_id", connID)
}

// ---------------------------------------------------------------------------
// Bridge registration
// ---------------------------------------------------------------------------

// RegisterBridge stores an authenticated bridge connection.
func (r *Router) RegisterBridge(connID, bridgeID string, sendCh chan []byte) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.bridges[connID] = &bridgeState{
		connID:   connID,
		bridgeID: bridgeID,
		send:     sendCh,
	}
	slog.Info("bridge registered", "conn_id", connID, "bridge_id", bridgeID)
}

// DisconnectBridge removes a bridge and discards its pending calls (no
// response needed since the bridge is gone).
func (r *Router) DisconnectBridge(connID string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.bridges, connID)
	for reqID, call := range r.pending {
		if call.bridgeConnID == connID {
			delete(r.pending, reqID)
		}
	}
	slog.Info("bridge disconnected", "conn_id", connID)
}

// ---------------------------------------------------------------------------
// Tool call routing
// ---------------------------------------------------------------------------

// RouteToolCall handles an incoming tool_call from a bridge.
// It either resolves the call immediately (internal tools) or forwards it
// to the appropriate extension as an inspect_capture message.
func (r *Router) RouteToolCall(msg *ipc.ToolCallMessage, bridgeConnID string) {
	// 1. Internal tools — no extension required.
	if result, handled := r.handleInternalTool(msg.ToolName, msg.Arguments); handled {
		r.mu.Lock()
		bridge := r.bridges[bridgeConnID]
		r.mu.Unlock()
		if bridge != nil {
			data := marshalToolResult(msg.RequestID, msg.ToolName, result, "")
			safeSend(bridge.send, data)
		}
		return
	}

	// 2. Forwarded inspection tools.
	operation, ok := r.operationForTool(msg.ToolName)
	if !ok {
		r.mu.Lock()
		bridge := r.bridges[bridgeConnID]
		r.mu.Unlock()
		if bridge != nil {
			result := map[string]interface{}{
				"error":   "not_implemented_in_go_service",
				"message": fmt.Sprintf("Tool %q requires the Python Shared IPC Service.", msg.ToolName),
			}
			data := marshalToolResult(msg.RequestID, msg.ToolName, result, "")
			safeSend(bridge.send, data)
		}
		return
	}

	// 3. Select target extension.
	instanceID, _ := msg.Arguments["instance_id"].(string)
	ext := r.selectExtension(instanceID)
	if ext == nil {
		r.mu.Lock()
		bridge := r.bridges[bridgeConnID]
		r.mu.Unlock()
		var result map[string]interface{}
		if instanceID != "" {
			result = map[string]interface{}{
				"status":      "session_not_found",
				"instance_id": instanceID,
				"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
			}
		} else {
			result = map[string]interface{}{
				"status":  "no_renderdoc_connected",
				"message": "No RenderDoc GUI instances are currently connected",
			}
		}
		if bridge != nil {
			data := marshalToolResult(msg.RequestID, msg.ToolName, result, "")
			safeSend(bridge.send, data)
		}
		return
	}

	// 4. Build params — strip instance_id, forward the rest.
	params := make(map[string]interface{}, len(msg.Arguments))
	for k, v := range msg.Arguments {
		if k != "instance_id" {
			params[k] = v
		}
	}

	// 5. Store pending call.
	r.mu.Lock()
	r.pending[msg.RequestID] = &pendingCall{
		requestID:    msg.RequestID,
		bridgeConnID: bridgeConnID,
		toolName:     msg.ToolName,
		extConnID:    ext.connID,
		createdAt:    time.Now(),
	}
	r.mu.Unlock()

	// 6. Send inspect_capture to extension.
	data := marshalInspectCapture(msg.RequestID, operation, params)
	if data == nil {
		// Marshal failed (logged inside marshalInspectCapture). Remove the pending
		// entry and return an error immediately rather than letting it time out.
		r.mu.Lock()
		delete(r.pending, msg.RequestID)
		bridge := r.bridges[bridgeConnID]
		r.mu.Unlock()
		if bridge != nil {
			sendToolResultError(bridge.send, msg.ToolName, msg.RequestID, "internal_marshal_error")
		}
		return
	}
	safeSend(ext.send, data)
}

// RouteInspectCaptureResult handles an inspect_capture_result from an extension
// and delivers the corresponding tool_result to the waiting bridge.
func (r *Router) RouteInspectCaptureResult(msg *ipc.InspectCaptureResultMessage) {
	r.mu.Lock()
	call := r.pending[msg.RequestID]
	if call != nil {
		delete(r.pending, msg.RequestID)
	}
	var bridge *bridgeState
	if call != nil {
		bridge = r.bridges[call.bridgeConnID]
	}
	r.mu.Unlock()

	if bridge == nil {
		return // bridge disconnected
	}
	toolName := ""
	if call != nil {
		toolName = call.toolName
	}
	data := marshalToolResult(msg.RequestID, toolName, msg.Result, msg.Error)
	safeSend(bridge.send, data)
}

// ---------------------------------------------------------------------------
// Internal tool implementations
// ---------------------------------------------------------------------------

func (r *Router) handleInternalTool(toolName string, arguments map[string]interface{}) (map[string]interface{}, bool) {
	switch toolName {
	case "server_status":
		return r.toolServerStatus(), true
	case "list_renderdoc_sessions":
		return r.toolListRenderdocSessions(), true
	case "get_renderdoc_session_state":
		instanceID, _ := arguments["instance_id"].(string)
		return r.toolGetRenderdocSessionState(instanceID), true
	case "get_current_capture":
		instanceID, _ := arguments["instance_id"].(string)
		return r.toolGetCurrentCapture(instanceID), true
	case "instance_gui_state":
		instanceID, _ := arguments["instance_id"].(string)
		return r.toolInstanceGuiState(instanceID), true
	}
	return nil, false
}

func (r *Router) toolServerStatus() map[string]interface{} {
	r.mu.Lock()
	extCount := len(r.extensions)
	activeExt := 0
	for _, e := range r.extensions {
		if e.connected {
			activeExt++
		}
	}
	r.mu.Unlock()

	return map[string]interface{}{
		"server_name":                "RenderEyeMCP",
		"server_version":             config.GoServiceVersion,
		"os":                         runtime.GOOS,
		"go_version":                 runtime.Version(),
		"ipc_listener_status":        "running",
		"extension_connections":      extCount,
		"active_extension_connections": activeExt,
		"ipc_protocol_version":       ipc.ProtocolVersion,
		"service_instance_id":        r.serviceInstanceID,
	}
}

func (r *Router) toolListRenderdocSessions() map[string]interface{} {
	r.mu.Lock()
	sessions := make([]map[string]interface{}, 0, len(r.extensions))
	for _, e := range r.extensions {
		sessions = append(sessions, e.toGuiSessionDict())
	}
	r.mu.Unlock()
	return map[string]interface{}{
		"sessions": sessions,
		"total":    len(sessions),
	}
}

func (r *Router) toolGetRenderdocSessionState(instanceID string) map[string]interface{} {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, e := range r.extensions {
		if e.instanceID == instanceID {
			return e.toGuiSessionDict()
		}
	}
	return map[string]interface{}{
		"error":       "session_not_found",
		"instance_id": instanceID,
		"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
	}
}

func (r *Router) toolGetCurrentCapture(instanceID string) map[string]interface{} {
	r.mu.Lock()
	defer r.mu.Unlock()

	if instanceID != "" {
		for _, e := range r.extensions {
			if e.instanceID == instanceID {
				return r.captureStatusForExt(e)
			}
		}
		return map[string]interface{}{
			"status":      "session_not_found",
			"instance_id": instanceID,
			"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
		}
	}

	var connected []*extState
	for _, e := range r.extensions {
		if e.connected {
			connected = append(connected, e)
		}
	}
	if len(connected) == 0 {
		return map[string]interface{}{
			"status":  "no_renderdoc_connected",
			"message": "No RenderDoc GUI instances are currently connected",
		}
	}
	var loaded []*extState
	for _, e := range connected {
		if e.capLoaded {
			loaded = append(loaded, e)
		}
	}
	if len(loaded) == 0 {
		return map[string]interface{}{
			"status":   "no_capture_loaded",
			"message":  "Connected RenderDoc GUI instance(s) have no capture loaded",
			"sessions": guiSessionList(connected),
		}
	}
	if len(loaded) == 1 {
		return r.captureStatusForExt(loaded[0])
	}
	return map[string]interface{}{
		"status":   "ambiguous",
		"message":  fmt.Sprintf("Multiple RenderDoc GUI sessions have a capture loaded (%d). Specify instance_id.", len(loaded)),
		"sessions": guiSessionList(loaded),
	}
}

func (r *Router) captureStatusForExt(e *extState) map[string]interface{} {
	if !e.connected {
		return map[string]interface{}{
			"status":           "session_disconnected",
			"instance_id":      e.instanceID,
			"connection_state": "disconnected",
			"message":          "The specified RenderDoc GUI session is not currently connected",
		}
	}
	if !e.capLoaded {
		return map[string]interface{}{
			"status":           "no_capture_loaded",
			"instance_id":      e.instanceID,
			"connection_state": "connected",
			"capture_state":    e.capState,
			"message":          "The specified RenderDoc GUI session has no capture loaded",
		}
	}
	return map[string]interface{}{
		"status":           "loaded",
		"instance_id":      e.instanceID,
		"process_id":       e.processID,
		"connection_state": "connected",
		"capture_path":     e.capPath,
		"capture_state":    e.capState,
		"state_version":    e.revision,
	}
}

func (r *Router) toolInstanceGuiState(instanceID string) map[string]interface{} {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, e := range r.extensions {
		if e.instanceID == instanceID && e.connected {
			m := map[string]interface{}{
				"connection_id":     e.connID,
				"instance_id":       e.instanceID,
				"process_id":        e.processID,
				"extension_version": e.extVersion,
				"renderdoc_version": e.rdocVersion,
				"connected":         e.connected,
				"connection_state":  "connected",
				"capture_loaded":    e.capLoaded,
				"capture_path":      e.capPath,
				"capture_state":     e.capState,
				"gui_state_revision": e.revision,
				"freshness":         "fresh",
			}
			return m
		}
	}
	return map[string]interface{}{
		"instance_id":      instanceID,
		"connected":        false,
		"capture_loaded":   false,
		"capture_path":     nil,
		"capture_state":    "unknown",
		"freshness":        "unavailable",
	}
}

// ---------------------------------------------------------------------------
// Extension selection
// ---------------------------------------------------------------------------

// selectExtension picks the best extension for a tool call.
// If instanceID is set it must match.  Otherwise the preference order is:
//
//  1. Single connected extension.
//  2. Single connected extension with a loaded capture.
//  3. Any connected extension (ambiguous — returns nil if > 1 with loaded captures).
func (r *Router) selectExtension(instanceID string) *extState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if instanceID != "" {
		for _, e := range r.extensions {
			if e.instanceID == instanceID && e.connected {
				return e
			}
		}
		return nil
	}

	var connected []*extState
	for _, e := range r.extensions {
		if e.connected {
			connected = append(connected, e)
		}
	}
	if len(connected) == 0 {
		return nil
	}
	if len(connected) == 1 {
		return connected[0]
	}

	var loaded []*extState
	for _, e := range connected {
		if e.capLoaded {
			loaded = append(loaded, e)
		}
	}
	if len(loaded) == 1 {
		return loaded[0]
	}
	return nil // ambiguous
}

// ---------------------------------------------------------------------------
// Timeout cleanup
// ---------------------------------------------------------------------------

// timeoutLoop periodically expires pending tool calls that have not received
// a response within toolCallTimeout.  It exits when r.done is closed.
func (r *Router) timeoutLoop() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-r.done:
			return
		case <-ticker.C:
		}

		now := time.Now()
		r.mu.Lock()
		var expired []*pendingCall
		for reqID, call := range r.pending {
			if now.Sub(call.createdAt) > toolCallTimeout {
				delete(r.pending, reqID)
				expired = append(expired, call)
			}
		}
		bridges := r.bridges
		r.mu.Unlock()

		for _, call := range expired {
			r.mu.Lock()
			bridge := bridges[call.bridgeConnID]
			r.mu.Unlock()
			if bridge != nil {
				slog.Warn("tool call timed out", "tool", call.toolName, "bridge", call.bridgeConnID)
				sendToolResultError(bridge.send, call.toolName, call.requestID, "timeout")
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// operationForTool returns the inspect_capture operation name for toolName.
// The second return is false if the tool is not an inspection tool.
func (r *Router) operationForTool(toolName string) (string, bool) {
	if !inspectionTools[toolName] {
		return "", false
	}
	if op, ok := toolToOperation[toolName]; ok {
		return op, true
	}
	// Same name by convention.
	return toolName, true
}

func guiSessionList(exts []*extState) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(exts))
	for _, e := range exts {
		out = append(out, e.toGuiSessionDict())
	}
	return out
}

// safeSend attempts to send data on ch without blocking.  If the queue is full
// the message is dropped with a warning (bounded queue policy).
func safeSend(ch chan []byte, data []byte) {
	select {
	case ch <- data:
	default:
		slog.Warn("outbound queue full; message dropped")
	}
}

// sendToolResultError sends an error tool_result to a bridge's send channel.
func sendToolResultError(sendCh chan []byte, toolName, requestID, errMsg string) {
	result := map[string]interface{}{"error": errMsg, "message": errMsg}
	data := marshalToolResult(requestID, toolName, result, errMsg)
	safeSend(sendCh, data)
}

// marshalToolResult serialises a ToolResultMessage to a newline-terminated JSON frame.
func marshalToolResult(requestID, toolName string, result interface{}, errMsg string) []byte {
	msg := ipc.ToolResultMessage{
		RequestID: requestID,
		ToolName:  toolName,
		Result:    result,
		Error:     errMsg,
		Type:      "tool_result",
	}
	data, err := json.Marshal(msg)
	if err != nil {
		// Fallback: hand-build a minimal error result.
		data = []byte(fmt.Sprintf(
			`{"request_id":%q,"tool_name":%q,"result":null,"error":"marshal_error","type":"tool_result"}`,
			requestID, toolName,
		))
	}
	return append(data, '\n')
}

// marshalInspectCapture serialises an InspectCaptureRequestMessage.
func marshalInspectCapture(requestID, operation string, params map[string]interface{}) []byte {
	msg := ipc.InspectCaptureRequestMessage{
		RequestID: requestID,
		Operation: operation,
		Params:    params,
		Type:      "inspect_capture",
	}
	data, err := json.Marshal(msg)
	if err != nil {
		slog.Error("failed to marshal inspect_capture", "err", err)
		return nil
	}
	return append(data, '\n')
}

// WriteReadyFile writes the service-ready JSON to the well-known path so that
// Python bridge processes know the service is accepting connections.
func WriteReadyFile(serviceInstanceID, host string, port, pid int) {
	data, _ := json.Marshal(map[string]interface{}{
		"pid":         pid,
		"instance_id": serviceInstanceID,
		"port":        port,
		"host":        host,
	})
	if err := os.WriteFile(config.ReadyFilePath(), data, 0644); err != nil {
		slog.Warn("failed to write ready file", "path", config.ReadyFilePath(), "err", err)
	}
}

// RemoveReadyFile deletes the ready file on service shutdown.
func RemoveReadyFile() {
	if err := os.Remove(config.ReadyFilePath()); err != nil && !os.IsNotExist(err) {
		slog.Warn("failed to remove ready file", "path", config.ReadyFilePath(), "err", err)
	}
}
