//go:build windows

// Package lifecycle provides cross-platform service startup coordination.
package lifecycle

import (
	"fmt"
	"syscall"
	"time"
	"unsafe"
)

const mutexName = "Local\\RenderEyeMCPServiceStartup"

var (
	kernel32             = syscall.NewLazyDLL("kernel32.dll")
	procCreateMutexW     = kernel32.NewProc("CreateMutexW")
	procWaitForSingleObject = kernel32.NewProc("WaitForSingleObject")
	procReleaseMutex     = kernel32.NewProc("ReleaseMutex")
	procCloseHandle      = kernel32.NewProc("CloseHandle")
)

const (
	waitObject0   = 0x00000000
	waitAbandoned = 0x00000080
	waitTimeout   = 0x00000102
	infinite      = 0xFFFFFFFF
)

// ServiceStartupLock coordinates service startup via a Windows named mutex
// so that exactly one process creates the service.
type ServiceStartupLock struct {
	timeout time.Duration
	handle  uintptr
}

// NewServiceStartupLock returns a lock with the given acquisition timeout.
func NewServiceStartupLock(timeout time.Duration) *ServiceStartupLock {
	return &ServiceStartupLock{timeout: timeout}
}

// Acquire attempts to take the named mutex within the configured timeout.
func (l *ServiceStartupLock) Acquire() error {
	name, err := syscall.UTF16PtrFromString(mutexName)
	if err != nil {
		return fmt.Errorf("UTF16PtrFromString: %w", err)
	}
	h, _, e := procCreateMutexW.Call(0, 0, uintptr(unsafe.Pointer(name)))
	if h == 0 {
		return fmt.Errorf("CreateMutexW failed: %v", e)
	}

	ms := uint32(l.timeout.Milliseconds())
	ret, _, _ := procWaitForSingleObject.Call(h, uintptr(ms))
	switch ret {
	case waitObject0, waitAbandoned:
		l.handle = h
		return nil
	case waitTimeout:
		procCloseHandle.Call(h)
		return fmt.Errorf("could not acquire startup lock within %v", l.timeout)
	default:
		procCloseHandle.Call(h)
		return fmt.Errorf("WaitForSingleObject returned %#x", ret)
	}
}

// Release releases and closes the named mutex handle.
func (l *ServiceStartupLock) Release() {
	if l.handle != 0 {
		procReleaseMutex.Call(l.handle)
		procCloseHandle.Call(l.handle)
		l.handle = 0
	}
}
