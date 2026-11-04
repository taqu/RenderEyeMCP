// Package store opens the SQLite database shared by the capture registry and
// the managed-session manager.
//
// The schema is identical to the one used by the former Python Shared IPC
// Service (captures, sessions, registry_meta), so an existing captures.db keeps
// its stable capture and session IDs after switching to the Go service.
package store

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	_ "modernc.org/sqlite" // pure-Go SQLite driver (no cgo)
)

const schema = `
CREATE TABLE IF NOT EXISTS captures (
    capture_id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    fs_created_at TEXT,
    fs_modified_at TEXT,
    discovered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    readiness_confirmed_at TEXT,
    status TEXT NOT NULL,
    selection_basis TEXT NOT NULL DEFAULT 'filesystem_modification_time',
    ordering_confidence TEXT NOT NULL DEFAULT 'heuristic',
    source_directory TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS registry_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    capture_path TEXT NOT NULL,
    instance_id TEXT,
    window_id TEXT,
    process_id INTEGER,
    status TEXT NOT NULL,
    managed INTEGER NOT NULL DEFAULT 1,
    protected INTEGER NOT NULL DEFAULT 0,
    association_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);
INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('next_capture_id', '1');
INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('next_session_id', '1');
INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('schema_version', '1');
`

// Open opens (creating if needed) the database at path and applies the schema.
// Use ":memory:" for an in-memory database (tests).
func Open(path string) (*sql.DB, error) {
	dsn := path
	if path != ":memory:" {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, fmt.Errorf("create storage directory: %w", err)
		}
		dsn = "file:" + filepath.ToSlash(path) + "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)"
	}
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	// SQLite serialises writers; a single connection also keeps ":memory:"
	// databases coherent across calls.
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("apply schema: %w", err)
	}
	return db, nil
}

// NextID atomically reads and increments the registry_meta counter key and
// returns prefix-NNNNNN (e.g. "cap-000001").
func NextID(db *sql.DB, key, prefix string) (string, error) {
	tx, err := db.Begin()
	if err != nil {
		return "", err
	}
	defer tx.Rollback() //nolint:errcheck // no-op after Commit
	var raw string
	n := 1
	switch err := tx.QueryRow(`SELECT value FROM registry_meta WHERE key = ?`, key).Scan(&raw); err {
	case nil:
		if v, perr := strconv.Atoi(raw); perr == nil && v > 0 {
			n = v
		}
	case sql.ErrNoRows:
	default:
		return "", err
	}
	if _, err := tx.Exec(`INSERT OR REPLACE INTO registry_meta (key, value) VALUES (?, ?)`, key, strconv.Itoa(n+1)); err != nil {
		return "", err
	}
	if err := tx.Commit(); err != nil {
		return "", err
	}
	return fmt.Sprintf("%s-%06d", prefix, n), nil
}

// isoLayout matches Python's datetime.isoformat() for aware UTC datetimes
// with microseconds, keeping lexical ordering consistent with rows written by
// the former Python service.
const isoLayout = "2006-01-02T15:04:05.000000-07:00"

// FormatTime renders t like Python's isoformat() in UTC.
func FormatTime(t time.Time) string {
	return t.UTC().Format(isoLayout)
}

// ParseTime parses an ISO-8601 timestamp written by either implementation.
// Naive timestamps are treated as UTC.  It returns nil for empty or invalid input.
func ParseTime(s sql.NullString) *time.Time {
	if !s.Valid || s.String == "" {
		return nil
	}
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02T15:04:05.999999", "2006-01-02 15:04:05.999999"} {
		if t, err := time.Parse(layout, s.String); err == nil {
			u := t.UTC()
			return &u
		}
	}
	return nil
}

// NullTime converts an optional time to a value for a nullable TEXT column.
func NullTime(t *time.Time) interface{} {
	if t == nil {
		return nil
	}
	return FormatTime(*t)
}
