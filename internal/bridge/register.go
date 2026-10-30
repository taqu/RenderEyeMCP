package bridge

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"log/slog"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// NewMCPServer creates and configures an mcp.Server with all 57 RenderEye tools
// registered and connected to client.
func NewMCPServer(client *ServiceClient) *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{
		Name:    "RenderEyeMCP",
		Version: "1.0.0-go",
	}, nil)
	RegisterTools(server, client)
	return server
}

// RegisterTools registers all 57 MCP tools on server, forwarding calls via client.
func RegisterTools(server *mcp.Server, client *ServiceClient) {
	// ---- server_status ----
	server.AddTool(&mcp.Tool{
		Name:        "server_status",
		Description: "Return the current health and configuration of the RenderEyeMCP server. Use this to verify the server is running, check whether RenderDoc is detected on this machine, inspect IPC listener state, and count active extension connections and sessions. Does not modify any GUI state.",
		InputSchema: objSchema(nil),
	}, makeHandler(client, "server_status"))

	// ---- capture_list ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_list",
		Description: "List captures from the Capture Registry. Use this to discover available .rdc files with their Capture IDs, paths, and readiness status. Supports filtering by status (ready/pending/missing/invalid) and directory, with pagination. Returns stable Capture IDs needed for capture_open. This tool does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"status":    prop("string", "Filter by status", ""),
			"directory": prop("string", "Filter by directory", ""),
			"limit":     prop("integer", "Maximum results", 50),
			"offset":    prop("integer", "Pagination offset", 0),
		}),
	}, makeHandler(client, "capture_list"))

	// ---- capture_get ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_get",
		Description: "Get full metadata for a single capture by its Capture ID (e.g. 'cap-000018'). Use this to confirm a capture is ready before opening it, or to retrieve its file path, size, and status. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"capture_id": prop("string", "Capture ID", nil),
		}, "capture_id"),
	}, makeHandler(client, "capture_get"))

	// ---- capture_latest ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_latest",
		Description: "Get the most recently discovered ready capture. Use this when you want to open the newest available capture without knowing its ID. Optionally filter by directory. Set include_pending=true to fall back to pending captures when no ready capture exists. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"directory":       prop("string", "Filter by directory", ""),
			"include_pending": prop("boolean", "Include pending captures", false),
		}),
	}, makeHandler(client, "capture_latest"))

	// ---- capture_rescan ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_rescan",
		Description: "Trigger an immediate rescan of all watched directories in the Capture Registry. Use this to pick up newly written .rdc files without waiting for the background watcher interval. Returns counts of scanned, new, and updated captures. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(nil),
	}, makeHandler(client, "capture_rescan"))

	// ---- capture_registry_status ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_registry_status",
		Description: "Get the current status of the Capture Registry including whether the background watcher is active, watched directories, total capture counts by status, and scan interval. Use this to diagnose why captures are not appearing. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(nil),
	}, makeHandler(client, "capture_registry_status"))

	// ---- instance_list ----
	server.AddTool(&mcp.Tool{
		Name:        "instance_list",
		Description: "List all discovered RenderDoc processes and their windows. Use this to see which RenderDoc instances are running, whether each has an active extension connection, and what capture is currently loaded. Refreshes process/window discovery before returning. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(nil),
	}, makeHandler(client, "instance_list"))

	// ---- instance_gui_state ----
	server.AddTool(&mcp.Tool{
		Name:        "instance_gui_state",
		Description: "Get the authoritative GUI state for a specific RenderDoc instance as reported by its extension. Returns whether a capture is loaded, the loaded capture path, and state freshness. Use this to verify which capture is actually visible in the RenderDoc GUI. Requires an active extension connection. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Instance ID", nil),
		}, "instance_id"),
	}, makeHandler(client, "instance_gui_state"))

	// ---- capture_open ----
	server.AddTool(&mcp.Tool{
		Name:        "capture_open",
		Description: "Open a .rdc capture in RenderDoc and create or return a managed session. Use this as the primary tool for opening captures. Modes: 'new_window' (default) launches a new RenderDoc window; 'reuse' returns an existing session for the same capture or creates a new one; 'replace' replaces the capture in a specific managed session (requires target_session_id and an active extension connection). Specify capture_id as a Capture ID (e.g. 'cap-000018') or 'latest' for the most recent ready capture. Returns an operation record with operation_id, status, and session/window identifiers. STATUS VALUES: confirmed=success, unknown_outcome=launched but unverified, failed=error. THIS TOOL CHANGES GUI STATE.",
		InputSchema: objSchema(map[string]interface{}{
			"capture_id":        prop("string", "Capture ID or 'latest'", "latest"),
			"open_mode":         prop("string", "Open mode: new_window, reuse, replace", "new_window"),
			"target_session_id": prop("string", "Target session ID for replace mode", ""),
		}),
	}, makeHandler(client, "capture_open"))

	// ---- operation_get ----
	server.AddTool(&mcp.Tool{
		Name:        "operation_get",
		Description: "Query the status of an async capture_open operation. Use this to check if a previously initiated operation has completed. Returns the operation record including final session/instance/window IDs when confirmed. STATUS VALUES: requested, validating, launching, waiting_for_gui, verifying, confirmed, failed, unsupported, timed_out, unknown_outcome. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"operation_id": prop("string", "Operation ID", nil),
		}, "operation_id"),
	}, makeHandler(client, "operation_get"))

	// ---- session_list ----
	server.AddTool(&mcp.Tool{
		Name:        "session_list",
		Description: "List managed sessions with optional filtering. Use this to see all open RenderDoc sessions, their status (active/disconnected/closing/closed), and which captures they have loaded. Supports filtering by status, managed_only flag, and capture_id, with pagination via limit/offset. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"status":       prop("string", "Filter by status", ""),
			"managed_only": prop("boolean", "Only managed sessions", false),
			"capture_id":   prop("string", "Filter by capture ID", ""),
			"limit":        prop("integer", "Maximum results", 50),
			"offset":       prop("integer", "Pagination offset", 0),
		}),
	}, makeHandler(client, "session_list"))

	// ---- session_get ----
	server.AddTool(&mcp.Tool{
		Name:        "session_get",
		Description: "Get the full record for a single session by its Session ID (e.g. 'session-000001'). Use this to check session status, associated capture, instance, and window IDs, and whether extension GUI state has been verified. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"session_id": prop("string", "Session ID", nil),
		}, "session_id"),
	}, makeHandler(client, "session_get"))

	// ---- session_focus ----
	server.AddTool(&mcp.Tool{
		Name:        "session_focus",
		Description: "Bring a session's RenderDoc window to the foreground. Use this to make a specific session visible without closing other sessions. Requires the session to have an associated window (the window must still be open). THIS TOOL CHANGES GUI STATE (raises a window).",
		InputSchema: objSchema(map[string]interface{}{
			"session_id": prop("string", "Session ID", nil),
		}, "session_id"),
	}, makeHandler(client, "session_focus"))

	// ---- session_close ----
	server.AddTool(&mcp.Tool{
		Name:        "session_close",
		Description: "Gracefully close a managed, unprotected session's RenderDoc window. The session must be managed (launched by this server) and not protected. Use session_protect first to unprotect if needed. Returns session_protected error if protected, session_unmanaged if not managed, session_not_found if the session ID is unknown. THIS TOOL CHANGES GUI STATE and is destructive — it closes a window.",
		InputSchema: objSchema(map[string]interface{}{
			"session_id": prop("string", "Session ID", nil),
		}, "session_id"),
	}, makeHandler(client, "session_close"))

	// ---- session_protect ----
	server.AddTool(&mcp.Tool{
		Name:        "session_protect",
		Description: "Set or unset the protection flag on a session. Protected sessions cannot be closed or replaced by capture_open replace mode. Use protected=true to prevent accidental closure, protected=false to allow closure. Returns the updated session record. Does not modify RenderDoc GUI state directly.",
		InputSchema: objSchema(map[string]interface{}{
			"session_id": prop("string", "Session ID", nil),
			"protected":  prop("boolean", "Set protection flag", nil),
		}, "session_id", "protected"),
	}, makeHandler(client, "session_protect"))

	// ---- list_renderdoc_sessions ----
	server.AddTool(&mcp.Tool{
		Name:        "list_renderdoc_sessions",
		Description: "List all known RenderDoc GUI instances and their current state. Returns each instance's connection state (connected/disconnected/unknown) and capture information. Connected instances show the live capture state; disconnected instances show the last-known state under 'last_known_capture'. Use this to discover which RenderDoc instances are running and what they have loaded, including instances opened by Unity, Unreal Engine, or manually. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(nil),
	}, makeHandler(client, "list_renderdoc_sessions"))

	// ---- get_renderdoc_session_state ----
	server.AddTool(&mcp.Tool{
		Name:        "get_renderdoc_session_state",
		Description: "Get the current state of a specific RenderDoc GUI instance by its instance_id. Returns connection state (connected/disconnected/unknown) and capture information. A connected instance shows live capture state; a disconnected instance shows the last-known state under 'last_known_capture'. Use 'list_renderdoc_sessions' to discover valid instance_id values. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Instance ID", nil),
		}, "instance_id"),
	}, makeHandler(client, "get_renderdoc_session_state"))

	// ---- get_current_capture ----
	server.AddTool(&mcp.Tool{
		Name:        "get_current_capture",
		Description: "Return the capture currently loaded in RenderDoc. If exactly one connected RenderDoc GUI has a capture loaded, returns it directly. If multiple instances have captures loaded, returns all for disambiguation — specify instance_id to target a particular session. If no capture is loaded, returns the connection state and connected sessions. Works with captures opened externally (Unity, Unreal Engine, or manually) — no MCP capture_open call is required. STATUS VALUES: loaded=capture found, no_capture_loaded=connected but empty, capture_loading=loading in progress, ambiguous=multiple sessions, session_not_found=unknown instance_id, session_disconnected=offline session, no_renderdoc_connected=no active extension. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_current_capture"))

	// ---- get_current_capture_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_current_capture_info",
		Description: "Get metadata about the capture currently loaded in a connected RenderDoc GUI session. Returns file path, frame count, capture time, API, and other capture-level metadata. If multiple sessions are connected, specify instance_id to target a particular one. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_current_capture_info"))

	// ---- list_capture_events ----
	server.AddTool(&mcp.Tool{
		Name:        "list_capture_events",
		Description: "List draw calls, dispatches, and other events from the currently loaded capture. Supports pagination via limit/offset, filtering by parent_event_id for hierarchical traversal, and optional debug marker inclusion via include_markers. Use flags_filter to restrict to specific event types (e.g. 'drawcall', 'dispatch'). Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id":     prop("string", "Optional instance ID", ""),
			"limit":           prop("integer", "Maximum results", 50),
			"offset":          prop("integer", "Pagination offset", 0),
			"include_markers": prop("boolean", "Include debug markers", true),
			"flags_filter":    prop("string", "Event type filter", ""),
			"parent_event_id": prop("integer", "Parent event ID for hierarchy", 0),
		}),
	}, makeHandler(client, "list_capture_events"))

	// ---- get_capture_event ----
	server.AddTool(&mcp.Tool{
		Name:        "get_capture_event",
		Description: "Get detailed information about a specific event in the loaded capture by event ID. Returns event type, flags, draw call parameters, resource bindings, and timing information for the given event. Use list_capture_events to discover valid event IDs. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":    prop("integer", "Event ID", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "event_id"),
	}, makeHandler(client, "get_capture_event"))

	// ---- get_selected_event ----
	server.AddTool(&mcp.Tool{
		Name:        "get_selected_event",
		Description: "Get the event currently selected in the RenderDoc GUI timeline. Returns the same detailed event information as get_capture_event for whichever event the user has highlighted in the RenderDoc UI. Useful for inspecting what the user is currently looking at without needing to know the event ID. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_selected_event"))

	// ---- get_pipeline_state ----
	server.AddTool(&mcp.Tool{
		Name:        "get_pipeline_state",
		Description: "Inspect the graphics or compute pipeline state. Sections: summary, input_assembly, shaders, rasterizer, depth_stencil, output_merger, resources. If event_id is 0 (default), uses the currently selected event. Returns the pipeline state for the specified section at the given event. Does not modify RenderDoc GUI state.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
			"event_id":    prop("integer", "Event ID (0 = current selection)", 0),
			"section":     prop("string", "Pipeline section", "summary"),
		}),
	}, makeHandler(client, "get_pipeline_state"))

	// ---- list_resources ----
	server.AddTool(&mcp.Tool{
		Name:        "list_resources",
		Description: "Enumerate GPU resources in the currently loaded capture. resource_type: 'all', 'texture', 'buffer'. Supports name filtering and pagination.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id":   prop("string", "Optional instance ID", ""),
			"resource_type": prop("string", "Resource type: all, texture, buffer", "all"),
			"name_filter":   prop("string", "Name filter", ""),
			"limit":         prop("integer", "Maximum results", 50),
			"offset":        prop("integer", "Pagination offset", 0),
		}),
	}, makeHandler(client, "list_resources"))

	// ---- get_resource_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_resource_info",
		Description: "Get metadata for a GPU resource by its ID. Returns type-specific details for textures and buffers.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id": prop("string", "Resource ID", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "get_resource_info"))

	// ---- get_texture_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_texture_info",
		Description: "Get detailed metadata for a GPU texture resource: dimensions, format, mip levels, sample count, usage flags.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id": prop("string", "Resource ID", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "get_texture_info"))

	// ---- get_buffer_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_buffer_info",
		Description: "Get detailed metadata for a GPU buffer resource: byte size, usage flags.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id": prop("string", "Resource ID", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "get_buffer_info"))

	// ---- read_buffer_data ----
	server.AddTool(&mcp.Tool{
		Name:        "read_buffer_data",
		Description: "Read a bounded byte range from a GPU buffer. output_format: hex, base64, bytes. Optionally decode with decode_layout (stride, element_count, fields with name/type/offset/components).",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id":   prop("string", "Resource ID", nil),
			"offset":        prop("integer", "Byte offset", 0),
			"length":        prop("integer", "Byte length", 256),
			"output_format": prop("string", "Output format: hex, base64, bytes", "hex"),
			"decode_layout": map[string]interface{}{"type": "object", "description": "Optional decode layout"},
			"instance_id":   prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "read_buffer_data"))

	// ---- list_shaders ----
	server.AddTool(&mcp.Tool{
		Name:        "list_shaders",
		Description: "List shaders bound to the currently selected event. Returns stage name, shader ID, entry point, and reflection summary for each bound shader.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "list_shaders"))

	// ---- get_shader_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_info",
		Description: "Get metadata for the shader bound at a specific pipeline stage. stage: 'Vertex', 'Pixel', 'Compute', 'Geometry', 'Hull', 'Domain' (case-insensitive). Returns shader ID, entry point, reflection counts, and disassembly targets.",
		InputSchema: objSchema(map[string]interface{}{
			"stage":       prop("string", "Shader stage", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "stage"),
	}, makeHandler(client, "get_shader_info"))

	// ---- get_shader_reflection ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_reflection",
		Description: "Get shader reflection data: input/output signatures, constant buffer declarations, resource and sampler declarations. stage: shader stage. section: 'all', 'input', 'output', 'cbuffers', 'resources', 'samplers'.",
		InputSchema: objSchema(map[string]interface{}{
			"stage":       prop("string", "Shader stage", nil),
			"section":     prop("string", "Reflection section", "all"),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "stage"),
	}, makeHandler(client, "get_shader_reflection"))

	// ---- get_shader_bindings ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_bindings",
		Description: "Correlate reflected shader resource declarations with actual runtime bindings. Returns each declared cbuffer, texture, and UAV with its bound resource ID (or null if unbound). stage: shader stage.",
		InputSchema: objSchema(map[string]interface{}{
			"stage":       prop("string", "Shader stage", nil),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "stage"),
	}, makeHandler(client, "get_shader_bindings"))

	// ---- get_shader_disassembly ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_disassembly",
		Description: "Retrieve bounded shader disassembly. stage: shader stage. target: disassembly target (empty = default). offset/limit: line pagination (max 200 lines). search: optional text to search for (returns matching lines with context).",
		InputSchema: objSchema(map[string]interface{}{
			"stage":       prop("string", "Shader stage", nil),
			"target":      prop("string", "Disassembly target", ""),
			"offset":      prop("integer", "Line offset", 0),
			"limit":       prop("integer", "Max lines (max 200)", 200),
			"search":      prop("string", "Search text", ""),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "stage"),
	}, makeHandler(client, "get_shader_disassembly"))

	// ---- get_shader_debug_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_debug_info",
		Description: "Retrieve shader source-level debug information where available. stage: shader stage. file_index: source file to read (0-based). start_line/max_lines: line range to retrieve (max 500).",
		InputSchema: objSchema(map[string]interface{}{
			"stage":       prop("string", "Shader stage", nil),
			"file_index":  prop("integer", "Source file index", 0),
			"start_line":  prop("integer", "Start line", 0),
			"max_lines":   prop("integer", "Max lines", 100),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "stage"),
	}, makeHandler(client, "get_shader_debug_info"))

	// ---- get_render_targets ----
	server.AddTool(&mcp.Tool{
		Name:        "get_render_targets",
		Description: "List the color render targets and depth/stencil attachment bound to the currently selected draw call. Returns resource IDs, formats, dimensions, and binding indices. Use the returned resource_id values with get_texture_info or get_texture_image.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_render_targets"))

	// ---- get_texture_image (special handler) ----
	server.AddTool(&mcp.Tool{
		Name:        "get_texture_image",
		Description: "Retrieve a bounded PNG image of a GPU texture. Returns an MCP image content block plus metadata. resource_id: GPU resource ID (from list_resources or get_render_targets). mip: mip level (0 = full resolution). array_slice: array layer index. max_dim: maximum output dimension in pixels (default 1024). If the requested mip exceeds max_dim, returns image_too_large with suggested_mip. Texture contents reflect the current replay event.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id": prop("string", "Resource ID", nil),
			"mip":         prop("integer", "Mip level", 0),
			"array_slice": prop("integer", "Array slice", 0),
			"max_dim":     prop("integer", "Max dimension", 1024),
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeTextureImageHandler(client))

	// ---- get_pixel_value ----
	server.AddTool(&mcp.Tool{
		Name:        "get_pixel_value",
		Description: "Retrieve exact typed pixel component values at a coordinate (or batch of coordinates). resource_id: GPU texture resource ID. x, y: pixel coordinate (integer, top-left origin). mip: mip level (default 0). array_slice: array layer (default 0). sample: MSAA sample index (default 0). coords: optional list of {x, y} dicts for batch queries (max 16 pixels). Returns float, uint, and sint component arrays as reported by RenderDoc. Values are exact GPU resource data, not display-converted colors.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id": prop("string", "Resource ID", nil),
			"x":           prop("integer", "X coordinate", 0),
			"y":           prop("integer", "Y coordinate", 0),
			"mip":         prop("integer", "Mip level", 0),
			"array_slice": prop("integer", "Array slice", 0),
			"sample":      prop("integer", "MSAA sample", 0),
			"coords": map[string]interface{}{
				"type":        "array",
				"description": "Optional batch coordinates",
				"items":       map[string]interface{}{"type": "object"},
			},
			"instance_id": prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "get_pixel_value"))

	// ---- get_texture_statistics ----
	server.AddTool(&mcp.Tool{
		Name:        "get_texture_statistics",
		Description: "Retrieve per-component min/max pixel values for a texture subresource. Optionally retrieves a value histogram. resource_id: GPU texture resource ID. mip: mip level (default 0). array_slice: array layer (default 0). include_histogram: if true, returns a histogram (default false). hist_min, hist_max: histogram value range (default 0.0-1.0). Useful for checking whether a render target is blank, saturated, or has unexpected values.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id":       prop("string", "Resource ID", nil),
			"mip":               prop("integer", "Mip level", 0),
			"array_slice":       prop("integer", "Array slice", 0),
			"include_histogram": prop("boolean", "Include histogram", false),
			"hist_min":          prop("number", "Histogram min", 0.0),
			"hist_max":          prop("number", "Histogram max", 1.0),
			"instance_id":       prop("string", "Optional instance ID", ""),
		}, "resource_id"),
	}, makeHandler(client, "get_texture_statistics"))

	// ---- list_gpu_counters ----
	server.AddTool(&mcp.Tool{
		Name:        "list_gpu_counters",
		Description: "Enumerate GPU performance counters available for the currently loaded capture. Returns counter IDs, names, units, and value types as reported by RenderDoc. Counter availability depends on the GPU, graphics driver, graphics API, and RenderDoc version. Use the returned counter_id values with collect_gpu_counters. Call this first to discover which counters are supported before requesting measurement.",
		InputSchema: objSchema(map[string]interface{}{
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "list_gpu_counters"))

	// ---- collect_gpu_counters ----
	server.AddTool(&mcp.Tool{
		Name:        "collect_gpu_counters",
		Description: "Collect GPU performance counter values for all events in the loaded capture. counter_ids: list of integer counter IDs from list_gpu_counters. instance_id: optional RenderDoc session ID. repeats: number of collection runs (1-5, default 1); multiple runs average results. Returns a measurement_id that identifies the stored results. This operation executes FetchCounters() which performs GPU replay and may take several seconds for large captures. It is NOT read-only. Use get_gpu_timings, get_performance_summary, get_render_pass_performance, and get_pipeline_statistics to analyze the stored results without re-running the GPU.",
		InputSchema: objSchema(map[string]interface{}{
			"counter_ids": map[string]interface{}{
				"type":        "array",
				"description": "Counter IDs to collect",
				"items":       map[string]interface{}{"type": "integer"},
			},
			"instance_id": prop("string", "Optional instance ID", ""),
			"repeats":     prop("integer", "Collection runs (1-5)", 1),
		}, "counter_ids"),
	}, makeHandler(client, "collect_gpu_counters"))

	// ---- get_gpu_measurement_status ----
	server.AddTool(&mcp.Tool{
		Name:        "get_gpu_measurement_status",
		Description: "Retrieve the status and metadata of a GPU counter measurement. measurement_id: ID returned by collect_gpu_counters. Returns status (completed/failed/invalidated), capture path, counter list, result count, and timing metadata. Use to confirm a measurement completed before calling analysis tools.",
		InputSchema: objSchema(map[string]interface{}{
			"measurement_id": prop("string", "Measurement ID", nil),
		}, "measurement_id"),
	}, makeHandler(client, "get_gpu_measurement_status"))

	// ---- get_gpu_timings ----
	server.AddTool(&mcp.Tool{
		Name:        "get_gpu_timings",
		Description: "Retrieve event-level GPU timing values from a completed measurement. measurement_id: ID from collect_gpu_counters. counter_id: optional counter ID to use; defaults to the first timing/duration counter. min_value: optional minimum value filter. sort_by: value_desc (default), value_asc, event_id, event_id_desc. limit/offset: pagination (default limit=100). Returns event IDs, counter values, and units. Does NOT re-run GPU collection.",
		InputSchema: objSchema(map[string]interface{}{
			"measurement_id": prop("string", "Measurement ID", nil),
			"counter_id":     map[string]interface{}{"type": "integer", "description": "Optional counter ID"},
			"min_value":      map[string]interface{}{"type": "number", "description": "Optional minimum value filter"},
			"limit":          prop("integer", "Maximum results", 100),
			"offset":         prop("integer", "Pagination offset", 0),
			"sort_by":        prop("string", "Sort order", "value_desc"),
		}, "measurement_id"),
	}, makeHandler(client, "get_gpu_timings"))

	// ---- get_performance_summary ----
	server.AddTool(&mcp.Tool{
		Name:        "get_performance_summary",
		Description: "Rank the most expensive GPU events from a completed measurement. measurement_id: ID from collect_gpu_counters. counter_id: optional counter ID to rank by; defaults to the first timing counter. top_n: number of top events to return (default 20, max 100). Returns events sorted by counter value descending, with total across all events. Use this to identify expensive draw calls and dispatches for deeper investigation with get_pipeline_state, get_shader_info, and related tools.",
		InputSchema: objSchema(map[string]interface{}{
			"measurement_id": prop("string", "Measurement ID", nil),
			"counter_id":     map[string]interface{}{"type": "integer", "description": "Optional counter ID"},
			"top_n":          prop("integer", "Top N events", 20),
		}, "measurement_id"),
	}, makeHandler(client, "get_performance_summary"))

	// ---- get_render_pass_performance ----
	server.AddTool(&mcp.Tool{
		Name:        "get_render_pass_performance",
		Description: "Aggregate GPU counter results by render pass (debug marker hierarchy). measurement_id: ID from collect_gpu_counters. counter_id: optional counter to aggregate; defaults to the first timing counter. instance_id: optional RenderDoc session for event hierarchy lookup. Groups draw calls and dispatches under their parent debug marker regions. aggregated_duration is the SUM of measured leaf event values — it is not the GPU elapsed wall-clock time of the pass. Useful for comparing shadow pass vs G-buffer pass vs lighting pass costs.",
		InputSchema: objSchema(map[string]interface{}{
			"measurement_id": prop("string", "Measurement ID", nil),
			"counter_id":     map[string]interface{}{"type": "integer", "description": "Optional counter ID"},
			"instance_id":    prop("string", "Optional instance ID", ""),
		}, "measurement_id"),
	}, makeHandler(client, "get_render_pass_performance"))

	// ---- get_pipeline_statistics ----
	server.AddTool(&mcp.Tool{
		Name:        "get_pipeline_statistics",
		Description: "Retrieve pipeline statistics counters from a completed measurement. measurement_id: ID from collect_gpu_counters. event_id: optional event ID to filter results to a single draw call. limit/offset: pagination (default limit=100). Filters for counters related to vertex invocations, primitive counts, rasterizer invocations, pixel/compute shader invocations, etc. Counter availability is hardware and API dependent. Does NOT re-run GPU collection.",
		InputSchema: objSchema(map[string]interface{}{
			"measurement_id": prop("string", "Measurement ID", nil),
			"event_id":       map[string]interface{}{"type": "integer", "description": "Optional event ID filter"},
			"limit":          prop("integer", "Maximum results", 100),
			"offset":         prop("integer", "Pagination offset", 0),
		}, "measurement_id"),
	}, makeHandler(client, "get_pipeline_statistics"))

	// ---- get_draw_geometry_info ----
	server.AddTool(&mcp.Tool{
		Name:        "get_draw_geometry_info",
		Description: "Return draw parameters and geometry configuration for the currently selected draw call. Reports topology, vertex/index counts, instance count, draw offsets (index_offset, base_vertex, instance_offset), vertex buffer bindings, and index buffer binding. event_id: optional — pass the expected EID to verify the correct event is selected; 0 (default) uses whatever is currently selected. Returns error: not_a_draw if the selected event is not a draw call.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_draw_geometry_info"))

	// ---- get_vertex_input_layout ----
	server.AddTool(&mcp.Tool{
		Name:        "get_vertex_input_layout",
		Description: "Return vertex input attributes and buffer bindings for the currently selected pipeline state. Lists every declared vertex attribute with its semantic name, format (component type, count, byte width), buffer slot, byte offset within the vertex, and per-instance flag. Also returns bound vertex buffers (slot, resource_id, byte_offset, byte_stride) and the index buffer binding. Includes the vertex shader input signature for layout correlation. event_id: optional EID sanity check; 0 uses the currently selected event.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_vertex_input_layout"))

	// ---- get_mesh_indices ----
	server.AddTool(&mcp.Tool{
		Name:        "get_mesh_indices",
		Description: "Decode a bounded range of index values from the bound index buffer. Returns each index's position in the buffer, its raw stored value, and the effective vertex reference after applying base_vertex. first_index: first index to read (default 0). count: number of indices to read (default 100, max 1000). event_id: optional EID sanity check. Requires an indexed draw call with a bound index buffer.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"first_index": prop("integer", "First index", 0),
			"count":       prop("integer", "Number of indices", 100),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_mesh_indices"))

	// ---- get_mesh_vertices ----
	server.AddTool(&mcp.Tool{
		Name:        "get_mesh_vertices",
		Description: "Decode vertex attributes for a bounded range of vertices from the bound vertex buffers. Returns per-vertex attribute values (position, normal, texcoord, etc.) decoded according to the pipeline's input layout. first_vertex: first vertex index to read (default 0). count: number of vertices to read (default 10, max 100). attributes: optional list of attribute semantic names to include (e.g. ['POSITION', 'NORMAL']); omit to include all per-vertex attributes. Per-instance attributes are excluded — use get_draw_geometry_info to see instance counts. event_id: optional EID sanity check.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":     prop("integer", "Event ID (0 = current)", 0),
			"first_vertex": prop("integer", "First vertex", 0),
			"count":        prop("integer", "Number of vertices", 10),
			"attributes": map[string]interface{}{
				"type":        "array",
				"description": "Optional attribute names to include",
				"items":       map[string]interface{}{"type": "string"},
			},
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_mesh_vertices"))

	// ---- get_post_vs_geometry ----
	server.AddTool(&mcp.Tool{
		Name:        "get_post_vs_geometry",
		Description: "Retrieve post-vertex-shader geometry for the selected draw call. Calls GetPostVSData() which performs replay work — not read-only. Returns clip-space vertex positions (SV_Position) and NDC coordinates, plus other VS output attributes decoded from the vertex shader output signature. stage: 'vs_out' (default), 'vs_in', or 'gs_out'. instance: instance index (default 0). view: view index for multi-view rendering (default 0). max_vertices: maximum vertices to decode (default 50, max 100). Positions are clip-space (XYZW); SV_Position_ndc gives X/W, Y/W, Z/W. Returns error: no_post_vs_data when the draw does not support post-VS inspection.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":     prop("integer", "Event ID (0 = current)", 0),
			"instance":     prop("integer", "Instance index", 0),
			"view":         prop("integer", "View index", 0),
			"stage":        prop("string", "Stage: vs_out, vs_in, gs_out", "vs_out"),
			"max_vertices": prop("integer", "Max vertices", 50),
			"instance_id":  prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_post_vs_geometry"))

	// ---- get_mesh_statistics ----
	server.AddTool(&mcp.Tool{
		Name:        "get_mesh_statistics",
		Description: "Compute geometry statistics from a bounded vertex position sample for the selected draw call. Reports: axis-aligned bounding box (object-space, from vertex buffer input), NaN and infinity component counts, valid vertex count, and whether results are complete or from a sample. max_vertices: maximum vertices to analyze (default 200, max 500). The bounding box reflects vertex buffer data before vertex transformation. Use get_post_vs_geometry for clip-space bounds. event_id: optional EID sanity check.",
		InputSchema: objSchema(map[string]interface{}{
			"event_id":     prop("integer", "Event ID (0 = current)", 0),
			"max_vertices": prop("integer", "Max vertices", 200),
			"instance_id":  prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_mesh_statistics"))

	// ---- get_pixel_history ----
	server.AddTool(&mcp.Tool{
		Name:        "get_pixel_history",
		Description: "Retrieve the modification history of a pixel in a texture across the current frame. Shows which draw calls modified the pixel, their fragment results, depth/stencil test outcomes, and pre/post pixel values. Uses RenderDoc PixelHistory replay — not read-only. resource_id: ResourceId of the target texture. x, y: pixel coordinates. mip: mip level (default 0). slice: array slice (default 0). sample: MSAA sample (default 0). max_modifications: maximum modifications to return (default 50, max 200). Returns error: pixel_history_failed if the API or texture format is unsupported.",
		InputSchema: objSchema(map[string]interface{}{
			"resource_id":       prop("string", "Resource ID", ""),
			"x":                 prop("integer", "X coordinate", 0),
			"y":                 prop("integer", "Y coordinate", 0),
			"mip":               prop("integer", "Mip level", 0),
			"slice":             prop("integer", "Array slice", 0),
			"sample":            prop("integer", "MSAA sample", 0),
			"max_modifications": prop("integer", "Max modifications", 50),
			"event_id":          prop("integer", "Event ID (0 = current)", 0),
			"instance_id":       prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_pixel_history"))

	// ---- debug_pixel_shader ----
	server.AddTool(&mcp.Tool{
		Name:        "debug_pixel_shader",
		Description: "Collect a bounded pixel shader debug trace for a given pixel coordinate. Executes RenderDoc DebugPixel replay — not read-only and has GPU/CPU cost. Returns a debug_id for subsequent inspection with get_shader_debug_trace and get_shader_debug_variables. x, y: pixel to debug. event_id: draw event (0 = current selection). sample: MSAA sample index. primitive: fragment primitive ID (-1 = auto-select). max_steps: maximum trace steps to collect (default 200, max 500). Returns error: debug_pixel_unsupported if the API or shader is not debuggable.",
		InputSchema: objSchema(map[string]interface{}{
			"x":           prop("integer", "X coordinate", 0),
			"y":           prop("integer", "Y coordinate", 0),
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"sample":      prop("integer", "MSAA sample", 0),
			"primitive":   prop("integer", "Primitive ID (-1 = auto)", -1),
			"view":        prop("integer", "View index", 0),
			"max_steps":   prop("integer", "Max trace steps", 200),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "debug_pixel_shader"))

	// ---- debug_vertex_shader ----
	server.AddTool(&mcp.Tool{
		Name:        "debug_vertex_shader",
		Description: "Collect a bounded vertex shader debug trace for a specific vertex invocation. Executes RenderDoc DebugVertex replay — not read-only. Returns a debug_id for inspection with get_shader_debug_trace. vert_id: vertex ID to debug. inst_id: instance ID. idx: for indexed draws, the index value. view: multi-view index. event_id: draw event (0 = current). max_steps: trace step limit (default 200, max 500). Returns error: debug_vertex_unsupported if the API or shader is not debuggable.",
		InputSchema: objSchema(map[string]interface{}{
			"vert_id":     prop("integer", "Vertex ID", 0),
			"inst_id":     prop("integer", "Instance ID", 0),
			"idx":         prop("integer", "Index value", 0),
			"view":        prop("integer", "View index", 0),
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"max_steps":   prop("integer", "Max trace steps", 200),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "debug_vertex_shader"))

	// ---- debug_compute_shader ----
	server.AddTool(&mcp.Tool{
		Name:        "debug_compute_shader",
		Description: "Collect a bounded compute shader debug trace for a specific thread invocation. Executes RenderDoc DebugThread replay — not read-only. Returns a debug_id for inspection with get_shader_debug_trace. group_x/y/z: workgroup indices. thread_x/y/z: thread within the workgroup. event_id: dispatch event (0 = current). max_steps: trace step limit (default 200, max 500). Note: only the targeted thread is debugged; cross-thread behavior is not observable. Returns error: debug_compute_unsupported if the API does not support compute debugging.",
		InputSchema: objSchema(map[string]interface{}{
			"group_x":     prop("integer", "Workgroup X", 0),
			"group_y":     prop("integer", "Workgroup Y", 0),
			"group_z":     prop("integer", "Workgroup Z", 0),
			"thread_x":    prop("integer", "Thread X", 0),
			"thread_y":    prop("integer", "Thread Y", 0),
			"thread_z":    prop("integer", "Thread Z", 0),
			"event_id":    prop("integer", "Event ID (0 = current)", 0),
			"max_steps":   prop("integer", "Max trace steps", 200),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "debug_compute_shader"))

	// ---- get_shader_debug_trace ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_debug_trace",
		Description: "Retrieve bounded steps from a stored shader debug trace. Read-only — reads from the debug store populated by debug_pixel_shader, debug_vertex_shader, or debug_compute_shader. debug_id: the ID returned by a debug tool. first_step: starting step index (default 0). count: number of steps to return (default 50, max 500). Each step includes instruction index, variable changes (name + before/after values), and flags such as generated_nan_or_inf. Use get_shader_debug_variables to reconstruct the full variable state at a step.",
		InputSchema: objSchema(map[string]interface{}{
			"debug_id":    prop("string", "Debug ID", ""),
			"first_step":  prop("integer", "First step", 0),
			"count":       prop("integer", "Number of steps", 50),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_shader_debug_trace"))

	// ---- get_shader_debug_variables ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_debug_variables",
		Description: "Inspect variable state at a specific step of a stored shader debug trace. Read-only — reconstructs variable values by applying all change deltas from the initial state up to and including the requested step. debug_id: the ID returned by a debug tool. step: the step index to inspect (0-based, default 0). variable_names: optional list of variable names to filter; null returns all. Returns the reconstructed variable state at the requested step.",
		InputSchema: objSchema(map[string]interface{}{
			"debug_id": prop("string", "Debug ID", ""),
			"step":     prop("integer", "Step index", 0),
			"variable_names": map[string]interface{}{
				"type":        "array",
				"description": "Optional variable name filter",
				"items":       map[string]interface{}{"type": "string"},
			},
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_shader_debug_variables"))

	// ---- get_shader_debug_status ----
	server.AddTool(&mcp.Tool{
		Name:        "get_shader_debug_status",
		Description: "Check the status of a shader debug trace stored in the debug store. Read-only — no replay required. debug_id: the ID to query; omit to list all stored debug IDs. Returns status (ready/failed/invalidated), stage, event_id, step_count, and metadata.",
		InputSchema: objSchema(map[string]interface{}{
			"debug_id":    prop("string", "Debug ID (empty = list all)", ""),
			"instance_id": prop("string", "Optional instance ID", ""),
		}),
	}, makeHandler(client, "get_shader_debug_status"))
}

// ---------------------------------------------------------------------------
// Handler factories
// ---------------------------------------------------------------------------

// makeHandler returns a ToolHandler that forwards any tool call to the IPC
// service and returns the JSON-formatted result as TextContent.
func makeHandler(client *ServiceClient, toolName string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := map[string]interface{}{}
		if len(req.Params.Arguments) > 0 {
			if err := json.Unmarshal(req.Params.Arguments, &args); err != nil {
				slog.Warn("failed to unmarshal tool arguments", "tool", toolName, "err", err)
			}
		}
		result, err := client.CallTool(ctx, toolName, args)
		if err != nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}},
				IsError: true,
			}, nil
		}
		text, _ := json.MarshalIndent(result, "", "  ")
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: string(text)}},
		}, nil
	}
}

// makeTextureImageHandler returns a handler for get_texture_image that, if the
// result contains an "image_data" key (base64-encoded PNG), decodes it to raw
// bytes and returns ImageContent + TextContent with the remaining fields.
func makeTextureImageHandler(client *ServiceClient) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := map[string]interface{}{}
		if len(req.Params.Arguments) > 0 {
			if err := json.Unmarshal(req.Params.Arguments, &args); err != nil {
				slog.Warn("failed to unmarshal get_texture_image arguments", "err", err)
			}
		}
		result, err := client.CallTool(ctx, "get_texture_image", args)
		if err != nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}},
				IsError: true,
			}, nil
		}

		// Check if result is a map with image_data.
		resultMap, ok := result.(map[string]interface{})
		if !ok {
			text, _ := json.MarshalIndent(result, "", "  ")
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: string(text)}},
			}, nil
		}

		imageDataRaw, hasImage := resultMap["image_data"]
		if !hasImage {
			text, _ := json.MarshalIndent(result, "", "  ")
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: string(text)}},
			}, nil
		}

		imageDataStr, ok := imageDataRaw.(string)
		if !ok {
			text, _ := json.MarshalIndent(result, "", "  ")
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: string(text)}},
			}, nil
		}

		// Decode base64 PNG.
		imgBytes, err := base64.StdEncoding.DecodeString(imageDataStr)
		if err != nil {
			slog.Warn("failed to decode image_data base64", "err", err)
			text, _ := json.MarshalIndent(result, "", "  ")
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: string(text)}},
			}, nil
		}

		// Build remaining metadata without image_data.
		remaining := make(map[string]interface{}, len(resultMap))
		for k, v := range resultMap {
			if k != "image_data" {
				remaining[k] = v
			}
		}
		metaText, _ := json.MarshalIndent(remaining, "", "  ")

		return &mcp.CallToolResult{
			Content: []mcp.Content{
				&mcp.ImageContent{Data: imgBytes, MIMEType: "image/png"},
				&mcp.TextContent{Text: string(metaText)},
			},
		}, nil
	}
}

// ---------------------------------------------------------------------------
// Schema helpers
// ---------------------------------------------------------------------------

// objSchema constructs a JSON Schema object with the given properties.
// If required is provided, it is added to the schema.
func objSchema(props map[string]interface{}, required ...string) json.RawMessage {
	s := map[string]interface{}{"type": "object"}
	if len(props) > 0 {
		s["properties"] = props
	}
	if len(required) > 0 {
		s["required"] = required
	}
	data, _ := json.Marshal(s)
	return json.RawMessage(data)
}

// prop builds a simple JSON Schema property descriptor.
// defaultVal may be nil for required fields.
func prop(typ, description string, defaultVal interface{}) map[string]interface{} {
	m := map[string]interface{}{
		"type":        typ,
		"description": description,
	}
	if defaultVal != nil {
		m["default"] = defaultVal
	}
	return m
}
