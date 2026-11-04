// Package toolspec is the single source of truth for how every MCP tool is
// executed.
//
// The MCP bridge (internal/bridge) registers the tool schemas; the Shared IPC
// Service (internal/server) dispatches tool calls.  Both consult this catalog:
//
//   - the service uses Route/Operation to decide whether a tool is handled in
//     the Go service or forwarded 1:1 to the RenderDoc extension as an
//     inspect_capture operation, and Timeout as the service-side budget;
//   - the bridge uses BridgeTimeout so it never gives up before the service
//     has had a chance to return a structured timeout result.
//
// Tests in both packages assert that the registered tool set, this catalog
// and the service handler table are identical, so a tool can no longer be
// registered without a valid execution path.
package toolspec

import (
	"sort"
	"time"
)

// Route describes where a tool call is executed.
type Route int

const (
	// RouteService tools are implemented in the Go Shared IPC Service.  They
	// may still issue one or more inspect_capture requests to an extension
	// (composite tools such as collect_gpu_counters).
	RouteService Route = iota + 1
	// RouteExtension tools are forwarded unchanged (minus instance_id) to the
	// selected RenderDoc extension as a single inspect_capture operation.
	RouteExtension
)

func (r Route) String() string {
	switch r {
	case RouteService:
		return "service"
	case RouteExtension:
		return "extension"
	}
	return "invalid"
}

// Timeouts used by the catalog.
const (
	// DefaultTimeout bounds ordinary inspection and service tools.
	DefaultTimeout = 30 * time.Second
	// ReplayTimeout bounds a single replay-dependent extension operation
	// (FetchCounters, PixelHistory, GetPostVSData, shader debugging).
	ReplayTimeout = 120 * time.Second
	// MaxCounterRepeats is the maximum value of collect_gpu_counters.repeats.
	MaxCounterRepeats = 5
	// CollectCountersTimeout bounds the whole collect_gpu_counters call:
	// one capture_info round-trip plus up to MaxCounterRepeats FetchCounters runs.
	CollectCountersTimeout = DefaultTimeout + MaxCounterRepeats*ReplayTimeout
	// BridgeGrace is added to the service budget on the bridge side so the
	// service's own timeout result wins the race.
	BridgeGrace = 15 * time.Second
)

// Spec describes the execution path of one MCP tool.
type Spec struct {
	Name string
	// Route selects the executor.
	Route Route
	// Operation is the inspect_capture operation for RouteExtension tools.
	Operation string
	// Timeout is the service-side budget for the whole tool call.
	Timeout time.Duration
}

func svc(name string, timeout time.Duration) Spec {
	return Spec{Name: name, Route: RouteService, Timeout: timeout}
}

func ext(name, op string, timeout time.Duration) Spec {
	return Spec{Name: name, Route: RouteExtension, Operation: op, Timeout: timeout}
}

// catalog lists every MCP tool exposed by the bridge, in registration order.
var catalog = []Spec{
	// Diagnostics, capture registry, instances and managed sessions.
	svc("server_status", DefaultTimeout),
	svc("capture_list", DefaultTimeout),
	svc("capture_get", DefaultTimeout),
	svc("capture_latest", DefaultTimeout),
	svc("capture_rescan", ReplayTimeout),
	svc("capture_registry_status", DefaultTimeout),
	svc("instance_list", DefaultTimeout),
	svc("instance_gui_state", DefaultTimeout),
	svc("capture_open", 60*time.Second),
	svc("operation_get", DefaultTimeout),
	svc("session_list", DefaultTimeout),
	svc("session_get", DefaultTimeout),
	svc("session_focus", DefaultTimeout),
	svc("session_close", DefaultTimeout),
	svc("session_protect", DefaultTimeout),

	// GUI state discovery.
	svc("list_renderdoc_sessions", DefaultTimeout),
	svc("get_renderdoc_session_state", DefaultTimeout),
	svc("get_current_capture", DefaultTimeout),

	// Active capture inspection.
	ext("get_current_capture_info", "capture_info", DefaultTimeout),
	ext("list_capture_events", "list_events", DefaultTimeout),
	ext("get_capture_event", "get_event", DefaultTimeout),
	ext("get_selected_event", "selected_event", DefaultTimeout),
	ext("get_pipeline_state", "pipeline_state", DefaultTimeout),

	// Resources and buffers.
	ext("list_resources", "list_resources", DefaultTimeout),
	ext("get_resource_info", "get_resource_info", DefaultTimeout),
	ext("get_texture_info", "get_texture_info", DefaultTimeout),
	ext("get_buffer_info", "get_buffer_info", DefaultTimeout),
	ext("read_buffer_data", "read_buffer_data", DefaultTimeout),

	// Shaders.
	ext("list_shaders", "list_shaders", DefaultTimeout),
	ext("get_shader_info", "get_shader_info", DefaultTimeout),
	ext("get_shader_reflection", "get_shader_reflection", DefaultTimeout),
	ext("get_shader_bindings", "get_shader_bindings", DefaultTimeout),
	ext("get_shader_disassembly", "get_shader_disassembly", DefaultTimeout),
	ext("get_shader_debug_info", "get_shader_debug_info", DefaultTimeout),

	// Render targets, textures and pixels.
	ext("get_render_targets", "get_render_targets", DefaultTimeout),
	ext("get_texture_image", "get_texture_image", ReplayTimeout),
	ext("get_pixel_value", "get_pixel_value", DefaultTimeout),
	ext("get_texture_statistics", "get_texture_statistics", ReplayTimeout),

	// GPU performance analysis.
	ext("list_gpu_counters", "list_gpu_counters", DefaultTimeout),
	svc("collect_gpu_counters", CollectCountersTimeout),
	svc("get_gpu_measurement_status", DefaultTimeout),
	svc("get_gpu_timings", DefaultTimeout),
	svc("get_performance_summary", DefaultTimeout),
	svc("get_render_pass_performance", 2*DefaultTimeout),
	svc("get_pipeline_statistics", DefaultTimeout),

	// Geometry and mesh inspection.
	ext("get_draw_geometry_info", "draw_geometry_info", DefaultTimeout),
	ext("get_vertex_input_layout", "vertex_input_layout", DefaultTimeout),
	ext("get_mesh_indices", "mesh_indices", DefaultTimeout),
	ext("get_mesh_vertices", "mesh_vertices", DefaultTimeout),
	ext("get_post_vs_geometry", "post_vs_geometry", ReplayTimeout),
	ext("get_mesh_statistics", "mesh_statistics", DefaultTimeout),

	// Pixel history and shader debugging.
	ext("get_pixel_history", "pixel_history", ReplayTimeout),
	svc("debug_pixel_shader", ReplayTimeout),
	svc("debug_vertex_shader", ReplayTimeout),
	svc("debug_compute_shader", ReplayTimeout),
	svc("get_shader_debug_trace", DefaultTimeout),
	svc("get_shader_debug_variables", DefaultTimeout),
	svc("get_shader_debug_status", DefaultTimeout),
}

// Extension operations that service-routed (composite) tools issue directly.
const (
	OpCaptureInfo      = "capture_info"
	OpListEvents       = "list_events"
	OpEventTree        = "event_tree"
	OpFetchGPUCounters = "fetch_gpu_counters"
	OpDebugPixel       = "debug_pixel"
	OpDebugVertex      = "debug_vertex"
	OpDebugCompute     = "debug_compute"
)

// ExtensionOperations returns every inspect_capture operation the Go service
// may send to the RenderDoc extension, sorted.  The extension must implement
// each of them; a test checks this against extensions/rendereye/gui_context.py.
func ExtensionOperations() []string {
	set := map[string]bool{
		OpCaptureInfo: true, OpListEvents: true, OpEventTree: true,
		OpFetchGPUCounters: true, OpDebugPixel: true, OpDebugVertex: true, OpDebugCompute: true,
	}
	for _, s := range catalog {
		if s.Route == RouteExtension {
			set[s.Operation] = true
		}
	}
	out := make([]string, 0, len(set))
	for op := range set {
		out = append(out, op)
	}
	sort.Strings(out)
	return out
}

var byName = func() map[string]Spec {
	m := make(map[string]Spec, len(catalog))
	for _, s := range catalog {
		if _, dup := m[s.Name]; dup {
			panic("toolspec: duplicate tool " + s.Name)
		}
		m[s.Name] = s
	}
	return m
}()

// Lookup returns the Spec for name.
func Lookup(name string) (Spec, bool) {
	s, ok := byName[name]
	return s, ok
}

// All returns a copy of the catalog in registration order.
func All() []Spec {
	out := make([]Spec, len(catalog))
	copy(out, catalog)
	return out
}

// Names returns every tool name, sorted.
func Names() []string {
	out := make([]string, 0, len(catalog))
	for _, s := range catalog {
		out = append(out, s.Name)
	}
	sort.Strings(out)
	return out
}

// BridgeTimeout is how long the MCP bridge waits for a tool_result.
func BridgeTimeout(name string) time.Duration {
	if s, ok := byName[name]; ok {
		return s.Timeout + BridgeGrace
	}
	return DefaultTimeout + BridgeGrace
}
