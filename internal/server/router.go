package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"runtime"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/ipc"
	"github.com/taqu/rendereye-mcp/internal/sessions"
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
	// Phase 20
	"collect_gpu_counters":  "fetch_gpu_counters",
	"debug_pixel_shader":    "debug_pixel",
	"debug_vertex_shader":   "debug_vertex",
	"debug_compute_shader":  "debug_compute",
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
	// Phase 20
	"collect_gpu_counters":  true,
	"debug_pixel_shader":    true,
	"debug_vertex_shader":   true,
	"debug_compute_shader":  true,
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

	// Subsystems (may be nil if not initialised).
	measurements *MeasurementStore
	debugs       *DebugStore
	captures     *captures.CaptureRegistry
	instances    *instances.InstanceManager
	sessions     *sessions.SessionManager

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
		measurements:      newMeasurementStore(),
		debugs:            newDebugStore(),
		instances:         instances.NewInstanceManager(),
		done:              make(chan struct{}),
	}
	go r.timeoutLoop()
	return r
}

// InitSubsystems initialises the capture registry and session manager.
// capDirs is the list of directories to watch; pass nil to use platform defaults.
// This should be called from Server.Start() so a cancellable context is available.
func (r *Router) InitSubsystems(ctx context.Context, capDirs []string) {
	cap := captures.NewCaptureRegistry(capDirs)
	cap.Start(ctx)
	sess := sessions.NewSessionManager(cap, r.instances)
	r.mu.Lock()
	r.captures = cap
	r.sessions = sess
	r.mu.Unlock()
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
				"error":   "unknown_tool",
				"message": fmt.Sprintf("Tool %q is not recognised by the Go IPC Service.", msg.ToolName),
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
	// Capture extension context for post-processing.
	var capturePath string
	var instanceID string
	if call != nil {
		if ext, ok := r.extensions[call.extConnID]; ok {
			if ext.capPath != nil {
				capturePath = *ext.capPath
			}
			instanceID = ext.instanceID
		}
	}
	r.mu.Unlock()

	if bridge == nil {
		return // bridge disconnected
	}
	toolName := ""
	if call != nil {
		toolName = call.toolName
	}

	// Post-process special tools that store results internally.
	var result interface{}
	var errMsg string

	if msg.Error != "" {
		result = map[string]interface{}{"error": msg.Error, "message": msg.Error}
		errMsg = msg.Error
	} else {
		switch toolName {
		case "collect_gpu_counters":
			result, errMsg = r.postProcessMeasurement(msg.Result, capturePath, instanceID)
		case "debug_pixel_shader", "debug_vertex_shader", "debug_compute_shader":
			result, errMsg = r.postProcessDebug(msg.Result, capturePath, instanceID, toolName)
		default:
			result = msg.Result
			errMsg = msg.Error
		}
	}

	data := marshalToolResult(msg.RequestID, toolName, result, errMsg)
	safeSend(bridge.send, data)
}

// postProcessMeasurement stores GPU counter results and returns a summary dict.
func (r *Router) postProcessMeasurement(extResult interface{}, capturePath, instanceID string) (interface{}, string) {
	raw, ok := extResult.(map[string]interface{})
	if !ok {
		return map[string]interface{}{"error": "invalid_extension_response"}, "invalid_extension_response"
	}

	results, _ := raw["results"].([]interface{})
	counterDescs, _ := raw["counter_descriptions"].([]interface{})
	countersFetched, _ := raw["counters_fetched"].([]interface{})
	countersInvalid, _ := raw["counters_invalid"].([]interface{})
	resultCount, _ := raw["result_count"].(float64)

	mid := r.measurements.makeID()
	rec := &MeasurementRecord{
		MeasurementID:       mid,
		Status:              "completed",
		CapturePath:         capturePath,
		InstanceID:          instanceID,
		Results:             results,
		CounterDescriptions: counterDescs,
		CreatedAt:           float64(time.Now().UnixNano()) / 1e9,
		Metadata: map[string]interface{}{
			"counters_invalid": countersInvalid,
			"repeats":          1,
			"result_count":     resultCount,
		},
	}
	// Extract counter IDs from descriptions.
	for _, d := range counterDescs {
		if dm, ok := d.(map[string]interface{}); ok {
			if cid, ok := dm["counter_id"]; ok {
				rec.CounterIDs = append(rec.CounterIDs, cid)
			}
		}
	}
	r.measurements.store(rec)

	return map[string]interface{}{
		"measurement_id":   mid,
		"status":           "completed",
		"capture_path":     capturePath,
		"counters_fetched": countersFetched,
		"counters_invalid": countersInvalid,
		"result_count":     int(resultCount),
		"repeats":          1,
	}, ""
}

// postProcessDebug stores a shader debug trace and returns a summary dict.
func (r *Router) postProcessDebug(extResult interface{}, capturePath, instanceID, toolName string) (interface{}, string) {
	raw, ok := extResult.(map[string]interface{})
	if !ok {
		return map[string]interface{}{"error": "invalid_extension_response"}, "invalid_extension_response"
	}

	stage, _ := raw["stage"].(string)
	if stage == "" {
		switch toolName {
		case "debug_pixel_shader":
			stage = "pixel"
		case "debug_vertex_shader":
			stage = "vertex"
		case "debug_compute_shader":
			stage = "compute"
		}
	}

	eventID := toInt(raw["event_id"])
	steps, _ := raw["steps"].([]interface{})
	initialVars, _ := raw["initial_vars"].(map[string]interface{})
	truncated, _ := raw["truncated"].(bool)

	did := r.debugs.makeID()
	rec := &DebugRecord{
		DebugID:     did,
		Status:      "ready",
		Stage:       stage,
		EventID:     eventID,
		CapturePath: capturePath,
		InstanceID:  instanceID,
		Steps:       steps,
		InitialVars: initialVars,
		CreatedAt:   float64(time.Now().UnixNano()) / 1e9,
		Metadata:    map[string]interface{}{"truncated": truncated},
	}
	r.debugs.store(rec)

	return map[string]interface{}{
		"debug_id":   did,
		"stage":      stage,
		"event_id":   eventID,
		"step_count": len(steps),
		"truncated":  truncated,
	}, ""
}

// ---------------------------------------------------------------------------
// Internal tool implementations
// ---------------------------------------------------------------------------

func (r *Router) handleInternalTool(toolName string, arguments map[string]interface{}) (map[string]interface{}, bool) {
	switch toolName {
	// ---- Existing internal tools ----
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

	// ---- Measurement analysis tools ----
	case "get_gpu_measurement_status":
		mid, _ := arguments["measurement_id"].(string)
		return r.toolGetGPUMeasurementStatus(mid), true
	case "get_gpu_timings":
		mid, _ := arguments["measurement_id"].(string)
		counterID := -1
		if v, ok := arguments["counter_id"]; ok && v != nil {
			counterID = toInt(v)
		}
		limit := 100
		if v, ok := arguments["limit"]; ok && v != nil {
			limit = toInt(v)
		}
		offset := 0
		if v, ok := arguments["offset"]; ok && v != nil {
			offset = toInt(v)
		}
		sortBy, _ := arguments["sort_by"].(string)
		return r.toolGetGPUTimings(mid, counterID, limit, offset, sortBy), true
	case "get_performance_summary":
		mid, _ := arguments["measurement_id"].(string)
		counterID := -1
		if v, ok := arguments["counter_id"]; ok && v != nil {
			counterID = toInt(v)
		}
		topN := 20
		if v, ok := arguments["top_n"]; ok && v != nil {
			topN = toInt(v)
		}
		return r.toolGetPerformanceSummary(mid, counterID, topN), true
	case "get_render_pass_performance":
		mid, _ := arguments["measurement_id"].(string)
		counterID := -1
		if v, ok := arguments["counter_id"]; ok && v != nil {
			counterID = toInt(v)
		}
		return r.toolGetRenderPassPerformance(mid, counterID), true
	case "get_pipeline_statistics":
		mid, _ := arguments["measurement_id"].(string)
		eventID := -1
		if v, ok := arguments["event_id"]; ok && v != nil {
			eventID = toInt(v)
		}
		limit := 100
		if v, ok := arguments["limit"]; ok && v != nil {
			limit = toInt(v)
		}
		offset := 0
		if v, ok := arguments["offset"]; ok && v != nil {
			offset = toInt(v)
		}
		return r.toolGetPipelineStatistics(mid, eventID, limit, offset), true

	// ---- Debug trace tools ----
	case "get_shader_debug_trace":
		did, _ := arguments["debug_id"].(string)
		firstStep := 0
		if v, ok := arguments["first_step"]; ok && v != nil {
			firstStep = toInt(v)
		}
		limit := 0
		if v, ok := arguments["limit"]; ok && v != nil {
			limit = toInt(v)
		}
		return r.toolGetShaderDebugTrace(did, firstStep, limit), true
	case "get_shader_debug_variables":
		did, _ := arguments["debug_id"].(string)
		step := 0
		if v, ok := arguments["step"]; ok && v != nil {
			step = toInt(v)
		}
		return r.toolGetShaderDebugVariables(did, step), true
	case "get_shader_debug_status":
		did, _ := arguments["debug_id"].(string)
		return r.toolGetShaderDebugStatus(did), true

	// ---- Capture registry tools ----
	case "capture_list":
		status, _ := arguments["status"].(string)
		directory, _ := arguments["directory"].(string)
		limit := 50
		if v, ok := arguments["limit"]; ok && v != nil {
			limit = toInt(v)
		}
		offset := 0
		if v, ok := arguments["offset"]; ok && v != nil {
			offset = toInt(v)
		}
		return r.toolCaptureList(status, directory, limit, offset), true
	case "capture_get":
		id, _ := arguments["capture_id"].(string)
		return r.toolCaptureGet(id), true
	case "capture_latest":
		directory, _ := arguments["directory"].(string)
		return r.toolCaptureLatest(directory), true
	case "capture_rescan":
		return r.toolCaptureRescan(), true
	case "capture_registry_status":
		return r.toolCaptureRegistryStatus(), true

	// ---- Instance tools ----
	case "instance_list":
		return r.toolInstanceList(), true

	// ---- Session / operation tools ----
	case "capture_open":
		captureID, _ := arguments["capture_id"].(string)
		openMode, _ := arguments["open_mode"].(string)
		targetSession, _ := arguments["target_session_id"].(string)
		return r.toolCaptureOpen(captureID, openMode, targetSession), true
	case "operation_get":
		opID, _ := arguments["operation_id"].(string)
		return r.toolOperationGet(opID), true
	case "session_list":
		status, _ := arguments["status"].(string)
		managedOnly := false
		if v, ok := arguments["managed_only"].(bool); ok {
			managedOnly = v
		}
		captureID, _ := arguments["capture_id"].(string)
		limit := 50
		if v, ok := arguments["limit"]; ok && v != nil {
			limit = toInt(v)
		}
		offset := 0
		if v, ok := arguments["offset"]; ok && v != nil {
			offset = toInt(v)
		}
		return r.toolSessionList(status, managedOnly, captureID, limit, offset), true
	case "session_get":
		sid, _ := arguments["session_id"].(string)
		return r.toolSessionGet(sid), true
	case "session_focus":
		sid, _ := arguments["session_id"].(string)
		return r.toolSessionFocus(sid), true
	case "session_close":
		sid, _ := arguments["session_id"].(string)
		return r.toolSessionClose(sid), true
	case "session_protect":
		sid, _ := arguments["session_id"].(string)
		protected := true
		if v, ok := arguments["protected"].(bool); ok {
			protected = v
		}
		return r.toolSessionProtect(sid, protected), true
	}
	return nil, false
}

// ---------------------------------------------------------------------------
// Measurement analysis tool implementations
// ---------------------------------------------------------------------------

func (r *Router) toolGetGPUMeasurementStatus(measurementID string) map[string]interface{} {
	if measurementID == "" {
		return map[string]interface{}{"error": "missing_measurement_id"}
	}
	rec := r.measurements.get(measurementID)
	if rec == nil {
		return map[string]interface{}{"error": "measurement_not_found", "measurement_id": measurementID}
	}
	return rec.toDict()
}

func (r *Router) toolGetGPUTimings(measurementID string, counterID, limit, offset int, sortBy string) map[string]interface{} {
	if measurementID == "" {
		return map[string]interface{}{"error": "missing_measurement_id"}
	}
	result, errMsg := r.measurements.queryTimings(measurementID, counterID, limit, offset, sortBy)
	if errMsg != "" {
		return map[string]interface{}{"error": errMsg, "measurement_id": measurementID}
	}
	return result
}

func (r *Router) toolGetPerformanceSummary(measurementID string, counterID, topN int) map[string]interface{} {
	if measurementID == "" {
		return map[string]interface{}{"error": "missing_measurement_id"}
	}
	result, errMsg := r.measurements.queryPerformanceSummary(measurementID, counterID, topN)
	if errMsg != "" {
		return map[string]interface{}{"error": errMsg, "measurement_id": measurementID}
	}
	return result
}

func (r *Router) toolGetRenderPassPerformance(measurementID string, counterID int) map[string]interface{} {
	if measurementID == "" {
		return map[string]interface{}{"error": "missing_measurement_id"}
	}
	rec := r.measurements.get(measurementID)
	if rec == nil {
		return map[string]interface{}{"error": "measurement_not_found", "measurement_id": measurementID}
	}
	if counterID < 0 {
		counterID = autoDetectTimingCounter(rec.CounterDescriptions)
	}
	return map[string]interface{}{
		"measurement_id":   measurementID,
		"counter_id":       counterID,
		"counter_name":     findCounterName(rec.CounterDescriptions, counterID),
		"unit":             findCounterUnit(rec.CounterDescriptions, counterID),
		"passes":           []interface{}{},
		"pass_count":       0,
		"aggregation_note": "event hierarchy not available in Go service; use get_gpu_timings",
	}
}

func (r *Router) toolGetPipelineStatistics(measurementID string, eventID, limit, offset int) map[string]interface{} {
	if measurementID == "" {
		return map[string]interface{}{"error": "missing_measurement_id"}
	}
	result, errMsg := r.measurements.queryPipelineStatistics(measurementID, eventID, limit, offset)
	if errMsg != "" {
		return map[string]interface{}{"error": errMsg, "measurement_id": measurementID}
	}
	return result
}

// ---------------------------------------------------------------------------
// Debug trace tool implementations
// ---------------------------------------------------------------------------

func (r *Router) toolGetShaderDebugTrace(debugID string, firstStep, limit int) map[string]interface{} {
	if debugID == "" {
		return map[string]interface{}{"error": "missing_debug_id"}
	}
	rec := r.debugs.get(debugID)
	if rec == nil {
		return map[string]interface{}{"error": "debug_not_found", "debug_id": debugID}
	}
	steps := rec.Steps
	totalSteps := len(steps)
	if firstStep > totalSteps {
		firstStep = totalSteps
	}
	steps = steps[firstStep:]
	if limit > 0 && len(steps) > limit {
		steps = steps[:limit]
	}
	hasMore := (firstStep + len(steps)) < totalSteps
	return map[string]interface{}{
		"debug_id":       debugID,
		"stage":          rec.Stage,
		"event_id":       rec.EventID,
		"first_step":     firstStep,
		"returned_steps": len(steps),
		"total_steps":    totalSteps,
		"has_more":       hasMore,
		"steps":          steps,
	}
}

func (r *Router) toolGetShaderDebugVariables(debugID string, step int) map[string]interface{} {
	if debugID == "" {
		return map[string]interface{}{"error": "missing_debug_id"}
	}
	rec := r.debugs.get(debugID)
	if rec == nil {
		return map[string]interface{}{"error": "debug_not_found", "debug_id": debugID}
	}
	vars := map[string]interface{}(nil)
	if step == 0 {
		vars = rec.InitialVars
	} else if step < len(rec.Steps) {
		if stepMap, ok := rec.Steps[step].(map[string]interface{}); ok {
			if v, ok := stepMap["variables"]; ok {
				vars, _ = v.(map[string]interface{})
			}
		}
	}
	if vars == nil {
		vars = map[string]interface{}{}
	}
	return map[string]interface{}{
		"debug_id":    debugID,
		"stage":       rec.Stage,
		"event_id":    rec.EventID,
		"step":        step,
		"total_steps": len(rec.Steps),
		"variables":   vars,
	}
}

func (r *Router) toolGetShaderDebugStatus(debugID string) map[string]interface{} {
	if debugID != "" {
		rec := r.debugs.get(debugID)
		if rec == nil {
			return map[string]interface{}{"error": "debug_not_found", "debug_id": debugID}
		}
		return map[string]interface{}{
			"debug_id":   debugID,
			"status":     rec.Status,
			"stage":      rec.Stage,
			"event_id":   rec.EventID,
			"step_count": len(rec.Steps),
			"created_at": rec.CreatedAt,
			"metadata":   rec.Metadata,
		}
	}
	// Return all IDs.
	ids := r.debugs.listIDs()
	idsOut := make([]interface{}, len(ids))
	for i, id := range ids {
		idsOut[i] = id
	}
	return map[string]interface{}{
		"debug_ids": idsOut,
		"count":     len(ids),
	}
}

// ---------------------------------------------------------------------------
// Capture registry tool implementations
// ---------------------------------------------------------------------------

func (r *Router) toolCaptureList(status, directory string, limit, offset int) map[string]interface{} {
	r.mu.Lock()
	cap := r.captures
	r.mu.Unlock()
	if cap == nil {
		return map[string]interface{}{
			"captures": []interface{}{},
			"total":    0,
			"limit":    limit,
			"offset":   offset,
			"message":  "capture registry not initialised",
		}
	}
	return cap.List(status, directory, limit, offset)
}

func (r *Router) toolCaptureGet(captureID string) map[string]interface{} {
	r.mu.Lock()
	cap := r.captures
	r.mu.Unlock()
	if cap == nil {
		return map[string]interface{}{"error": "capture_registry_unavailable"}
	}
	return cap.Get(captureID)
}

func (r *Router) toolCaptureLatest(directory string) map[string]interface{} {
	r.mu.Lock()
	cap := r.captures
	r.mu.Unlock()
	if cap == nil {
		return map[string]interface{}{"error": "no_capture_available"}
	}
	return cap.Latest(directory)
}

func (r *Router) toolCaptureRescan() map[string]interface{} {
	r.mu.Lock()
	cap := r.captures
	r.mu.Unlock()
	if cap == nil {
		return map[string]interface{}{
			"status":  "completed",
			"scanned": 0,
			"new":     0,
			"updated": 0,
			"message": "capture registry not initialised",
		}
	}
	return cap.Rescan()
}

func (r *Router) toolCaptureRegistryStatus() map[string]interface{} {
	r.mu.Lock()
	cap := r.captures
	r.mu.Unlock()
	if cap == nil {
		return map[string]interface{}{
			"enabled":             false,
			"running":             false,
			"total_captures":      0,
			"captures_by_status":  map[string]int{},
			"watched_directories": []interface{}{},
			"message":             "capture registry not initialised",
		}
	}
	return cap.Status()
}

// ---------------------------------------------------------------------------
// Instance tool implementation
// ---------------------------------------------------------------------------

func (r *Router) toolInstanceList() map[string]interface{} {
	if r.instances == nil {
		return map[string]interface{}{
			"instances": []interface{}{},
			"windows":   []interface{}{},
		}
	}
	return r.instances.ListInstances()
}

// ---------------------------------------------------------------------------
// Session / operation tool implementations
// ---------------------------------------------------------------------------

func (r *Router) toolCaptureOpen(captureID, openMode, targetSessionID string) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{
			"error":   "session_manager_unavailable",
			"message": "Session manager is not initialised",
		}
	}
	result, _ := sess.OpenCapture(captureID, openMode, targetSessionID)
	return result
}

func (r *Router) toolOperationGet(operationID string) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{"error": "session_manager_unavailable"}
	}
	return sess.GetOperation(operationID)
}

func (r *Router) toolSessionList(status string, managedOnly bool, captureID string, limit, offset int) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{
			"sessions": []interface{}{},
			"total":    0,
			"limit":    limit,
			"offset":   offset,
		}
	}
	return sess.ListSessions(status, managedOnly, captureID, limit, offset)
}

func (r *Router) toolSessionGet(sessionID string) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{"error": "session_manager_unavailable"}
	}
	return sess.GetSession(sessionID)
}

func (r *Router) toolSessionFocus(sessionID string) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{"error": "session_manager_unavailable"}
	}
	return sess.FocusSession(sessionID)
}

func (r *Router) toolSessionClose(sessionID string) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{"error": "session_manager_unavailable"}
	}
	return sess.CloseSession(sessionID)
}

func (r *Router) toolSessionProtect(sessionID string, protected bool) map[string]interface{} {
	r.mu.Lock()
	sess := r.sessions
	r.mu.Unlock()
	if sess == nil {
		return map[string]interface{}{"error": "session_manager_unavailable"}
	}
	return sess.ProtectSession(sessionID, protected)
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
