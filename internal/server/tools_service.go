package server

import (
	"context"
	"fmt"
	"math"
	"runtime"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/ipc"
	"github.com/taqu/rendereye-mcp/internal/sessions"
)

// Services are the optional subsystems behind service-routed tools.  A nil
// member makes the corresponding tools report themselves unavailable with
// the same structured results the former Python service used.
type Services struct {
	RenderdocExe string
	Captures     *captures.Registry
	Sessions     *sessions.Manager
	Instances    *instances.Manager
}

// serviceHandler implements one RouteService tool.  It must honour ctx.
type serviceHandler func(ctx context.Context, call *toolCall) map[string]interface{}

// serviceHandlers is the handler table for every toolspec.RouteService tool.
// TestEveryToolHasExecutionPath keeps it in sync with the catalog.
func (r *Router) serviceHandlers() map[string]serviceHandler {
	return map[string]serviceHandler{
		// Diagnostics and GUI state discovery.
		"server_status":               r.toolServerStatus,
		"list_renderdoc_sessions":     r.toolListRenderdocSessions,
		"get_renderdoc_session_state": r.toolGetRenderdocSessionState,
		"get_current_capture":         r.toolGetCurrentCapture,
		"instance_gui_state":          r.toolInstanceGuiState,

		// Capture registry.
		"capture_list":            r.toolCaptureList,
		"capture_get":             r.toolCaptureGet,
		"capture_latest":          r.toolCaptureLatest,
		"capture_rescan":          r.toolCaptureRescan,
		"capture_registry_status": r.toolCaptureRegistryStatus,

		// Instances, managed sessions and operations.
		"instance_list":   r.toolInstanceList,
		"capture_open":    r.toolCaptureOpen,
		"operation_get":   r.toolOperationGet,
		"session_list":    r.toolSessionList,
		"session_get":     r.toolSessionGet,
		"session_focus":   r.toolSessionFocus,
		"session_close":   r.toolSessionClose,
		"session_protect": r.toolSessionProtect,

		// GPU performance measurement store.
		"collect_gpu_counters":        r.toolCollectGPUCounters,
		"get_gpu_measurement_status":  r.toolGetGPUMeasurementStatus,
		"get_gpu_timings":             r.toolGetGPUTimings,
		"get_performance_summary":     r.toolGetPerformanceSummary,
		"get_render_pass_performance": r.toolGetRenderPassPerformance,
		"get_pipeline_statistics":     r.toolGetPipelineStatistics,

		// Shader debugging store.
		"debug_pixel_shader":         r.toolDebugPixelShader,
		"debug_vertex_shader":        r.toolDebugVertexShader,
		"debug_compute_shader":       r.toolDebugComputeShader,
		"get_shader_debug_trace":     r.toolGetShaderDebugTrace,
		"get_shader_debug_variables": r.toolGetShaderDebugVariables,
		"get_shader_debug_status":    r.toolGetShaderDebugStatus,
	}
}

// ---------------------------------------------------------------------------
// Argument helpers (JSON numbers arrive as float64)
// ---------------------------------------------------------------------------

func argString(args map[string]interface{}, key, def string) string {
	if v, ok := args[key].(string); ok {
		return v
	}
	return def
}

func toInt(v interface{}) (int, bool) {
	switch n := v.(type) {
	case float64:
		if math.IsNaN(n) || math.IsInf(n, 0) {
			return 0, false
		}
		return int(n), true
	case int:
		return n, true
	case int64:
		return int(n), true
	case string:
		var i int
		if _, err := fmt.Sscan(n, &i); err == nil {
			return i, true
		}
	}
	return 0, false
}

func argInt(args map[string]interface{}, key string, def int) int {
	if v, ok := toInt(args[key]); ok {
		return v
	}
	return def
}

// argIntPtr returns nil when the key is absent or null.
func argIntPtr(args map[string]interface{}, key string) *int {
	if v, ok := toInt(args[key]); ok {
		return &v
	}
	return nil
}

func argFloatPtr(args map[string]interface{}, key string) *float64 {
	switch n := args[key].(type) {
	case float64:
		return &n
	case int:
		f := float64(n)
		return &f
	}
	return nil
}

func argBool(args map[string]interface{}, key string, def bool) bool {
	if v, ok := args[key].(bool); ok {
		return v
	}
	return def
}

func argStringList(args map[string]interface{}, key string) []string {
	raw, ok := args[key].([]interface{})
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, v := range raw {
		if s, ok := v.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// ---------------------------------------------------------------------------
// Diagnostics and GUI state discovery
// ---------------------------------------------------------------------------

func (r *Router) toolServerStatus(context.Context, *toolCall) map[string]interface{} {
	r.mu.Lock()
	extCount := len(r.extensions)
	activeExt := 0
	for _, e := range r.extensions {
		if e.connected {
			activeExt++
		}
	}
	r.mu.Unlock()

	rdocPath := instances.FindRenderdocExe(r.svc.RenderdocExe)
	var rdocPathVal interface{}
	if rdocPath != "" {
		rdocPathVal = rdocPath
	}
	activeSessions := 0
	if r.svc.Sessions != nil {
		activeSessions = r.svc.Sessions.ActiveCount()
	}
	return map[string]interface{}{
		"server_name":                  "RenderEyeMCP",
		"server_version":               config.GoServiceVersion,
		"os":                           runtime.GOOS,
		"go_version":                   runtime.Version(),
		"renderdoc_detected":           rdocPath != "",
		"renderdoc_path":               rdocPathVal,
		"ipc_listener_status":          "running",
		"extension_connections":        extCount,
		"active_extension_connections": activeExt,
		"active_sessions":              activeSessions,
		"ipc_protocol_version":         ipc.ProtocolVersion,
		"service_instance_id":          r.serviceInstanceID,
	}
}

func (r *Router) toolListRenderdocSessions(context.Context, *toolCall) map[string]interface{} {
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

func (r *Router) toolGetRenderdocSessionState(_ context.Context, call *toolCall) map[string]interface{} {
	instanceID := argString(call.args, "instance_id", "")
	r.mu.Lock()
	defer r.mu.Unlock()
	var disconnected *extState
	for _, e := range r.extensions {
		if e.instanceID == instanceID {
			if e.connected {
				return e.toGuiSessionDict()
			}
			disconnected = e
		}
	}
	if disconnected != nil {
		return disconnected.toGuiSessionDict()
	}
	return map[string]interface{}{
		"error":       "session_not_found",
		"instance_id": instanceID,
		"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
	}
}

func (r *Router) toolGetCurrentCapture(_ context.Context, call *toolCall) map[string]interface{} {
	instanceID := argString(call.args, "instance_id", "")
	r.mu.Lock()
	defer r.mu.Unlock()

	if instanceID != "" {
		var match *extState
		for _, e := range r.extensions {
			if e.instanceID == instanceID && (match == nil || e.connected) {
				match = e
			}
		}
		if match != nil {
			return captureStatusForExt(match)
		}
		return map[string]interface{}{
			"status":      "session_not_found",
			"instance_id": instanceID,
			"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
		}
	}

	var connected, loaded, loading []*extState
	for _, e := range r.extensions {
		if !e.connected {
			continue
		}
		connected = append(connected, e)
		if e.capLoaded {
			loaded = append(loaded, e)
		} else if e.capState == "loading" {
			loading = append(loading, e)
		}
	}
	switch {
	case len(connected) == 0:
		return map[string]interface{}{
			"status":  "no_renderdoc_connected",
			"message": "No RenderDoc GUI instances are currently connected",
		}
	case len(loaded) == 1:
		return captureStatusForExt(loaded[0])
	case len(loaded) > 1:
		return map[string]interface{}{
			"status":   "ambiguous",
			"message":  fmt.Sprintf("Multiple RenderDoc GUI sessions have a capture loaded (%d). Specify instance_id.", len(loaded)),
			"sessions": guiSessionList(loaded),
		}
	case len(loading) > 0:
		return map[string]interface{}{
			"status":   "capture_loading",
			"message":  "A capture is currently loading",
			"sessions": guiSessionList(loading),
		}
	}
	return map[string]interface{}{
		"status":   "no_capture_loaded",
		"message":  "Connected RenderDoc GUI instance(s) have no capture loaded",
		"sessions": guiSessionList(connected),
	}
}

func captureStatusForExt(e *extState) map[string]interface{} {
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

func (r *Router) toolInstanceGuiState(_ context.Context, call *toolCall) map[string]interface{} {
	instanceID := argString(call.args, "instance_id", "")
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, e := range r.extensions {
		if e.instanceID == instanceID && e.connected {
			return map[string]interface{}{
				"connection_id":      e.connID,
				"instance_id":        e.instanceID,
				"process_id":         e.processID,
				"extension_version":  e.extVersion,
				"renderdoc_version":  e.rdocVersion,
				"connected":          e.connected,
				"connection_state":   "connected",
				"capture_loaded":     e.capLoaded,
				"capture_path":       e.capPath,
				"capture_state":      e.capState,
				"gui_state_revision": e.revision,
				"freshness":          "fresh",
			}
		}
	}
	return map[string]interface{}{
		"instance_id":    instanceID,
		"connected":      false,
		"capture_loaded": false,
		"capture_path":   nil,
		"capture_state":  "unknown",
		"freshness":      "unavailable",
	}
}

// ---------------------------------------------------------------------------
// Capture registry
// ---------------------------------------------------------------------------

func internalError(err error) map[string]interface{} {
	return sessions.ErrorResponse(sessions.ErrInternal, err.Error(), nil)
}

func (r *Router) toolCaptureList(_ context.Context, call *toolCall) map[string]interface{} {
	limit := argInt(call.args, "limit", 50)
	offset := clamp(argInt(call.args, "offset", 0), 0, math.MaxInt32)
	if limit < 0 {
		limit = 0
	}
	if r.svc.Captures == nil {
		return map[string]interface{}{"captures": []interface{}{}, "total": 0, "limit": limit, "offset": offset}
	}
	var status captures.Status
	if s := argString(call.args, "status", ""); s != "" {
		st, ok := captures.ParseStatus(s)
		if !ok {
			valid := make([]string, 0, len(captures.AllStatuses))
			for _, v := range captures.AllStatuses {
				valid = append(valid, string(v))
			}
			return map[string]interface{}{
				"error":          "invalid_status",
				"message":        fmt.Sprintf("Unknown status: %q", s),
				"valid_statuses": valid,
			}
		}
		status = st
	}
	recs, total, err := r.svc.Captures.List(status, argString(call.args, "directory", ""), limit, offset)
	if err != nil {
		return internalError(err)
	}
	out := make([]map[string]interface{}, 0, len(recs))
	for _, rec := range recs {
		out = append(out, rec.ToMap())
	}
	return map[string]interface{}{"captures": out, "total": total, "limit": limit, "offset": offset}
}

func (r *Router) toolCaptureGet(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "capture_id", "")
	if r.svc.Captures == nil {
		return map[string]interface{}{"error": "not_found", "capture_id": id}
	}
	rec, err := r.svc.Captures.Get(id)
	if err != nil {
		return internalError(err)
	}
	if rec == nil {
		return map[string]interface{}{"error": "not_found", "capture_id": id}
	}
	return rec.ToMap()
}

func (r *Router) toolCaptureLatest(_ context.Context, call *toolCall) map[string]interface{} {
	if r.svc.Captures == nil {
		return map[string]interface{}{"error": "no_capture_available"}
	}
	dir := argString(call.args, "directory", "")
	rec, err := r.svc.Captures.Latest(dir)
	if err != nil {
		return internalError(err)
	}
	if rec == nil && argBool(call.args, "include_pending", false) {
		recs, _, err := r.svc.Captures.List(captures.StatusPending, dir, 1, 0)
		if err != nil {
			return internalError(err)
		}
		if len(recs) > 0 {
			rec = recs[0]
		}
	}
	if rec == nil {
		return map[string]interface{}{"error": "no_capture_available"}
	}
	return rec.ToMap()
}

func (r *Router) toolCaptureRescan(context.Context, *toolCall) map[string]interface{} {
	if r.svc.Captures == nil {
		return map[string]interface{}{"status": "unavailable", "message": "Registry not initialized"}
	}
	scanned, added, updated, err := r.svc.Captures.Rescan()
	if err != nil {
		return internalError(err)
	}
	return map[string]interface{}{"status": "completed", "scanned": scanned, "new": added, "updated": updated}
}

func (r *Router) toolCaptureRegistryStatus(context.Context, *toolCall) map[string]interface{} {
	if r.svc.Captures == nil {
		return map[string]interface{}{"enabled": false, "running": false, "message": "Registry not initialized"}
	}
	return r.svc.Captures.Status()
}

// ---------------------------------------------------------------------------
// Instances, managed sessions and operations
// ---------------------------------------------------------------------------

func (r *Router) toolInstanceList(context.Context, *toolCall) map[string]interface{} {
	if r.svc.Instances == nil {
		return map[string]interface{}{"instances": []interface{}{}, "windows": []interface{}{}}
	}
	r.svc.Instances.Refresh()
	insts := r.svc.Instances.List()
	out := make([]map[string]interface{}, 0, len(insts))
	for _, inst := range insts {
		m := inst.ToMap()
		m["extension_connected"] = false
		m["extension_capture_path"] = nil
		if ext, ok := r.ExtensionForProcess(inst.ProcessID); ok {
			m["extension_connected"] = true
			m["extension_instance_id"] = ext.InstanceID
			if ext.CaptureLoaded {
				m["extension_capture_path"] = ext.CapturePath
			}
		}
		out = append(out, m)
	}
	wins := r.svc.Instances.Windows()
	winOut := make([]map[string]interface{}, 0, len(wins))
	for _, w := range wins {
		winOut = append(winOut, w.ToMap())
	}
	return map[string]interface{}{"instances": out, "windows": winOut}
}

func (r *Router) sessionsUnavailable(extra map[string]interface{}) map[string]interface{} {
	return sessions.ErrorResponse(sessions.ErrExtensionUnavailable, "Session manager not initialized", extra)
}

func (r *Router) toolCaptureOpen(ctx context.Context, call *toolCall) map[string]interface{} {
	if r.svc.Sessions == nil {
		return r.sessionsUnavailable(nil)
	}
	return r.svc.Sessions.Open(ctx,
		argString(call.args, "capture_id", "latest"),
		argString(call.args, "open_mode", "new_window"),
		argString(call.args, "target_session_id", ""))
}

func (r *Router) toolOperationGet(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "operation_id", "")
	extra := map[string]interface{}{"operation_id": id}
	if r.svc.Sessions == nil {
		return sessions.ErrorResponse(sessions.ErrInternal, "Operation tracker not initialized", extra)
	}
	op, ok := r.svc.Sessions.Operation(id)
	if !ok {
		return sessions.ErrorResponse(sessions.ErrOperationUnsupported, "Operation not found: "+id, extra)
	}
	return op.ToMap()
}

func (r *Router) toolSessionList(_ context.Context, call *toolCall) map[string]interface{} {
	limit := argInt(call.args, "limit", 50)
	offset := clamp(argInt(call.args, "offset", 0), 0, math.MaxInt32)
	if r.svc.Sessions == nil {
		return map[string]interface{}{"sessions": []interface{}{}, "total": 0, "limit": limit, "offset": offset}
	}
	return r.svc.Sessions.List(argString(call.args, "status", ""), argBool(call.args, "managed_only", false),
		argString(call.args, "capture_id", ""), limit, offset)
}

func (r *Router) toolSessionGet(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "session_id", "")
	if r.svc.Sessions == nil {
		return map[string]interface{}{"error": "session_manager_unavailable", "session_id": id}
	}
	return r.svc.Sessions.Get(id)
}

func (r *Router) toolSessionFocus(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "session_id", "")
	if r.svc.Sessions == nil {
		return map[string]interface{}{"error": "session_manager_unavailable", "session_id": id}
	}
	return r.svc.Sessions.Focus(id)
}

func (r *Router) toolSessionClose(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "session_id", "")
	if r.svc.Sessions == nil {
		return r.sessionsUnavailable(map[string]interface{}{"session_id": id})
	}
	return r.svc.Sessions.Close(id)
}

func (r *Router) toolSessionProtect(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "session_id", "")
	if r.svc.Sessions == nil {
		return map[string]interface{}{"error": "session_manager_unavailable", "session_id": id}
	}
	protected, ok := call.args["protected"].(bool)
	if !ok {
		return map[string]interface{}{"error": "invalid_arguments", "message": "protected (boolean) is required", "session_id": id}
	}
	return r.svc.Sessions.Protect(id, protected)
}
