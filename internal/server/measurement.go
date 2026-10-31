package server

import (
	"crypto/rand"
	"encoding/hex"
	"sort"
	"strings"
	"sync"
)

// MeasurementRecord stores GPU counter results from a collect_gpu_counters call.
type MeasurementRecord struct {
	MeasurementID       string
	Status              string // "completed" | "failed" | "invalidated"
	CapturePath         string
	InstanceID          string
	CounterIDs          []interface{}
	CounterDescriptions []interface{}
	Results             []interface{}
	CreatedAt           float64
	Metadata            map[string]interface{}
	Error               string
}

// toDict converts a MeasurementRecord to a map for JSON serialisation.
func (m *MeasurementRecord) toDict() map[string]interface{} {
	var errVal interface{}
	if m.Error != "" {
		errVal = m.Error
	}
	return map[string]interface{}{
		"measurement_id":      m.MeasurementID,
		"status":              m.Status,
		"capture_path":        m.CapturePath,
		"instance_id":         m.InstanceID,
		"counter_ids":         m.CounterIDs,
		"counter_descriptions": m.CounterDescriptions,
		"result_count":        len(m.Results),
		"created_at":          m.CreatedAt,
		"metadata":            m.Metadata,
		"error":               errVal,
	}
}

// MeasurementStore is an in-memory LRU store for MeasurementRecords.
// It evicts the oldest entries when the capacity limit is exceeded.
const measurementStoreMax = 20

type measurementEntry struct {
	id  string
	rec *MeasurementRecord
}

// MeasurementStore is an in-memory LRU store for MeasurementRecords.
type MeasurementStore struct {
	mu      sync.Mutex
	entries []measurementEntry // ordered oldest→newest
}

func newMeasurementStore() *MeasurementStore {
	return &MeasurementStore{}
}

// makeID returns an 8-character random hex string.
func (s *MeasurementStore) makeID() string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		return "00000000"
	}
	return hex.EncodeToString(b)
}

// store saves a MeasurementRecord, evicting the oldest if capacity is exceeded.
func (s *MeasurementStore) store(rec *MeasurementRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.entries = append(s.entries, measurementEntry{id: rec.MeasurementID, rec: rec})
	if len(s.entries) > measurementStoreMax {
		s.entries = s.entries[len(s.entries)-measurementStoreMax:]
	}
}

// get returns the MeasurementRecord with the given ID, or nil if not found.
func (s *MeasurementStore) get(id string) *MeasurementRecord {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := len(s.entries) - 1; i >= 0; i-- {
		if s.entries[i].id == id {
			return s.entries[i].rec
		}
	}
	return nil
}

// invalidateForCapture marks all records for the given capture path as
// "invalidated" and returns the count of records affected.
func (s *MeasurementStore) invalidateForCapture(path string) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	n := 0
	for _, e := range s.entries {
		if e.rec.CapturePath == path && e.rec.Status == "completed" {
			e.rec.Status = "invalidated"
			n++
		}
	}
	return n
}

// ---------------------------------------------------------------------------
// Analysis query helpers
// ---------------------------------------------------------------------------

// findCounterName returns the name string for a counter_id in the descriptions.
func findCounterName(descs []interface{}, counterID int) string {
	for _, d := range descs {
		dm, ok := d.(map[string]interface{})
		if !ok {
			continue
		}
		cid := toInt(dm["counter_id"])
		if cid == counterID {
			if name, ok := dm["name"].(string); ok {
				return name
			}
		}
	}
	return ""
}

// findCounterUnit returns the unit string for a counter_id in the descriptions.
func findCounterUnit(descs []interface{}, counterID int) string {
	for _, d := range descs {
		dm, ok := d.(map[string]interface{})
		if !ok {
			continue
		}
		cid := toInt(dm["counter_id"])
		if cid == counterID {
			if unit, ok := dm["unit"].(string); ok {
				return unit
			}
		}
	}
	return ""
}

// autoDetectTimingCounter picks a counter_id that looks like a timing counter.
// It prefers counters whose unit or name contains time-related keywords.
// Returns -1 if no good candidate is found.
func autoDetectTimingCounter(descs []interface{}) int {
	if len(descs) == 0 {
		return -1
	}
	timeKW := []string{"time", "ms", "ns", "duration", "elapsed"}
	for _, d := range descs {
		dm, ok := d.(map[string]interface{})
		if !ok {
			continue
		}
		unit, _ := dm["unit"].(string)
		name, _ := dm["name"].(string)
		lower := strings.ToLower(unit + " " + name)
		for _, kw := range timeKW {
			if strings.Contains(lower, kw) {
				return toInt(dm["counter_id"])
			}
		}
	}
	// Fall back to the first counter.
	if dm, ok := descs[0].(map[string]interface{}); ok {
		return toInt(dm["counter_id"])
	}
	return -1
}

// toInt converts a JSON number (float64) or int to int.
func toInt(v interface{}) int {
	switch x := v.(type) {
	case float64:
		return int(x)
	case int:
		return x
	case int64:
		return int(x)
	}
	return 0
}

// queryTimings returns events for a single counter, with paging and sort.
// sortBy: "event_id" (default) or "value".
func (s *MeasurementStore) queryTimings(measurementID string, counterID int, limit, offset int, sortBy string) (map[string]interface{}, string) {
	rec := s.get(measurementID)
	if rec == nil {
		return nil, "measurement_not_found"
	}
	if rec.Status != "completed" {
		return nil, "measurement_not_ready"
	}

	if counterID < 0 {
		counterID = autoDetectTimingCounter(rec.CounterDescriptions)
		if counterID < 0 {
			return nil, "no_timing_counter_available"
		}
	}

	// Filter results to the requested counter.
	var events []map[string]interface{}
	for _, r := range rec.Results {
		rm, ok := r.(map[string]interface{})
		if !ok {
			continue
		}
		if toInt(rm["counter_id"]) == counterID {
			events = append(events, rm)
		}
	}

	// Sort.
	switch sortBy {
	case "value":
		sort.Slice(events, func(i, j int) bool {
			vi, _ := events[i]["value"].(float64)
			vj, _ := events[j]["value"].(float64)
			return vi > vj // descending by value
		})
	default:
		sort.Slice(events, func(i, j int) bool {
			return toInt(events[i]["event_id"]) < toInt(events[j]["event_id"])
		})
	}

	total := len(events)
	if offset > total {
		offset = total
	}
	events = events[offset:]
	if limit > 0 && len(events) > limit {
		events = events[:limit]
	}

	out := make([]interface{}, len(events))
	for i, e := range events {
		out[i] = e
	}

	return map[string]interface{}{
		"measurement_id": measurementID,
		"counter_id":     counterID,
		"counter_name":   findCounterName(rec.CounterDescriptions, counterID),
		"unit":           findCounterUnit(rec.CounterDescriptions, counterID),
		"total":          total,
		"offset":         offset,
		"limit":          limit,
		"events":         out,
	}, ""
}

// queryPerformanceSummary returns the top-N events by counter value.
func (s *MeasurementStore) queryPerformanceSummary(measurementID string, counterID, topN int) (map[string]interface{}, string) {
	rec := s.get(measurementID)
	if rec == nil {
		return nil, "measurement_not_found"
	}
	if rec.Status != "completed" {
		return nil, "measurement_not_ready"
	}

	if counterID < 0 {
		counterID = autoDetectTimingCounter(rec.CounterDescriptions)
		if counterID < 0 {
			return nil, "no_timing_counter_available"
		}
	}

	var events []map[string]interface{}
	for _, r := range rec.Results {
		rm, ok := r.(map[string]interface{})
		if !ok {
			continue
		}
		if toInt(rm["counter_id"]) == counterID {
			events = append(events, rm)
		}
	}

	// Sort descending by value.
	sort.Slice(events, func(i, j int) bool {
		vi, _ := events[i]["value"].(float64)
		vj, _ := events[j]["value"].(float64)
		return vi > vj
	})

	// Sum total.
	var totalValue float64
	for _, e := range events {
		v, _ := e["value"].(float64)
		totalValue += v
	}

	if topN <= 0 {
		topN = 20
	}
	top := events
	if len(top) > topN {
		top = top[:topN]
	}
	out := make([]interface{}, len(top))
	for i, e := range top {
		out[i] = e
	}

	return map[string]interface{}{
		"measurement_id":        measurementID,
		"counter_id":            counterID,
		"counter_name":          findCounterName(rec.CounterDescriptions, counterID),
		"unit":                  findCounterUnit(rec.CounterDescriptions, counterID),
		"top_n":                 topN,
		"total_events_measured": len(events),
		"total_value":           totalValue,
		"top_events":            out,
	}, ""
}

// queryPipelineStatistics returns all measurement results with paging.
// eventID < 0 means no filter.
func (s *MeasurementStore) queryPipelineStatistics(measurementID string, eventID, limit, offset int) (map[string]interface{}, string) {
	rec := s.get(measurementID)
	if rec == nil {
		return nil, "measurement_not_found"
	}
	if rec.Status != "completed" {
		return nil, "measurement_not_ready"
	}

	var stats []map[string]interface{}
	for _, r := range rec.Results {
		rm, ok := r.(map[string]interface{})
		if !ok {
			continue
		}
		if eventID >= 0 && toInt(rm["event_id"]) != eventID {
			continue
		}
		// Enrich with counter name.
		cid := toInt(rm["counter_id"])
		enriched := map[string]interface{}{
			"event_id":     rm["event_id"],
			"counter_id":   rm["counter_id"],
			"value":        rm["value"],
			"counter_name": findCounterName(rec.CounterDescriptions, cid),
		}
		stats = append(stats, enriched)
	}

	total := len(stats)
	if offset > total {
		offset = total
	}
	stats = stats[offset:]
	if limit > 0 && len(stats) > limit {
		stats = stats[:limit]
	}

	out := make([]interface{}, len(stats))
	for i, e := range stats {
		out[i] = e
	}

	// Collect unique counter IDs from full result set.
	cidSet := map[int]bool{}
	for _, r := range rec.Results {
		rm, ok := r.(map[string]interface{})
		if !ok {
			continue
		}
		cidSet[toInt(rm["counter_id"])] = true
	}
	cids := make([]int, 0, len(cidSet))
	for cid := range cidSet {
		cids = append(cids, cid)
	}
	sort.Ints(cids)
	cidsOut := make([]interface{}, len(cids))
	for i, c := range cids {
		cidsOut[i] = c
	}

	return map[string]interface{}{
		"measurement_id":   measurementID,
		"total":            total,
		"offset":           offset,
		"limit":            limit,
		"statistics":       out,
		"stats_counter_ids": cidsOut,
	}, ""
}
