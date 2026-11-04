package server

import (
	"context"
	"sort"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/toolspec"
)

// maxDebugRecords bounds the in-memory shader debug trace store.
const maxDebugRecords = 10

// maxDebugVariables bounds get_shader_debug_variables output.
const maxDebugVariables = 50

type debugRecord struct {
	id          string
	status      string // ready | invalidated
	stage       string
	eventID     int
	capturePath string
	instanceID  string
	steps       []map[string]interface{}
	initialVars map[string]interface{}
	metadata    map[string]interface{}
	createdAt   time.Time
}

type debugStore struct {
	mu      sync.Mutex
	max     int
	records map[string]*debugRecord
}

func newDebugStore(max int) *debugStore {
	return &debugStore{max: max, records: map[string]*debugRecord{}}
}

func (s *debugStore) put(rec *debugRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.records[rec.id]; !exists && len(s.records) >= s.max {
		var oldest *debugRecord
		for _, r := range s.records {
			if oldest == nil || r.createdAt.Before(oldest.createdAt) {
				oldest = r
			}
		}
		delete(s.records, oldest.id)
	}
	s.records[rec.id] = rec
}

func (s *debugStore) get(id string) (debugRecord, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rec, ok := s.records[id]
	if !ok {
		return debugRecord{}, false
	}
	return *rec, true
}

// ids returns every stored debug ID, newest first.
func (s *debugStore) ids() []string {
	s.mu.Lock()
	defer s.mu.Unlock()
	recs := make([]*debugRecord, 0, len(s.records))
	for _, r := range s.records {
		recs = append(recs, r)
	}
	sort.Slice(recs, func(i, j int) bool { return recs[i].createdAt.After(recs[j].createdAt) })
	out := make([]string, 0, len(recs))
	for _, r := range recs {
		out = append(out, r.id)
	}
	return out
}

func (s *debugStore) invalidate(instanceID, capturePath string) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	n := 0
	for _, r := range s.records {
		if r.instanceID == instanceID && r.capturePath == capturePath && r.status == "ready" {
			r.status = "invalidated"
			n++
		}
	}
	return n
}

// runShaderDebug executes a debug_* extension operation and stores the trace.
func (r *Router) runShaderDebug(ctx context.Context, call *toolCall, op, defaultStage string, params, metadata map[string]interface{}) map[string]interface{} {
	ext, errResult := r.resolveExtension(argString(call.args, "instance_id", ""))
	if ext == nil {
		return errResult
	}
	res, errRes := r.inspect(ctx, ext, op, params, toolspec.ReplayTimeout)
	if errRes != nil {
		return errRes
	}

	stage, _ := res["stage"].(string)
	if stage == "" {
		stage = defaultStage
	}
	eventID, ok := toInt(res["event_id"])
	if !ok {
		eventID, _ = toInt(params["event_id"])
	}
	stepCount, _ := toInt(res["step_count"])
	truncated, _ := res["truncated"].(bool)
	metadata["step_count"] = stepCount
	metadata["truncated"] = truncated
	if w, ok := res["collection_warning"]; ok && w != nil && w != "" {
		metadata["collection_warning"] = w
	}
	initial, _ := res["initial_vars"].(map[string]interface{})
	if initial == nil {
		initial = map[string]interface{}{}
	}
	path, _ := res["_capture_path"].(string)

	r.mu.Lock()
	instanceID := ext.instanceID
	r.mu.Unlock()
	rec := &debugRecord{
		id:          "dbg_" + shortID(),
		status:      "ready",
		stage:       stage,
		eventID:     eventID,
		capturePath: path,
		instanceID:  instanceID,
		steps:       mapList(res["steps"]),
		initialVars: initial,
		metadata:    metadata,
		createdAt:   time.Now(),
	}
	r.debug.put(rec)
	return map[string]interface{}{
		"debug_id":   rec.id,
		"stage":      rec.stage,
		"event_id":   rec.eventID,
		"step_count": stepCount,
		"truncated":  truncated,
	}
}

func (r *Router) toolDebugPixelShader(ctx context.Context, call *toolCall) map[string]interface{} {
	a := call.args
	x, y := argInt(a, "x", 0), argInt(a, "y", 0)
	sample, primitive, view := argInt(a, "sample", 0), argInt(a, "primitive", -1), argInt(a, "view", 0)
	params := map[string]interface{}{
		"x": x, "y": y, "event_id": argInt(a, "event_id", 0), "sample": sample,
		"primitive": primitive, "view": view, "max_steps": argInt(a, "max_steps", 200),
	}
	meta := map[string]interface{}{"x": x, "y": y, "sample": sample, "primitive": primitive, "view": view}
	return r.runShaderDebug(ctx, call, toolspec.OpDebugPixel, "pixel", params, meta)
}

func (r *Router) toolDebugVertexShader(ctx context.Context, call *toolCall) map[string]interface{} {
	a := call.args
	vert, inst, idx, view := argInt(a, "vert_id", 0), argInt(a, "inst_id", 0), argInt(a, "idx", 0), argInt(a, "view", 0)
	params := map[string]interface{}{
		"vert_id": vert, "inst_id": inst, "idx": idx, "view": view,
		"event_id": argInt(a, "event_id", 0), "max_steps": argInt(a, "max_steps", 200),
	}
	meta := map[string]interface{}{"vert_id": vert, "inst_id": inst, "idx": idx, "view": view}
	return r.runShaderDebug(ctx, call, toolspec.OpDebugVertex, "vertex", params, meta)
}

func (r *Router) toolDebugComputeShader(ctx context.Context, call *toolCall) map[string]interface{} {
	a := call.args
	g := []int{argInt(a, "group_x", 0), argInt(a, "group_y", 0), argInt(a, "group_z", 0)}
	t := []int{argInt(a, "thread_x", 0), argInt(a, "thread_y", 0), argInt(a, "thread_z", 0)}
	params := map[string]interface{}{
		"group_x": g[0], "group_y": g[1], "group_z": g[2],
		"thread_x": t[0], "thread_y": t[1], "thread_z": t[2],
		"event_id": argInt(a, "event_id", 0), "max_steps": argInt(a, "max_steps", 200),
	}
	meta := map[string]interface{}{"group": g, "thread": t}
	return r.runShaderDebug(ctx, call, toolspec.OpDebugCompute, "compute", params, meta)
}

// readyDebugRecord loads a ready trace or returns the error result.
func (r *Router) readyDebugRecord(id string) (debugRecord, map[string]interface{}) {
	if id == "" {
		return debugRecord{}, map[string]interface{}{"error": "debug_id is required"}
	}
	rec, ok := r.debug.get(id)
	if !ok {
		return debugRecord{}, map[string]interface{}{"error": "debug_id_not_found", "debug_id": id}
	}
	if rec.status != "ready" {
		return debugRecord{}, map[string]interface{}{"error": "debug_not_ready", "debug_id": id, "status": rec.status}
	}
	return rec, nil
}

func (r *Router) toolGetShaderDebugTrace(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "debug_id", "")
	rec, errRes := r.readyDebugRecord(id)
	if errRes != nil {
		return errRes
	}
	count := clamp(argInt(call.args, "count", 50), 1, 500)
	first := clamp(argInt(call.args, "first_step", 0), 0, 1<<31-1)
	lo, hi := page(len(rec.steps), first, count)
	return map[string]interface{}{
		"debug_id":       id,
		"stage":          rec.stage,
		"event_id":       rec.eventID,
		"first_step":     first,
		"returned_steps": hi - lo,
		"total_steps":    len(rec.steps),
		"has_more":       first+count < len(rec.steps),
		"steps":          rec.steps[lo:hi],
	}
}

func (r *Router) toolGetShaderDebugVariables(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "debug_id", "")
	rec, errRes := r.readyDebugRecord(id)
	if errRes != nil {
		return errRes
	}
	step := argInt(call.args, "step", 0)
	total := len(rec.steps)
	if total == 0 {
		return map[string]interface{}{
			"debug_id":  id,
			"step":      step,
			"variables": rec.initialVars,
			"note":      "no trace steps available; showing initial state",
		}
	}
	step = clamp(step, 0, total-1)

	// Reconstruct state: initial variables, then every change up to step.
	var order []string
	state := map[string]interface{}{}
	set := func(name string, v interface{}) {
		if _, seen := state[name]; !seen {
			order = append(order, name)
		}
		state[name] = v
	}
	initNames := make([]string, 0, len(rec.initialVars))
	for name := range rec.initialVars {
		initNames = append(initNames, name)
	}
	sort.Strings(initNames)
	for _, name := range initNames {
		set(name, rec.initialVars[name])
	}
	for i := 0; i <= step; i++ {
		for _, ch := range mapList(rec.steps[i]["changes"]) {
			after, _ := ch["after"].(map[string]interface{})
			if name, _ := after["name"].(string); name != "" {
				set(name, after)
			}
		}
	}

	filter := map[string]bool{}
	for _, n := range argStringList(call.args, "variable_names") {
		filter[n] = true
	}
	vars := map[string]interface{}{}
	for _, name := range order {
		if len(filter) > 0 && !filter[name] {
			continue
		}
		if len(vars) >= maxDebugVariables {
			break
		}
		vars[name] = state[name]
	}
	return map[string]interface{}{
		"debug_id":    id,
		"stage":       rec.stage,
		"event_id":    rec.eventID,
		"step":        step,
		"total_steps": total,
		"variables":   vars,
	}
}

func (r *Router) toolGetShaderDebugStatus(_ context.Context, call *toolCall) map[string]interface{} {
	id := argString(call.args, "debug_id", "")
	if id == "" {
		ids := r.debug.ids()
		return map[string]interface{}{"debug_ids": ids, "count": len(ids)}
	}
	rec, ok := r.debug.get(id)
	if !ok {
		return map[string]interface{}{"error": "debug_id_not_found", "debug_id": id}
	}
	out := map[string]interface{}{
		"debug_id":   id,
		"status":     rec.status,
		"stage":      rec.stage,
		"event_id":   rec.eventID,
		"step_count": len(rec.steps),
	}
	for k, v := range rec.metadata {
		out[k] = v
	}
	out["step_count"] = len(rec.steps)
	return out
}
