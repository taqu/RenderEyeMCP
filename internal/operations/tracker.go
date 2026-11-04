// Package operations tracks asynchronous GUI operations (capture_open) so
// clients can poll their outcome with operation_get.
package operations

import (
	"fmt"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/store"
)

// Status is an operation lifecycle state.
type Status string

const (
	StatusRequested      Status = "requested"
	StatusValidating     Status = "validating"
	StatusLaunching      Status = "launching"
	StatusWaitingForGUI  Status = "waiting_for_gui"
	StatusVerifying      Status = "verifying"
	StatusConfirmed      Status = "confirmed"
	StatusFailed         Status = "failed"
	StatusUnsupported    Status = "unsupported"
	StatusTimedOut       Status = "timed_out"
	StatusUnknownOutcome Status = "unknown_outcome"
)

// maxOperations bounds the in-memory history (oldest evicted first).
const maxOperations = 200

// Record is one tracked operation.  Fields are only mutated through
// Tracker.Update so concurrent readers always see a consistent snapshot.
type Record struct {
	OperationID           string
	OperationType         string
	Status                Status
	CaptureID             *string
	SessionID             *string
	InstanceID            *string
	WindowID              *string
	OpenMode              *string
	LoadedCaptureVerified bool
	ErrorCode             *string
	ErrorMessage          string
	CreatedAt             time.Time
	UpdatedAt             time.Time
}

func strOrNil(s *string) interface{} {
	if s == nil {
		return nil
	}
	return *s
}

// ToMap serialises the record using the operation_get contract.
func (r Record) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"operation_id":            r.OperationID,
		"operation_type":          r.OperationType,
		"status":                  string(r.Status),
		"capture_id":              strOrNil(r.CaptureID),
		"session_id":              strOrNil(r.SessionID),
		"instance_id":             strOrNil(r.InstanceID),
		"window_id":               strOrNil(r.WindowID),
		"open_mode":               strOrNil(r.OpenMode),
		"loaded_capture_verified": r.LoadedCaptureVerified,
		"error_code":              strOrNil(r.ErrorCode),
		"error_message":           r.ErrorMessage,
		"created_at":              store.FormatTime(r.CreatedAt),
		"updated_at":              store.FormatTime(r.UpdatedAt),
	}
}

// Tracker is a bounded, thread-safe operation registry.
type Tracker struct {
	mu      sync.Mutex
	ops     map[string]*Record
	order   []string
	counter int
}

// NewTracker returns an empty tracker.
func NewTracker() *Tracker { return &Tracker{ops: map[string]*Record{}} }

// Create registers a new operation in the requested state.
func (t *Tracker) Create(opType string, captureID, openMode string) Record {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.counter++
	now := time.Now().UTC()
	rec := &Record{
		OperationID:   fmt.Sprintf("op-%06d", t.counter),
		OperationType: opType,
		Status:        StatusRequested,
		CaptureID:     &captureID,
		OpenMode:      &openMode,
		CreatedAt:     now,
		UpdatedAt:     now,
	}
	t.ops[rec.OperationID] = rec
	t.order = append(t.order, rec.OperationID)
	for len(t.order) > maxOperations {
		delete(t.ops, t.order[0])
		t.order = t.order[1:]
	}
	return *rec
}

// Update applies fn to the operation and bumps updated_at.
func (t *Tracker) Update(id string, fn func(*Record)) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if rec, ok := t.ops[id]; ok {
		fn(rec)
		rec.UpdatedAt = time.Now().UTC()
	}
}

// Get returns a snapshot of the operation.
func (t *Tracker) Get(id string) (Record, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	rec, ok := t.ops[id]
	if !ok {
		return Record{}, false
	}
	return *rec, true
}

// Str returns a pointer to a copy of s (helper for optional fields).
func Str(s string) *string { return &s }
