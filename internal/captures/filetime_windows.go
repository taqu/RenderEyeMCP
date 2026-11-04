//go:build windows

package captures

import (
	"os"
	"syscall"
	"time"
)

// creationTime returns the filesystem creation time when the platform records it.
func creationTime(fi os.FileInfo) *time.Time {
	if d, ok := fi.Sys().(*syscall.Win32FileAttributeData); ok && d != nil {
		t := time.Unix(0, d.CreationTime.Nanoseconds()).UTC()
		return &t
	}
	return nil
}
