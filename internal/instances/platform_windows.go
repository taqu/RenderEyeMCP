//go:build windows

package instances

import (
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	user32                  = windows.NewLazySystemDLL("user32.dll")
	procGetWindowTextW      = user32.NewProc("GetWindowTextW")
	procShowWindow          = user32.NewProc("ShowWindow")
	procSetForegroundWindow = user32.NewProc("SetForegroundWindow")
	procPostMessageW        = user32.NewProc("PostMessageW")
)

const (
	wmClose   = 0x0010
	swRestore = 9
)

// guiExeNames identifies RenderDoc GUI processes (not renderdoccmd).
var guiExeNames = map[string]bool{"qrenderdoc.exe": true, "renderdocui.exe": true}

// defaultExeCandidates are probed when RENDEREYE_RENDERDOC_EXE is unset.
var defaultExeCandidates = []string{
	`C:\Program Files\RenderDoc\qrenderdoc.exe`,
	`C:\Program Files (x86)\RenderDoc\qrenderdoc.exe`,
}

func filetimeToUnix(ft windows.Filetime) float64 {
	return float64(ft.Nanoseconds()) / float64(time.Second)
}

// processCreateTime returns the process creation time (Unix seconds).
func processCreateTime(pid int) (float64, bool) {
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, uint32(pid))
	if err != nil {
		return 0, false
	}
	defer windows.CloseHandle(h)
	var c, e, k, u windows.Filetime
	if err := windows.GetProcessTimes(h, &c, &e, &k, &u); err != nil {
		return 0, false
	}
	return filetimeToUnix(c), true
}

func processExePath(pid int) string {
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, uint32(pid))
	if err != nil {
		return ""
	}
	defer windows.CloseHandle(h)
	buf := make([]uint16, windows.MAX_LONG_PATH)
	n := uint32(len(buf))
	if err := windows.QueryFullProcessImageName(h, 0, &buf[0], &n); err != nil {
		return ""
	}
	return windows.UTF16ToString(buf[:n])
}

// listGUIProcesses enumerates running RenderDoc GUI processes.
func listGUIProcesses() []ProcInfo {
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil
	}
	defer windows.CloseHandle(snap)
	var out []ProcInfo
	var pe windows.ProcessEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	for err = windows.Process32First(snap, &pe); err == nil; err = windows.Process32Next(snap, &pe) {
		name := windows.UTF16ToString(pe.ExeFile[:])
		if !guiExeNames[strings.ToLower(name)] {
			continue
		}
		pid := int(pe.ProcessID)
		ct, _ := processCreateTime(pid)
		out = append(out, ProcInfo{PID: pid, Name: name, Exe: processExePath(pid), CreateTime: ct})
	}
	return out
}

// processAlive reports whether pid is running (and, when createTime > 0,
// is the same process instance).
func processAlive(pid int, createTime float64) bool {
	if pid <= 0 {
		return false
	}
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, uint32(pid))
	if err != nil {
		return false
	}
	defer windows.CloseHandle(h)
	var code uint32
	if err := windows.GetExitCodeProcess(h, &code); err != nil || code != 259 /* STILL_ACTIVE */ {
		return false
	}
	if createTime > 0 {
		if ct, ok := processCreateTime(pid); ok && absf(ct-createTime) >= 1.0 {
			return false
		}
	}
	return true
}

// syscall.NewCallback slots are never freed (the runtime allows ~2000), so a
// single callback is created once and fed through package state guarded by
// enumMu.
var (
	enumMu  sync.Mutex
	enumPID int
	enumOut []WindowInfo
	enumCB  = syscall.NewCallback(func(hwnd windows.HWND, _ uintptr) uintptr {
		var owner uint32
		if _, err := windows.GetWindowThreadProcessId(hwnd, &owner); err != nil || int(owner) != enumPID {
			return 1
		}
		buf := make([]uint16, 256)
		n, _, _ := procGetWindowTextW.Call(uintptr(hwnd), uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
		enumOut = append(enumOut, WindowInfo{
			HWND:    uintptr(hwnd),
			Title:   windows.UTF16ToString(buf[:n]),
			Visible: windows.IsWindowVisible(hwnd),
		})
		return 1
	})
)

// enumWindows returns the top-level windows owned by pid.
func enumWindows(pid int) []WindowInfo {
	enumMu.Lock()
	defer enumMu.Unlock()
	enumPID, enumOut = pid, nil
	_ = windows.EnumWindows(enumCB, nil)
	out := enumOut
	enumOut = nil
	return out
}

func isWindow(hwnd uintptr) bool { return windows.IsWindow(windows.HWND(hwnd)) }

// focusWindow restores and foregrounds hwnd.  Windows may refuse foreground
// activation for background processes ("denied_by_windows").
func focusWindow(hwnd uintptr) (bool, string) {
	if !isWindow(hwnd) {
		return false, "window_not_found"
	}
	procShowWindow.Call(hwnd, swRestore) //nolint:errcheck
	if r, _, _ := procSetForegroundWindow.Call(hwnd); r != 0 {
		return true, "focused"
	}
	return false, "denied_by_windows"
}

// closeWindow posts WM_CLOSE (never TerminateProcess) and waits up to wait
// for the window to disappear.
func closeWindow(hwnd uintptr, wait time.Duration) (success, confirmed bool, message string) {
	if !isWindow(hwnd) {
		return true, true, "window_already_gone"
	}
	procPostMessageW.Call(hwnd, wmClose, 0, 0) //nolint:errcheck
	deadline := time.Now().Add(wait)
	for time.Now().Before(deadline) {
		if !isWindow(hwnd) {
			return true, true, "window_closed"
		}
		time.Sleep(100 * time.Millisecond)
	}
	if !isWindow(hwnd) {
		return true, true, "window_closed"
	}
	return false, false, "timeout_window_still_exists"
}

const windowControlSupported = true
