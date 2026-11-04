// Package sessions manages RenderDoc sessions created by capture_open:
// launching RenderDoc, associating windows, replacing captures through the
// extension, focusing/closing windows and reconciling state with running
// processes.
package sessions

import (
	"database/sql"
	"errors"
	"strings"
	"time"

	"github.com/taqu/rendereye-mcp/internal/store"
)

// Status is a session lifecycle state.
type Status string

const (
	StatusCreating     Status = "creating"
	StatusActive       Status = "active"
	StatusDisconnected Status = "disconnected"
	StatusRecovering   Status = "recovering"
	StatusClosing      Status = "closing"
	StatusClosed       Status = "closed"
)

// AllStatuses lists every session status.
var AllStatuses = []Status{StatusCreating, StatusActive, StatusDisconnected, StatusRecovering, StatusClosing, StatusClosed}

// Association describes how confidently a window belongs to the session.
type Association string

const (
	AssociationConfirmed Association = "confirmed"
	AssociationInferred  Association = "inferred"
	AssociationUnknown   Association = "unknown"
	AssociationLost      Association = "lost"
)

// Record is one persisted session.
type Record struct {
	SessionID         string
	CaptureID         string
	CapturePath       string
	InstanceID        *string
	WindowID          *string
	ProcessID         *int
	Status            Status
	Managed           bool
	Protected         bool
	AssociationStatus Association
	CreatedAt         time.Time
	UpdatedAt         time.Time
	LastActivityAt    time.Time
	ErrorMessage      string

	// Not persisted (matching the former Python service): last capture the
	// extension reported for this session's process, and when.
	GUICapturePath *string
	GUIVerifiedAt  *time.Time
}

func strOrNil(s *string) interface{} {
	if s == nil {
		return nil
	}
	return *s
}

// ToMap serialises the session using the session_* tool contract.
func (r *Record) ToMap() map[string]interface{} {
	var pid interface{}
	if r.ProcessID != nil {
		pid = *r.ProcessID
	}
	return map[string]interface{}{
		"session_id":         r.SessionID,
		"capture_id":         r.CaptureID,
		"capture_path":       r.CapturePath,
		"instance_id":        strOrNil(r.InstanceID),
		"window_id":          strOrNil(r.WindowID),
		"process_id":         pid,
		"status":             string(r.Status),
		"managed":            r.Managed,
		"protected":          r.Protected,
		"association_status": string(r.AssociationStatus),
		"created_at":         store.FormatTime(r.CreatedAt),
		"updated_at":         store.FormatTime(r.UpdatedAt),
		"last_activity_at":   store.FormatTime(r.LastActivityAt),
		"error_message":      r.ErrorMessage,
		"gui_capture_path":   strOrNil(r.GUICapturePath),
		"gui_verified_at":    store.NullTime(r.GUIVerifiedAt),
	}
}

// Storage persists session records in the shared database.
type Storage struct {
	db *sql.DB
}

// NewStorage wraps a database opened with store.Open.
func NewStorage(db *sql.DB) *Storage { return &Storage{db: db} }

const sessionColumns = `session_id, capture_id, capture_path, instance_id, window_id, process_id,
	status, managed, protected, association_status, created_at, updated_at, last_activity_at, error_message`

func nullStr(s *string) interface{} {
	if s == nil {
		return nil
	}
	return *s
}

// Upsert inserts or updates rec.
func (s *Storage) Upsert(rec *Record) error {
	var pid interface{}
	if rec.ProcessID != nil {
		pid = *rec.ProcessID
	}
	b := func(v bool) int {
		if v {
			return 1
		}
		return 0
	}
	_, err := s.db.Exec(`INSERT INTO sessions (`+sessionColumns+`) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
		ON CONFLICT(session_id) DO UPDATE SET
			capture_id=excluded.capture_id, capture_path=excluded.capture_path,
			instance_id=excluded.instance_id, window_id=excluded.window_id,
			process_id=excluded.process_id, status=excluded.status, managed=excluded.managed,
			protected=excluded.protected, association_status=excluded.association_status,
			updated_at=excluded.updated_at, last_activity_at=excluded.last_activity_at,
			error_message=excluded.error_message`,
		rec.SessionID, rec.CaptureID, rec.CapturePath, nullStr(rec.InstanceID), nullStr(rec.WindowID), pid,
		string(rec.Status), b(rec.Managed), b(rec.Protected), string(rec.AssociationStatus),
		store.FormatTime(rec.CreatedAt), store.FormatTime(rec.UpdatedAt), store.FormatTime(rec.LastActivityAt),
		rec.ErrorMessage)
	return err
}

type scanner interface {
	Scan(dest ...interface{}) error
}

func scanRecord(row scanner) (*Record, error) {
	var (
		rec                           Record
		inst, win                     sql.NullString
		pid                           sql.NullInt64
		status, assoc, errMsg         sql.NullString
		managed, protected            int
		created, updated, lastActivty sql.NullString
	)
	if err := row.Scan(&rec.SessionID, &rec.CaptureID, &rec.CapturePath, &inst, &win, &pid,
		&status, &managed, &protected, &assoc, &created, &updated, &lastActivty, &errMsg); err != nil {
		return nil, err
	}
	if inst.Valid {
		v := inst.String
		rec.InstanceID = &v
	}
	if win.Valid {
		v := win.String
		rec.WindowID = &v
	}
	if pid.Valid {
		v := int(pid.Int64)
		rec.ProcessID = &v
	}
	rec.Status = Status(status.String)
	rec.Managed = managed != 0
	rec.Protected = protected != 0
	rec.AssociationStatus = Association(assoc.String)
	now := time.Now().UTC()
	pick := func(ns sql.NullString) time.Time {
		if t := store.ParseTime(ns); t != nil {
			return *t
		}
		return now
	}
	rec.CreatedAt, rec.UpdatedAt, rec.LastActivityAt = pick(created), pick(updated), pick(lastActivty)
	rec.ErrorMessage = errMsg.String
	return &rec, nil
}

// Get returns the session, or nil.
func (s *Storage) Get(id string) (*Record, error) {
	rec, err := scanRecord(s.db.QueryRow(`SELECT `+sessionColumns+` FROM sessions WHERE session_id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return rec, err
}

// List returns filtered sessions (newest first) and the total count.
func (s *Storage) List(status Status, managedOnly bool, captureID string, limit, offset int) ([]*Record, int, error) {
	var conds []string
	var args []interface{}
	if status != "" {
		conds = append(conds, "status = ?")
		args = append(args, string(status))
	}
	if managedOnly {
		conds = append(conds, "managed = 1")
	}
	if captureID != "" {
		conds = append(conds, "capture_id = ?")
		args = append(args, captureID)
	}
	where := ""
	if len(conds) > 0 {
		where = "WHERE " + strings.Join(conds, " AND ")
	}
	var total int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM sessions `+where, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	if limit <= 0 {
		return []*Record{}, total, nil
	}
	rows, err := s.db.Query(`SELECT `+sessionColumns+` FROM sessions `+where+
		` ORDER BY created_at DESC LIMIT ? OFFSET ?`, append(args, limit, offset)...)
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

// NextSessionID allocates the next "session-NNNNNN" ID.
func (s *Storage) NextSessionID() (string, error) {
	return store.NextID(s.db, "next_session_id", "session")
}
