// Package captures implements the capture-file registry: discovery of .rdc
// files in configured folders, readiness checks, SQLite persistence with
// stable "cap-NNNNNN" IDs, a filesystem watcher and periodic reconciliation.
package captures

import (
	"database/sql"
	"errors"
	"strings"
	"time"

	"github.com/taqu/rendereye-mcp/internal/store"
)

// Status is the readiness state of a capture record.
type Status string

const (
	StatusDiscovered   Status = "discovered"
	StatusPending      Status = "pending"
	StatusReady        Status = "ready"
	StatusMissing      Status = "missing"
	StatusInaccessible Status = "inaccessible"
	StatusInvalid      Status = "invalid"
	StatusStale        Status = "stale"
)

// AllStatuses lists every status in declaration order.
var AllStatuses = []Status{
	StatusDiscovered, StatusPending, StatusReady, StatusMissing,
	StatusInaccessible, StatusInvalid, StatusStale,
}

// ParseStatus validates s.
func ParseStatus(s string) (Status, bool) {
	for _, st := range AllStatuses {
		if string(st) == s {
			return st, true
		}
	}
	return "", false
}

// Record is one registered capture file.
type Record struct {
	CaptureID            string
	Path                 string
	Filename             string
	FileSize             int64
	FSCreatedAt          *time.Time
	FSModifiedAt         *time.Time
	DiscoveredAt         time.Time
	LastSeenAt           time.Time
	ReadinessConfirmedAt *time.Time
	Status               Status
	SelectionBasis       string
	OrderingConfidence   string
	SourceDirectory      string
	ErrorMessage         string
}

// ToMap serialises the record using the MCP tool contract field names.
func (r *Record) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"capture_id":             r.CaptureID,
		"path":                   r.Path,
		"filename":               r.Filename,
		"file_size":              r.FileSize,
		"fs_created_at":          store.NullTime(r.FSCreatedAt),
		"fs_modified_at":         store.NullTime(r.FSModifiedAt),
		"discovered_at":          store.FormatTime(r.DiscoveredAt),
		"last_seen_at":           store.FormatTime(r.LastSeenAt),
		"readiness_confirmed_at": store.NullTime(r.ReadinessConfirmedAt),
		"status":                 string(r.Status),
		"selection_basis":        r.SelectionBasis,
		"ordering_confidence":    r.OrderingConfidence,
		"source_directory":       r.SourceDirectory,
		"error_message":          r.ErrorMessage,
	}
}

// Storage persists capture records.
type Storage struct {
	db *sql.DB
}

// NewStorage wraps a database opened with store.Open.
func NewStorage(db *sql.DB) *Storage { return &Storage{db: db} }

const captureColumns = `capture_id, path, filename, file_size, fs_created_at, fs_modified_at,
	discovered_at, last_seen_at, readiness_confirmed_at, status, selection_basis,
	ordering_confidence, source_directory, error_message`

// Upsert inserts or updates rec (keyed by capture_id).
func (s *Storage) Upsert(rec *Record) error {
	if rec.SelectionBasis == "" {
		rec.SelectionBasis = "filesystem_modification_time"
	}
	if rec.OrderingConfidence == "" {
		rec.OrderingConfidence = "heuristic"
	}
	_, err := s.db.Exec(`INSERT INTO captures (`+captureColumns+`) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
		ON CONFLICT(capture_id) DO UPDATE SET
			path=excluded.path, filename=excluded.filename, file_size=excluded.file_size,
			fs_created_at=excluded.fs_created_at, fs_modified_at=excluded.fs_modified_at,
			last_seen_at=excluded.last_seen_at, readiness_confirmed_at=excluded.readiness_confirmed_at,
			status=excluded.status, selection_basis=excluded.selection_basis,
			ordering_confidence=excluded.ordering_confidence,
			source_directory=excluded.source_directory, error_message=excluded.error_message`,
		rec.CaptureID, rec.Path, rec.Filename, rec.FileSize,
		store.NullTime(rec.FSCreatedAt), store.NullTime(rec.FSModifiedAt),
		store.FormatTime(rec.DiscoveredAt), store.FormatTime(rec.LastSeenAt),
		store.NullTime(rec.ReadinessConfirmedAt), string(rec.Status), rec.SelectionBasis,
		rec.OrderingConfidence, rec.SourceDirectory, rec.ErrorMessage)
	return err
}

type scanner interface {
	Scan(dest ...interface{}) error
}

func scanRecord(row scanner) (*Record, error) {
	var (
		rec                                      Record
		created, modified, discovered, lastSeen  sql.NullString
		ready                                    sql.NullString
		status, basis, confidence, source, errMs sql.NullString
	)
	if err := row.Scan(&rec.CaptureID, &rec.Path, &rec.Filename, &rec.FileSize,
		&created, &modified, &discovered, &lastSeen, &ready, &status,
		&basis, &confidence, &source, &errMs); err != nil {
		return nil, err
	}
	rec.FSCreatedAt = store.ParseTime(created)
	rec.FSModifiedAt = store.ParseTime(modified)
	if t := store.ParseTime(discovered); t != nil {
		rec.DiscoveredAt = *t
	}
	if t := store.ParseTime(lastSeen); t != nil {
		rec.LastSeenAt = *t
	}
	rec.ReadinessConfirmedAt = store.ParseTime(ready)
	rec.Status = Status(status.String)
	rec.SelectionBasis = basis.String
	rec.OrderingConfidence = confidence.String
	rec.SourceDirectory = source.String
	rec.ErrorMessage = errMs.String
	return &rec, nil
}

func (s *Storage) getOne(query string, arg interface{}) (*Record, error) {
	rec, err := scanRecord(s.db.QueryRow(query, arg))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return rec, err
}

// Get returns the record with captureID, or nil.
func (s *Storage) Get(captureID string) (*Record, error) {
	return s.getOne(`SELECT `+captureColumns+` FROM captures WHERE capture_id = ?`, captureID)
}

// GetByPath returns the record with the canonical path, or nil.
func (s *Storage) GetByPath(path string) (*Record, error) {
	return s.getOne(`SELECT `+captureColumns+` FROM captures WHERE path = ?`, path)
}

// List returns records filtered by status/directory (empty = any), newest
// discovery first, plus the total matching count.
func (s *Storage) List(status Status, directory string, limit, offset int) ([]*Record, int, error) {
	var conds []string
	var args []interface{}
	if status != "" {
		conds = append(conds, "status = ?")
		args = append(args, string(status))
	}
	if directory != "" {
		conds = append(conds, "source_directory = ?")
		args = append(args, directory)
	}
	where := ""
	if len(conds) > 0 {
		where = "WHERE " + strings.Join(conds, " AND ")
	}
	var total int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM captures `+where, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	if limit <= 0 {
		return []*Record{}, total, nil
	}
	rows, err := s.db.Query(`SELECT `+captureColumns+` FROM captures `+where+
		` ORDER BY discovered_at DESC LIMIT ? OFFSET ?`, append(args, limit, offset)...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []*Record{}
	for rows.Next() {
		rec, err := scanRecord(rows)
		if err != nil {
			return nil, 0, err
		}
		out = append(out, rec)
	}
	return out, total, rows.Err()
}

// Latest returns the most recently modified READY capture, or nil.
func (s *Storage) Latest(directory string) (*Record, error) {
	q := `SELECT ` + captureColumns + ` FROM captures WHERE status = ?`
	args := []interface{}{string(StatusReady)}
	if directory != "" {
		q += ` AND source_directory = ?`
		args = append(args, directory)
	}
	q += ` ORDER BY fs_modified_at DESC NULLS LAST, fs_created_at DESC NULLS LAST,
		discovered_at DESC, capture_id DESC LIMIT 1`
	rec, err := scanRecord(s.db.QueryRow(q, args...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return rec, err
}

// NextCaptureID allocates the next "cap-NNNNNN" ID.
func (s *Storage) NextCaptureID() (string, error) {
	return store.NextID(s.db, "next_capture_id", "cap")
}
