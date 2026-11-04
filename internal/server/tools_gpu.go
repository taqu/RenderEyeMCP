package server

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/toolspec"
)

// maxMeasurements bounds the in-memory GPU measurement store.
const maxMeasurements = 20

// maxEventTreePages bounds the list_events fallback used with extensions that
// predate the event_tree operation (200 events per page).
const maxEventTreePages = 100

func shortID() string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%08x", time.Now().UnixNano()&0xffffffff)
	}
	return hex.EncodeToString(b)
}

// ---------------------------------------------------------------------------
// Measurement store
// ---------------------------------------------------------------------------

type counterResult struct {
	EventID   int         `json:"event_id"`
	CounterID int         `json:"counter_id"`
	Value     interface{} `json:"value"`
}

func (c counterResult) toMap() map[string]interface{} {
	return map[string]interface{}{"event_id": c.EventID, "counter_id": c.CounterID, "value": c.Value}
}

func (c counterResult) num() (float64, bool) {
	switch v := c.Value.(type) {
	case float64:
		return v, true
	case int:
		return float64(v), true
	}
	return 0, false
}

type measurementRecord struct {
	id           string
	status       string // completed | invalidated
	capturePath  string
	instanceID   string
	counterIDs   []int
	descriptions []map[string]interface{}
	results      []counterResult
	createdAt    time.Time
	metadata     map[string]interface{}
}

type measurementStore struct {
	mu      sync.Mutex
	max     int
	records map[string]*measurementRecord
}

func newMeasurementStore(max int) *measurementStore {
	return &measurementStore{max: max, records: map[string]*measurementRecord{}}
}

func (s *measurementStore) put(rec *measurementRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.records[rec.id]; !exists && len(s.records) >= s.max {
		var oldest *measurementRecord
		for _, r := range s.records {
			if oldest == nil || r.createdAt.Before(oldest.createdAt) {
				oldest = r
			}
		}
		delete(s.records, oldest.id)
	}
	s.records[rec.id] = rec
}

// get returns a snapshot (records are immutable apart from status).
func (s *measurementStore) get(id string) (measurementRecord, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rec, ok := s.records[id]
	if !ok {
		return measurementRecord{}, false
	}
	return *rec, true
}

func (s *measurementStore) invalidate(instanceID, capturePath string) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	n := 0
	for _, r := range s.records {
		if r.instanceID == instanceID && r.capturePath == capturePath && r.status == "completed" {
			r.status = "invalidated"
			n++
		}
	}
	return n
}

func (rec *measurementRecord) counterDesc(id int) map[string]interface{} {
	for _, d := range rec.descriptions {
		if cid, ok := toInt(d["counter_id"]); ok && cid == id {
			return d
		}
	}
	return map[string]interface{}{}
}

func descString(d map[string]interface{}, key string) string {
	s, _ := d[key].(string)
	return s
}

// resolveTimingCounter picks counterID, else the first duration/time counter,
// else the first collected counter.
func (rec *measurementRecord) resolveTimingCounter(counterID *int) (int, bool) {
	if counterID != nil {
		return *counterID, true
	}
	for _, d := range rec.descriptions {
		name := strings.ToLower(descString(d, "name"))
		unit := strings.ToLower(descString(d, "unit"))
		if strings.Contains(name, "duration") || strings.Contains(unit, "second") || strings.Contains(name, "time") {
			if id, ok := toInt(d["counter_id"]); ok {
				return id, true
			}
		}
	}
	if len(rec.counterIDs) > 0 {
		return rec.counterIDs[0], true
	}
	return 0, false
}

// ---------------------------------------------------------------------------
// collect_gpu_counters
// ---------------------------------------------------------------------------

func parseCounterResults(raw interface{}) []counterResult {
	list, _ := raw.([]interface{})
	out := make([]counterResult, 0, len(list))
	for _, item := range list {
		m, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		eid, _ := toInt(m["event_id"])
		cid, _ := toInt(m["counter_id"])
		out = append(out, counterResult{EventID: eid, CounterID: cid, Value: m["value"]})
	}
	return out
}

func intList(raw interface{}) []int {
	list, _ := raw.([]interface{})
	out := make([]int, 0, len(list))
	for _, v := range list {
		if i, ok := toInt(v); ok {
			out = append(out, i)
		}
	}
	return out
}

func mapList(raw interface{}) []map[string]interface{} {
	list, _ := raw.([]interface{})
	out := make([]map[string]interface{}, 0, len(list))
	for _, v := range list {
		if m, ok := v.(map[string]interface{}); ok {
			out = append(out, m)
		}
	}
	return out
}

// isWholeNumber reports whether v is an integral JSON number.
func isWholeNumber(v interface{}) bool {
	f, ok := v.(float64)
	return ok && f == float64(int64(f))
}

// averageRuns averages each (event, counter) value across runs.  Integral
// series use floor division, matching the former Python implementation.
func averageRuns(runs [][]counterResult) []counterResult {
	type key struct{ e, c int }
	var order []key
	values := map[key][]interface{}{}
	for _, run := range runs {
		for _, r := range run {
			if r.Value == nil {
				continue
			}
			k := key{r.EventID, r.CounterID}
			if _, seen := values[k]; !seen {
				order = append(order, k)
			}
			values[k] = append(values[k], r.Value)
		}
	}
	out := make([]counterResult, 0, len(order))
	for _, k := range order {
		vals := values[k]
		allInt := true
		sum := 0.0
		for _, v := range vals {
			f, _ := v.(float64)
			sum += f
			if !isWholeNumber(v) {
				allInt = false
			}
		}
		var avg interface{} = sum / float64(len(vals))
		if allInt {
			avg = float64(int64(sum) / int64(len(vals)))
		}
		out = append(out, counterResult{EventID: k.e, CounterID: k.c, Value: avg})
	}
	return out
}

func (r *Router) toolCollectGPUCounters(ctx context.Context, call *toolCall) map[string]interface{} {
	raw, _ := call.args["counter_ids"].([]interface{})
	counterIDs := make([]interface{}, 0, len(raw))
	for _, v := range raw {
		if i, ok := toInt(v); ok {
			counterIDs = append(counterIDs, i)
		}
	}
	if len(counterIDs) == 0 {
		return map[string]interface{}{"error": "missing_counter_ids", "message": "counter_ids must be a non-empty list"}
	}
	repeats := clamp(argInt(call.args, "repeats", 1), 1, toolspec.MaxCounterRepeats)

	ext, errResult := r.resolveExtension(argString(call.args, "instance_id", ""))
	if ext == nil {
		return errResult
	}

	var runs [][]counterResult
	var last map[string]interface{}
	capturePath := ""
	for i := 0; i < repeats; i++ {
		res, errRes := r.inspect(ctx, ext, toolspec.OpFetchGPUCounters,
			map[string]interface{}{"counter_ids": counterIDs}, toolspec.ReplayTimeout)
		if errRes != nil {
			if i > 0 {
				errRes["completed_runs"] = i
			}
			return errRes
		}
		path, _ := res["_capture_path"].(string)
		if i == 0 {
			capturePath = path
		} else if path != capturePath {
			return map[string]interface{}{
				"error":   "capture_changed",
				"message": "The loaded capture changed between collection runs; measurement discarded",
			}
		}
		runs = append(runs, parseCounterResults(res["results"]))
		last = res
	}

	results := runs[0]
	if repeats > 1 {
		results = averageRuns(runs)
	}
	fetched := intList(last["counters_fetched"])
	invalid, _ := last["counters_invalid"].([]interface{})
	if invalid == nil {
		invalid = []interface{}{}
	}

	r.mu.Lock()
	instanceID := ext.instanceID
	r.mu.Unlock()
	rec := &measurementRecord{
		id:           shortID(),
		status:       "completed",
		capturePath:  capturePath,
		instanceID:   instanceID,
		counterIDs:   fetched,
		descriptions: mapList(last["counter_descriptions"]),
		results:      results,
		createdAt:    time.Now(),
		metadata: map[string]interface{}{
			"counters_invalid": invalid,
			"repeats":          repeats,
			"result_count":     len(results),
			"instance_id":      instanceID,
		},
	}
	r.measure.put(rec)

	return map[string]interface{}{
		"measurement_id":   rec.id,
		"status":           "completed",
		"capture_path":     capturePath,
		"counters_fetched": fetched,
		"counters_invalid": invalid,
		"result_count":     len(results),
		"repeats":          repeats,
	}
}

// ---------------------------------------------------------------------------
// Analysis tools (no GPU work)
// ---------------------------------------------------------------------------

func measurementNotFound(id string) map[string]interface{} {
	return map[string]interface{}{"error": "measurement_not_found", "measurement_id": id}
}

func (r *Router) toolGetGPUMeasurementStatus(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "measurement_id", "")
	rec, ok := r.measure.get(id)
	if !ok {
		return measurementNotFound(id)
	}
	var capturePath interface{}
	if rec.capturePath != "" {
		capturePath = rec.capturePath
	}
	return map[string]interface{}{
		"measurement_id":       rec.id,
		"status":               rec.status,
		"capture_path":         capturePath,
		"counter_ids":          rec.counterIDs,
		"counter_descriptions": rec.descriptions,
		"result_count":         len(rec.results),
		"created_at":           float64(rec.createdAt.UnixNano()) / 1e9,
		"metadata":             rec.metadata,
		"error":                nil,
	}
}

func sortResults(entries []counterResult, sortBy string) {
	val := func(c counterResult) float64 { v, _ := c.num(); return v }
	switch sortBy {
	case "value_asc":
		sort.SliceStable(entries, func(i, j int) bool { return val(entries[i]) < val(entries[j]) })
	case "event_id":
		sort.SliceStable(entries, func(i, j int) bool { return entries[i].EventID < entries[j].EventID })
	case "event_id_desc":
		sort.SliceStable(entries, func(i, j int) bool { return entries[i].EventID > entries[j].EventID })
	default: // value_desc
		sort.SliceStable(entries, func(i, j int) bool { return val(entries[i]) > val(entries[j]) })
	}
}

func resultMaps(entries []counterResult) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(entries))
	for _, e := range entries {
		out = append(out, e.toMap())
	}
	return out
}

func page(n, offset, limit int) (int, int) {
	if offset > n {
		offset = n
	}
	end := offset + limit
	if end > n {
		end = n
	}
	return offset, end
}

func (r *Router) toolGetGPUTimings(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "measurement_id", "")
	rec, ok := r.measure.get(id)
	if !ok {
		return measurementNotFound(id)
	}
	cid, ok := rec.resolveTimingCounter(argIntPtr(call.args, "counter_id"))
	if !ok {
		return map[string]interface{}{"error": "no_timing_counter", "message": "No timing counter found in measurement. Specify counter_id."}
	}
	minValue := argFloatPtr(call.args, "min_value")
	var entries []counterResult
	for _, e := range rec.results {
		if e.CounterID != cid {
			continue
		}
		if minValue != nil {
			if v, ok := e.num(); !ok || v < *minValue {
				continue
			}
		}
		entries = append(entries, e)
	}
	sortResults(entries, argString(call.args, "sort_by", "value_desc"))
	limit := clamp(argInt(call.args, "limit", 100), 1, 1000)
	offset := clamp(argInt(call.args, "offset", 0), 0, 1<<31-1)
	lo, hi := page(len(entries), offset, limit)
	desc := rec.counterDesc(cid)
	return map[string]interface{}{
		"measurement_id": id,
		"counter_id":     cid,
		"counter_name":   descString(desc, "name"),
		"unit":           descString(desc, "unit"),
		"total":          len(entries),
		"offset":         offset,
		"limit":          limit,
		"events":         resultMaps(entries[lo:hi]),
	}
}

func (r *Router) toolGetPerformanceSummary(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "measurement_id", "")
	rec, ok := r.measure.get(id)
	if !ok {
		return measurementNotFound(id)
	}
	cid, ok := rec.resolveTimingCounter(argIntPtr(call.args, "counter_id"))
	if !ok {
		return map[string]interface{}{"error": "no_counter", "message": "No counter available. Specify counter_id."}
	}
	var entries []counterResult
	total := 0.0
	for _, e := range rec.results {
		if e.CounterID != cid {
			continue
		}
		if v, ok := e.num(); ok {
			entries = append(entries, e)
			total += v
		}
	}
	sortResults(entries, "value_desc")
	topN := clamp(argInt(call.args, "top_n", 20), 1, 100)
	if topN > len(entries) {
		topN = len(entries)
	}
	desc := rec.counterDesc(cid)
	return map[string]interface{}{
		"measurement_id":        id,
		"counter_id":            cid,
		"counter_name":          descString(desc, "name"),
		"unit":                  descString(desc, "unit"),
		"top_n":                 topN,
		"total_events_measured": len(entries),
		"total_value":           total,
		"top_events":            resultMaps(entries[:topN]),
	}
}

var pipelineStatsKeywords = []string{
	"vertices", "primitives", "invocations", "samples", "rasterizer",
	"vertex shader", "pixel shader", "fragment shader", "geometry shader",
	"hull shader", "domain shader", "compute shader", "tessellation", "input assembl",
}

func (r *Router) toolGetPipelineStatistics(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "measurement_id", "")
	rec, ok := r.measure.get(id)
	if !ok {
		return measurementNotFound(id)
	}
	statsIDs := map[int]bool{}
	names := map[int]string{}
	for _, d := range rec.descriptions {
		cid, ok := toInt(d["counter_id"])
		if !ok {
			continue
		}
		name := descString(d, "name")
		names[cid] = name
		lower := strings.ToLower(name)
		for _, kw := range pipelineStatsKeywords {
			if strings.Contains(lower, kw) {
				statsIDs[cid] = true
				break
			}
		}
	}
	eventID := argIntPtr(call.args, "event_id")
	var filtered []counterResult
	for _, e := range rec.results {
		if len(statsIDs) > 0 && !statsIDs[e.CounterID] {
			continue
		}
		if eventID != nil && e.EventID != *eventID {
			continue
		}
		filtered = append(filtered, e)
	}
	limit := clamp(argInt(call.args, "limit", 100), 1, 1000)
	offset := clamp(argInt(call.args, "offset", 0), 0, 1<<31-1)
	lo, hi := page(len(filtered), offset, limit)
	stats := make([]map[string]interface{}, 0, hi-lo)
	for _, e := range filtered[lo:hi] {
		m := e.toMap()
		m["counter_name"] = names[e.CounterID]
		stats = append(stats, m)
	}
	ids := make([]int, 0, len(statsIDs))
	for cid := range statsIDs {
		ids = append(ids, cid)
	}
	sort.Ints(ids)
	return map[string]interface{}{
		"measurement_id":    id,
		"total":             len(filtered),
		"offset":            offset,
		"limit":             limit,
		"statistics":        stats,
		"stats_counter_ids": ids,
	}
}

// ---------------------------------------------------------------------------
// get_render_pass_performance
// ---------------------------------------------------------------------------

func (r *Router) toolGetRenderPassPerformance(ctx context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "measurement_id", "")
	rec, ok := r.measure.get(id)
	if !ok {
		return measurementNotFound(id)
	}
	cid, ok := rec.resolveTimingCounter(argIntPtr(call.args, "counter_id"))
	if !ok {
		return map[string]interface{}{"error": "no_counter", "message": "No counter available. Specify counter_id."}
	}
	values := map[int]float64{}
	for _, e := range rec.results {
		if e.CounterID == cid {
			if v, ok := e.num(); ok {
				values[e.EventID] = v
			}
		}
	}

	warn := func(msg string) map[string]interface{} {
		return map[string]interface{}{"measurement_id": id, "warning": msg, "passes": []interface{}{}}
	}

	// Default to the session the measurement was collected from.
	instanceID := argString(call.args, "instance_id", "")
	if instanceID == "" && rec.instanceID != "" {
		if e, _ := r.resolveExtension(rec.instanceID); e != nil {
			instanceID = rec.instanceID
		}
	}
	ext, errResult := r.resolveExtension(instanceID)
	if ext == nil {
		msg, _ := errResult["message"].(string)
		return warn("Could not connect to RenderDoc for event hierarchy: " + msg)
	}

	tree, path, errRes := r.eventTree(ctx, ext)
	if errRes != nil {
		msg, _ := errRes["message"].(string)
		if msg == "" {
			msg, _ = errRes["error"].(string)
		}
		return warn("Could not retrieve event hierarchy: " + msg)
	}
	if rec.capturePath != "" && path != "" && path != rec.capturePath {
		return warn(fmt.Sprintf("The loaded capture (%s) differs from the measured capture (%s); load the measured capture to aggregate passes", path, rec.capturePath))
	}

	passes := aggregatePasses(tree, values, 0)
	sort.SliceStable(passes, func(i, j int) bool {
		a, _ := passes[i]["aggregated_duration"].(float64)
		b, _ := passes[j]["aggregated_duration"].(float64)
		return a > b
	})
	desc := rec.counterDesc(cid)
	return map[string]interface{}{
		"measurement_id": id,
		"counter_id":     cid,
		"counter_name":   descString(desc, "name"),
		"unit":           descString(desc, "unit"),
		"passes":         passes,
		"pass_count":     len(passes),
		"aggregation_note": "aggregated_duration is the sum of leaf draw/dispatch event durations. " +
			"It is not the GPU elapsed wall-clock time of the pass.",
	}
}

// eventTree fetches the hierarchical action tree.  Extensions without the
// event_tree operation fall back to paging list_events and rebuilding the
// hierarchy from each event's depth (pre-order traversal).
func (r *Router) eventTree(ctx context.Context, ext *extState) ([]map[string]interface{}, string, map[string]interface{}) {
	res, errRes := r.inspect(ctx, ext, toolspec.OpEventTree, map[string]interface{}{}, toolspec.DefaultTimeout)
	if errRes == nil {
		path, _ := res["_capture_path"].(string)
		return mapList(res["events"]), path, nil
	}
	if code, _ := errRes["error"].(string); code != "unsupported_operation" {
		return nil, "", errRes
	}

	var flat []map[string]interface{}
	path := ""
	for p := 0; p < maxEventTreePages; p++ {
		res, errRes := r.inspect(ctx, ext, toolspec.OpListEvents,
			map[string]interface{}{"limit": 200, "offset": p * 200, "include_markers": true}, toolspec.DefaultTimeout)
		if errRes != nil {
			return nil, "", errRes
		}
		if p == 0 {
			path, _ = res["_capture_path"].(string)
		}
		flat = append(flat, mapList(res["events"])...)
		if more, _ := res["has_more"].(bool); !more {
			break
		}
	}
	return buildTree(flat), path, nil
}

// buildTree rebuilds children lists from a pre-order list annotated with depth.
func buildTree(flat []map[string]interface{}) []map[string]interface{} {
	var roots []map[string]interface{}
	var stack []map[string]interface{}
	for _, ev := range flat {
		node := make(map[string]interface{}, len(ev)+1)
		for k, v := range ev {
			node[k] = v
		}
		node["children"] = []interface{}{}
		depth, _ := toInt(ev["depth"])
		if depth > len(stack) {
			depth = len(stack)
		}
		stack = stack[:depth]
		if depth == 0 {
			roots = append(roots, node)
		} else {
			parent := stack[depth-1]
			parent["children"] = append(parent["children"].([]interface{}), node)
		}
		stack = append(stack, node)
	}
	return roots
}

func children(action map[string]interface{}) []map[string]interface{} {
	return mapList(action["children"])
}

// aggregatePasses groups leaf draw/dispatch values under marker regions.
func aggregatePasses(actions []map[string]interface{}, values map[int]float64, depth int) []map[string]interface{} {
	passes := []map[string]interface{}{}
	for _, a := range actions {
		kids := children(a)
		if a["action_type"] == "marker_begin" {
			total, measured, unmeasured, largest := sumLeafEvents(kids, values)
			eid, _ := toInt(a["event_id"])
			entry := map[string]interface{}{
				"name":                   a["name"],
				"event_id":               eid,
				"depth":                  depth,
				"event_count":            measured,
				"aggregated_duration":    total,
				"unmeasured_event_count": unmeasured,
				"aggregation":            "sum_of_leaf_event_durations",
			}
			if largest != nil {
				entry["largest_event"] = largest
			}
			if sub := aggregatePasses(kids, values, depth+1); len(sub) > 0 {
				entry["sub_passes"] = sub
			}
			passes = append(passes, entry)
		} else if len(kids) > 0 {
			passes = append(passes, aggregatePasses(kids, values, depth)...)
		}
	}
	return passes
}

func sumLeafEvents(actions []map[string]interface{}, values map[int]float64) (float64, int, int, map[string]interface{}) {
	total := 0.0
	measured, unmeasured := 0, 0
	var largest map[string]interface{}
	largestVal := 0.0
	consider := func(m map[string]interface{}) {
		if m == nil {
			return
		}
		v, _ := m["value"].(float64)
		if largest == nil || v > largestVal {
			largest, largestVal = m, v
		}
	}
	for _, a := range actions {
		kids := children(a)
		switch a["action_type"] {
		case "drawcall", "dispatch":
			eid, _ := toInt(a["event_id"])
			if v, ok := values[eid]; ok {
				total += v
				measured++
				consider(map[string]interface{}{"event_id": eid, "name": a["name"], "value": v})
			} else {
				unmeasured++
			}
		default:
			if len(kids) > 0 {
				t, m, u, l := sumLeafEvents(kids, values)
				total += t
				measured += m
				unmeasured += u
				consider(l)
			}
		}
	}
	return total, measured, unmeasured, largest
}
