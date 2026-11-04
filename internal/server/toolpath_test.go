package server

import (
	"encoding/json"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/ipc"
	"github.com/taqu/rendereye-mcp/internal/operations"
	"github.com/taqu/rendereye-mcp/internal/sessions"
	"github.com/taqu/rendereye-mcp/internal/store"
	"github.com/taqu/rendereye-mcp/internal/toolspec"
)

// newServiceRouter builds a Router with real (empty) registry, instance and
// session subsystems backed by a temporary database.
func newServiceRouter(t *testing.T) *Router {
	t.Helper()
	db, err := store.Open(filepath.Join(t.TempDir(), "captures.db"))
	if err != nil {
		t.Fatalf("open store: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	capCfg := config.DefaultCaptureConfig()
	capCfg.Enabled = false
	reg := captures.NewRegistry(capCfg, captures.NewStorage(db))
	inst := instances.NewManager()
	sess := sessions.NewManager(sessions.NewStorage(db), inst, reg, operations.NewTracker(), filepath.Join(t.TempDir(), "missing-qrenderdoc.exe"))
	r := NewRouterWithServices("svc-test", &Auth{token: "t"}, &Services{
		RenderdocExe: "", Captures: reg, Sessions: sess, Instances: inst,
	})
	t.Cleanup(r.Close)
	return r
}

// fakeExtension answers every inspect_capture with a generic successful
// result and records the operations it received.
type fakeExtension struct {
	mu  sync.Mutex
	ops []string
}

func (f *fakeExtension) serve(t *testing.T, r *Router, ch chan []byte, reply func(req ipc.InspectCaptureRequestMessage) map[string]interface{}) {
	go func() {
		for data := range ch {
			var req ipc.InspectCaptureRequestMessage
			if err := json.Unmarshal(trimNewline(data), &req); err != nil || req.Type != "inspect_capture" {
				continue
			}
			f.mu.Lock()
			f.ops = append(f.ops, req.Operation)
			f.mu.Unlock()
			r.RouteInspectCaptureResult(&ipc.InspectCaptureResultMessage{
				RequestID: req.RequestID, Operation: req.Operation, Result: reply(req), Type: "inspect_capture_result",
			})
		}
	}()
}

func (f *fakeExtension) last() string {
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.ops) == 0 {
		return ""
	}
	return f.ops[len(f.ops)-1]
}

func genericReply(ipc.InspectCaptureRequestMessage) map[string]interface{} {
	return map[string]interface{}{
		"_capture_path":        "/captures/a.rdc",
		"results":              []interface{}{},
		"counters_fetched":     []interface{}{},
		"counters_invalid":     []interface{}{},
		"counter_descriptions": []interface{}{},
		"events":               []interface{}{},
		"steps":                []interface{}{},
		"initial_vars":         map[string]interface{}{},
		"stage":                "pixel",
		"event_id":             1,
	}
}

// TestEveryToolHasExecutionPath statically checks that each catalog entry has
// a handler (service tools) or an operation (extension tools), and that the
// handler table contains nothing outside the catalog.
func TestEveryToolHasExecutionPath(t *testing.T) {
	r := newTestRouter()
	for _, s := range toolspec.All() {
		_, hasHandler := r.handlers[s.Name]
		switch s.Route {
		case toolspec.RouteService:
			if !hasHandler {
				t.Errorf("service tool %q has no handler", s.Name)
			}
		case toolspec.RouteExtension:
			if hasHandler {
				t.Errorf("extension tool %q also has a service handler; pick one route", s.Name)
			}
		}
	}
	for name := range r.handlers {
		if s, ok := toolspec.Lookup(name); !ok || s.Route != toolspec.RouteService {
			t.Errorf("handler %q is not a service tool in the catalog", name)
		}
	}
}

// TestEveryToolDispatches calls every registered tool through RouteToolCall
// with a connected fake extension and asserts that none of them falls through
// to an unknown/unimplemented path, times out, or reaches an unsupported
// extension operation.  Extension-routed tools must send their catalog operation.
func TestEveryToolDispatches(t *testing.T) {
	r := newServiceRouter(t)
	extCh := addExt(r, "ext-1", "inst-1", true)
	path := "/captures/a.rdc"
	r.extensions["ext-1"].capPath = &path
	bridgeCh := addBridge(r, "bridge-1")
	fake := &fakeExtension{}
	fake.serve(t, r, extCh, genericReply)

	args := map[string]map[string]interface{}{
		"collect_gpu_counters":  {"counter_ids": []interface{}{1.0}},
		"session_protect":       {"session_id": "session-000999", "protected": true},
		"capture_open":          {"capture_id": "cap-000999"},
		"get_shader_debug_info": {"stage": "ps"},
	}
	forbidden := map[string]bool{
		errUnknownTool: true, errInternalHandler: true, "not_implemented_in_go_service": true,
		failTimeout: true, failCancelled: true, "unsupported_operation": true, failInvalidReply: true,
	}

	for _, s := range toolspec.All() {
		a := args[s.Name]
		if a == nil {
			a = map[string]interface{}{}
		}
		r.RouteToolCall(&ipc.ToolCallMessage{RequestID: "rq-" + s.Name, ToolName: s.Name, Arguments: a, Type: "tool_call"}, "bridge-1")
		res := receiveToolResult(t, bridgeCh, 5*time.Second)
		if res.RequestID != "rq-"+s.Name || res.ToolName != s.Name {
			t.Errorf("%s: mismatched tool_result %q/%q", s.Name, res.RequestID, res.ToolName)
		}
		if res.Error != "" {
			t.Errorf("%s: transport error %q", s.Name, res.Error)
		}
		m, ok := res.Result.(map[string]interface{})
		if !ok {
			t.Errorf("%s: result is not an object: %T", s.Name, res.Result)
			continue
		}
		if code, _ := m["error"].(string); forbidden[code] {
			t.Errorf("%s: dispatched to a dead end: %v", s.Name, m)
		}
		if s.Route == toolspec.RouteExtension && fake.last() != s.Operation {
			t.Errorf("%s: extension received %q, want %q", s.Name, fake.last(), s.Operation)
		}
	}
}
