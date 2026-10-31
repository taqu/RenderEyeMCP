//go:build !windows

package sessions

import (
	"os/exec"
	"syscall"
)

// detachedSysProcAttr returns a SysProcAttr for detached process launch on Unix.
func detachedSysProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		Setsid: true,
	}
}

// setCmd is a no-op shim on Unix.
func setCmd(_ *exec.Cmd) {}
