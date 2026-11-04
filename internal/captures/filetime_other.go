//go:build !windows

package captures

import (
	"os"
	"time"
)

// creationTime returns nil: portable Unix stat data has no reliable birth time.
func creationTime(fi os.FileInfo) *time.Time { return nil }
