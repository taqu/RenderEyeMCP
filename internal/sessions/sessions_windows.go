//go:build windows

package sessions

import (
	"os/exec"
	"syscall"
)

// detachedSysProcAttr returns a SysProcAttr that launches the process detached
// from the current console on Windows.
func detachedSysProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP,
	}
}

// setCmd is a no-op shim; the caller sets cmd.SysProcAttr directly.
func setCmd(_ *exec.Cmd) {}
