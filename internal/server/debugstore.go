package server

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
)

// DebugRecord stores a shader debug trace returned by the extension.
type DebugRecord struct {
	DebugID     string
	Status      string // "ready" | "failed"
	Stage       string // "pixel" | "vertex" | "compute"
	EventID     int
	CapturePath string
	InstanceID  string
	Steps       []interface{}
	InitialVars map[string]interface{}
	Metadata    map[string]interface{}
	Error       string
	CreatedAt   float64
}

// toDict converts a DebugRecord to a map for JSON serialisation.
func (d *DebugRecord) toDict() map[string]interface{} {
	return map[string]interface{}{
		"debug_id":     d.DebugID,
		"status":       d.Status,
		"stage":        d.Stage,
		"event_id":     d.EventID,
		"capture_path": d.CapturePath,
		"instance_id":  d.InstanceID,
		"step_count":   len(d.Steps),
		"created_at":   d.CreatedAt,
		"metadata":     d.Metadata,
		"error":        d.Error,
	}
}

// debugStoreMax is the maximum number of DebugRecords retained in memory.
const debugStoreMax = 10

type debugEntry struct {
	id  string
	rec *DebugRecord
}

// DebugStore is an in-memory LRU store for DebugRecords.
type DebugStore struct {
	mu      sync.Mutex
	entries []debugEntry // ordered oldest→newest
}

func newDebugStore() *DebugStore {
	return &DebugStore{}
}

// makeID returns a "dbg_" + 8-character random hex string.
func (s *DebugStore) makeID() string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		return "dbg_00000000"
	}
	return "dbg_" + hex.EncodeToString(b)
}

// store saves a DebugRecord, evicting the oldest if capacity is exceeded.
func (s *DebugStore) store(rec *DebugRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.entries = append(s.entries, debugEntry{id: rec.DebugID, rec: rec})
	if len(s.entries) > debugStoreMax {
		s.entries = s.entries[len(s.entries)-debugStoreMax:]
	}
}

// get returns the DebugRecord with the given ID, or nil if not found.
func (s *DebugStore) get(id string) *DebugRecord {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := len(s.entries) - 1; i >= 0; i-- {
		if s.entries[i].id == id {
			return s.entries[i].rec
		}
	}
	return nil
}

// listIDs returns all stored debug IDs in insertion order.
func (s *DebugStore) listIDs() []string {
	s.mu.Lock()
	defer s.mu.Unlock()
	ids := make([]string, 0, len(s.entries))
	for _, e := range s.entries {
		ids = append(ids, e.id)
	}
	return ids
}
