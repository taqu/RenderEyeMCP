package sessions

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/operations"
)

// Timing used by capture_open and session_close.
var (
	windowPollTimeout  = 5 * time.Second
	verifyTimeout      = 15 * time.Second
	pollInterval       = 500 * time.Millisecond
	guiCommandTimeout  = 10 * time.Second
	closeWindowTimeout = 3 * time.Second
)

// Error codes shared with the former Python service (errors.py).
const (
	ErrCaptureNotFound       = "capture_not_found"
	ErrSessionNotFound       = "session_not_found"
	ErrSessionProtected      = "session_protected"
	ErrSessionUnmanaged      = "session_unmanaged"
	ErrInstanceNotFound      = "instance_not_found"
	ErrExtensionUnavailable  = "extension_unavailable"
	ErrOperationUnsupported  = "operation_unsupported"
	ErrOperationTimeout      = "operation_timeout"
	ErrInternal              = "internal_error"
	errInvalidStatus         = "invalid_status"
	errSessionManagerMissing = "session_manager_unavailable"
)

var retryable = map[string]bool{ErrOperationTimeout: true, "ipc_disconnected": true, ErrExtensionUnavailable: true}

// ErrorResponse builds the standard structured error result.
func ErrorResponse(code, message string, extra map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{
		"status": "failed",
		"error": map[string]interface{}{
			"code":      code,
			"message":   message,
			"retryable": retryable[code],
		},
	}
	for k, v := range extra {
		out[k] = v
	}
	return out
}

// Extension is the gateway view of a connected RenderDoc extension.
type Extension struct {
	ConnID        string
	InstanceID    string // extension UUID
	ProcessID     int
	CaptureLoaded bool
	CapturePath   *string
}

// GuiCommandResult is the outcome of execute_gui_command.
type GuiCommandResult struct {
	Success bool
	Outcome string
	Error   string
}

// Gateway lets the session manager reach RenderDoc extensions without
// depending on the IPC server package.
type Gateway interface {
	// ExtensionForProcess returns the connected extension running in pid.
	ExtensionForProcess(pid int) (Extension, bool)
	// ExecuteGuiCommand sends execute_gui_command and waits for the result.
	// failure is "" on success, otherwise e.g. "timeout" or "extension_disconnected".
	ExecuteGuiCommand(ctx context.Context, connID, command string, params map[string]interface{}, timeout time.Duration) (res GuiCommandResult, failure string)
}

// CaptureSource resolves capture IDs (implemented by *captures.Registry).
type CaptureSource interface {
	Get(captureID string) (*captures.Record, error)
	Latest(directory string) (*captures.Record, error)
}

// Manager orchestrates managed sessions.  It is safe for concurrent use.
type Manager struct {
	storage      *Storage
	instances    *instances.Manager
	captures     CaptureSource
	ops          *operations.Tracker
	renderdocExe string

	gwMu    sync.RWMutex
	gateway Gateway

	// mu serialises read-modify-write cycles on session records.
	mu sync.Mutex
	// gui holds the non-persisted gui_capture_path / gui_verified_at fields.
	gui map[string]guiState

	// Hooks replaced in tests.
	launch    func(exe, capture string) (instances.LaunchResult, error)
	findExe   func(configured string) string
	focus     func(hwnd uintptr) (bool, string)
	closeWin  func(hwnd uintptr, wait time.Duration) (bool, bool, string)
	isWindow  func(hwnd uintptr) bool
	procAlive func(pid int, createTime float64) bool
}

type guiState struct {
	path       *string
	verifiedAt time.Time
}

// NewManager builds a session manager.
func NewManager(storage *Storage, inst *instances.Manager, caps CaptureSource, ops *operations.Tracker, renderdocExe string) *Manager {
	return &Manager{
		storage:      storage,
		instances:    inst,
		captures:     caps,
		ops:          ops,
		renderdocExe: renderdocExe,
		gui:          map[string]guiState{},
		launch:       instances.Launch,
		findExe:      instances.FindRenderdocExe,
		focus:        instances.FocusWindow,
		closeWin:     instances.CloseWindow,
		isWindow:     instances.IsWindow,
		procAlive:    instances.ProcessAlive,
	}
}

// SetGateway attaches the extension gateway (the IPC router).
func (m *Manager) SetGateway(g Gateway) {
	m.gwMu.Lock()
	m.gateway = g
	m.gwMu.Unlock()
}

func (m *Manager) gw() Gateway {
	m.gwMu.RLock()
	defer m.gwMu.RUnlock()
	return m.gateway
}

func (m *Manager) decorate(rec *Record) *Record {
	m.mu.Lock()
	defer m.mu.Unlock()
	if g, ok := m.gui[rec.SessionID]; ok {
		rec.GUICapturePath = g.path
		t := g.verifiedAt
		rec.GUIVerifiedAt = &t
	}
	return rec
}

func (m *Manager) get(id string) (*Record, error) {
	rec, err := m.storage.Get(id)
	if err != nil || rec == nil {
		return rec, err
	}
	return m.decorate(rec), nil
}

func (m *Manager) save(rec *Record) {
	if err := m.storage.Upsert(rec); err != nil {
		slog.Warn("session storage write failed", "session_id", rec.SessionID, "err", err)
	}
}

func samePath(a, b string) bool {
	ca, cb := filepath.Clean(a), filepath.Clean(b)
	if os.PathSeparator == '\\' {
		return strings.EqualFold(ca, cb)
	}
	return ca == cb
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

// Operation returns a snapshot of a capture_open operation.
func (m *Manager) Operation(id string) (operations.Record, bool) { return m.ops.Get(id) }

// ActiveCount returns the number of active sessions.
func (m *Manager) ActiveCount() int {
	_, n, err := m.storage.List(StatusActive, false, "", 0, 0)
	if err != nil {
		return 0
	}
	return n
}

// List implements session_list.
func (m *Manager) List(status string, managedOnly bool, captureID string, limit, offset int) map[string]interface{} {
	var st Status
	if status != "" {
		valid := false
		for _, s := range AllStatuses {
			if string(s) == status {
				st, valid = s, true
			}
		}
		if !valid {
			names := make([]string, 0, len(AllStatuses))
			for _, s := range AllStatuses {
				names = append(names, string(s))
			}
			return map[string]interface{}{
				"error":          errInvalidStatus,
				"message":        fmt.Sprintf("Unknown status: %q", status),
				"valid_statuses": names,
			}
		}
	}
	recs, total, err := m.storage.List(st, managedOnly, captureID, limit, offset)
	if err != nil {
		return ErrorResponse(ErrInternal, err.Error(), nil)
	}
	out := make([]map[string]interface{}, 0, len(recs))
	for _, r := range recs {
		out = append(out, m.decorate(r).ToMap())
	}
	return map[string]interface{}{"sessions": out, "total": total, "limit": limit, "offset": offset}
}

// Get implements session_get.
func (m *Manager) Get(id string) map[string]interface{} {
	rec, err := m.get(id)
	if err != nil {
		return ErrorResponse(ErrInternal, err.Error(), map[string]interface{}{"session_id": id})
	}
	if rec == nil {
		return map[string]interface{}{"error": "not_found", "session_id": id}
	}
	return rec.ToMap()
}

// Protect implements session_protect.
func (m *Manager) Protect(id string, protected bool) map[string]interface{} {
	rec, err := m.get(id)
	if err != nil {
		return ErrorResponse(ErrInternal, err.Error(), map[string]interface{}{"session_id": id})
	}
	if rec == nil {
		return map[string]interface{}{"error": ErrSessionNotFound, "session_id": id}
	}
	rec.Protected = protected
	rec.UpdatedAt = time.Now().UTC()
	m.save(rec)
	return rec.ToMap()
}

// ---------------------------------------------------------------------------
// Focus / close
// ---------------------------------------------------------------------------

// sessionWindow returns the session's window, verifying that it is owned by
// the session's process.  Window and instance IDs are in-memory counters, so
// after a service restart a persisted window_id may name another process's
// window; such stale IDs are re-associated from the process's own windows and
// never used to focus or close a foreign window.
func (m *Manager) sessionWindow(rec *Record) (instances.Window, bool) {
	if rec.ProcessID == nil {
		return instances.Window{}, false
	}
	pid := *rec.ProcessID
	if rec.WindowID != nil {
		if win, ok := m.instances.Window(*rec.WindowID); ok && win.ProcessID == pid {
			return win, true
		}
	}
	wins := m.instances.WindowsForProcess(pid)
	if len(wins) == 0 {
		return instances.Window{}, false
	}
	win := wins[0]
	id, instID := win.WindowID, win.InstanceID
	rec.WindowID, rec.InstanceID = &id, &instID
	rec.AssociationStatus = AssociationConfirmed
	rec.UpdatedAt = time.Now().UTC()
	m.save(rec)
	return win, true
}

// Focus implements session_focus.
func (m *Manager) Focus(id string) map[string]interface{} {
	rec, err := m.get(id)
	if err != nil {
		return ErrorResponse(ErrInternal, err.Error(), map[string]interface{}{"session_id": id})
	}
	if rec == nil {
		return map[string]interface{}{"error": ErrSessionNotFound, "session_id": id}
	}
	m.instances.Refresh()
	win, ok := m.sessionWindow(rec)
	if !ok {
		msg := "no_window_associated"
		if rec.WindowID != nil {
			msg = "window_not_found"
		}
		return map[string]interface{}{"success": false, "session_id": id, "message": msg}
	}
	success, msg := m.focus(win.HWND)
	return map[string]interface{}{"success": success, "session_id": id, "message": msg}
}

// Close implements session_close (managed, unprotected sessions only).
func (m *Manager) Close(id string) map[string]interface{} {
	extra := map[string]interface{}{"session_id": id}
	rec, err := m.get(id)
	if err != nil {
		return ErrorResponse(ErrInternal, err.Error(), extra)
	}
	if rec == nil {
		return ErrorResponse(ErrSessionNotFound, "Session not found: "+id, extra)
	}
	if !rec.Managed {
		return ErrorResponse(ErrSessionUnmanaged, "Session is not managed by this server", extra)
	}
	if rec.Protected {
		return ErrorResponse(ErrSessionProtected, "Session is protected and cannot be closed", extra)
	}
	m.instances.Refresh()
	if win, ok := m.sessionWindow(rec); ok {
		rec.Status = StatusClosing
		rec.UpdatedAt = time.Now().UTC()
		m.save(rec)
		success, confirmed, msg := m.closeWin(win.HWND, closeWindowTimeout)
		rec.Status = StatusClosed
		rec.UpdatedAt = time.Now().UTC()
		m.save(rec)
		return map[string]interface{}{"success": success, "session_id": id, "confirmed": confirmed, "message": msg}
	}
	rec.Status = StatusClosed
	rec.UpdatedAt = time.Now().UTC()
	m.save(rec)
	return map[string]interface{}{"success": true, "session_id": id, "message": "closed_no_window"}
}

// ---------------------------------------------------------------------------
// capture_open
// ---------------------------------------------------------------------------

// resolveCapture maps "latest" or a capture ID to a READY capture record.
func (m *Manager) resolveCapture(captureID string) *captures.Record {
	if m.captures == nil {
		return nil
	}
	var rec *captures.Record
	var err error
	if captureID == "" || captureID == "latest" {
		rec, err = m.captures.Latest("")
	} else {
		rec, err = m.captures.Get(captureID)
	}
	if err != nil || rec == nil {
		return nil
	}
	if rec.Status != captures.StatusReady {
		slog.Warn("capture is not ready; refusing to open", "capture_id", rec.CaptureID, "status", rec.Status)
		return nil
	}
	return rec
}

type opUpdater struct {
	ops *operations.Tracker
	id  string
}

func (u opUpdater) set(status operations.Status, fn func(*operations.Record)) {
	u.ops.Update(u.id, func(r *operations.Record) {
		r.Status = status
		if fn != nil {
			fn(r)
		}
	})
}

func (u opUpdater) fail(status operations.Status, code, msg string, extra map[string]interface{}) map[string]interface{} {
	u.set(status, func(r *operations.Record) {
		r.ErrorCode = operations.Str(code)
		r.ErrorMessage = msg
	})
	resp := ErrorResponse(code, msg, extra)
	resp["operation_id"] = u.id
	return resp
}

// Open implements capture_open.
func (m *Manager) Open(ctx context.Context, captureID, openMode, targetSessionID string) map[string]interface{} {
	if captureID == "" {
		captureID = "latest"
	}
	if openMode == "" {
		openMode = "new_window"
	}
	op := m.ops.Create("capture_open", captureID, openMode)
	u := opUpdater{ops: m.ops, id: op.OperationID}
	u.set(operations.StatusValidating, nil)

	switch openMode {
	case "new_window", "reuse", "replace":
	default:
		return u.fail(operations.StatusUnsupported, ErrOperationUnsupported,
			fmt.Sprintf("Unknown open_mode %q (expected new_window, reuse or replace)", openMode), nil)
	}

	capRec := m.resolveCapture(captureID)
	if capRec == nil {
		return u.fail(operations.StatusFailed, ErrCaptureNotFound, "Capture not found: "+captureID, nil)
	}
	u.set(operations.StatusValidating, func(r *operations.Record) { r.CaptureID = operations.Str(capRec.CaptureID) })

	if openMode == "reuse" {
		existing, _, err := m.storage.List(StatusActive, false, capRec.CaptureID, 1, 0)
		if err == nil && len(existing) > 0 {
			sess := m.decorate(existing[0])
			u.set(operations.StatusConfirmed, func(r *operations.Record) {
				r.SessionID = operations.Str(sess.SessionID)
				r.InstanceID = sess.InstanceID
				r.WindowID = sess.WindowID
			})
			res := sess.ToMap()
			res["status"] = "confirmed"
			res["operation_id"] = op.OperationID
			return res
		}
		openMode = "new_window"
	}
	if openMode == "replace" {
		return m.openReplace(ctx, u, capRec, targetSessionID)
	}
	return m.openNewWindow(ctx, u, capRec)
}

func (m *Manager) openNewWindow(ctx context.Context, u opUpdater, capRec *captures.Record) map[string]interface{} {
	exe := m.findExe(m.renderdocExe)
	if exe == "" {
		return u.fail(operations.StatusFailed, ErrInstanceNotFound, "RenderDoc executable not found", nil)
	}
	u.set(operations.StatusLaunching, nil)
	launched, err := m.launch(exe, capRec.Path)
	if err != nil {
		return u.fail(operations.StatusFailed, ErrInternal, err.Error(), nil)
	}
	inst := m.instances.RegisterLaunched(launched.PID, launched.CreateTime, exe)

	id, err := m.storage.NextSessionID()
	if err != nil {
		return u.fail(operations.StatusFailed, ErrInternal, err.Error(), nil)
	}
	now := time.Now().UTC()
	pid := launched.PID
	instID := inst.InstanceID
	rec := &Record{
		SessionID: id, CaptureID: capRec.CaptureID, CapturePath: capRec.Path,
		InstanceID: &instID, ProcessID: &pid, Status: StatusActive, Managed: true,
		AssociationStatus: AssociationUnknown, CreatedAt: now, UpdatedAt: now, LastActivityAt: now,
	}
	m.save(rec)
	u.set(operations.StatusWaitingForGUI, func(r *operations.Record) {
		r.SessionID = operations.Str(id)
		r.InstanceID = operations.Str(instID)
	})

	if winID := m.pollForWindow(ctx, instID); winID != "" {
		rec.WindowID = &winID
		rec.AssociationStatus = AssociationConfirmed
		rec.UpdatedAt = time.Now().UTC()
		m.save(rec)
	}

	u.set(operations.StatusVerifying, func(r *operations.Record) { r.WindowID = rec.WindowID })
	if m.waitForLoadedCapture(ctx, pid, capRec.Path) {
		m.mu.Lock()
		p := capRec.Path
		m.gui[id] = guiState{path: &p, verifiedAt: time.Now().UTC()}
		m.mu.Unlock()
		u.set(operations.StatusConfirmed, func(r *operations.Record) { r.LoadedCaptureVerified = true })
		res := m.decorate(rec).ToMap()
		res["status"] = "confirmed"
		res["note"] = launched.Note
		res["operation_id"] = u.id
		return res
	}
	u.set(operations.StatusUnknownOutcome, nil)
	res := rec.ToMap()
	res["status"] = "unknown_outcome"
	res["note"] = launched.Note
	res["message"] = "Session created but GUI state not yet verified by extension"
	res["operation_id"] = u.id
	return res
}

// pollForWindow waits for the launched process to show a window.
func (m *Manager) pollForWindow(ctx context.Context, instanceID string) string {
	deadline := time.Now().Add(windowPollTimeout)
	for {
		m.instances.Refresh()
		if inst, ok := m.instances.Get(instanceID); ok {
			if inst.Status == instances.StatusExited {
				return ""
			}
			if len(inst.Windows) > 0 {
				return inst.Windows[0].WindowID
			}
		}
		if time.Now().After(deadline) || !sleepCtx(ctx, pollInterval) {
			return ""
		}
	}
}

// waitForLoadedCapture waits for the extension in pid to report path loaded.
func (m *Manager) waitForLoadedCapture(ctx context.Context, pid int, path string) bool {
	g := m.gw()
	if g == nil {
		return false
	}
	deadline := time.Now().Add(verifyTimeout)
	for {
		if ext, ok := g.ExtensionForProcess(pid); ok && ext.CaptureLoaded && ext.CapturePath != nil && samePath(*ext.CapturePath, path) {
			return true
		}
		if time.Now().After(deadline) || !sleepCtx(ctx, pollInterval) {
			return false
		}
	}
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

func (m *Manager) openReplace(ctx context.Context, u opUpdater, capRec *captures.Record, targetID string) map[string]interface{} {
	if targetID == "" {
		return u.fail(operations.StatusFailed, ErrSessionNotFound, "replace mode requires target_session_id", nil)
	}
	extra := map[string]interface{}{"session_id": targetID}
	rec, err := m.get(targetID)
	if err != nil {
		return u.fail(operations.StatusFailed, ErrInternal, err.Error(), extra)
	}
	if rec == nil {
		return u.fail(operations.StatusFailed, ErrSessionNotFound, "Session not found: "+targetID, extra)
	}
	if !rec.Managed {
		return u.fail(operations.StatusFailed, ErrSessionUnmanaged, "Session is not managed", extra)
	}
	if rec.Protected {
		return u.fail(operations.StatusFailed, ErrSessionProtected, "Session is protected", extra)
	}
	g := m.gw()
	if g == nil {
		return u.fail(operations.StatusFailed, ErrExtensionUnavailable, "No extension connection manager", extra)
	}
	var ext Extension
	ok := false
	if rec.ProcessID != nil {
		ext, ok = g.ExtensionForProcess(*rec.ProcessID)
	}
	if !ok {
		return u.fail(operations.StatusFailed, ErrExtensionUnavailable, "No active extension connection for this session", extra)
	}

	u.set(operations.StatusWaitingForGUI, func(r *operations.Record) { r.SessionID = operations.Str(targetID) })
	res, failure := g.ExecuteGuiCommand(ctx, ext.ConnID, "open_capture", map[string]interface{}{"path": capRec.Path}, guiCommandTimeout)
	switch failure {
	case "":
	case "timeout":
		return u.fail(operations.StatusTimedOut, ErrOperationTimeout, "Timed out waiting for extension to open capture", extra)
	default:
		return u.fail(operations.StatusFailed, ErrExtensionUnavailable, "Extension command failed: "+failure, extra)
	}
	u.set(operations.StatusVerifying, nil)
	if !res.Success {
		msg := res.Error
		if msg == "" {
			msg = "Extension reported failure"
		}
		return u.fail(operations.StatusFailed, ErrInternal, msg, extra)
	}

	now := time.Now().UTC()
	rec.CaptureID = capRec.CaptureID
	rec.CapturePath = capRec.Path
	rec.UpdatedAt = now
	rec.LastActivityAt = now
	m.save(rec)
	m.mu.Lock()
	p := capRec.Path
	m.gui[targetID] = guiState{path: &p, verifiedAt: now}
	m.mu.Unlock()
	u.set(operations.StatusConfirmed, func(r *operations.Record) {
		r.InstanceID = rec.InstanceID
		r.WindowID = rec.WindowID
		r.LoadedCaptureVerified = true
	})
	out := m.decorate(rec).ToMap()
	out["status"] = "confirmed"
	out["operation_id"] = u.id
	return out
}

// ---------------------------------------------------------------------------
// Extension events and reconciliation
// ---------------------------------------------------------------------------

// sessionsForProcess returns active/disconnected sessions owned by pid.
func (m *Manager) sessionsForProcess(pid int, statuses ...Status) []*Record {
	var out []*Record
	for _, st := range statuses {
		recs, _, err := m.storage.List(st, false, "", 10000, 0)
		if err != nil {
			continue
		}
		for _, r := range recs {
			if r.ProcessID != nil && *r.ProcessID == pid {
				out = append(out, r)
			}
		}
	}
	return out
}

// OnGuiState records the capture an extension (in pid) reports as loaded.
func (m *Manager) OnGuiState(pid int, loaded bool, path *string) {
	now := time.Now().UTC()
	for _, r := range m.sessionsForProcess(pid, StatusActive) {
		m.mu.Lock()
		var p *string
		if loaded && path != nil {
			v := *path
			p = &v
		}
		m.gui[r.SessionID] = guiState{path: p, verifiedAt: now}
		m.mu.Unlock()
	}
}

// OnExtensionConnected re-activates disconnected sessions for pid.
func (m *Manager) OnExtensionConnected(pid int) {
	for _, r := range m.sessionsForProcess(pid, StatusDisconnected) {
		r.Status = StatusActive
		r.UpdatedAt = time.Now().UTC()
		m.save(r)
	}
}

// OnExtensionDisconnected marks the sessions of pid as disconnected without
// touching the RenderDoc process.
func (m *Manager) OnExtensionDisconnected(pid int) {
	for _, r := range m.sessionsForProcess(pid, StatusActive) {
		r.Status = StatusDisconnected
		r.UpdatedAt = time.Now().UTC()
		m.save(r)
		slog.Info("session marked disconnected", "session_id", r.SessionID, "pid", pid)
	}
}

// Reconcile aligns persisted sessions with running processes and windows.
func (m *Manager) Reconcile() (reconciled, recovered, lost int) {
	m.instances.Refresh()
	var toCheck []*Record
	for _, st := range []Status{StatusActive, StatusDisconnected} {
		recs, _, err := m.storage.List(st, false, "", 10000, 0)
		if err == nil {
			toCheck = append(toCheck, recs...)
		}
	}
	now := time.Now().UTC()
	for _, r := range toCheck {
		changed := false
		alive := r.ProcessID != nil && m.procAlive(*r.ProcessID, 0)
		if !alive && r.Status == StatusActive {
			r.Status = StatusDisconnected
			r.AssociationStatus = AssociationLost
			changed = true
			lost++
		} else if alive && r.Status == StatusDisconnected {
			r.Status = StatusActive
			changed = true
			recovered++
		}
		if r.WindowID != nil {
			win, ok := m.instances.Window(*r.WindowID)
			if (!ok || r.ProcessID == nil || win.ProcessID != *r.ProcessID || !m.isWindow(win.HWND)) && r.AssociationStatus != AssociationLost && r.AssociationStatus != AssociationUnknown {
				r.AssociationStatus = AssociationLost
				changed = true
			}
		}
		if changed {
			r.UpdatedAt = now
			m.save(r)
			reconciled++
		}
	}
	return reconciled, recovered, lost
}
