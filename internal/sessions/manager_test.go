package sessions

import (
	"context"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/operations"
	"github.com/taqu/rendereye-mcp/internal/store"
)

type fakeCaptures struct{ recs map[string]*captures.Record }

func (f *fakeCaptures) Get(id string) (*captures.Record, error) { return f.recs[id], nil }
func (f *fakeCaptures) Latest(string) (*captures.Record, error) {
	return f.recs["cap-000002"], nil
}

type fakeGateway struct {
	mu       sync.Mutex
	exts     map[int]Extension
	commands []string
	result   GuiCommandResult
	failure  string
}

func (g *fakeGateway) ExtensionForProcess(pid int) (Extension, bool) {
	g.mu.Lock()
	defer g.mu.Unlock()
	e, ok := g.exts[pid]
	return e, ok
}

func (g *fakeGateway) ExecuteGuiCommand(_ context.Context, connID, command string, params map[string]interface{}, _ time.Duration) (GuiCommandResult, string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.commands = append(g.commands, connID+":"+command+":"+params["path"].(string))
	return g.result, g.failure
}

type procTable struct {
	mu    sync.Mutex
	procs []instances.ProcInfo
	wins  map[int][]instances.WindowInfo
}

func (p *procTable) list() []instances.ProcInfo {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]instances.ProcInfo(nil), p.procs...)
}

func (p *procTable) windows(pid int) []instances.WindowInfo {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.wins[pid]
}

type harness struct {
	m       *Manager
	gw      *fakeGateway
	procs   *procTable
	focused []uintptr
	closed  []uintptr
}

func newHarness(t *testing.T) *harness {
	t.Helper()
	windowPollTimeout, verifyTimeout, pollInterval = 200*time.Millisecond, 200*time.Millisecond, 10*time.Millisecond
	db, err := store.Open(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	exe := filepath.Join(t.TempDir(), "qrenderdoc.exe")
	os.WriteFile(exe, []byte("exe"), 0o755)
	caps := &fakeCaptures{recs: map[string]*captures.Record{
		"cap-000001": {CaptureID: "cap-000001", Path: "/caps/one.rdc", Status: captures.StatusReady},
		"cap-000002": {CaptureID: "cap-000002", Path: "/caps/two.rdc", Status: captures.StatusReady},
		"cap-000003": {CaptureID: "cap-000003", Path: "/caps/pending.rdc", Status: captures.StatusPending},
	}}
	h := &harness{procs: &procTable{wins: map[int][]instances.WindowInfo{}}, gw: &fakeGateway{exts: map[int]Extension{}, result: GuiCommandResult{Success: true, Outcome: "success"}}}
	inst := instances.NewManagerWith(h.procs.list, h.procs.windows)
	h.m = NewManager(NewStorage(db), inst, caps, operations.NewTracker(), exe)
	h.m.SetGateway(h.gw)
	h.m.findExe = func(string) string { return exe }
	nextPID := 4000
	h.m.launch = func(_, capture string) (instances.LaunchResult, error) {
		nextPID++
		pid := nextPID
		h.procs.mu.Lock()
		h.procs.procs = append(h.procs.procs, instances.ProcInfo{PID: pid, Name: "qrenderdoc.exe", CreateTime: 100})
		h.procs.wins[pid] = []instances.WindowInfo{{HWND: uintptr(pid * 10), Title: "RenderDoc", Visible: true}}
		h.procs.mu.Unlock()
		p := capture
		h.gw.mu.Lock()
		h.gw.exts[pid] = Extension{ConnID: "conn-" + capture, InstanceID: "uuid", ProcessID: pid, CaptureLoaded: true, CapturePath: &p}
		h.gw.mu.Unlock()
		return instances.LaunchResult{PID: pid, CreateTime: 100, Note: instances.LaunchNote}, nil
	}
	h.m.focus = func(hwnd uintptr) (bool, string) { h.focused = append(h.focused, hwnd); return true, "focused" }
	h.m.closeWin = func(hwnd uintptr, _ time.Duration) (bool, bool, string) {
		h.closed = append(h.closed, hwnd)
		return true, true, "window_closed"
	}
	h.m.isWindow = func(uintptr) bool { return true }
	h.m.procAlive = func(pid int, _ float64) bool {
		for _, p := range h.procs.list() {
			if p.PID == pid {
				return true
			}
		}
		return false
	}
	return h
}

func TestOpen_newWindowConfirmedThenReuse(t *testing.T) {
	h := newHarness(t)
	res := h.m.Open(context.Background(), "cap-000001", "new_window", "")
	if res["status"] != "confirmed" || res["window_id"] == nil || res["association_status"] != "confirmed" {
		t.Fatalf("new_window: %v", res)
	}
	opID := res["operation_id"].(string)
	op, ok := h.m.Operation(opID)
	if !ok || op.Status != operations.StatusConfirmed || !op.LoadedCaptureVerified {
		t.Errorf("operation not confirmed: %+v", op)
	}
	sid := res["session_id"].(string)
	if res["gui_capture_path"] != "/caps/one.rdc" {
		t.Errorf("gui_capture_path not recorded: %v", res)
	}

	reuse := h.m.Open(context.Background(), "cap-000001", "reuse", "")
	if reuse["session_id"] != sid || reuse["status"] != "confirmed" {
		t.Errorf("reuse should return the existing session: %v", reuse)
	}
	if list := h.m.List("active", true, "", 10, 0); list["total"] != 1 {
		t.Errorf("session_list: %v", list)
	}
	if latest := h.m.Open(context.Background(), "latest", "new_window", ""); latest["capture_id"] != "cap-000002" {
		t.Errorf("latest should resolve to cap-000002: %v", latest)
	}
}

func TestOpen_unknownOutcomeWithoutExtension(t *testing.T) {
	h := newHarness(t)
	launch := h.m.launch
	h.m.launch = func(exe, c string) (instances.LaunchResult, error) {
		r, err := launch(exe, c)
		h.gw.mu.Lock()
		delete(h.gw.exts, r.PID) // extension never connects
		h.gw.mu.Unlock()
		return r, err
	}
	res := h.m.Open(context.Background(), "cap-000001", "", "")
	if res["status"] != "unknown_outcome" {
		t.Errorf("expected unknown_outcome, got %v", res)
	}
}

func TestOpen_validation(t *testing.T) {
	h := newHarness(t)
	errCode := func(res map[string]interface{}) string {
		e, _ := res["error"].(map[string]interface{})
		s, _ := e["code"].(string)
		return s
	}
	if c := errCode(h.m.Open(context.Background(), "cap-404", "new_window", "")); c != ErrCaptureNotFound {
		t.Errorf("unknown capture: %s", c)
	}
	if c := errCode(h.m.Open(context.Background(), "cap-000003", "new_window", "")); c != ErrCaptureNotFound {
		t.Errorf("pending capture must be refused: %s", c)
	}
	if c := errCode(h.m.Open(context.Background(), "cap-000001", "sideways", "")); c != ErrOperationUnsupported {
		t.Errorf("bad mode: %s", c)
	}
	if c := errCode(h.m.Open(context.Background(), "cap-000001", "replace", "")); c != ErrSessionNotFound {
		t.Errorf("replace without target: %s", c)
	}
	h.m.findExe = func(string) string { return "" }
	if c := errCode(h.m.Open(context.Background(), "cap-000001", "new_window", "")); c != ErrInstanceNotFound {
		t.Errorf("missing RenderDoc: %s", c)
	}
}

func TestOpen_replaceUsesExtensionMatchedByPID(t *testing.T) {
	h := newHarness(t)
	sid := h.m.Open(context.Background(), "cap-000001", "new_window", "")["session_id"].(string)

	res := h.m.Open(context.Background(), "cap-000002", "replace", sid)
	if res["status"] != "confirmed" || res["capture_id"] != "cap-000002" || res["session_id"] != sid {
		t.Fatalf("replace: %v", res)
	}
	if len(h.gw.commands) != 1 || h.gw.commands[0] != "conn-/caps/one.rdc:open_capture:/caps/two.rdc" {
		t.Errorf("open_capture not sent to the session's extension: %v", h.gw.commands)
	}

	h.gw.failure = "timeout"
	res = h.m.Open(context.Background(), "cap-000001", "replace", sid)
	if e, _ := res["error"].(map[string]interface{}); e["code"] != ErrOperationTimeout || e["retryable"] != true {
		t.Errorf("timeout mapping: %v", res)
	}
	op, _ := h.m.Operation(res["operation_id"].(string))
	if op.Status != operations.StatusTimedOut {
		t.Errorf("operation status %s", op.Status)
	}

	h.m.Protect(sid, true)
	res = h.m.Open(context.Background(), "cap-000001", "replace", sid)
	if e, _ := res["error"].(map[string]interface{}); e["code"] != ErrSessionProtected {
		t.Errorf("protected session must not be replaced: %v", res)
	}
}

func TestFocusCloseProtect(t *testing.T) {
	h := newHarness(t)
	res := h.m.Open(context.Background(), "cap-000001", "new_window", "")
	sid := res["session_id"].(string)
	pid := int(res["process_id"].(int))

	if f := h.m.Focus(sid); f["success"] != true || len(h.focused) != 1 || h.focused[0] != uintptr(pid*10) {
		t.Errorf("focus: %v %v", f, h.focused)
	}
	if p := h.m.Protect(sid, true); p["protected"] != true {
		t.Errorf("protect: %v", p)
	}
	if c := h.m.Close(sid); c["status"] != "failed" || len(h.closed) != 0 {
		t.Errorf("protected session must not close: %v", c)
	}
	h.m.Protect(sid, false)
	if c := h.m.Close(sid); c["success"] != true || c["confirmed"] != true || len(h.closed) != 1 {
		t.Errorf("close: %v", c)
	}
	if g := h.m.Get(sid); g["status"] != "closed" {
		t.Errorf("session should be closed: %v", g)
	}
	if g := h.m.Get("session-999999"); g["error"] != "not_found" {
		t.Errorf("unknown session: %v", g)
	}
}

// TestClose_neverTouchesForeignWindow guards against stale window IDs after a
// restart: a persisted window_id that now names another process's window must
// not be closed or focused.
func TestClose_neverTouchesForeignWindow(t *testing.T) {
	h := newHarness(t)
	res := h.m.Open(context.Background(), "cap-000001", "new_window", "")
	sid := res["session_id"].(string)
	pid := res["process_id"].(int)

	// Simulate a restart: the session's process is gone and an unrelated
	// RenderDoc window now owns the remembered window ID.
	h.procs.mu.Lock()
	h.procs.procs = []instances.ProcInfo{{PID: 9999, Name: "qrenderdoc.exe", CreateTime: 5}}
	h.procs.wins = map[int][]instances.WindowInfo{9999: {{HWND: uintptr(pid * 10), Title: "User RenderDoc"}}}
	h.procs.mu.Unlock()

	if f := h.m.Focus(sid); f["success"] != false || len(h.focused) != 0 {
		t.Errorf("must not focus a foreign window: %v", f)
	}
	if c := h.m.Close(sid); c["message"] != "closed_no_window" || len(h.closed) != 0 {
		t.Errorf("must not close a foreign window: %v %v", c, h.closed)
	}
}

func TestExtensionEventsAndReconcile(t *testing.T) {
	h := newHarness(t)
	res := h.m.Open(context.Background(), "cap-000001", "new_window", "")
	sid := res["session_id"].(string)
	pid := res["process_id"].(int)

	h.m.OnExtensionDisconnected(pid)
	if g := h.m.Get(sid); g["status"] != "disconnected" {
		t.Errorf("expected disconnected: %v", g)
	}
	h.m.OnExtensionConnected(pid)
	if g := h.m.Get(sid); g["status"] != "active" {
		t.Errorf("expected active after reconnect: %v", g)
	}
	other := "/caps/other.rdc"
	h.m.OnGuiState(pid, true, &other)
	if g := h.m.Get(sid); g["gui_capture_path"] != other {
		t.Errorf("gui state not tracked: %v", g)
	}

	h.procs.mu.Lock()
	h.procs.procs = nil
	h.procs.mu.Unlock()
	if rec, _, lost := h.m.Reconcile(); rec != 1 || lost != 1 {
		t.Errorf("reconcile: reconciled=%d lost=%d", rec, lost)
	}
	if g := h.m.Get(sid); g["status"] != "disconnected" || g["association_status"] != "lost" {
		t.Errorf("dead process should be disconnected/lost: %v", g)
	}
	if h.m.ActiveCount() != 0 {
		t.Error("no active sessions expected")
	}
}

func TestList_invalidStatus(t *testing.T) {
	h := newHarness(t)
	if res := h.m.List("bogus", false, "", 10, 0); res["error"] != "invalid_status" {
		t.Errorf("expected invalid_status: %v", res)
	}
}
