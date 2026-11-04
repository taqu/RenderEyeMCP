package server

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/ipc"
	"github.com/taqu/rendereye-mcp/internal/toolspec"
)

// sendQueueSize is the capacity of each connection's outbound message channel.
const sendQueueSize = 64

// Failure codes reported when an extension request does not complete.  They
// are returned in both ToolResultMessage.error and result.error, as before.
const (
	failTimeout        = "timeout"
	failDisconnected   = "extension_disconnected"
	failMarshal        = "internal_marshal_error"
	failQueueFull      = "extension_queue_full"
	failCancelled      = "cancelled"
	failInvalidReply   = "invalid_extension_result"
	errUnknownTool     = "unknown_tool"
	errInternalHandler = "internal_error"
)

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

// extReply is the outcome of one request sent to an extension.
type extReply struct {
	// result and errStr are the extension's inspect_capture_result fields.
	result interface{}
	errStr string
	// gui is set for gui_command_result replies.
	gui *ipc.GuiCommandResultMessage
	// failure is non-empty when no reply was received (timeout, disconnect…).
	failure string
}

// pendingCall is a request sent to an extension awaiting its reply.
type pendingCall struct {
	requestID string
	extConnID string
	operation string
	ch        chan extReply // buffered (1); receives exactly one reply
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

// Router is the central coordinator for all client connections and message
// routing.  It is safe for concurrent use.
//
// Every tool call runs in its own goroutine (see connHandler.handleToolCall)
// with a context bounded by the tool's toolspec timeout.  The context is
// cancelled when the originating bridge disconnects or the router closes, so
// composite tools stop issuing further extension requests.
type Router struct {
	serviceInstanceID string
	auth              *Auth
	mu                sync.Mutex
	extensions        map[string]*extState    // connID → ext
	bridges           map[string]*bridgeState // connID → bridge
	pending           map[string]*pendingCall // extension requestID → pending request
	inflight          map[string]map[string]context.CancelFunc

	svc      *Services
	handlers map[string]serviceHandler
	measure  *measurementStore
	debug    *debugStore

	ctx    context.Context
	cancel context.CancelFunc

	// timeoutOverride, when positive, replaces every toolspec timeout (tests).
	timeoutOverride time.Duration
}

// timeout returns d, or the test override when set.
func (r *Router) timeout(d time.Duration) time.Duration {
	if r.timeoutOverride > 0 {
		return r.timeoutOverride
	}
	return d
}

// NewRouter creates a Router without registry/session subsystems (they report
// themselves as unavailable).  Use NewRouterWithServices in production.
func NewRouter(serviceInstanceID string, auth *Auth) *Router {
	return NewRouterWithServices(serviceInstanceID, auth, nil)
}

// NewRouterWithServices creates a Router wired to the given subsystems.
func NewRouterWithServices(serviceInstanceID string, auth *Auth, svc *Services) *Router {
	if svc == nil {
		svc = &Services{}
	}
	ctx, cancel := context.WithCancel(context.Background())
	r := &Router{
		serviceInstanceID: serviceInstanceID,
		auth:              auth,
		extensions:        make(map[string]*extState),
		bridges:           make(map[string]*bridgeState),
		pending:           make(map[string]*pendingCall),
		inflight:          make(map[string]map[string]context.CancelFunc),
		svc:               svc,
		measure:           newMeasurementStore(maxMeasurements),
		debug:             newDebugStore(maxDebugRecords),
		ctx:               ctx,
		cancel:            cancel,
	}
	r.handlers = r.serviceHandlers()
	if svc.Sessions != nil {
		svc.Sessions.SetGateway(r)
	}
	return r
}

// Close cancels every in-flight tool call.  It is safe to call more than once.
func (r *Router) Close() {
	r.cancel()
}

// ---------------------------------------------------------------------------
// Extension registration / state
// ---------------------------------------------------------------------------

// RegisterExtension stores an authenticated extension connection in the router.
func (r *Router) RegisterExtension(connID, instanceID string, processID int, extVersion, rdocVersion string, sendCh chan []byte) {
	r.mu.Lock()
	r.extensions[connID] = &extState{
		connID:      connID,
		instanceID:  instanceID,
		processID:   processID,
		extVersion:  extVersion,
		rdocVersion: rdocVersion,
		connected:   true,
		send:        sendCh,
	}
	r.mu.Unlock()
	if r.svc.Sessions != nil {
		r.svc.Sessions.OnExtensionConnected(processID)
	}
	slog.Info("extension registered", "conn_id", connID, "instance_id", instanceID, "pid", processID)
}

// UpdateGuiState updates cached capture state from a gui_state_changed or
// gui_state_response.  When the loaded capture changes, stored GPU
// measurements and shader debug traces of the previous capture for that
// instance are marked invalidated.
func (r *Router) UpdateGuiState(connID string, revision int, capLoaded bool, capPath *string, capState string) {
	r.mu.Lock()
	ext, ok := r.extensions[connID]
	if !ok || revision <= ext.revision {
		r.mu.Unlock()
		return // unknown or stale
	}
	oldPath := ""
	if ext.capLoaded && ext.capPath != nil {
		oldPath = *ext.capPath
	}
	ext.revision = revision
	ext.capLoaded = capLoaded
	ext.capPath = capPath
	ext.capState = capState
	instanceID, pid := ext.instanceID, ext.processID
	r.mu.Unlock()

	newPath := ""
	if capLoaded && capPath != nil {
		newPath = *capPath
	}
	if oldPath != "" && oldPath != newPath {
		m := r.measure.invalidate(instanceID, oldPath)
		d := r.debug.invalidate(instanceID, oldPath)
		if m+d > 0 {
			slog.Info("capture changed; invalidated stored results", "instance_id", instanceID, "measurements", m, "debug_traces", d)
		}
	}
	if r.svc.Sessions != nil {
		r.svc.Sessions.OnGuiState(pid, capLoaded, capPath)
	}
}

// DisconnectExtension marks an extension as disconnected and fails every
// request still waiting on it.
func (r *Router) DisconnectExtension(connID string) {
	r.mu.Lock()
	pid := 0
	if ext, ok := r.extensions[connID]; ok {
		ext.connected = false
		pid = ext.processID
	}
	var failed []*pendingCall
	for reqID, call := range r.pending {
		if call.extConnID == connID {
			delete(r.pending, reqID)
			failed = append(failed, call)
		}
	}
	r.mu.Unlock()

	for _, call := range failed {
		call.ch <- extReply{failure: failDisconnected}
	}
	if r.svc.Sessions != nil && pid != 0 {
		r.svc.Sessions.OnExtensionDisconnected(pid)
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

// DisconnectBridge removes a bridge and cancels its in-flight tool calls (no
// response is needed since the bridge is gone).
func (r *Router) DisconnectBridge(connID string) {
	r.mu.Lock()
	delete(r.bridges, connID)
	calls := r.inflight[connID]
	delete(r.inflight, connID)
	r.mu.Unlock()
	for _, cancel := range calls {
		cancel()
	}
	slog.Info("bridge disconnected", "conn_id", connID, "cancelled_calls", len(calls))
}

// ---------------------------------------------------------------------------
// Tool call routing
// ---------------------------------------------------------------------------

// toolCall is the parsed form of a tool_call handed to service handlers.
type toolCall struct {
	requestID    string
	bridgeConnID string
	name         string
	args         map[string]interface{}
}

// RouteToolCall executes one tool_call and delivers its tool_result to the
// originating bridge.  It blocks until the call completes; the connection
// handler runs it in its own goroutine.
func (r *Router) RouteToolCall(msg *ipc.ToolCallMessage, bridgeConnID string) {
	args := msg.Arguments
	if args == nil {
		args = map[string]interface{}{}
	}
	call := &toolCall{requestID: msg.RequestID, bridgeConnID: bridgeConnID, name: msg.ToolName, args: args}

	spec, ok := toolspec.Lookup(msg.ToolName)
	if !ok {
		r.reply(call, map[string]interface{}{
			"error":     errUnknownTool,
			"tool_name": msg.ToolName,
			"message":   fmt.Sprintf("Unknown tool %q", msg.ToolName),
		}, "")
		return
	}

	ctx, done := r.beginCall(bridgeConnID, msg.RequestID, r.timeout(spec.Timeout))
	defer done()

	switch spec.Route {
	case toolspec.RouteExtension:
		r.forward(ctx, call, spec)
	case toolspec.RouteService:
		h := r.handlers[spec.Name]
		if h == nil { // guarded by TestEveryToolHasExecutionPath
			r.reply(call, map[string]interface{}{"error": errInternalHandler, "message": "no handler for " + spec.Name}, "")
			return
		}
		result := h(ctx, call)
		if errors.Is(ctx.Err(), context.Canceled) {
			return // cancelled by the client, its bridge disconnecting, or shutdown
		}
		r.reply(call, result, "")
	}
}

// forward sends a RouteExtension tool as a single inspect_capture request.
func (r *Router) forward(ctx context.Context, call *toolCall, spec toolspec.Spec) {
	instanceID, _ := call.args["instance_id"].(string)
	ext, errResult := r.resolveExtension(instanceID)
	if ext == nil {
		r.reply(call, errResult, "")
		return
	}
	params := make(map[string]interface{}, len(call.args))
	for k, v := range call.args {
		if k != "instance_id" {
			params[k] = v
		}
	}
	rep := r.callExtension(ctx, ext, call.requestID, spec.Operation, params, spec.Timeout)
	if rep.failure != "" {
		if rep.failure == failCancelled {
			return // nobody is waiting for this result any more
		}
		r.replyFailure(call, rep.failure, spec.Operation, r.timeout(spec.Timeout))
		return
	}
	r.reply(call, rep.result, rep.errStr)
}

// beginCall derives a per-call context and registers its cancel function
// under the bridge so DisconnectBridge can abort it.
func (r *Router) beginCall(bridgeConnID, requestID string, timeout time.Duration) (context.Context, func()) {
	ctx, cancel := context.WithTimeout(r.ctx, timeout)
	key := fmt.Sprintf("%s#%p", requestID, ctx)
	r.mu.Lock()
	if r.inflight[bridgeConnID] == nil {
		r.inflight[bridgeConnID] = map[string]context.CancelFunc{}
	}
	r.inflight[bridgeConnID][key] = cancel
	r.mu.Unlock()
	return ctx, func() {
		r.mu.Lock()
		if m := r.inflight[bridgeConnID]; m != nil {
			delete(m, key)
			if len(m) == 0 {
				delete(r.inflight, bridgeConnID)
			}
		}
		r.mu.Unlock()
		cancel()
	}
}

// CancelToolCall cancels the in-flight call requestID of a bridge (sent as
// tool_cancel when the MCP client abandons a call).  Composite tools stop
// before their next extension request; an extension operation already running
// on RenderDoc's GUI thread cannot be interrupted and its late result is
// discarded.  It reports whether a call was found.
func (r *Router) CancelToolCall(bridgeConnID, requestID string) bool {
	prefix := requestID + "#"
	var cancels []context.CancelFunc
	r.mu.Lock()
	for key, cancel := range r.inflight[bridgeConnID] {
		if strings.HasPrefix(key, prefix) {
			cancels = append(cancels, cancel)
		}
	}
	r.mu.Unlock()
	for _, c := range cancels {
		c()
	}
	return len(cancels) > 0
}

func (r *Router) bridgeGone(bridgeConnID string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	_, ok := r.bridges[bridgeConnID]
	return !ok
}

// reply sends a tool_result to the call's bridge (dropped if it is gone).
func (r *Router) reply(call *toolCall, result interface{}, errMsg string) {
	r.mu.Lock()
	bridge := r.bridges[call.bridgeConnID]
	r.mu.Unlock()
	if bridge != nil {
		safeSend(bridge.send, marshalToolResult(call.requestID, call.name, result, errMsg))
	}
}

func failureMessage(failure, operation string, timeout time.Duration) string {
	switch failure {
	case failTimeout:
		return fmt.Sprintf("RenderDoc extension did not answer %q within %s (RenderDoc busy or blocked by a dialog)", operation, timeout)
	case failDisconnected:
		return "RenderDoc extension disconnected before answering"
	case failQueueFull:
		return "RenderDoc extension outbound queue is full; retry later"
	case failCancelled:
		return "Tool call cancelled"
	case failMarshal:
		return "Could not serialise the request for the extension"
	}
	return failure
}

// replyFailure reports a transport-level failure in the legacy shape
// ({"error": code, "message": …} plus ToolResultMessage.error = code).
func (r *Router) replyFailure(call *toolCall, failure, operation string, timeout time.Duration) {
	r.reply(call, map[string]interface{}{
		"error":   failure,
		"message": failureMessage(failure, operation, timeout),
	}, failure)
}

// callExtension sends one inspect_capture request and waits for its result,
// the per-request timeout, cancellation of ctx, or extension disconnect.
func (r *Router) callExtension(ctx context.Context, ext *extState, requestID, operation string, params map[string]interface{}, timeout time.Duration) extReply {
	if params == nil {
		params = map[string]interface{}{}
	}
	return r.request(ctx, ext, requestID, operation, timeout, func(id string) []byte {
		return marshalInspectCapture(id, operation, params)
	})
}

// request implements the request/response exchange shared by inspect_capture
// and execute_gui_command.
func (r *Router) request(ctx context.Context, ext *extState, requestID, operation string, timeout time.Duration, build func(id string) []byte) extReply {
	timeout = r.timeout(timeout)
	call := &pendingCall{extConnID: ext.connID, operation: operation, ch: make(chan extReply, 1)}

	r.mu.Lock()
	if !ext.connected {
		r.mu.Unlock()
		return extReply{failure: failDisconnected}
	}
	if requestID == "" || r.pending[requestID] != nil {
		requestID = newUUID()
	}
	call.requestID = requestID
	r.pending[requestID] = call
	r.mu.Unlock()

	remove := func() {
		r.mu.Lock()
		if r.pending[requestID] == call {
			delete(r.pending, requestID)
		}
		r.mu.Unlock()
	}

	data := build(requestID)
	if data == nil {
		remove()
		return extReply{failure: failMarshal}
	}
	if !safeSend(ext.send, data) {
		remove()
		return extReply{failure: failQueueFull}
	}

	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case rep := <-call.ch:
		return rep
	case <-timer.C:
		remove()
		slog.Warn("extension request timed out", "operation", operation, "timeout", timeout, "ext", ext.connID)
		return extReply{failure: failTimeout}
	case <-ctx.Done():
		remove()
		if ctx.Err() == context.DeadlineExceeded {
			return extReply{failure: failTimeout}
		}
		return extReply{failure: failCancelled}
	}
}

// deliver hands a reply to the pending request, if still waiting.  When
// fromConnID is non-empty the reply is only accepted from the extension the
// request was sent to.
func (r *Router) deliver(fromConnID, requestID string, rep extReply) {
	r.mu.Lock()
	call := r.pending[requestID]
	if call != nil && fromConnID != "" && call.extConnID != fromConnID {
		r.mu.Unlock()
		slog.Warn("ignoring reply from a different extension", "request_id", requestID, "from", fromConnID)
		return
	}
	if call != nil {
		delete(r.pending, requestID)
	}
	r.mu.Unlock()
	if call != nil {
		call.ch <- rep
	}
}

// RouteInspectCaptureResult delivers an inspect_capture_result to the waiting
// tool call.  Late results (after timeout/cancel) are dropped.
func (r *Router) RouteInspectCaptureResult(msg *ipc.InspectCaptureResultMessage) {
	r.RouteInspectCaptureResultFrom("", msg)
}

// RouteInspectCaptureResultFrom is RouteInspectCaptureResult restricted to
// replies from the extension connection extConnID.
func (r *Router) RouteInspectCaptureResultFrom(extConnID string, msg *ipc.InspectCaptureResultMessage) {
	r.deliver(extConnID, msg.RequestID, extReply{result: msg.Result, errStr: msg.Error})
}

// RouteGuiCommandResult delivers a gui_command_result from extConnID to the
// waiting caller.
func (r *Router) RouteGuiCommandResult(extConnID string, msg *ipc.GuiCommandResultMessage) {
	r.deliver(extConnID, msg.RequestID, extReply{gui: msg})
}

// ---------------------------------------------------------------------------
// Extension selection
// ---------------------------------------------------------------------------

// selectExtension picks the target extension: the one matching instanceID, or
// the only connected one, or the only connected one with a loaded capture.
// It returns nil when no extension qualifies or the choice is ambiguous.
func (r *Router) selectExtension(instanceID string) *extState {
	ext, _ := r.resolveExtension(instanceID)
	return ext
}

// resolveExtension is selectExtension plus the structured result to return
// when no extension can be selected.
func (r *Router) resolveExtension(instanceID string) (*extState, map[string]interface{}) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if instanceID != "" {
		var disconnected *extState
		for _, e := range r.extensions {
			if e.instanceID != instanceID {
				continue
			}
			if e.connected {
				return e, nil
			}
			disconnected = e
		}
		if disconnected != nil {
			return nil, map[string]interface{}{
				"status":           "session_disconnected",
				"instance_id":      instanceID,
				"connection_state": "disconnected",
				"message":          "The specified RenderDoc GUI session is not currently connected",
			}
		}
		return nil, map[string]interface{}{
			"status":      "session_not_found",
			"instance_id": instanceID,
			"message":     fmt.Sprintf("No RenderDoc GUI session found with instance_id=%q", instanceID),
		}
	}

	var connected, loaded []*extState
	for _, e := range r.extensions {
		if e.connected {
			connected = append(connected, e)
			if e.capLoaded {
				loaded = append(loaded, e)
			}
		}
	}
	switch {
	case len(connected) == 0:
		return nil, map[string]interface{}{
			"status":  "no_renderdoc_connected",
			"message": "No RenderDoc GUI instances are currently connected",
		}
	case len(connected) == 1:
		return connected[0], nil
	case len(loaded) == 1:
		return loaded[0], nil
	}
	candidates := loaded
	if len(candidates) == 0 {
		candidates = connected
	}
	return nil, map[string]interface{}{
		"status": "ambiguous",
		"message": fmt.Sprintf("Multiple RenderDoc GUI sessions are connected (%d, %d with a loaded capture). "+
			"Specify instance_id to target a specific session.", len(connected), len(loaded)),
		"sessions": guiSessionList(candidates),
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func guiSessionList(exts []*extState) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(exts))
	for _, e := range exts {
		out = append(out, e.toGuiSessionDict())
	}
	return out
}

// safeSend attempts to send data on ch without blocking.  If the queue is full
// (or the connection is closing) the message is dropped with a warning and
// false is returned (bounded queue policy).
func safeSend(ch chan []byte, data []byte) (sent bool) {
	defer func() {
		if recover() != nil { // channel closed by a disconnecting handler
			sent = false
		}
	}()
	select {
	case ch <- data:
		return true
	default:
		slog.Warn("outbound queue full; message dropped")
		return false
	}
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
// bridge processes know the service is accepting connections.
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
