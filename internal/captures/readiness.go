package captures

import (
	"context"
	"errors"
	"io/fs"
	"os"
	"time"
)

// readinessResult is the outcome of a stability check.
type readinessResult struct {
	Passed   bool
	Reason   string // stable, growing, missing, too_small, inaccessible, cancelled
	FileSize int64
}

func statReason(err error) string {
	if errors.Is(err, fs.ErrNotExist) {
		return "missing"
	}
	return "inaccessible"
}

// checkReadiness verifies that path is readable, at least minSize bytes and
// unchanged (size and mtime) across two consecutive half-stability windows.
func checkReadiness(ctx context.Context, path string, stability time.Duration, minSize int64) readinessResult {
	st1, err := os.Stat(path)
	if err != nil {
		return readinessResult{Reason: statReason(err)}
	}
	f, err := os.Open(path)
	if err != nil {
		return readinessResult{Reason: statReason(err)}
	}
	f.Close()
	if st1.Size() < minSize {
		return readinessResult{Reason: "too_small", FileSize: st1.Size()}
	}

	prev := st1
	half := stability / 2
	for i := 0; i < 2; i++ {
		select {
		case <-ctx.Done():
			return readinessResult{Reason: "cancelled", FileSize: prev.Size()}
		case <-time.After(half):
		}
		cur, err := os.Stat(path)
		if err != nil {
			return readinessResult{Reason: "missing", FileSize: prev.Size()}
		}
		if cur.Size() != prev.Size() || !cur.ModTime().Equal(prev.ModTime()) {
			return readinessResult{Reason: "growing", FileSize: cur.Size()}
		}
		prev = cur
	}
	return readinessResult{Passed: true, Reason: "stable", FileSize: prev.Size()}
}
