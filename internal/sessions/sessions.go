// Package sessions implements session and operation management.
package sessions

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/instances"
)

// SessionRecord tracks a RenderDoc session.
type SessionRecord struct {
	SessionID           string
	CaptureID           string
	CapturePath         string
	InstanceID          string
	WindowID            string
	ProcessID           int
	Status              string // "active"|"disconnected"|"closing"|"closed"
	Managed             bool
	Protected           bool
	AssociationStatus   string
	CreatedAt           float64
	UpdatedAt           float64
	LastActivityAt      float64
	ErrorMessage        string
	GUICapturePath      string
	GUIVerifiedAt       float64
}

func (s *SessionRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"session_id":           s.SessionID,
		"capture_id":           s.CaptureID,
		"capture_path":         s.CapturePath,
		"instance_id":          s.InstanceID,
		"window_id":            s.WindowID,
		"process_id":           s.ProcessID,
		"status":               s.Status,
		"managed":              s.Managed,
		"protected":            s.Protected,
		"association_status":   s.AssociationStatus,
		"created_at":           s.CreatedAt,
		"updated_at":           s.UpdatedAt,
		"last_activity_at":     s.LastActivityAt,
		"error_message":        s.ErrorMessage,
		"gui_capture_path":     s.GUICapturePath,
		"gui_verified_at":      s.GUIVerifiedAt,
	}
}

// OperationRecord tracks a capture-open or other async operation.
type OperationRecord struct {
	OperationID              string
	OperationType            string
	Status                   string // "requested"|"launching"|"waiting_for_gui"|"confirmed"|"failed"|"timed_out"|"unknown_outcome"
	CaptureID                string
	SessionID                string
	InstanceID               string
	WindowID                 string
	OpenMode                 string
	LoadedCaptureVerified    bool
	ErrorCode                string
	ErrorMessage             string
	CreatedAt                float64
	UpdatedAt                float64
}

func (o *OperationRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"operation_id":             o.OperationID,
		"operation_type":           o.OperationType,
		"status":                   o.Status,
		"capture_id":               o.CaptureID,
		"session_id":               o.SessionID,
		"instance_id":              o.InstanceID,
		"window_id":                o.WindowID,
		"open_mode":                o.OpenMode,
		"loaded_capture_verified":  o.LoadedCaptureVerified,
		"error_code":               o.ErrorCode,
		"error_message":            o.ErrorMessage,
		"created_at":               o.CreatedAt,
		"updated_at":               o.UpdatedAt,
	}
}

// SessionManager manages sessions and operations.
type SessionManager struct {
	mu          sync.Mutex
	sessions    map[string]*SessionRecord
	operations  map[string]*OperationRecord
	sessCounter atomic.Int64
	opCounter   atomic.Int64
	captures    *captures.CaptureRegistry
	instances   *instances.InstanceManager
}

// NewSessionManager creates a new SessionManager.
func NewSessionManager(caps *captures.CaptureRegistry, insts *instances.InstanceManager) *SessionManager {
	return &SessionManager{
		sessions:   make(map[string]*SessionRecord),
		operations: make(map[string]*OperationRecord),
		captures:   caps,
		instances:  insts,
	}
}

func (m *SessionManager) nextSessionID() string {
	return fmt.Sprintf("session-%06d", m.sessCounter.Add(1))
}

func (m *SessionManager) nextOpID() string {
	return fmt.Sprintf("op-%06d", m.opCounter.Add(1))
}

func nowFloat() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}

// OpenCapture opens a capture file in RenderDoc.
// captureID can be an ID like "cap-000001" or "latest".
// openMode: "new_window" | "reuse"
// targetSessionID: optional existing session to reuse.
func (m *SessionManager) OpenCapture(captureID, openMode, targetSessionID string) (map[string]interface{}, error) {
	// Resolve capture.
	var capRec *captures.CaptureRecord
	if captureID == "latest" || captureID == "" {
		capRec = m.captures.GetLatestRecord("")
		if capRec == nil {
			return map[string]interface{}{
				"error":   "no_capture_available",
				"message": "No captures are available in the registry",
			}, nil
		}
		captureID = capRec.CaptureID
	} else {
		capRec = m.captures.GetRecord(captureID)
		if capRec == nil {
			return map[string]interface{}{
				"error":      "capture_not_found",
				"capture_id": captureID,
			}, nil
		}
	}

	// For reuse mode, find an existing active session.
	if openMode == "reuse" || openMode == "" {
		m.mu.Lock()
		for _, sess := range m.sessions {
			if sess.CaptureID == captureID && sess.Status == "active" {
				existing := sess.toDict()
				m.mu.Unlock()
				return map[string]interface{}{
					"session":      existing,
					"session_id":   sess.SessionID,
					"capture_id":   captureID,
					"open_mode":    "reuse",
					"reused":       true,
					"message":      "Reusing existing active session",
				}, nil
			}
		}
		m.mu.Unlock()
		// Fall through to new_window.
		openMode = "new_window"
	}

	// new_window: launch RenderDoc.
	rdocExe := findRenderDocExe()
	now := nowFloat()

	sessID := m.nextSessionID()
	opID := m.nextOpID()

	sess := &SessionRecord{
		SessionID:         sessID,
		CaptureID:         captureID,
		CapturePath:       capRec.Path,
		Status:            "active",
		Managed:           true,
		Protected:         false,
		AssociationStatus: "pending",
		CreatedAt:         now,
		UpdatedAt:         now,
		LastActivityAt:    now,
	}

	op := &OperationRecord{
		OperationID:   opID,
		OperationType: "open_capture",
		Status:        "launching",
		CaptureID:     captureID,
		SessionID:     sessID,
		OpenMode:      openMode,
		CreatedAt:     now,
		UpdatedAt:     now,
	}

	if rdocExe == "" {
		op.Status = "failed"
		op.ErrorCode = "renderdoc_not_found"
		op.ErrorMessage = "RenderDoc executable not found. Set RENDEREYE_RENDERDOC_EXE env var."
		op.UpdatedAt = nowFloat()
		m.mu.Lock()
		m.sessions[sessID] = sess
		m.operations[opID] = op
		m.mu.Unlock()
		return map[string]interface{}{
			"operation_id": opID,
			"session_id":   sessID,
			"capture_id":   captureID,
			"status":       "failed",
			"error":        op.ErrorCode,
			"message":      op.ErrorMessage,
		}, nil
	}

	// Launch RenderDoc asynchronously.
	go func() {
		cmd := exec.Command(rdocExe, capRec.Path)
		cmd.SysProcAttr = detachedSysProcAttr()
		if err := cmd.Start(); err != nil {
			m.mu.Lock()
			op.Status = "failed"
			op.ErrorCode = "launch_failed"
			op.ErrorMessage = err.Error()
			op.UpdatedAt = nowFloat()
			m.mu.Unlock()
			return
		}
		m.mu.Lock()
		op.Status = "unknown_outcome"
		op.UpdatedAt = nowFloat()
		m.mu.Unlock()
	}()

	m.mu.Lock()
	m.sessions[sessID] = sess
	m.operations[opID] = op
	m.mu.Unlock()

	return map[string]interface{}{
		"operation_id": opID,
		"status":       "unknown_outcome",
		"session_id":   sessID,
		"capture_id":   captureID,
		"open_mode":    openMode,
		"message":      "RenderDoc launched; confirm capture is loaded with get_current_capture",
	}, nil
}

// GetOperation returns an operation record by ID.
func (m *SessionManager) GetOperation(opID string) map[string]interface{} {
	m.mu.Lock()
	op, ok := m.operations[opID]
	m.mu.Unlock()
	if !ok {
		return map[string]interface{}{
			"error":        "not_found",
			"operation_id": opID,
		}
	}
	return op.toDict()
}

// ListSessions returns a paginated list of sessions.
func (m *SessionManager) ListSessions(status string, managedOnly bool, captureID string, limit, offset int) map[string]interface{} {
	m.mu.Lock()
	var filtered []*SessionRecord
	for _, sess := range m.sessions {
		if status != "" && sess.Status != status {
			continue
		}
		if managedOnly && !sess.Managed {
			continue
		}
		if captureID != "" && sess.CaptureID != captureID {
			continue
		}
		filtered = append(filtered, sess)
	}
	m.mu.Unlock()

	total := len(filtered)
	if offset > total {
		offset = total
	}
	filtered = filtered[offset:]
	if limit > 0 && len(filtered) > limit {
		filtered = filtered[:limit]
	}

	out := make([]interface{}, len(filtered))
	for i, s := range filtered {
		out[i] = s.toDict()
	}

	return map[string]interface{}{
		"sessions": out,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	}
}

// GetSession returns a session by ID.
func (m *SessionManager) GetSession(sessionID string) map[string]interface{} {
	m.mu.Lock()
	sess, ok := m.sessions[sessionID]
	m.mu.Unlock()
	if !ok {
		return map[string]interface{}{
			"error":      "not_found",
			"session_id": sessionID,
		}
	}
	return sess.toDict()
}

// FocusSession brings a session's window to the foreground.
func (m *SessionManager) FocusSession(sessionID string) map[string]interface{} {
	m.mu.Lock()
	sess, ok := m.sessions[sessionID]
	m.mu.Unlock()
	if !ok {
		return map[string]interface{}{
			"error":      "not_found",
			"session_id": sessionID,
		}
	}

	if m.instances != nil && sess.InstanceID != "" {
		win := m.instances.FindWindowForInstance(sess.InstanceID)
		if win != nil {
			m.instances.FocusWindow(win.HWND)
			return map[string]interface{}{
				"session_id": sessionID,
				"status":     "focused",
				"window_id":  win.WindowID,
			}
		}
	}
	return map[string]interface{}{
		"session_id": sessionID,
		"status":     "no_window_found",
		"message":    "No window found for session",
	}
}

// CloseSession closes an unprotected managed session.
func (m *SessionManager) CloseSession(sessionID string) map[string]interface{} {
	m.mu.Lock()
	defer m.mu.Unlock()
	sess, ok := m.sessions[sessionID]
	if !ok {
		return map[string]interface{}{
			"error":      "not_found",
			"session_id": sessionID,
		}
	}
	if sess.Protected {
		return map[string]interface{}{
			"error":      "session_protected",
			"session_id": sessionID,
			"message":    "Session is protected and cannot be closed",
		}
	}
	sess.Status = "closed"
	sess.UpdatedAt = nowFloat()
	return map[string]interface{}{
		"session_id": sessionID,
		"status":     "closed",
	}
}

// ProtectSession sets or clears the protected flag on a session.
func (m *SessionManager) ProtectSession(sessionID string, protected bool) map[string]interface{} {
	m.mu.Lock()
	defer m.mu.Unlock()
	sess, ok := m.sessions[sessionID]
	if !ok {
		return map[string]interface{}{
			"error":      "not_found",
			"session_id": sessionID,
		}
	}
	sess.Protected = protected
	sess.UpdatedAt = nowFloat()
	return map[string]interface{}{
		"session_id": sessionID,
		"protected":  protected,
		"status":     "updated",
	}
}

// OnGuiStateChanged updates session GUI state when extension reports a change.
func (m *SessionManager) OnGuiStateChanged(connID, capturePath string, captureLoaded bool) {
	now := nowFloat()
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, sess := range m.sessions {
		if sess.InstanceID == connID || sess.CapturePath == capturePath {
			if captureLoaded {
				sess.GUICapturePath = capturePath
				sess.GUIVerifiedAt = now
				sess.Status = "active"
			}
			sess.UpdatedAt = now
			sess.LastActivityAt = now
		}
	}
}

// OnExtensionDisconnected marks sessions as disconnected for a given connection.
func (m *SessionManager) OnExtensionDisconnected(connID string) {
	now := nowFloat()
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, sess := range m.sessions {
		if sess.InstanceID == connID {
			if sess.Status == "active" {
				sess.Status = "disconnected"
				sess.UpdatedAt = now
			}
		}
	}
}

// ---------------------------------------------------------------------------
// RenderDoc executable discovery
// ---------------------------------------------------------------------------

func findRenderDocExe() string {
	// Env var override.
	if env := os.Getenv("RENDEREYE_RENDERDOC_EXE"); env != "" {
		return env
	}

	if runtime.GOOS == "windows" {
		candidates := []string{
			`C:\Program Files\RenderDoc\qrenderdoc.exe`,
			`C:\Program Files (x86)\RenderDoc\qrenderdoc.exe`,
			filepath.Join(os.Getenv("LOCALAPPDATA"), "RenderDoc", "qrenderdoc.exe"),
			filepath.Join(os.Getenv("ProgramFiles"), "RenderDoc", "qrenderdoc.exe"),
		}
		for _, c := range candidates {
			if _, err := os.Stat(c); err == nil {
				return c
			}
		}
		// Try PATH.
		if p, err := exec.LookPath("qrenderdoc"); err == nil {
			return p
		}
		return ""
	}

	// Linux / macOS.
	names := []string{"qrenderdoc", "renderdoc"}
	for _, name := range names {
		if p, err := exec.LookPath(name); err == nil {
			return p
		}
	}
	// Common install paths.
	linuxPaths := []string{
		"/usr/bin/qrenderdoc",
		"/usr/local/bin/qrenderdoc",
	}
	for _, p := range linuxPaths {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// detachedSysProcAttr returns OS-specific SysProcAttr for detached process launch.
// Platform-specific implementations are in sessions_windows.go / sessions_unix.go.

// isRenderDocExeBase checks if a base filename is a RenderDoc executable.
func isRenderDocExeBase(name string) bool {
	lower := strings.ToLower(filepath.Base(name))
	return lower == "qrenderdoc.exe" || lower == "renderdoc.exe" ||
		lower == "qrenderdoc" || lower == "renderdoc"
}
