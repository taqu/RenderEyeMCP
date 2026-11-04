// Package instances discovers running RenderDoc GUI processes and their
// top-level windows, launches RenderDoc, and focuses/closes windows.
package instances

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/store"
)

// ProcInfo describes a running RenderDoc GUI process.
type ProcInfo struct {
	PID        int
	Name       string
	Exe        string
	CreateTime float64 // Unix seconds; 0 when unknown
}

// WindowInfo describes a top-level window.
type WindowInfo struct {
	HWND    uintptr
	Title   string
	Visible bool
}

func absf(f float64) float64 { return math.Abs(f) }

// Ownership classifies whether this service launched the process.
type Ownership string

const (
	OwnershipManaged  Ownership = "managed"
	OwnershipExternal Ownership = "external"
)

// Status of a tracked process.
type Status string

const (
	StatusRunning Status = "running"
	StatusExited  Status = "exited"
)

// Window is a top-level window of a RenderDoc process.
type Window struct {
	WindowID   string
	HWND       uintptr
	InstanceID string
	ProcessID  int
	Title      string
	Visible    bool
	LastSeenAt time.Time
}

// ToMap serialises the window for instance_list.
func (w Window) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"window_id":    w.WindowID,
		"hwnd":         uint64(w.HWND),
		"instance_id":  w.InstanceID,
		"process_id":   w.ProcessID,
		"title":        w.Title,
		"visible":      w.Visible,
		"last_seen_at": store.FormatTime(w.LastSeenAt),
		"session_id":   nil,
	}
}

// Instance is a RenderDoc GUI process.  Instance IDs ("instance-NNNNNN")
// identify processes and are distinct from the extension instance_id UUIDs
// reported over IPC; the two are correlated by process ID.
type Instance struct {
	InstanceID        string
	ProcessID         int
	ProcessCreateTime float64
	ExePath           string
	Ownership         Ownership
	Status            Status
	Windows           []Window
	LastSeenAt        *time.Time
}

// ToMap serialises the instance for instance_list.
func (i Instance) ToMap() map[string]interface{} {
	wins := make([]map[string]interface{}, 0, len(i.Windows))
	for _, w := range i.Windows {
		wins = append(wins, w.ToMap())
	}
	return map[string]interface{}{
		"instance_id":         i.InstanceID,
		"process_id":          i.ProcessID,
		"process_create_time": i.ProcessCreateTime,
		"exe_path":            i.ExePath,
		"ownership":           string(i.Ownership),
		"status":              string(i.Status),
		"windows":             wins,
		"last_seen_at":        store.NullTime(i.LastSeenAt),
		"command_line":        "",
	}
}

// Manager tracks known instances and windows.  It is safe for concurrent use.
type Manager struct {
	mu          sync.Mutex
	instances   map[string]*Instance
	managedPIDs map[int]bool
	windowIDs   map[uintptr]string // hwnd -> stable window ID
	nextInst    int
	nextWin     int

	// Platform hooks (replaced in tests).
	listProcs   func() []ProcInfo
	listWindows func(pid int) []WindowInfo
}

// NewManager returns a manager using the native platform hooks.
func NewManager() *Manager { return NewManagerWith(listGUIProcesses, enumWindows) }

// NewManagerWith returns a manager using custom process/window enumeration
// (used by tests and non-native platforms).
func NewManagerWith(listProcs func() []ProcInfo, listWindows func(pid int) []WindowInfo) *Manager {
	return &Manager{
		instances:   map[string]*Instance{},
		managedPIDs: map[int]bool{},
		windowIDs:   map[uintptr]string{},
		nextInst:    1,
		nextWin:     1,
		listProcs:   listProcs,
		listWindows: listWindows,
	}
}

func sameProcess(a, b float64) bool {
	return a == 0 || b == 0 || absf(a-b) < 1.0
}

// Refresh re-enumerates processes and windows.
func (m *Manager) Refresh() {
	procs := m.listProcs()
	wins := make(map[int][]WindowInfo, len(procs))
	for _, p := range procs {
		wins[p.PID] = m.listWindows(p.PID)
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	now := time.Now().UTC()
	seen := map[string]bool{}
	for _, p := range procs {
		var inst *Instance
		for _, existing := range m.instances {
			if existing.ProcessID == p.PID && sameProcess(existing.ProcessCreateTime, p.CreateTime) && !seen[existing.InstanceID] {
				inst = existing
				break
			}
		}
		if inst == nil {
			inst = &Instance{InstanceID: m.nextInstanceID(), ProcessID: p.PID, ProcessCreateTime: p.CreateTime, Ownership: OwnershipExternal}
			m.instances[inst.InstanceID] = inst
		}
		if inst.ProcessCreateTime == 0 {
			inst.ProcessCreateTime = p.CreateTime
		}
		if p.Exe != "" {
			inst.ExePath = p.Exe
		}
		if m.managedPIDs[p.PID] {
			inst.Ownership = OwnershipManaged
		}
		inst.Status = StatusRunning
		t := now
		inst.LastSeenAt = &t
		inst.Windows = nil
		for _, w := range wins[p.PID] {
			id, ok := m.windowIDs[w.HWND]
			if !ok {
				id = fmt.Sprintf("window-%06d", m.nextWin)
				m.nextWin++
				m.windowIDs[w.HWND] = id
			}
			inst.Windows = append(inst.Windows, Window{
				WindowID: id, HWND: w.HWND, InstanceID: inst.InstanceID, ProcessID: p.PID,
				Title: w.Title, Visible: w.Visible, LastSeenAt: now,
			})
		}
		seen[inst.InstanceID] = true
	}
	for id, inst := range m.instances {
		if !seen[id] {
			inst.Status = StatusExited
			inst.Windows = nil
		}
	}
}

func (m *Manager) nextInstanceID() string {
	id := fmt.Sprintf("instance-%06d", m.nextInst)
	m.nextInst++
	return id
}

// RegisterLaunched records a process this service launched as managed.
func (m *Manager) RegisterLaunched(pid int, createTime float64, exe string) Instance {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.managedPIDs[pid] = true
	now := time.Now().UTC()
	inst := &Instance{
		InstanceID: m.nextInstanceID(), ProcessID: pid, ProcessCreateTime: createTime,
		ExePath: exe, Ownership: OwnershipManaged, Status: StatusRunning, LastSeenAt: &now,
	}
	m.instances[inst.InstanceID] = inst
	return *inst
}

func snapshot(inst *Instance) Instance {
	cp := *inst
	cp.Windows = append([]Window(nil), inst.Windows...)
	return cp
}

// Get returns a snapshot of the instance.
func (m *Manager) Get(id string) (Instance, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	inst, ok := m.instances[id]
	if !ok {
		return Instance{}, false
	}
	return snapshot(inst), true
}

// List returns snapshots of all instances ordered by instance ID.
func (m *Manager) List() []Instance {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]Instance, 0, len(m.instances))
	for _, inst := range m.instances {
		out = append(out, snapshot(inst))
	}
	sort.Slice(out, func(i, j int) bool { return out[i].InstanceID < out[j].InstanceID })
	return out
}

// Windows returns every known window.
func (m *Manager) Windows() []Window {
	out := []Window{}
	for _, inst := range m.List() {
		out = append(out, inst.Windows...)
	}
	return out
}

// Window returns the window with windowID.
func (m *Manager) Window(windowID string) (Window, bool) {
	for _, w := range m.Windows() {
		if w.WindowID == windowID {
			return w, true
		}
	}
	return Window{}, false
}

// WindowsForProcess returns the windows of running instances with pid.
func (m *Manager) WindowsForProcess(pid int) []Window {
	var out []Window
	for _, inst := range m.List() {
		if inst.ProcessID == pid && inst.Status == StatusRunning {
			out = append(out, inst.Windows...)
		}
	}
	return out
}

// WindowsFor returns the windows of instanceID.
func (m *Manager) WindowsFor(instanceID string) []Window {
	inst, ok := m.Get(instanceID)
	if !ok {
		return nil
	}
	return inst.Windows
}

// ---------------------------------------------------------------------------
// Platform operations
// ---------------------------------------------------------------------------

// ProcessAlive reports whether pid (with matching create time) is running.
func ProcessAlive(pid int, createTime float64) bool { return processAlive(pid, createTime) }

// IsWindow reports whether hwnd is still a valid window.
func IsWindow(hwnd uintptr) bool { return isWindow(hwnd) }

// FocusWindow restores and foregrounds hwnd.
func FocusWindow(hwnd uintptr) (bool, string) { return focusWindow(hwnd) }

// CloseWindow sends WM_CLOSE and waits for the window to disappear.
func CloseWindow(hwnd uintptr, wait time.Duration) (success, confirmed bool, message string) {
	return closeWindow(hwnd, wait)
}

// WindowControlSupported reports whether focus/close are implemented here.
func WindowControlSupported() bool { return windowControlSupported }

// FindRenderdocExe returns the configured executable if it exists, otherwise
// the first existing standard install location; "" when none is found.
func FindRenderdocExe(configured string) string {
	if configured != "" {
		if st, err := os.Stat(configured); err == nil && !st.IsDir() {
			if abs, err := filepath.Abs(configured); err == nil {
				return abs
			}
			return configured
		}
		return ""
	}
	for _, c := range defaultExeCandidates {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c
		}
	}
	if p, err := exec.LookPath("qrenderdoc"); err == nil {
		return p
	}
	return ""
}

// LaunchResult describes a RenderDoc launch.
type LaunchResult struct {
	PID        int
	CreateTime float64
	Note       string
}

// LaunchNote documents that RenderDoc may route a file to an existing window.
const LaunchNote = "RenderDoc may route to an existing window; window association requires post-launch discovery."

// Launch starts exe with capturePath as its only argument (no shell).
func Launch(exe, capturePath string) (LaunchResult, error) {
	if st, err := os.Stat(exe); err != nil || st.IsDir() {
		return LaunchResult{Note: LaunchNote}, fmt.Errorf("executable not found: %s", exe)
	}
	if st, err := os.Stat(capturePath); err != nil || st.IsDir() {
		return LaunchResult{Note: LaunchNote}, fmt.Errorf("capture file not found: %s", capturePath)
	}
	cmd := exec.Command(exe, capturePath)
	if err := cmd.Start(); err != nil {
		return LaunchResult{Note: LaunchNote}, err
	}
	pid := cmd.Process.Pid
	ct, _ := processCreateTime(pid)
	go cmd.Wait() //nolint:errcheck // reap the child; RenderDoc outlives the call
	return LaunchResult{PID: pid, CreateTime: ct, Note: LaunchNote}, nil
}
