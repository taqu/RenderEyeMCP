//go:build !windows

package bridge

import "syscall"

// detachedSysProcAttr returns a SysProcAttr that starts the child process in a
// new session so it is not killed when the parent bridge process exits.
func detachedSysProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		Setsid: true,
	}
}
