//go:build windows

package bridge

import "syscall"

// detachedSysProcAttr returns a SysProcAttr that starts the child process in a
// new process group so it is not killed when the parent bridge process exits.
func detachedSysProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP,
	}
}
