package captures

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/store"
)

func testConfig(dir string) config.CaptureConfig {
	c := config.DefaultCaptureConfig()
	c.StabilityDuration = 40 * time.Millisecond
	c.ScanInterval = time.Hour // reconciliation is triggered explicitly
	c.Directories = []config.CaptureDirectory{{Path: dir}}
	return c
}

func waitStatus(t *testing.T, reg *Registry, path string, want Status) *Record {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for {
		rec, err := reg.storage.GetByPath(canonicalPath(path))
		if err != nil {
			t.Fatal(err)
		}
		if rec != nil && rec.Status == want {
			return rec
		}
		if time.Now().After(deadline) {
			t.Fatalf("%s: wanted status %s, have %+v", path, want, rec)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func TestRegistry_discoveryReadinessAndPersistence(t *testing.T) {
	dir := t.TempDir()
	dbPath := filepath.Join(t.TempDir(), "captures.db")
	a := filepath.Join(dir, "frame_a.rdc")
	b := filepath.Join(dir, "frame_b.RDC") // extension match is case-insensitive
	os.WriteFile(a, []byte("RDOC-a"), 0o644)
	os.WriteFile(b, []byte("RDOC-b"), 0o644)
	os.WriteFile(filepath.Join(dir, "notes.txt"), []byte("ignored"), 0o644)
	os.WriteFile(filepath.Join(dir, "tiny.rdc"), []byte("x"), 0o644) // below min size
	later := time.Now().Add(time.Minute)
	os.Chtimes(b, later, later)

	db, err := store.Open(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	reg := NewRegistry(testConfig(dir), NewStorage(db))
	reg.Start()

	recA := waitStatus(t, reg, a, StatusReady)
	waitStatus(t, reg, b, StatusReady)
	if recA.CaptureID == "" || recA.ReadinessConfirmedAt == nil || recA.Filename != "frame_a.rdc" {
		t.Errorf("unexpected record: %+v", recA)
	}
	if _, total, _ := reg.List("", "", 0, 0); total != 2 {
		t.Errorf("expected 2 captures (txt and tiny skipped), got %d", total)
	}
	latest, _ := reg.Latest("")
	if latest == nil || latest.Filename != "frame_b.RDC" {
		t.Errorf("latest should be the most recently modified ready capture, got %+v", latest)
	}

	// Rescan of an unchanged folder adds nothing.
	if scanned, added, _, err := reg.Rescan(); err != nil || scanned != 2 || added != 0 {
		t.Errorf("rescan: scanned=%d added=%d err=%v", scanned, added, err)
	}

	st := reg.Status()
	if st["total_captures"] != 2 || st["enabled"] != true {
		t.Errorf("status: %v", st)
	}
	reg.Stop()
	db.Close()

	// Re-opening the database keeps stable capture IDs.
	db2, err := store.Open(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db2.Close()
	reg2 := NewRegistry(testConfig(dir), NewStorage(db2))
	reg2.ScanAll()
	again, _ := reg2.storage.GetByPath(canonicalPath(a))
	if again == nil || again.CaptureID != recA.CaptureID {
		t.Errorf("capture ID not stable across restarts: %+v vs %s", again, recA.CaptureID)
	}
	reg2.Stop()
}

func TestRegistry_watcherTracksNewAndDeletedFiles(t *testing.T) {
	dir := t.TempDir()
	db, err := store.Open(filepath.Join(t.TempDir(), "captures.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	reg := NewRegistry(testConfig(dir), NewStorage(db))
	reg.Start()
	defer reg.Stop()
	if reg.Status()["watcher_active"] != true {
		t.Skip("filesystem watcher unavailable on this platform")
	}

	p := filepath.Join(dir, "new.rdc")
	os.WriteFile(p, []byte("RDOC-new"), 0o644)
	waitStatus(t, reg, p, StatusReady)

	os.Remove(p)
	waitStatus(t, reg, p, StatusMissing)
}

func TestRegistry_disabledDoesNotScan(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "a.rdc"), []byte("RDOC"), 0o644)
	db, _ := store.Open(":memory:")
	defer db.Close()
	cfg := testConfig(dir)
	cfg.Enabled = false
	reg := NewRegistry(cfg, NewStorage(db))
	reg.Start()
	defer reg.Stop()
	if _, total, _ := reg.List("", "", 0, 0); total != 0 {
		t.Errorf("disabled registry must not scan, found %d", total)
	}
	if reg.Status()["enabled"] != false {
		t.Error("status should report disabled")
	}
}

func TestParseTime_acceptsPythonISOFormat(t *testing.T) {
	for _, s := range []string{"2026-10-31T13:02:29.123456+00:00", "2026-10-31T13:02:29+00:00", "2026-10-31T13:02:29.5"} {
		if store.ParseTime(nullString(s)) == nil {
			t.Errorf("failed to parse %q", s)
		}
	}
	now := time.Date(2026, 11, 4, 1, 2, 3, 4000, time.UTC)
	if got := store.FormatTime(now); got != "2026-11-04T01:02:03.000004+00:00" {
		t.Errorf("FormatTime = %q", got)
	}
}

func nullString(s string) sql.NullString { return sql.NullString{String: s, Valid: true} }
