//go:build windows

package instances

import (
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

var (
	modKernel32 = syscall.NewLazyDLL("kernel32.dll")
	modUser32   = syscall.NewLazyDLL("user32.dll")
	modPsapi    = syscall.NewLazyDLL("psapi.dll")

	procEnumWindows              = modUser32.NewProc("EnumWindows")
	procGetWindowThreadProcessId = modUser32.NewProc("GetWindowThreadProcessId")
	procGetWindowTextW           = modUser32.NewProc("GetWindowTextW")
	procIsWindowVisible          = modUser32.NewProc("IsWindowVisible")
	procSetForegroundWindow      = modUser32.NewProc("SetForegroundWindow")
	procEnumProcesses            = modPsapi.NewProc("EnumProcesses")
	procGetProcessImageFileNameW = modPsapi.NewProc("GetProcessImageFileNameW")
	procOpenProcess              = modKernel32.NewProc("OpenProcess")
	procCloseHandle              = modKernel32.NewProc("CloseHandle")
)

const (
	processQueryLimitedInformation = 0x1000
	processQueryInformation        = 0x0400
)

// InstanceRecord holds discovered information about a RenderDoc process.
type InstanceRecord struct {
	InstanceID string
	ProcessID  int
	ExePath    string
	Status     string // "running" | "exited"
	Ownership  string // "managed" | "external"
	Windows    []*WindowRecord
	LastSeenAt float64
}

func (r *InstanceRecord) toDict() map[string]interface{} {
	windows := make([]interface{}, len(r.Windows))
	for i, w := range r.Windows {
		windows[i] = w.toDict()
	}
	return map[string]interface{}{
		"instance_id": r.InstanceID,
		"process_id":  r.ProcessID,
		"exe_path":    r.ExePath,
		"status":      r.Status,
		"ownership":   r.Ownership,
		"windows":     windows,
		"last_seen_at": r.LastSeenAt,
	}
}

// WindowRecord holds information about a top-level window of a RenderDoc process.
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

// InstanceManager discovers and tracks RenderDoc processes and their windows.
type InstanceManager struct {
	mu          sync.Mutex
	instances   map[int]*InstanceRecord  // pid → instance
	windows     map[uintptr]*WindowRecord // hwnd → window
	instCounter atomic.Int64
	winCounter  atomic.Int64
}

// NewInstanceManager creates a new InstanceManager.
func NewInstanceManager() *InstanceManager {
	return &InstanceManager{
		instances: make(map[int]*InstanceRecord),
		windows:   make(map[uintptr]*WindowRecord),
	}
}

// Refresh scans for RenderDoc processes and their windows.
func (m *InstanceManager) Refresh() {
	pids, exes := enumerateProcesses()
	now := float64(time.Now().UnixNano()) / 1e9

	m.mu.Lock()
	defer m.mu.Unlock()

	// Mark all existing instances as exited.
	for _, inst := range m.instances {
		inst.Status = "exited"
	}

	// Update/add instances for discovered processes.
	for i, pid := range pids {
		exe := exes[i]
		if !isRenderDocExe(exe) {
			continue
		}
		inst, ok := m.instances[pid]
		if !ok {
			id := fmt.Sprintf("instance-%06d", m.instCounter.Add(1))
			inst = &InstanceRecord{
				InstanceID: id,
				ProcessID:  pid,
				ExePath:    exe,
				Status:     "running",
				Ownership:  "external",
				Windows:    nil,
				LastSeenAt: now,
			}
			m.instances[pid] = inst
		} else {
			inst.Status = "running"
			inst.LastSeenAt = now
		}
	}

	// Clear windows on running instances.
	for _, inst := range m.instances {
		if inst.Status == "running" {
			inst.Windows = nil
		}
	}
	// Clear window map for fresh enumeration.
	m.windows = make(map[uintptr]*WindowRecord)

	// Enumerate top-level windows.
	windowsByPID := enumerateWindows(m)
	for pid, wins := range windowsByPID {
		inst, ok := m.instances[pid]
		if !ok || inst.Status != "running" {
			continue
		}
		for _, w := range wins {
			w.InstanceID = inst.InstanceID
			inst.Windows = append(inst.Windows, w)
			m.windows[w.HWND] = w
		}
	}
}

// FocusWindow brings a window with the given HWND to the foreground.
func (m *InstanceManager) FocusWindow(hwnd uintptr) bool {
	ret, _, _ := procSetForegroundWindow.Call(hwnd)
	return ret != 0
}

// ListInstances returns all tracked instances and windows.
func (m *InstanceManager) ListInstances() map[string]interface{} {
	m.Refresh()
	m.mu.Lock()
	defer m.mu.Unlock()

	insts := make([]interface{}, 0)
	allWindows := make([]interface{}, 0)

	for _, inst := range m.instances {
		if inst.Status != "running" {
			continue
		}
		insts = append(insts, inst.toDict())
		for _, w := range inst.Windows {
			allWindows = append(allWindows, w.toDict())
		}
	}
	return map[string]interface{}{
		"instances": insts,
		"windows":   allWindows,
	}
}

// GetInstance returns info for a specific instance by ID.
func (m *InstanceManager) GetInstance(id string) *InstanceRecord {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, inst := range m.instances {
		if inst.InstanceID == id {
			return inst
		}
	}
	return nil
}

// FindWindowForInstance returns the first visible window for an instance.
func (m *InstanceManager) FindWindowForInstance(instanceID string) *WindowRecord {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, inst := range m.instances {
		if inst.InstanceID != instanceID {
			continue
		}
		for _, w := range inst.Windows {
			if w.Visible {
				return w
			}
		}
		if len(inst.Windows) > 0 {
			return inst.Windows[0]
		}
	}
	return nil
}

// ---------------------------------------------------------------------------
// Windows API helpers
// ---------------------------------------------------------------------------

func isRenderDocExe(path string) bool {
	lower := strings.ToLower(path)
	base := lower
	if idx := strings.LastIndexAny(lower, `/\`); idx >= 0 {
		base = lower[idx+1:]
	}
	return base == "qrenderdoc.exe" || base == "renderdoc.exe" || strings.Contains(base, "qrenderdoc") || strings.Contains(base, "renderdoc")
}

func enumerateProcesses() (pids []int, exes []string) {
	buf := make([]uint32, 4096)
	var needed uint32
	r, _, _ := procEnumProcesses.Call(
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(len(buf)*4),
		uintptr(unsafe.Pointer(&needed)),
	)
	if r == 0 {
		return
	}
	count := int(needed) / 4
	for i := 0; i < count; i++ {
		pid := int(buf[i])
		if pid == 0 {
			continue
		}
		exe := getProcessExe(pid)
		if exe != "" {
			pids = append(pids, pid)
			exes = append(exes, exe)
		}
	}
	return
}

func getProcessExe(pid int) string {
	handle, _, _ := procOpenProcess.Call(
		processQueryLimitedInformation,
		0,
		uintptr(pid),
	)
	if handle == 0 {
		// Try with a different access level.
		handle, _, _ = procOpenProcess.Call(
			processQueryInformation,
			0,
			uintptr(pid),
		)
		if handle == 0 {
			return ""
		}
	}
	defer procCloseHandle.Call(handle)

	buf := make([]uint16, 260)
	size := uint32(len(buf))
	r, _, _ := procGetProcessImageFileNameW.Call(
		handle,
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(size),
	)
	if r == 0 {
		return ""
	}
	return syscall.UTF16ToString(buf[:r])
}

type windowEnumState struct {
	mgr     *InstanceManager
	results map[int][]*WindowRecord
}

func enumerateWindows(mgr *InstanceManager) map[int][]*WindowRecord {
	state := &windowEnumState{
		mgr:     mgr,
		results: make(map[int][]*WindowRecord),
	}
	cb := syscall.NewCallback(func(hwnd syscall.Handle, lParam uintptr) uintptr {
		s := (*windowEnumState)(unsafe.Pointer(lParam))
		var pid uint32
		procGetWindowThreadProcessId.Call(uintptr(hwnd), uintptr(unsafe.Pointer(&pid)))

		// Only care about windows belonging to known RenderDoc instances.
		s.mgr.mu.Lock()
		_, known := s.mgr.instances[int(pid)]
		s.mgr.mu.Unlock()
		if !known {
			return 1 // continue
		}

		var titleBuf [512]uint16
		n, _, _ := procGetWindowTextW.Call(uintptr(hwnd), uintptr(unsafe.Pointer(&titleBuf[0])), uintptr(len(titleBuf)))
		title := ""
		if n > 0 {
			title = syscall.UTF16ToString(titleBuf[:n])
		}
		vis, _, _ := procIsWindowVisible.Call(uintptr(hwnd))

		now := float64(time.Now().UnixNano()) / 1e9
		w := &WindowRecord{
			WindowID:   fmt.Sprintf("window-%06d", s.mgr.winCounter.Add(1)),
			HWND:       uintptr(hwnd),
			ProcessID:  int(pid),
			Title:      title,
			Visible:    vis != 0,
			LastSeenAt: now,
		}
		s.results[int(pid)] = append(s.results[int(pid)], w)
		return 1 // continue
	})
	procEnumWindows.Call(cb, uintptr(unsafe.Pointer(state)))
	return state.results
}
