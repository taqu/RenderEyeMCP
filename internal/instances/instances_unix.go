//go:build !windows

package instances

// InstanceRecord holds discovered information about a RenderDoc process.
type InstanceRecord struct {
	InstanceID string
	ProcessID  int
	ExePath    string
	Status     string
	Ownership  string
	Windows    []*WindowRecord
	LastSeenAt float64
}

func (r *InstanceRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"instance_id":  r.InstanceID,
		"process_id":   r.ProcessID,
		"exe_path":     r.ExePath,
		"status":       r.Status,
		"ownership":    r.Ownership,
		"windows":      []interface{}{},
		"last_seen_at": r.LastSeenAt,
	}
}

// WindowRecord holds information about a top-level window.
type WindowRecord struct {
	WindowID   string
	HWND       uintptr
	InstanceID string
	ProcessID  int
	Title      string
	Visible    bool
	LastSeenAt float64
}

func (w *WindowRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"window_id":    w.WindowID,
		"hwnd":         w.HWND,
		"instance_id":  w.InstanceID,
		"process_id":   w.ProcessID,
		"title":        w.Title,
		"visible":      w.Visible,
		"last_seen_at": w.LastSeenAt,
	}
}

// InstanceManager is a stub on non-Windows platforms.
type InstanceManager struct{}

// NewInstanceManager returns a stub InstanceManager.
func NewInstanceManager() *InstanceManager {
	return &InstanceManager{}
}

// Refresh is a no-op on non-Windows.
func (m *InstanceManager) Refresh() {}

// ListInstances returns a not-supported message on non-Windows.
func (m *InstanceManager) ListInstances() map[string]interface{} {
	return map[string]interface{}{
		"instances": []interface{}{},
		"windows":   []interface{}{},
		"message":   "instance discovery not supported on this platform",
	}
}

// GetInstance always returns nil on non-Windows.
func (m *InstanceManager) GetInstance(id string) *InstanceRecord {
	return nil
}

// FocusWindow is a no-op on non-Windows.
func (m *InstanceManager) FocusWindow(hwnd uintptr) bool {
	return false
}

// FindWindowForInstance always returns nil on non-Windows.
func (m *InstanceManager) FindWindowForInstance(instanceID string) *WindowRecord {
	return nil
}
