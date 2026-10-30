//go:build !windows

// Package lifecycle provides cross-platform service startup coordination.
package lifecycle

import (
	"fmt"
	"os"
	"syscall"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
)

// ServiceStartupLock coordinates service startup via a Unix advisory file lock.
type ServiceStartupLock struct {
	timeout time.Duration
	fp      *os.File
}

// NewServiceStartupLock returns a lock with the given acquisition timeout.
func NewServiceStartupLock(timeout time.Duration) *ServiceStartupLock {
	return &ServiceStartupLock{timeout: timeout}
}

// Acquire attempts to obtain an exclusive flock within the configured timeout.
func (l *ServiceStartupLock) Acquire() error {
	path := config.LockFilePath()
	fp, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY, 0600)
	if err != nil {
		return fmt.Errorf("open lock file: %w", err)
	}

	deadline := time.Now().Add(l.timeout)
	for {
		err = syscall.Flock(int(fp.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			l.fp = fp
			return nil
		}
		if err != syscall.EWOULDBLOCK {
			fp.Close()
			return fmt.Errorf("flock: %w", err)
		}
		if time.Now().After(deadline) {
			fp.Close()
			return fmt.Errorf("could not acquire startup lock within %v", l.timeout)
		}
		time.Sleep(100 * time.Millisecond)
	}
}

// Release releases the flock and closes the file.
func (l *ServiceStartupLock) Release() {
	if l.fp != nil {
		syscall.Flock(int(l.fp.Fd()), syscall.LOCK_UN) //nolint:errcheck
		l.fp.Close()
		l.fp = nil
	}
}
