//go:build !windows

package instances

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

var guiExeNames = map[string]bool{"qrenderdoc": true}

var defaultExeCandidates = []string{"/usr/bin/qrenderdoc", "/usr/local/bin/qrenderdoc"}

// listGUIProcesses scans /proc where available (Linux); elsewhere it returns nil.
func listGUIProcesses() []ProcInfo {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil
	}
	var out []ProcInfo
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		comm, err := os.ReadFile(filepath.Join("/proc", e.Name(), "comm"))
		if err != nil {
			continue
		}
		name := strings.TrimSpace(string(comm))
		if !guiExeNames[strings.ToLower(name)] {
			continue
		}
		exe, _ := os.Readlink(filepath.Join("/proc", e.Name(), "exe"))
		out = append(out, ProcInfo{PID: pid, Name: name, Exe: exe})
	}
	return out
}

func processAlive(pid int, _ float64) bool {
	if pid <= 0 {
		return false
	}
	return syscall.Kill(pid, 0) == nil
}

func processCreateTime(int) (float64, bool) { return 0, false }

func enumWindows(int) []WindowInfo { return nil }

func isWindow(uintptr) bool { return false }

func focusWindow(uintptr) (bool, string) { return false, "unsupported_platform" }

func closeWindow(uintptr, time.Duration) (bool, bool, string) {
	return false, false, "unsupported_platform"
}

const windowControlSupported = false
