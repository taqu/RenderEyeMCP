package captures

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"

	"github.com/taqu/rendereye-mcp/internal/config"
)

// watchDebounce coalesces bursts of write events while RenderDoc writes a file.
const watchDebounce = 300 * time.Millisecond

// Registry coordinates discovery, readiness checks, the watcher and the
// reconciliation loop.  It is safe for concurrent use.
type Registry struct {
	cfg     config.CaptureConfig
	storage *Storage

	// mu serialises read-modify-write cycles on capture records so that the
	// watcher, the reconcile loop, rescans and readiness checks never race.
	mu sync.Mutex

	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup

	stateMu   sync.Mutex
	running   bool
	watcher   *fsnotify.Watcher
	readiness map[string]bool // capture_id -> readiness check in flight
	debounce  map[string]*time.Timer
}

// NewRegistry creates a registry over storage.  Call Start to begin scanning.
func NewRegistry(cfg config.CaptureConfig, storage *Storage) *Registry {
	ctx, cancel := context.WithCancel(context.Background())
	return &Registry{
		cfg:       cfg,
		storage:   storage,
		ctx:       ctx,
		cancel:    cancel,
		readiness: map[string]bool{},
		debounce:  map[string]*time.Timer{},
	}
}

// Start performs the initial scan and starts the watcher and the periodic
// reconciler.  It is a no-op (besides marking the registry running) when the
// registry is disabled.
func (r *Registry) Start() {
	r.stateMu.Lock()
	r.running = true
	r.stateMu.Unlock()
	if !r.cfg.Enabled {
		slog.Info("capture registry disabled by config")
		return
	}
	r.ScanAll()
	r.startWatcher()
	r.wg.Add(1)
	go r.reconcileLoop()
	slog.Info("capture registry started", "directories", len(r.cfg.Directories))
}

// Stop stops background work and waits for it to finish.
func (r *Registry) Stop() {
	r.cancel()
	r.stateMu.Lock()
	r.running = false
	if r.watcher != nil {
		r.watcher.Close()
	}
	for path, t := range r.debounce {
		if t.Stop() {
			r.wg.Done() // the callback will never run
		}
		delete(r.debounce, path)
	}
	r.stateMu.Unlock()
	r.wg.Wait()
}

// ---------------------------------------------------------------------------
// Scanning
// ---------------------------------------------------------------------------

// ScanAll scans every configured directory and returns the number of files
// processed.
func (r *Registry) ScanAll() int {
	total := 0
	for _, d := range r.cfg.Directories {
		total += r.scanDirectory(d.Path, d.Recursive)
	}
	return total
}

func (r *Registry) scanDirectory(dir string, recursive bool) int {
	source := canonicalPath(dir)
	count := 0
	for _, p := range scanDirectory(dir, recursive, r.cfg.MinFileSize) {
		if err := r.processFile(p, source); err != nil {
			slog.Warn("capture registry: process file failed", "path", p, "err", err)
			continue
		}
		count++
	}
	return count
}

// processFile discovers or refreshes one file and schedules a readiness check
// for new or reappearing captures.
func (r *Registry) processFile(path, source string) error {
	canonical := canonicalPath(path)
	now := time.Now().UTC()

	r.mu.Lock()
	defer r.mu.Unlock()

	existing, err := r.storage.GetByPath(canonical)
	if err != nil {
		return err
	}
	st, statErr := os.Stat(canonical)
	if statErr != nil {
		if existing != nil {
			existing.Status = StatusMissing
			existing.LastSeenAt = now
			return r.storage.Upsert(existing)
		}
		return nil
	}
	modified := st.ModTime().UTC()

	if existing == nil {
		id, err := r.storage.NextCaptureID()
		if err != nil {
			return err
		}
		rec := &Record{
			CaptureID:       id,
			Path:            canonical,
			Filename:        filepath.Base(canonical),
			FileSize:        st.Size(),
			FSCreatedAt:     creationTime(st),
			FSModifiedAt:    &modified,
			DiscoveredAt:    now,
			LastSeenAt:      now,
			Status:          StatusDiscovered,
			SourceDirectory: source,
		}
		if err := r.storage.Upsert(rec); err != nil {
			return err
		}
		r.scheduleReadiness(id, canonical)
		return nil
	}

	existing.LastSeenAt = now
	existing.FileSize = st.Size()
	existing.FSModifiedAt = &modified
	if existing.Status == StatusMissing {
		existing.Status = StatusDiscovered
		existing.ReadinessConfirmedAt = nil
		r.scheduleReadiness(existing.CaptureID, canonical)
	}
	return r.storage.Upsert(existing)
}

// scheduleReadiness starts one readiness goroutine per capture ID.
func (r *Registry) scheduleReadiness(captureID, path string) {
	r.stateMu.Lock()
	if r.readiness[captureID] || r.ctx.Err() != nil {
		r.stateMu.Unlock()
		return
	}
	r.readiness[captureID] = true
	r.stateMu.Unlock()

	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		defer func() {
			r.stateMu.Lock()
			delete(r.readiness, captureID)
			r.stateMu.Unlock()
		}()
		r.runReadiness(captureID, path)
	}()
}

// runReadiness marks the capture pending and re-checks until it is stable,
// missing or inaccessible, or the registry stops.
func (r *Registry) runReadiness(captureID, path string) {
	for {
		if !r.updateRecord(captureID, func(rec *Record) { rec.Status = StatusPending }) {
			return
		}
		res := checkReadiness(r.ctx, path, r.cfg.StabilityDuration, r.cfg.MinFileSize)
		if res.Reason == "cancelled" {
			return
		}
		pending := false
		if !r.updateRecord(captureID, func(rec *Record) {
			now := time.Now().UTC()
			switch {
			case res.Passed:
				rec.Status = StatusReady
				rec.ReadinessConfirmedAt = &now
				rec.FileSize = res.FileSize
				rec.ErrorMessage = ""
			case res.Reason == "missing":
				rec.Status = StatusMissing
				rec.ErrorMessage = res.Reason
			case res.Reason == "too_small" || res.Reason == "inaccessible":
				rec.Status = StatusInaccessible
				rec.ErrorMessage = res.Reason
			default: // growing
				rec.Status = StatusPending
				rec.ErrorMessage = res.Reason
				pending = true
			}
			rec.LastSeenAt = now
		}) || !pending {
			return
		}
		select {
		case <-r.ctx.Done():
			return
		case <-time.After(r.cfg.StabilityDuration):
		}
	}
}

// updateRecord applies fn to the stored record under the registry lock.
// It returns false when the record no longer exists or cannot be written.
func (r *Registry) updateRecord(captureID string, fn func(*Record)) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	rec, err := r.storage.Get(captureID)
	if err != nil || rec == nil {
		return false
	}
	fn(rec)
	if err := r.storage.Upsert(rec); err != nil {
		slog.Warn("capture registry: update failed", "capture_id", captureID, "err", err)
		return false
	}
	return true
}

// markMissing flags the record for path (if any) as missing.
func (r *Registry) markMissing(path string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	rec, err := r.storage.GetByPath(canonicalPath(path))
	if err != nil || rec == nil {
		return
	}
	rec.Status = StatusMissing
	rec.LastSeenAt = time.Now().UTC()
	if err := r.storage.Upsert(rec); err != nil {
		slog.Warn("capture registry: mark missing failed", "path", path, "err", err)
	}
}

func (r *Registry) reconcileLoop() {
	defer r.wg.Done()
	t := time.NewTicker(r.cfg.ScanInterval)
	defer t.Stop()
	for {
		select {
		case <-r.ctx.Done():
			return
		case <-t.C:
		}
		r.ScanAll()
		ready, _, err := r.storage.List(StatusReady, "", 10000, 0)
		if err != nil {
			slog.Warn("capture registry: reconcile list failed", "err", err)
			continue
		}
		for _, rec := range ready {
			if _, err := os.Stat(rec.Path); err != nil {
				r.markMissing(rec.Path)
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Watcher
// ---------------------------------------------------------------------------

func (r *Registry) startWatcher() {
	if len(r.cfg.Directories) == 0 {
		return
	}
	w, err := fsnotify.NewWatcher()
	if err != nil {
		slog.Warn("capture registry: watcher unavailable; relying on periodic scans", "err", err)
		return
	}
	added := 0
	for _, d := range r.cfg.Directories {
		added += addWatchTree(w, d.Path, d.Recursive)
	}
	if added == 0 {
		w.Close()
		return
	}
	r.stateMu.Lock()
	r.watcher = w
	r.stateMu.Unlock()
	r.wg.Add(1)
	go r.watchLoop(w)
}

// addWatchTree watches dir (and its subdirectories when recursive).
func addWatchTree(w *fsnotify.Watcher, dir string, recursive bool) int {
	info, err := os.Stat(dir)
	if err != nil || !info.IsDir() {
		slog.Warn("capture registry: watch directory not found, skipping", "path", dir)
		return 0
	}
	if !recursive {
		if err := w.Add(dir); err != nil {
			slog.Warn("capture registry: watch failed", "path", dir, "err", err)
			return 0
		}
		return 1
	}
	n := 0
	filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error { //nolint:errcheck
		if err != nil {
			return nil
		}
		if d.IsDir() {
			if w.Add(p) == nil {
				n++
			}
		}
		return nil
	})
	return n
}

func (r *Registry) watchLoop(w *fsnotify.Watcher) {
	defer r.wg.Done()
	for {
		select {
		case <-r.ctx.Done():
			return
		case ev, ok := <-w.Events:
			if !ok {
				return
			}
			r.handleEvent(w, ev)
		case err, ok := <-w.Errors:
			if !ok {
				return
			}
			slog.Debug("capture registry: watcher error", "err", err)
		}
	}
}

func (r *Registry) handleEvent(w *fsnotify.Watcher, ev fsnotify.Event) {
	if ev.Has(fsnotify.Create) {
		if info, err := os.Stat(ev.Name); err == nil && info.IsDir() {
			if dir, ok := r.directoryFor(ev.Name); ok && dir.Recursive {
				addWatchTree(w, ev.Name, true)
				r.scanDirectory(ev.Name, true)
			}
			return
		}
	}
	if !isRDC(ev.Name) {
		return
	}
	switch {
	case ev.Has(fsnotify.Remove), ev.Has(fsnotify.Rename):
		// Rename reports the old name; the new name arrives as Create.
		r.markMissing(ev.Name)
	case ev.Has(fsnotify.Create), ev.Has(fsnotify.Write):
		r.debounceProcess(ev.Name)
	}
}

func (r *Registry) debounceProcess(path string) {
	r.stateMu.Lock()
	defer r.stateMu.Unlock()
	if r.ctx.Err() != nil {
		return
	}
	if t, ok := r.debounce[path]; ok {
		t.Reset(watchDebounce)
		return
	}
	r.wg.Add(1)
	r.debounce[path] = time.AfterFunc(watchDebounce, func() {
		defer r.wg.Done()
		r.stateMu.Lock()
		delete(r.debounce, path)
		r.stateMu.Unlock()
		if r.ctx.Err() != nil {
			return
		}
		if st, err := os.Stat(path); err == nil && st.Size() < r.cfg.MinFileSize {
			return
		}
		if err := r.processFile(path, r.sourceDirFor(path)); err != nil {
			slog.Warn("capture registry: process file failed", "path", path, "err", err)
		}
	})
}

// directoryFor returns the configured directory containing path.
func (r *Registry) directoryFor(path string) (config.CaptureDirectory, bool) {
	resolved := canonicalPath(path)
	for _, d := range r.cfg.Directories {
		base := canonicalPath(d.Path)
		rel, err := filepath.Rel(base, resolved)
		if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
			return d, true
		}
	}
	return config.CaptureDirectory{}, false
}

func (r *Registry) sourceDirFor(path string) string {
	if d, ok := r.directoryFor(path); ok {
		return canonicalPath(d.Path)
	}
	return filepath.Dir(canonicalPath(path))
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

// Get returns the record with captureID, or nil.
func (r *Registry) Get(captureID string) (*Record, error) { return r.storage.Get(captureID) }

// List returns filtered records and the total count.
func (r *Registry) List(status Status, directory string, limit, offset int) ([]*Record, int, error) {
	return r.storage.List(status, directory, limit, offset)
}

// Latest returns the latest READY capture, or nil.
func (r *Registry) Latest(directory string) (*Record, error) { return r.storage.Latest(directory) }

// Rescan scans immediately and reports how many files were scanned, newly
// registered and updated.
func (r *Registry) Rescan() (scanned, added, updated int, err error) {
	_, before, err := r.storage.List("", "", 0, 0)
	if err != nil {
		return 0, 0, 0, err
	}
	scanned = r.ScanAll()
	_, after, err := r.storage.List("", "", 0, 0)
	if err != nil {
		return 0, 0, 0, err
	}
	added = after - before
	if added < 0 {
		added = 0
	}
	if scanned > added {
		updated = scanned - added
	}
	return scanned, added, updated, nil
}

// Status returns the capture_registry_status payload.
func (r *Registry) Status() map[string]interface{} {
	r.stateMu.Lock()
	running := r.running
	watcherActive := r.watcher != nil && r.ctx.Err() == nil
	r.stateMu.Unlock()

	dirs := make([]string, 0, len(r.cfg.Directories))
	for _, d := range r.cfg.Directories {
		dirs = append(dirs, d.Path)
	}
	total := 0
	byStatus := map[string]interface{}{}
	if r.cfg.Enabled {
		if _, n, err := r.storage.List("", "", 0, 0); err == nil {
			total = n
		}
		for _, s := range AllStatuses {
			if _, n, err := r.storage.List(s, "", 0, 0); err == nil {
				byStatus[string(s)] = n
			}
		}
	}
	return map[string]interface{}{
		"enabled":                     r.cfg.Enabled,
		"running":                     running,
		"watcher_active":              watcherActive,
		"watched_directories":         dirs,
		"total_captures":              total,
		"captures_by_status":          byStatus,
		"scan_interval_seconds":       r.cfg.ScanInterval.Seconds(),
		"readiness_stability_seconds": r.cfg.StabilityDuration.Seconds(),
	}
}
