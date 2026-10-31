// Package captures implements a polling-based capture file registry.
// It scans configured directories for .rdc files and tracks them in memory.
package captures

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const scanInterval = 30 * time.Second

// CaptureRecord represents a discovered .rdc capture file.
type CaptureRecord struct {
	CaptureID       string
	Path            string
	Filename        string
	FileSize        int64
	FsModifiedAt    float64
	DiscoveredAt    float64
	LastSeenAt      float64
	Status          string // "ready" | "missing"
	SourceDirectory string
}

// toDict converts a CaptureRecord to a map for JSON serialisation.
func (c *CaptureRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"capture_id":       c.CaptureID,
		"path":             c.Path,
		"filename":         c.Filename,
		"file_size":        c.FileSize,
		"fs_modified_at":   c.FsModifiedAt,
		"discovered_at":    c.DiscoveredAt,
		"last_seen_at":     c.LastSeenAt,
		"status":           c.Status,
		"source_directory": c.SourceDirectory,
	}
}

// CaptureRegistry is a polling-based in-memory registry of .rdc files.
type CaptureRegistry struct {
	dirs    []string
	mu      sync.Mutex
	records map[string]*CaptureRecord // capture_id → record
	byPath  map[string]*CaptureRecord // path → record (for dedup)
	counter atomic.Int64
	running atomic.Bool
	stop    chan struct{}
}

// NewCaptureRegistry creates a new CaptureRegistry for the given directories.
// If dirs is empty, the platform default is used.
func NewCaptureRegistry(dirs []string) *CaptureRegistry {
	if len(dirs) == 0 {
		dirs = defaultCaptureDirectories()
	}
	return &CaptureRegistry{
		dirs:    dirs,
		records: make(map[string]*CaptureRecord),
		byPath:  make(map[string]*CaptureRecord),
		stop:    make(chan struct{}),
	}
}

// defaultCaptureDirectories returns the default directories for the current OS.
func defaultCaptureDirectories() []string {
	if runtime.GOOS == "windows" {
		profile := os.Getenv("USERPROFILE")
		if profile == "" {
			profile = os.Getenv("HOMEDRIVE") + os.Getenv("HOMEPATH")
		}
		return []string{filepath.Join(profile, "AppData", "Roaming", "renderdoc", "captures")}
	}
	home, _ := os.UserHomeDir()
	return []string{filepath.Join(home, "renderdoc", "captures")}
}

// ParseCaptureDirectories parses a colon-or-semicolon-separated list of paths.
func ParseCaptureDirectories(envVal string) []string {
	if envVal == "" {
		return nil
	}
	var sep string
	if strings.Contains(envVal, ";") {
		sep = ";"
	} else {
		sep = ":"
	}
	parts := strings.Split(envVal, sep)
	var dirs []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			dirs = append(dirs, p)
		}
	}
	return dirs
}

// Start begins the background scanning goroutine.
func (r *CaptureRegistry) Start(ctx context.Context) {
	if !r.running.CompareAndSwap(false, true) {
		return
	}
	// Initial scan.
	r.scan()
	go func() {
		ticker := time.NewTicker(scanInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				r.running.Store(false)
				return
			case <-r.stop:
				r.running.Store(false)
				return
			case <-ticker.C:
				r.scan()
			}
		}
	}()
}

// Stop stops the background scanning goroutine.
func (r *CaptureRegistry) Stop() {
	select {
	case r.stop <- struct{}{}:
	default:
	}
}

// Rescan performs an immediate scan and returns statistics.
func (r *CaptureRegistry) Rescan() map[string]interface{} {
	before := r.snapshot()
	r.scan()
	after := r.snapshot()

	newCount := 0
	updatedCount := 0
	for id, rec := range after {
		if _, existed := before[id]; !existed {
			newCount++
		} else if rec.Status != before[id].Status || rec.FileSize != before[id].FileSize {
			updatedCount++
		}
	}

	return map[string]interface{}{
		"status":  "completed",
		"scanned": len(r.dirs),
		"new":     newCount,
		"updated": updatedCount,
	}
}

// scan walks the configured directories and updates the registry.
func (r *CaptureRegistry) scan() {
	nowF := nowFloat()
	seen := map[string]bool{}

	for _, dir := range r.dirs {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			if !strings.HasSuffix(strings.ToLower(entry.Name()), ".rdc") {
				continue
			}
			fullPath := filepath.Join(dir, entry.Name())
			seen[fullPath] = true

			info, err := entry.Info()
			if err != nil {
				continue
			}

			r.mu.Lock()
			rec, exists := r.byPath[fullPath]
			if !exists {
				id := r.nextID()
				rec = &CaptureRecord{
					CaptureID:       id,
					Path:            fullPath,
					Filename:        entry.Name(),
					FileSize:        info.Size(),
					FsModifiedAt:    float64(info.ModTime().UnixNano()) / 1e9,
					DiscoveredAt:    nowF,
					LastSeenAt:      nowF,
					Status:          "ready",
					SourceDirectory: dir,
				}
				r.records[id] = rec
				r.byPath[fullPath] = rec
			} else {
				rec.LastSeenAt = nowF
				rec.FileSize = info.Size()
				rec.FsModifiedAt = float64(info.ModTime().UnixNano()) / 1e9
				rec.Status = "ready"
			}
			r.mu.Unlock()
		}
	}

	// Mark unseen as missing.
	r.mu.Lock()
	for path, rec := range r.byPath {
		if !seen[path] {
			rec.Status = "missing"
		}
	}
	r.mu.Unlock()
}

func (r *CaptureRegistry) nextID() string {
	n := r.counter.Add(1)
	return fmt.Sprintf("cap-%06d", n)
}

func (r *CaptureRegistry) snapshot() map[string]*CaptureRecord {
	r.mu.Lock()
	defer r.mu.Unlock()
	snap := make(map[string]*CaptureRecord, len(r.records))
	for k, v := range r.records {
		cp := *v
		snap[k] = &cp
	}
	return snap
}

// List returns a paginated list of captures, optionally filtered by status and directory.
func (r *CaptureRegistry) List(status, directory string, limit, offset int) map[string]interface{} {
	r.mu.Lock()
	var filtered []*CaptureRecord
	for _, rec := range r.records {
		if status != "" && rec.Status != status {
			continue
		}
		if directory != "" && rec.SourceDirectory != directory {
			continue
		}
		filtered = append(filtered, rec)
	}
	r.mu.Unlock()

	// Sort by discovered_at desc.
	sortCapturesByDiscovered(filtered)

	total := len(filtered)
	if offset > total {
		offset = total
	}
	filtered = filtered[offset:]
	if limit > 0 && len(filtered) > limit {
		filtered = filtered[:limit]
	}

	out := make([]interface{}, len(filtered))
	for i, rec := range filtered {
		out[i] = rec.toDict()
	}

	return map[string]interface{}{
		"captures": out,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	}
}

// Get returns a single capture record by ID.
func (r *CaptureRegistry) Get(id string) map[string]interface{} {
	r.mu.Lock()
	rec, ok := r.records[id]
	r.mu.Unlock()
	if !ok {
		return map[string]interface{}{
			"error":      "not_found",
			"capture_id": id,
		}
	}
	return rec.toDict()
}

// Latest returns the most recently discovered capture, optionally from a directory.
func (r *CaptureRegistry) Latest(directory string) map[string]interface{} {
	r.mu.Lock()
	var candidates []*CaptureRecord
	for _, rec := range r.records {
		if rec.Status != "ready" {
			continue
		}
		if directory != "" && rec.SourceDirectory != directory {
			continue
		}
		candidates = append(candidates, rec)
	}
	r.mu.Unlock()

	if len(candidates) == 0 {
		return map[string]interface{}{"error": "no_capture_available"}
	}

	sortCapturesByDiscovered(candidates)
	return candidates[0].toDict()
}

// Status returns the registry status.
func (r *CaptureRegistry) Status() map[string]interface{} {
	r.mu.Lock()
	total := len(r.records)
	byStatus := map[string]int{"ready": 0, "missing": 0}
	for _, rec := range r.records {
		byStatus[rec.Status]++
	}
	r.mu.Unlock()

	dirs := make([]interface{}, len(r.dirs))
	for i, d := range r.dirs {
		dirs[i] = d
	}

	return map[string]interface{}{
		"enabled":             true,
		"running":             r.running.Load(),
		"total_captures":      total,
		"captures_by_status":  byStatus,
		"watched_directories": dirs,
	}
}

// GetRecord returns the raw *CaptureRecord for a given ID (used by session manager).
func (r *CaptureRegistry) GetRecord(id string) *CaptureRecord {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.records[id]
}

// GetLatestRecord returns the most recently discovered ready CaptureRecord, or nil.
func (r *CaptureRegistry) GetLatestRecord(directory string) *CaptureRecord {
	r.mu.Lock()
	var candidates []*CaptureRecord
	for _, rec := range r.records {
		if rec.Status != "ready" {
			continue
		}
		if directory != "" && rec.SourceDirectory != directory {
			continue
		}
		candidates = append(candidates, rec)
	}
	r.mu.Unlock()
	if len(candidates) == 0 {
		return nil
	}
	sortCapturesByDiscovered(candidates)
	return candidates[0]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func nowFloat() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}

// sortCapturesByDiscovered sorts captures newest-first by DiscoveredAt.
func sortCapturesByDiscovered(recs []*CaptureRecord) {
	for i := 1; i < len(recs); i++ {
		for j := i; j > 0 && recs[j].DiscoveredAt > recs[j-1].DiscoveredAt; j-- {
			recs[j], recs[j-1] = recs[j-1], recs[j]
		}
	}
}
