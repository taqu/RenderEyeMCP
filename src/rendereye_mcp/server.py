"""MCP server definition with the server_status tool."""

from __future__ import annotations

import logging
import os
import platform
import sys
import uuid
from typing import TYPE_CHECKING, List, Optional

from mcp.server.mcpserver import MCPServer

from rendereye_mcp import __version__
from rendereye_mcp.config import Config

if TYPE_CHECKING:
    from rendereye_mcp.captures.registry import CaptureRegistry
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager
    from rendereye_mcp.ipc.transport import IPCTransport
    from rendereye_mcp.operations.tracker import OperationTracker
    from rendereye_mcp.sessions.manager import SessionManager

logger = logging.getLogger(__name__)

# Module-level reference to the IPC transport so server_status can query it.
# Set by create_server() after transport is created.
_ipc_transport: Optional["IPCTransport"] = None

# Module-level reference to the capture registry.
_registry: Optional["CaptureRegistry"] = None

# Module-level reference to the session manager.
_session_manager: Optional["SessionManager"] = None

# Module-level reference to the extension connection manager.
_conn_manager: Optional["ExtensionConnectionManager"] = None

# Module-level operation tracker.
_operation_tracker: Optional["OperationTracker"] = None

# Module-level measurement store for standalone mode.
_measurement_store = None

# Module-level debug store for standalone mode.
_debug_store = None


def create_server(config: Config, service_client=None) -> MCPServer:
    """Create and configure the MCPServer instance.

    Args:
        config: RenderEyeMCP configuration.
        service_client: Optional ServiceClient for bridge mode.  When supplied,
            all tool calls are forwarded to the shared service via IPC.  When
            None, the server operates in standalone (legacy) mode and manages
            its own IPCTransport.
    """
    from rendereye_mcp.captures.models import CaptureStatus
    from rendereye_mcp.errors import ErrorCode, error_response
    from rendereye_mcp.ipc.transport import IPCTransport
    from rendereye_mcp.operations.tracker import OperationTracker

    global _ipc_transport, _registry, _operation_tracker

    # Only create IPCTransport in standalone / legacy mode.
    if service_client is None:
        _ipc_transport = IPCTransport(config)
    _operation_tracker = OperationTracker()

    server = MCPServer(
        name="RenderEyeMCP",
        version=__version__,
        description="MCP server bridging AI assistants to RenderDoc GPU frame debugger",
    )

    @server.tool(
        name="server_status",
        description=(
            "Return the current health and configuration of the RenderEyeMCP server. "
            "Use this to verify the server is running, check whether RenderDoc is "
            "detected on this machine, inspect IPC listener state, and count active "
            "extension connections and sessions. Does not modify any GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def server_status() -> dict:
        """Return server status information."""
        if service_client is not None:
            return await service_client.call_tool("server_status", {})

        from rendereye_mcp.platform.windows import find_renderdoc_exe

        rdoc_path = find_renderdoc_exe(config)
        rdoc_detected = rdoc_path is not None

        ipc_running = _ipc_transport is not None and _ipc_transport.is_running
        ext_connections = (
            _ipc_transport.connection_count if _ipc_transport is not None else 0
        )

        active_sessions = 0
        if _session_manager is not None:
            try:
                active_sessions = _session_manager.get_active_session_count()
            except Exception:
                pass

        active_ext_connections = 0
        if _conn_manager is not None:
            try:
                active_ext_connections = _conn_manager.active_count()
            except Exception:
                pass

        return {
            "server_name": "RenderEyeMCP",
            "server_version": __version__,
            "os": f"{platform.system()} {platform.version()}",
            "python_version": sys.version,
            "renderdoc_detected": rdoc_detected,
            "renderdoc_path": rdoc_path,
            "ipc_listener_status": "running" if ipc_running else "stopped",
            "extension_connections": ext_connections,
            "active_sessions": active_sessions,
            "active_extension_connections": active_ext_connections,
            "ipc_protocol_version": 1,
        }

    @server.tool(
        name="capture_list",
        description=(
            "List captures from the Capture Registry. Use this to discover available "
            ".rdc files with their Capture IDs, paths, and readiness status. Supports "
            "filtering by status (ready/pending/missing/invalid) and directory, with "
            "pagination. Returns stable Capture IDs needed for capture_open. "
            "This tool does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def capture_list(
        status: str = "",
        directory: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List captures with optional filtering."""
        if service_client is not None:
            return await service_client.call_tool(
                "capture_list",
                {"status": status, "directory": directory, "limit": limit, "offset": offset},
            )

        if _registry is None:
            return {"captures": [], "total": 0, "limit": limit, "offset": offset}

        status_filter: Optional[CaptureStatus] = None
        if status:
            try:
                status_filter = CaptureStatus(status)
            except ValueError:
                return {
                    "error": "invalid_status",
                    "message": f"Unknown status: {status!r}",
                    "valid_statuses": [s.value for s in CaptureStatus],
                }

        records, total = _registry.list_captures(
            status=status_filter,
            directory=directory if directory else None,
            limit=limit,
            offset=offset,
        )
        return {
            "captures": [r.to_dict() for r in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @server.tool(
        name="capture_get",
        description=(
            "Get full metadata for a single capture by its Capture ID (e.g. 'cap-000018'). "
            "Use this to confirm a capture is ready before opening it, or to retrieve its "
            "file path, size, and status. Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def capture_get(capture_id: str) -> dict:
        """Get a single capture record by ID."""
        if service_client is not None:
            return await service_client.call_tool("capture_get", {"capture_id": capture_id})

        if _registry is None:
            return {"error": "not_found", "capture_id": capture_id}

        record = _registry.get_capture(capture_id)
        if record is None:
            return {"error": "not_found", "capture_id": capture_id}
        return record.to_dict()

    @server.tool(
        name="capture_latest",
        description=(
            "Get the most recently discovered ready capture. Use this when you want to "
            "open the newest available capture without knowing its ID. Optionally filter "
            "by directory. Set include_pending=true to fall back to pending captures when "
            "no ready capture exists. Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def capture_latest(
        directory: str = "",
        include_pending: bool = False,
    ) -> dict:
        """Get the most recent ready capture."""
        if service_client is not None:
            return await service_client.call_tool(
                "capture_latest",
                {"directory": directory, "include_pending": include_pending},
            )

        if _registry is None:
            return {"error": "no_capture_available"}

        record = _registry.get_latest_capture(
            directory=directory if directory else None
        )

        if record is None and include_pending:
            # Try pending as fallback
            records, _ = _registry.list_captures(
                status=CaptureStatus.PENDING,
                directory=directory if directory else None,
                limit=1,
            )
            record = records[0] if records else None

        if record is None:
            return {"error": "no_capture_available"}
        return record.to_dict()

    @server.tool(
        name="capture_rescan",
        description=(
            "Trigger an immediate rescan of all watched directories in the Capture Registry. "
            "Use this to pick up newly written .rdc files without waiting for the background "
            "watcher interval. Returns counts of scanned, new, and updated captures. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": False},
    )
    async def capture_rescan() -> dict:
        """Trigger an immediate rescan of all watched directories."""
        if service_client is not None:
            return await service_client.call_tool("capture_rescan", {})

        if _registry is None:
            return {"status": "unavailable", "message": "Registry not initialized"}

        result = await _registry.rescan()
        return {
            "status": "completed",
            "scanned": result.get("scanned", 0),
            "new": result.get("new", 0),
            "updated": result.get("updated", 0),
        }

    @server.tool(
        name="capture_registry_status",
        description=(
            "Get the current status of the Capture Registry including whether the background "
            "watcher is active, watched directories, total capture counts by status, and scan "
            "interval. Use this to diagnose why captures are not appearing. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def capture_registry_status() -> dict:
        """Get the current status of the capture registry."""
        if service_client is not None:
            return await service_client.call_tool("capture_registry_status", {})

        if _registry is None:
            return {"enabled": False, "running": False, "message": "Registry not initialized"}
        return _registry.get_status()

    @server.tool(
        name="instance_list",
        description=(
            "List all discovered RenderDoc processes and their windows. Use this to see "
            "which RenderDoc instances are running, whether each has an active extension "
            "connection, and what capture is currently loaded. Refreshes process/window "
            "discovery before returning. Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def instance_list() -> dict:
        """List running RenderDoc instances and their windows."""
        if service_client is not None:
            return await service_client.call_tool("instance_list", {})

        if _session_manager is None:
            return {"instances": [], "windows": []}
        _session_manager._instances.refresh()
        instances = _session_manager._instances.list_instances()
        windows = _session_manager._instances.list_windows()
        inst_dicts = []
        for inst in instances:
            inst_dict = inst.to_dict()
            if _conn_manager is not None:
                ext_conn = _conn_manager.get_connection_for_instance(inst.instance_id)
                inst_dict["extension_connected"] = ext_conn is not None and ext_conn.connected
                inst_dict["extension_capture_path"] = ext_conn.capture_path if ext_conn else None
            else:
                inst_dict["extension_connected"] = False
                inst_dict["extension_capture_path"] = None
            inst_dicts.append(inst_dict)
        return {
            "instances": inst_dicts,
            "windows": [w.to_dict() for w in windows],
        }

    @server.tool(
        name="instance_gui_state",
        description=(
            "Get the authoritative GUI state for a specific RenderDoc instance as reported "
            "by its extension. Returns whether a capture is loaded, the loaded capture path, "
            "and state freshness. Use this to verify which capture is actually visible in the "
            "RenderDoc GUI. Requires an active extension connection. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def instance_gui_state(instance_id: str) -> dict:
        """Get the current GUI state for a specific instance."""
        if service_client is not None:
            return await service_client.call_tool("instance_gui_state", {"instance_id": instance_id})

        if _conn_manager is None:
            return {"error": "conn_manager_unavailable"}
        conn = _conn_manager.get_connection_for_instance(instance_id)
        if conn is None:
            return {
                "instance_id": instance_id,
                "connected": False,
                "capture_loaded": False,
                "capture_path": None,
                "capture_state": "unknown",
                "freshness": "unavailable",
            }
        result = conn.to_dict()
        result["freshness"] = "fresh" if conn.connected else "stale"
        return result

    @server.tool(
        name="capture_open",
        description=(
            "Open a .rdc capture in RenderDoc and create or return a managed session. "
            "Use this as the primary tool for opening captures. "
            "Modes: 'new_window' (default) launches a new RenderDoc window; "
            "'reuse' returns an existing session for the same capture or creates a new one; "
            "'replace' replaces the capture in a specific managed session (requires "
            "target_session_id and an active extension connection). "
            "Specify capture_id as a Capture ID (e.g. 'cap-000018') or 'latest' for the "
            "most recent ready capture. "
            "Returns an operation record with operation_id, status, and session/window "
            "identifiers. STATUS VALUES: confirmed=success, unknown_outcome=launched but "
            "unverified, failed=error. "
            "THIS TOOL CHANGES GUI STATE."
        ),
        annotations={"readOnlyHint": False},
    )
    async def capture_open(
        capture_id: str = "latest",
        open_mode: str = "new_window",
        target_session_id: str = "",
    ) -> dict:
        """Open a capture in RenderDoc and create/return a session."""
        if service_client is not None:
            return await service_client.call_tool(
                "capture_open",
                {
                    "capture_id": capture_id,
                    "open_mode": open_mode,
                    "target_session_id": target_session_id,
                },
            )

        if _session_manager is None:
            return error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "Session manager not initialized",
            )
        return await _session_manager.open_capture(
            capture_id=capture_id,
            open_mode=open_mode,
            target_session_id=target_session_id if target_session_id else None,
            operation_tracker=_operation_tracker,
        )

    @server.tool(
        name="operation_get",
        description=(
            "Query the status of an async capture_open operation. Use this to check if a "
            "previously initiated operation has completed. Returns the operation record "
            "including final session/instance/window IDs when confirmed. "
            "STATUS VALUES: requested, validating, launching, waiting_for_gui, verifying, "
            "confirmed, failed, unsupported, timed_out, unknown_outcome. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def operation_get(operation_id: str) -> dict:
        """Retrieve an operation record by ID."""
        if service_client is not None:
            return await service_client.call_tool("operation_get", {"operation_id": operation_id})

        if _operation_tracker is None:
            return error_response(
                ErrorCode.INTERNAL_ERROR,
                "Operation tracker not initialized",
                operation_id=operation_id,
            )
        op = _operation_tracker.get(operation_id)
        if op is None:
            return error_response(
                ErrorCode.OPERATION_UNSUPPORTED,
                f"Operation not found: {operation_id}",
                operation_id=operation_id,
            )
        return op.to_dict()

    @server.tool(
        name="session_list",
        description=(
            "List managed sessions with optional filtering. Use this to see all open "
            "RenderDoc sessions, their status (active/disconnected/closing/closed), and "
            "which captures they have loaded. Supports filtering by status, managed_only "
            "flag, and capture_id, with pagination via limit/offset. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def session_list(
        status: str = "",
        managed_only: bool = False,
        capture_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List sessions with optional filtering."""
        if service_client is not None:
            return await service_client.call_tool(
                "session_list",
                {
                    "status": status,
                    "managed_only": managed_only,
                    "capture_id": capture_id,
                    "limit": limit,
                    "offset": offset,
                },
            )

        if _session_manager is None:
            return {"sessions": [], "total": 0, "limit": limit, "offset": offset}
        return _session_manager.list_sessions(
            status=status if status else None,
            managed_only=managed_only,
            capture_id=capture_id if capture_id else None,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="session_get",
        description=(
            "Get the full record for a single session by its Session ID "
            "(e.g. 'session-000001'). Use this to check session status, associated "
            "capture, instance, and window IDs, and whether extension GUI state has been "
            "verified. Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def session_get(session_id: str) -> dict:
        """Get a single session record by ID."""
        if service_client is not None:
            return await service_client.call_tool("session_get", {"session_id": session_id})

        if _session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        record = _session_manager.get_session(session_id)
        if record is None:
            return {"error": "not_found", "session_id": session_id}
        return record.to_dict()

    @server.tool(
        name="session_focus",
        description=(
            "Bring a session's RenderDoc window to the foreground. Use this to make a "
            "specific session visible without closing other sessions. Requires the session "
            "to have an associated window (the window must still be open). "
            "THIS TOOL CHANGES GUI STATE (raises a window)."
        ),
        annotations={"readOnlyHint": False},
    )
    async def session_focus(session_id: str) -> dict:
        """Bring a session's window to the foreground."""
        if service_client is not None:
            return await service_client.call_tool("session_focus", {"session_id": session_id})

        if _session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        return _session_manager.focus_session(session_id)

    @server.tool(
        name="session_close",
        description=(
            "Gracefully close a managed, unprotected session's RenderDoc window. "
            "The session must be managed (launched by this server) and not protected. "
            "Use session_protect first to unprotect if needed. "
            "Returns session_protected error if protected, session_unmanaged if not managed, "
            "session_not_found if the session ID is unknown. "
            "THIS TOOL CHANGES GUI STATE and is destructive — it closes a window."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def session_close(session_id: str) -> dict:
        """Gracefully close a managed session's window."""
        if service_client is not None:
            return await service_client.call_tool("session_close", {"session_id": session_id})

        if _session_manager is None:
            return error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "Session manager not initialized",
                session_id=session_id,
            )
        return _session_manager.close_session(session_id)

    @server.tool(
        name="session_protect",
        description=(
            "Set or unset the protection flag on a session. Protected sessions cannot be "
            "closed or replaced by capture_open replace mode. Use protected=true to prevent "
            "accidental closure, protected=false to allow closure. "
            "Returns the updated session record. "
            "Does not modify RenderDoc GUI state directly."
        ),
        annotations={"readOnlyHint": False},
    )
    async def session_protect(session_id: str, protected: bool) -> dict:
        """Set or unset the protected flag on a session."""
        if service_client is not None:
            return await service_client.call_tool(
                "session_protect", {"session_id": session_id, "protected": protected}
            )

        if _session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        return _session_manager.protect_session(session_id, protected)

    @server.tool(
        name="list_renderdoc_sessions",
        description=(
            "List all known RenderDoc GUI instances and their current state. "
            "Returns each instance's connection state (connected/disconnected/unknown) "
            "and capture information. Connected instances show the live capture state; "
            "disconnected instances show the last-known state under 'last_known_capture'. "
            "Use this to discover which RenderDoc instances are running and what they have loaded, "
            "including instances opened by Unity, Unreal Engine, or manually. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def list_renderdoc_sessions() -> dict:
        """List all known RenderDoc GUI sessions with their state."""
        if service_client is not None:
            return await service_client.call_tool("list_renderdoc_sessions", {})

        if _conn_manager is None:
            return {"sessions": [], "total": 0}
        connections = _conn_manager.list_connections()
        sessions = [c.to_gui_session_dict() for c in connections]
        return {"sessions": sessions, "total": len(sessions)}

    @server.tool(
        name="get_renderdoc_session_state",
        description=(
            "Get the current state of a specific RenderDoc GUI instance by its instance_id. "
            "Returns connection state (connected/disconnected/unknown) and capture information. "
            "A connected instance shows live capture state; a disconnected instance shows the "
            "last-known state under 'last_known_capture'. "
            "Use 'list_renderdoc_sessions' to discover valid instance_id values. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_renderdoc_session_state(instance_id: str) -> dict:
        """Get state for a specific RenderDoc GUI session."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_renderdoc_session_state", {"instance_id": instance_id}
            )

        if _conn_manager is None:
            return {"error": "conn_manager_unavailable", "instance_id": instance_id}
        conn = _conn_manager.get_any_connection_for_instance(instance_id)
        if conn is None:
            return {
                "error": "session_not_found",
                "instance_id": instance_id,
                "message": f"No RenderDoc GUI session found with instance_id={instance_id!r}",
            }
        return conn.to_gui_session_dict()

    @server.tool(
        name="get_current_capture",
        description=(
            "Return the capture currently loaded in RenderDoc. "
            "If exactly one connected RenderDoc GUI has a capture loaded, returns it directly. "
            "If multiple instances have captures loaded, returns all for disambiguation — "
            "specify instance_id to target a particular session. "
            "If no capture is loaded, returns the connection state and connected sessions. "
            "Works with captures opened externally (Unity, Unreal Engine, or manually) — "
            "no MCP capture_open call is required. "
            "STATUS VALUES: loaded=capture found, no_capture_loaded=connected but empty, "
            "capture_loading=loading in progress, ambiguous=multiple sessions, "
            "session_not_found=unknown instance_id, session_disconnected=offline session, "
            "no_renderdoc_connected=no active extension. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_current_capture(instance_id: str = "") -> dict:
        """Return the currently loaded capture from a connected RenderDoc GUI."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_current_capture", {"instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }

        if instance_id:
            conn = _conn_manager.get_any_connection_for_instance(instance_id)
            if conn is None:
                return {
                    "status": "session_not_found",
                    "instance_id": instance_id,
                    "message": f"No RenderDoc GUI session found with instance_id={instance_id!r}",
                }
            if not conn.connected:
                return {
                    "status": "session_disconnected",
                    "instance_id": instance_id,
                    "connection_state": conn.connection_state,
                    "message": "The specified RenderDoc GUI session is not currently connected",
                    "last_known_capture": {
                        "state": conn.capture_state,
                        "path": conn.capture_path,
                    } if conn.last_state_at is not None else None,
                }
            if not conn.capture_loaded:
                return {
                    "status": "no_capture_loaded",
                    "instance_id": instance_id,
                    "connection_state": "connected",
                    "capture_state": conn.capture_state,
                    "message": "The specified RenderDoc GUI session has no capture loaded",
                }
            return {
                "status": "loaded",
                "instance_id": conn.instance_id,
                "process_id": conn.process_id,
                "connection_state": "connected",
                "capture_path": conn.capture_path,
                "capture_state": conn.capture_state,
                "state_version": conn.gui_state_revision,
            }

        # Auto-select from all connected sessions
        all_conns = _conn_manager.list_connections()
        connected = [c for c in all_conns if c.connected]

        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }

        loaded = [c for c in connected if c.capture_loaded]

        if len(loaded) == 0:
            loading = [c for c in connected if c.capture_state == "loading"]
            if loading:
                return {
                    "status": "capture_loading",
                    "message": "A capture is currently loading",
                    "sessions": [c.to_gui_session_dict() for c in loading],
                }
            return {
                "status": "no_capture_loaded",
                "message": "Connected RenderDoc GUI instance(s) have no capture loaded",
                "sessions": [c.to_gui_session_dict() for c in connected],
            }

        if len(loaded) == 1:
            conn = loaded[0]
            return {
                "status": "loaded",
                "instance_id": conn.instance_id,
                "process_id": conn.process_id,
                "connection_state": "connected",
                "capture_path": conn.capture_path,
                "capture_state": conn.capture_state,
                "state_version": conn.gui_state_revision,
            }

        return {
            "status": "ambiguous",
            "message": (
                f"Multiple RenderDoc GUI sessions have a capture loaded ({len(loaded)}). "
                "Specify instance_id to target a specific session."
            ),
            "sessions": [c.to_gui_session_dict() for c in loaded],
        }

    @server.tool(
        name="get_current_capture_info",
        description=(
            "Get metadata about the capture currently loaded in a connected RenderDoc GUI session. "
            "Returns file path, frame count, capture time, API, and other capture-level metadata. "
            "If multiple sessions are connected, specify instance_id to target a particular one. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_current_capture_info(instance_id: str = "") -> dict:
        """Get metadata about the currently loaded capture."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_current_capture_info", {"instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(conn_id, "capture_info", {})

    @server.tool(
        name="list_capture_events",
        description=(
            "List draw calls, dispatches, and other events from the currently loaded capture. "
            "Supports pagination via limit/offset, filtering by parent_event_id for hierarchical "
            "traversal, and optional debug marker inclusion via include_markers. "
            "Use flags_filter to restrict to specific event types (e.g. 'drawcall', 'dispatch'). "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def list_capture_events(
        instance_id: str = "",
        limit: int = 50,
        offset: int = 0,
        include_markers: bool = True,
        flags_filter: str = "",
        parent_event_id: int = 0,
    ) -> dict:
        """List events from the currently loaded capture."""
        if service_client is not None:
            return await service_client.call_tool(
                "list_capture_events",
                {
                    "instance_id": instance_id,
                    "limit": limit,
                    "offset": offset,
                    "include_markers": include_markers,
                    "flags_filter": flags_filter,
                    "parent_event_id": parent_event_id,
                },
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "list_events",
            {
                "limit": limit,
                "offset": offset,
                "include_markers": include_markers,
                "flags_filter": flags_filter,
                "parent_event_id": parent_event_id,
            },
        )

    @server.tool(
        name="get_capture_event",
        description=(
            "Get detailed information about a specific event in the loaded capture by event ID. "
            "Returns event type, flags, draw call parameters, resource bindings, and timing "
            "information for the given event. Use list_capture_events to discover valid event IDs. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_capture_event(event_id: int, instance_id: str = "") -> dict:
        """Get detailed information about a specific capture event."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_capture_event", {"event_id": event_id, "instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_event", {"event_id": event_id}
        )

    @server.tool(
        name="get_selected_event",
        description=(
            "Get the event currently selected in the RenderDoc GUI timeline. "
            "Returns the same detailed event information as get_capture_event for whichever "
            "event the user has highlighted in the RenderDoc UI. Useful for inspecting what "
            "the user is currently looking at without needing to know the event ID. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_selected_event(instance_id: str = "") -> dict:
        """Get the event currently selected in the RenderDoc GUI."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_selected_event", {"instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(conn_id, "selected_event", {})

    @server.tool(
        name="get_pipeline_state",
        description=(
            "Inspect the graphics or compute pipeline state. "
            "Sections: summary, input_assembly, shaders, rasterizer, depth_stencil, "
            "output_merger, resources. "
            "If event_id is 0 (default), uses the currently selected event. "
            "Returns the pipeline state for the specified section at the given event. "
            "Does not modify RenderDoc GUI state."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_pipeline_state(
        instance_id: str = "",
        event_id: int = 0,
        section: str = "summary",
    ) -> dict:
        """Inspect the graphics or compute pipeline state at an event."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_pipeline_state",
                {"instance_id": instance_id, "event_id": event_id, "section": section},
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "pipeline_state", {"event_id": event_id, "section": section}
        )

    @server.tool(
        name="list_resources",
        description=(
            "Enumerate GPU resources in the currently loaded capture. "
            "resource_type: 'all', 'texture', 'buffer'. "
            "Supports name filtering and pagination."
        ),
        annotations={"readOnlyHint": True},
    )
    async def list_resources(
        instance_id: str = "",
        resource_type: str = "all",
        name_filter: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Enumerate GPU resources in the currently loaded capture."""
        if service_client is not None:
            return await service_client.call_tool(
                "list_resources",
                {
                    "instance_id": instance_id,
                    "resource_type": resource_type,
                    "name_filter": name_filter,
                    "limit": limit,
                    "offset": offset,
                },
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "list_resources",
            {
                "resource_type": resource_type,
                "name_filter": name_filter,
                "limit": limit,
                "offset": offset,
            },
        )

    @server.tool(
        name="get_resource_info",
        description=(
            "Get metadata for a GPU resource by its ID. "
            "Returns type-specific details for textures and buffers."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_resource_info(resource_id: str, instance_id: str = "") -> dict:
        """Get metadata for a GPU resource by its ID."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_resource_info", {"resource_id": resource_id, "instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_resource_info", {"resource_id": resource_id}
        )

    @server.tool(
        name="get_texture_info",
        description=(
            "Get detailed metadata for a GPU texture resource: "
            "dimensions, format, mip levels, sample count, usage flags."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_texture_info(resource_id: str, instance_id: str = "") -> dict:
        """Get detailed metadata for a GPU texture resource."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_texture_info", {"resource_id": resource_id, "instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_texture_info", {"resource_id": resource_id}
        )

    @server.tool(
        name="get_buffer_info",
        description=(
            "Get detailed metadata for a GPU buffer resource: byte size, usage flags."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_buffer_info(resource_id: str, instance_id: str = "") -> dict:
        """Get detailed metadata for a GPU buffer resource."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_buffer_info", {"resource_id": resource_id, "instance_id": instance_id}
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_buffer_info", {"resource_id": resource_id}
        )

    @server.tool(
        name="read_buffer_data",
        description=(
            "Read a bounded byte range from a GPU buffer. "
            "output_format: hex, base64, bytes. "
            "Optionally decode with decode_layout (stride, element_count, fields with name/type/offset/components)."
        ),
        annotations={"readOnlyHint": True},
    )
    async def read_buffer_data(
        resource_id: str,
        offset: int = 0,
        length: int = 256,
        output_format: str = "hex",
        decode_layout: Optional[dict] = None,
        instance_id: str = "",
    ) -> dict:
        """Read a bounded byte range from a GPU buffer."""
        if service_client is not None:
            return await service_client.call_tool(
                "read_buffer_data",
                {
                    "resource_id": resource_id,
                    "offset": offset,
                    "length": length,
                    "output_format": output_format,
                    "decode_layout": decode_layout,
                    "instance_id": instance_id,
                },
            )

        if _conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        params: dict = {
            "resource_id": resource_id,
            "offset": offset,
            "length": length,
            "output_format": output_format,
        }
        if decode_layout is not None:
            params["decode_layout"] = decode_layout
        return await _conn_manager.request_capture_inspection(
            conn_id, "read_buffer_data", params
        )

    @server.tool(
        name="list_shaders",
        description=(
            "List shaders bound to the currently selected event. "
            "Returns stage name, shader ID, entry point, and reflection summary for each bound shader."
        ),
        annotations={"readOnlyHint": True},
    )
    async def list_shaders(instance_id: str = "") -> dict:
        """List shaders bound to the currently selected event."""
        if service_client is not None:
            return await service_client.call_tool("list_shaders", {"instance_id": instance_id})

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(conn_id, "list_shaders", {})

    @server.tool(
        name="get_shader_info",
        description=(
            "Get metadata for the shader bound at a specific pipeline stage. "
            "stage: 'Vertex', 'Pixel', 'Compute', 'Geometry', 'Hull', 'Domain' (case-insensitive). "
            "Returns shader ID, entry point, reflection counts, and disassembly targets."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_info(stage: str, instance_id: str = "") -> dict:
        """Get metadata for the shader at a specific pipeline stage."""
        if service_client is not None:
            return await service_client.call_tool("get_shader_info", {"stage": stage, "instance_id": instance_id})

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(conn_id, "get_shader_info", {"stage": stage})

    @server.tool(
        name="get_shader_reflection",
        description=(
            "Get shader reflection data: input/output signatures, constant buffer declarations, "
            "resource and sampler declarations. "
            "stage: shader stage. "
            "section: 'all', 'input', 'output', 'cbuffers', 'resources', 'samplers'."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_reflection(
        stage: str,
        section: str = "all",
        instance_id: str = "",
    ) -> dict:
        """Get shader reflection data for a specific stage."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_reflection",
                {"stage": stage, "section": section, "instance_id": instance_id},
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_shader_reflection", {"stage": stage, "section": section}
        )

    @server.tool(
        name="get_shader_bindings",
        description=(
            "Correlate reflected shader resource declarations with actual runtime bindings. "
            "Returns each declared cbuffer, texture, and UAV with its bound resource ID (or null if unbound). "
            "stage: shader stage."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_bindings(stage: str, instance_id: str = "") -> dict:
        """Correlate reflected shader declarations with actual pipeline bindings."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_bindings", {"stage": stage, "instance_id": instance_id}
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_shader_bindings", {"stage": stage}
        )

    @server.tool(
        name="get_shader_disassembly",
        description=(
            "Retrieve bounded shader disassembly. "
            "stage: shader stage. "
            "target: disassembly target (empty = default). "
            "offset/limit: line pagination (max 200 lines). "
            "search: optional text to search for (returns matching lines with context)."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_disassembly(
        stage: str,
        target: str = "",
        offset: int = 0,
        limit: int = 200,
        search: str = "",
        instance_id: str = "",
    ) -> dict:
        """Retrieve bounded shader disassembly."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_disassembly",
                {
                    "stage": stage,
                    "target": target,
                    "offset": offset,
                    "limit": limit,
                    "search": search,
                    "instance_id": instance_id,
                },
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "get_shader_disassembly",
            {"stage": stage, "target": target, "offset": offset, "limit": limit, "search": search},
        )

    @server.tool(
        name="get_shader_debug_info",
        description=(
            "Retrieve shader source-level debug information where available. "
            "stage: shader stage. "
            "file_index: source file to read (0-based). "
            "start_line/max_lines: line range to retrieve (max 500)."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_debug_info(
        stage: str,
        file_index: int = 0,
        start_line: int = 0,
        max_lines: int = 100,
        instance_id: str = "",
    ) -> dict:
        """Retrieve shader source/debug information."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_debug_info",
                {
                    "stage": stage,
                    "file_index": file_index,
                    "start_line": start_line,
                    "max_lines": max_lines,
                    "instance_id": instance_id,
                },
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "get_shader_debug_info",
            {
                "stage": stage,
                "file_index": file_index,
                "start_line": start_line,
                "max_lines": max_lines,
            },
        )

    @server.tool(
        name="get_render_targets",
        description=(
            "List the color render targets and depth/stencil attachment bound to the currently selected draw call. "
            "Returns resource IDs, formats, dimensions, and binding indices. "
            "Use the returned resource_id values with get_texture_info or get_texture_image."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_render_targets(instance_id: str = "") -> dict:
        """List render targets bound to the selected event."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_render_targets", {"instance_id": instance_id}
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id, "get_render_targets", {}
        )

    @server.tool(
        name="get_texture_image",
        description=(
            "Retrieve a bounded PNG image of a GPU texture. "
            "Returns an MCP image content block plus metadata. "
            "resource_id: GPU resource ID (from list_resources or get_render_targets). "
            "mip: mip level (0 = full resolution). "
            "array_slice: array layer index. "
            "max_dim: maximum output dimension in pixels (default 1024). "
            "If the requested mip exceeds max_dim, returns image_too_large with suggested_mip. "
            "Texture contents reflect the current replay event."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_texture_image(
        resource_id: str,
        mip: int = 0,
        array_slice: int = 0,
        max_dim: int = 1024,
        instance_id: str = "",
    ):
        """Retrieve PNG image of a texture. Returns ImageContent + TextContent metadata."""
        import json as _json

        from mcp.types import ImageContent, TextContent

        if service_client is not None:
            result = await service_client.call_tool(
                "get_texture_image",
                {
                    "resource_id": resource_id,
                    "mip": mip,
                    "array_slice": array_slice,
                    "max_dim": max_dim,
                    "instance_id": instance_id,
                },
            )
        else:
            if _conn_manager is None:
                return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
            connected = [c for c in _conn_manager.list_connections() if c.connected]
            if not connected:
                return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
            if len(connected) == 1:
                conn_id = connected[0].connection_id
            else:
                loaded = [c for c in connected if c.capture_loaded]
                if len(loaded) == 1:
                    conn_id = loaded[0].connection_id
                else:
                    return {
                        "status": "ambiguous",
                        "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                        "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                    }
            result = await _conn_manager.request_capture_inspection(
                conn_id,
                "get_texture_image",
                {
                    "resource_id": resource_id,
                    "mip": mip,
                    "array_slice": array_slice,
                    "max_dim": max_dim,
                },
            )

        if isinstance(result, dict) and "image_data" in result:
            img_b64 = result.pop("image_data")
            return [
                ImageContent(type="image", data=img_b64, mime_type="image/png"),
                TextContent(type="text", text=_json.dumps(result, indent=2)),
            ]
        return result

    @server.tool(
        name="get_pixel_value",
        description=(
            "Retrieve exact typed pixel component values at a coordinate (or batch of coordinates). "
            "resource_id: GPU texture resource ID. "
            "x, y: pixel coordinate (integer, top-left origin). "
            "mip: mip level (default 0). array_slice: array layer (default 0). sample: MSAA sample index (default 0). "
            "coords: optional list of {x, y} dicts for batch queries (max 16 pixels). "
            "Returns float, uint, and sint component arrays as reported by RenderDoc. "
            "Values are exact GPU resource data, not display-converted colors."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_pixel_value(
        resource_id: str,
        x: int = 0,
        y: int = 0,
        mip: int = 0,
        array_slice: int = 0,
        sample: int = 0,
        coords: Optional[list[dict]] = None,
        instance_id: str = "",
    ) -> dict:
        """Retrieve typed pixel component values at a coordinate."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_pixel_value",
                {
                    "resource_id": resource_id,
                    "x": x,
                    "y": y,
                    "mip": mip,
                    "array_slice": array_slice,
                    "sample": sample,
                    "coords": coords,
                    "instance_id": instance_id,
                },
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "get_pixel_value",
            {
                "resource_id": resource_id,
                "mip": mip,
                "array_slice": array_slice,
                "sample": sample,
                **({"coords": coords} if coords is not None else {"x": x, "y": y}),
            },
        )

    @server.tool(
        name="get_texture_statistics",
        description=(
            "Retrieve per-component min/max pixel values for a texture subresource. "
            "Optionally retrieves a value histogram. "
            "resource_id: GPU texture resource ID. "
            "mip: mip level (default 0). array_slice: array layer (default 0). "
            "include_histogram: if true, returns a histogram (default false). "
            "hist_min, hist_max: histogram value range (default 0.0-1.0). "
            "Useful for checking whether a render target is blank, saturated, or has unexpected values."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_texture_statistics(
        resource_id: str,
        mip: int = 0,
        array_slice: int = 0,
        include_histogram: bool = False,
        hist_min: float = 0.0,
        hist_max: float = 1.0,
        instance_id: str = "",
    ) -> dict:
        """Retrieve texture min/max and optional histogram."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_texture_statistics",
                {
                    "resource_id": resource_id,
                    "mip": mip,
                    "array_slice": array_slice,
                    "include_histogram": include_histogram,
                    "hist_min": hist_min,
                    "hist_max": hist_max,
                    "instance_id": instance_id,
                },
            )

        if _conn_manager is None:
            return {"status": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return {"status": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if len(connected) == 1:
            conn_id = connected[0].connection_id
        else:
            loaded = [c for c in connected if c.capture_loaded]
            if len(loaded) == 1:
                conn_id = loaded[0].connection_id
            else:
                return {
                    "status": "ambiguous",
                    "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
                    "sessions": [c.to_gui_session_dict() for c in (loaded if loaded else connected)],
                }
        return await _conn_manager.request_capture_inspection(
            conn_id,
            "get_texture_statistics",
            {
                "resource_id": resource_id,
                "mip": mip,
                "array_slice": array_slice,
                "include_histogram": include_histogram,
                "hist_min": hist_min,
                "hist_max": hist_max,
            },
        )

    # Phase 13: GPU performance analysis
    from rendereye_mcp.service.measurement_store import MeasurementRecord, MeasurementStore
    from rendereye_mcp.service.tools import (
        _aggregate_passes,
        _find_counter_desc,
        _resolve_timing_counter,
        _sort_entries,
    )

    global _measurement_store
    if _measurement_store is None:
        _measurement_store = MeasurementStore()

    # Phase 15: Shader debug store
    from rendereye_mcp.service.debug_store import DebugStore as _DebugStore
    global _debug_store
    if _debug_store is None:
        _debug_store = _DebugStore()

    def _resolve_conn_standalone(instance_id: str):
        if _conn_manager is None:
            return None, {"error": "no_renderdoc_connected", "message": "Extension connection manager unavailable"}
        connected = [c for c in _conn_manager.list_connections() if c.connected]
        if not connected:
            return None, {"error": "no_renderdoc_connected", "message": "No RenderDoc GUI instances are currently connected"}
        if instance_id:
            for c in connected:
                if c.connection_id == instance_id or getattr(c, "instance_id", None) == instance_id:
                    return c.connection_id, None
            return None, {"error": "instance_not_found", "instance_id": instance_id}
        if len(connected) == 1:
            return connected[0].connection_id, None
        loaded = [c for c in connected if c.capture_loaded]
        if len(loaded) == 1:
            return loaded[0].connection_id, None
        return None, {
            "error": "ambiguous",
            "message": "Multiple RenderDoc GUI sessions are connected. Specify instance_id.",
        }

    @server.tool(
        name="list_gpu_counters",
        description=(
            "Enumerate GPU performance counters available for the currently loaded capture. "
            "Returns counter IDs, names, units, and value types as reported by RenderDoc. "
            "Counter availability depends on the GPU, graphics driver, graphics API, and "
            "RenderDoc version. Use the returned counter_id values with collect_gpu_counters. "
            "Call this first to discover which counters are supported before requesting measurement."
        ),
        annotations={"readOnlyHint": True},
    )
    async def list_gpu_counters(instance_id: str = "") -> dict:
        """Enumerate available GPU performance counters."""
        if service_client is not None:
            return await service_client.call_tool("list_gpu_counters", {"instance_id": instance_id})
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(conn_id, "list_gpu_counters", {})

    @server.tool(
        name="collect_gpu_counters",
        description=(
            "Collect GPU performance counter values for all events in the loaded capture. "
            "counter_ids: list of integer counter IDs from list_gpu_counters. "
            "instance_id: optional RenderDoc session ID. "
            "repeats: number of collection runs (1-5, default 1); multiple runs average results. "
            "Returns a measurement_id that identifies the stored results. "
            "This operation executes FetchCounters() which performs GPU replay and may take "
            "several seconds for large captures. It is NOT read-only. "
            "Use get_gpu_timings, get_performance_summary, get_render_pass_performance, and "
            "get_pipeline_statistics to analyze the stored results without re-running the GPU."
        ),
        annotations={"readOnlyHint": False},
    )
    async def collect_gpu_counters(
        counter_ids: list,
        instance_id: str = "",
        repeats: int = 1,
    ) -> dict:
        """Start explicit GPU counter collection."""
        if service_client is not None:
            return await service_client.call_tool(
                "collect_gpu_counters",
                {"counter_ids": counter_ids, "instance_id": instance_id, "repeats": repeats},
            )
        if not counter_ids:
            return {"error": "missing_counter_ids", "message": "counter_ids must be a non-empty list"}
        repeats = max(1, min(int(repeats), 5))
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        capture_path = ""
        cap_info = await _conn_manager.request_capture_inspection(conn_id, "capture_info", {})
        if "error" not in cap_info:
            capture_path = cap_info.get("_capture_path", "") or ""
        all_run_results = []
        last_raw: dict = {}
        import time as _time
        for _run in range(repeats):
            raw = await _conn_manager.request_capture_inspection(
                conn_id, "fetch_gpu_counters", {"counter_ids": list(counter_ids)}
            )
            if "error" in raw:
                return raw
            all_run_results.append(raw.get("results", []))
            last_raw = raw
        counter_descriptions = last_raw.get("counter_descriptions", [])
        counters_fetched = last_raw.get("counters_fetched", [])
        counters_invalid = last_raw.get("counters_invalid", [])
        if repeats == 1:
            results = last_raw.get("results", [])
        else:
            from collections import defaultdict
            sums: dict = defaultdict(list)
            for run_results in all_run_results:
                for r in run_results:
                    key = (r["event_id"], r["counter_id"])
                    if r.get("value") is not None:
                        sums[key].append(r["value"])
            results = []
            for (eid, cid), values in sums.items():
                if values:
                    avg: object = int(sum(values) // len(values)) if all(isinstance(v, int) for v in values) else sum(float(v) for v in values) / len(values)
                    results.append({"event_id": eid, "counter_id": cid, "value": avg})
        mid = _measurement_store.make_id()
        record = MeasurementRecord(
            measurement_id=mid, status="completed", capture_path=capture_path or None,
            instance_id=conn_id, counter_ids=counters_fetched,
            counter_descriptions=counter_descriptions, results=results,
            created_at=_time.time(),
            metadata={"counters_invalid": counters_invalid, "repeats": repeats, "result_count": len(results)},
        )
        _measurement_store.store(record)
        return {
            "measurement_id": mid, "status": "completed", "capture_path": capture_path,
            "counters_fetched": counters_fetched, "counters_invalid": counters_invalid,
            "result_count": len(results), "repeats": repeats,
        }

    @server.tool(
        name="get_gpu_measurement_status",
        description=(
            "Retrieve the status and metadata of a GPU counter measurement. "
            "measurement_id: ID returned by collect_gpu_counters. "
            "Returns status (completed/failed/invalidated), capture path, counter list, "
            "result count, and timing metadata. "
            "Use to confirm a measurement completed before calling analysis tools."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_gpu_measurement_status(measurement_id: str) -> dict:
        """Check GPU measurement status."""
        if service_client is not None:
            return await service_client.call_tool(
                "get_gpu_measurement_status", {"measurement_id": measurement_id}
            )
        record = _measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        return {
            "measurement_id": record.measurement_id, "status": record.status,
            "capture_path": record.capture_path, "counter_ids": record.counter_ids,
            "counter_descriptions": record.counter_descriptions,
            "result_count": len(record.results) if record.results else 0,
            "created_at": record.created_at, "metadata": record.metadata,
            "error": record.error,
        }

    @server.tool(
        name="get_gpu_timings",
        description=(
            "Retrieve event-level GPU timing values from a completed measurement. "
            "measurement_id: ID from collect_gpu_counters. "
            "counter_id: optional counter ID to use; defaults to the first timing/duration counter. "
            "min_value: optional minimum value filter. "
            "sort_by: value_desc (default), value_asc, event_id, event_id_desc. "
            "limit/offset: pagination (default limit=100). "
            "Returns event IDs, counter values, and units. Does NOT re-run GPU collection."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_gpu_timings(
        measurement_id: str,
        counter_id: int = None,
        min_value: float = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "value_desc",
    ) -> dict:
        """Retrieve event-level GPU timings from stored measurement."""
        if service_client is not None:
            args = {"measurement_id": measurement_id, "limit": limit, "offset": offset, "sort_by": sort_by}
            if counter_id is not None:
                args["counter_id"] = counter_id
            if min_value is not None:
                args["min_value"] = min_value
            return await service_client.call_tool("get_gpu_timings", args)
        record = _measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        resolved_cid = _resolve_timing_counter(counter_id, record)
        if resolved_cid is None:
            return {"error": "no_timing_counter", "message": "No timing counter found. Specify counter_id."}
        entries = [r for r in (record.results or []) if r.get("counter_id") == resolved_cid]
        if min_value is not None:
            entries = [r for r in entries if r.get("value") is not None and r["value"] >= min_value]
        entries = _sort_entries(entries, sort_by)
        total = len(entries)
        limit = max(1, min(int(limit), 1000))
        page = entries[max(0, int(offset)): max(0, int(offset)) + limit]
        desc = _find_counter_desc(resolved_cid, record.counter_descriptions)
        return {
            "measurement_id": measurement_id, "counter_id": resolved_cid,
            "counter_name": desc.get("name", ""), "unit": desc.get("unit", ""),
            "total": total, "offset": offset, "limit": limit, "events": page,
        }

    @server.tool(
        name="get_performance_summary",
        description=(
            "Rank the most expensive GPU events from a completed measurement. "
            "measurement_id: ID from collect_gpu_counters. "
            "counter_id: optional counter ID to rank by; defaults to the first timing counter. "
            "top_n: number of top events to return (default 20, max 100). "
            "Returns events sorted by counter value descending, with total across all events. "
            "Use this to identify expensive draw calls and dispatches for deeper investigation "
            "with get_pipeline_state, get_shader_info, and related tools."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_performance_summary(
        measurement_id: str,
        counter_id: int = None,
        top_n: int = 20,
    ) -> dict:
        """Rank most expensive GPU events."""
        if service_client is not None:
            args: dict = {"measurement_id": measurement_id, "top_n": top_n}
            if counter_id is not None:
                args["counter_id"] = counter_id
            return await service_client.call_tool("get_performance_summary", args)
        record = _measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        resolved_cid = _resolve_timing_counter(counter_id, record)
        if resolved_cid is None:
            return {"error": "no_counter", "message": "No counter available. Specify counter_id."}
        desc = _find_counter_desc(resolved_cid, record.counter_descriptions)
        entries = [r for r in (record.results or []) if r.get("counter_id") == resolved_cid and r.get("value") is not None]
        entries.sort(key=lambda r: r.get("value", 0), reverse=True)
        top_n = max(1, min(int(top_n), 100))
        total_value = sum(r["value"] for r in entries if r.get("value") is not None)
        return {
            "measurement_id": measurement_id, "counter_id": resolved_cid,
            "counter_name": desc.get("name", ""), "unit": desc.get("unit", ""),
            "top_n": len(entries[:top_n]), "total_events_measured": len(entries),
            "total_value": total_value, "top_events": entries[:top_n],
        }

    @server.tool(
        name="get_render_pass_performance",
        description=(
            "Aggregate GPU counter results by render pass (debug marker hierarchy). "
            "measurement_id: ID from collect_gpu_counters. "
            "counter_id: optional counter to aggregate; defaults to the first timing counter. "
            "instance_id: optional RenderDoc session for event hierarchy lookup. "
            "Groups draw calls and dispatches under their parent debug marker regions. "
            "aggregated_duration is the SUM of measured leaf event values — it is not the "
            "GPU elapsed wall-clock time of the pass. "
            "Useful for comparing shadow pass vs G-buffer pass vs lighting pass costs."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_render_pass_performance(
        measurement_id: str,
        counter_id: int = None,
        instance_id: str = "",
    ) -> dict:
        """Aggregate measurement results by render pass hierarchy."""
        if service_client is not None:
            args = {"measurement_id": measurement_id, "instance_id": instance_id}
            if counter_id is not None:
                args["counter_id"] = counter_id
            return await service_client.call_tool("get_render_pass_performance", args)
        record = _measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        resolved_cid = _resolve_timing_counter(counter_id, record)
        if resolved_cid is None:
            return {"error": "no_counter", "message": "No counter available. Specify counter_id."}
        desc = _find_counter_desc(resolved_cid, record.counter_descriptions)
        value_map = {
            r["event_id"]: r["value"]
            for r in (record.results or [])
            if r.get("counter_id") == resolved_cid and r.get("value") is not None
        }
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return {"measurement_id": measurement_id, "warning": str(err.get("message", "")), "passes": []}
        events_result = await _conn_manager.request_capture_inspection(
            conn_id, "list_events", {"include_children": True, "limit": 10000}
        )
        if "error" in events_result:
            return {"measurement_id": measurement_id, "warning": events_result.get("message", ""), "passes": []}
        passes = _aggregate_passes(events_result.get("events", []), value_map)
        passes.sort(key=lambda p: p.get("aggregated_duration", 0), reverse=True)
        return {
            "measurement_id": measurement_id, "counter_id": resolved_cid,
            "counter_name": desc.get("name", ""), "unit": desc.get("unit", ""),
            "passes": passes, "pass_count": len(passes),
            "aggregation_note": (
                "aggregated_duration is the sum of leaf draw/dispatch event durations. "
                "It is not the GPU elapsed wall-clock time of the pass."
            ),
        }

    @server.tool(
        name="get_pipeline_statistics",
        description=(
            "Retrieve pipeline statistics counters from a completed measurement. "
            "measurement_id: ID from collect_gpu_counters. "
            "event_id: optional event ID to filter results to a single draw call. "
            "limit/offset: pagination (default limit=100). "
            "Filters for counters related to vertex invocations, primitive counts, "
            "rasterizer invocations, pixel/compute shader invocations, etc. "
            "Counter availability is hardware and API dependent. "
            "Does NOT re-run GPU collection."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_pipeline_statistics(
        measurement_id: str,
        event_id: int = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Retrieve pipeline statistics from stored measurement."""
        if service_client is not None:
            args = {"measurement_id": measurement_id, "limit": limit, "offset": offset}
            if event_id is not None:
                args["event_id"] = event_id
            return await service_client.call_tool("get_pipeline_statistics", args)
        record = _measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        _STATS_KW = (
            "vertices", "primitives", "invocations", "samples", "rasterizer",
            "vertex shader", "pixel shader", "fragment shader", "geometry shader",
            "hull shader", "domain shader", "compute shader", "tessellation", "input assembl",
        )
        stats_ids = {
            d["counter_id"] for d in record.counter_descriptions
            if any(kw in d.get("name", "").lower() for kw in _STATS_KW)
        }
        results = record.results or []
        if stats_ids:
            results = [r for r in results if r.get("counter_id") in stats_ids]
        if event_id is not None:
            results = [r for r in results if r.get("event_id") == event_id]
        total = len(results)
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        page = results[offset: offset + limit]
        name_map = {d["counter_id"]: d.get("name", "") for d in record.counter_descriptions}
        enriched = [{**r, "counter_name": name_map.get(r.get("counter_id"), "")} for r in page]
        return {
            "measurement_id": measurement_id, "total": total, "offset": offset,
            "limit": limit, "statistics": enriched, "stats_counter_ids": list(stats_ids),
        }

    # Phase 14: Geometry & mesh inspection

    @server.tool(
        name="get_draw_geometry_info",
        description=(
            "Return draw parameters and geometry configuration for the currently selected draw call. "
            "Reports topology, vertex/index counts, instance count, draw offsets (index_offset, "
            "base_vertex, instance_offset), vertex buffer bindings, and index buffer binding. "
            "event_id: optional — pass the expected EID to verify the correct event is selected; "
            "0 (default) uses whatever is currently selected. "
            "Returns error: not_a_draw if the selected event is not a draw call."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_draw_geometry_info(event_id: int = 0, instance_id: str = "") -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_draw_geometry_info", {"event_id": event_id, "instance_id": instance_id}
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "draw_geometry_info", {"event_id": event_id}
        )

    @server.tool(
        name="get_vertex_input_layout",
        description=(
            "Return vertex input attributes and buffer bindings for the currently selected pipeline state. "
            "Lists every declared vertex attribute with its semantic name, format (component type, count, "
            "byte width), buffer slot, byte offset within the vertex, and per-instance flag. "
            "Also returns bound vertex buffers (slot, resource_id, byte_offset, byte_stride) and the "
            "index buffer binding. Includes the vertex shader input signature for layout correlation. "
            "event_id: optional EID sanity check; 0 uses the currently selected event."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_vertex_input_layout(event_id: int = 0, instance_id: str = "") -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_vertex_input_layout", {"event_id": event_id, "instance_id": instance_id}
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "vertex_input_layout", {"event_id": event_id}
        )

    @server.tool(
        name="get_mesh_indices",
        description=(
            "Decode a bounded range of index values from the bound index buffer. "
            "Returns each index's position in the buffer, its raw stored value, and the effective "
            "vertex reference after applying base_vertex. "
            "first_index: first index to read (default 0). "
            "count: number of indices to read (default 100, max 1000). "
            "event_id: optional EID sanity check. "
            "Requires an indexed draw call with a bound index buffer."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_mesh_indices(
        event_id: int = 0,
        first_index: int = 0,
        count: int = 100,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_mesh_indices",
                {"event_id": event_id, "first_index": first_index,
                 "count": count, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "mesh_indices",
            {"event_id": event_id, "first_index": first_index, "count": count},
        )

    @server.tool(
        name="get_mesh_vertices",
        description=(
            "Decode vertex attributes for a bounded range of vertices from the bound vertex buffers. "
            "Returns per-vertex attribute values (position, normal, texcoord, etc.) decoded according "
            "to the pipeline's input layout. "
            "first_vertex: first vertex index to read (default 0). "
            "count: number of vertices to read (default 10, max 100). "
            "attributes: optional list of attribute semantic names to include (e.g. ['POSITION', 'NORMAL']); "
            "omit to include all per-vertex attributes. "
            "Per-instance attributes are excluded — use get_draw_geometry_info to see instance counts. "
            "event_id: optional EID sanity check."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_mesh_vertices(
        event_id: int = 0,
        first_vertex: int = 0,
        count: int = 10,
        attributes: list = None,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            args = {"event_id": event_id, "first_vertex": first_vertex,
                    "count": count, "instance_id": instance_id}
            if attributes:
                args["attributes"] = attributes
            return await service_client.call_tool("get_mesh_vertices", args)
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        params = {"event_id": event_id, "first_vertex": first_vertex, "count": count}
        if attributes:
            params["attributes"] = attributes
        return await _conn_manager.request_capture_inspection(conn_id, "mesh_vertices", params)

    @server.tool(
        name="get_post_vs_geometry",
        description=(
            "Retrieve post-vertex-shader geometry for the selected draw call. "
            "Calls GetPostVSData() which performs replay work — not read-only. "
            "Returns clip-space vertex positions (SV_Position) and NDC coordinates, plus other "
            "VS output attributes decoded from the vertex shader output signature. "
            "stage: 'vs_out' (default), 'vs_in', or 'gs_out'. "
            "instance: instance index (default 0). "
            "view: view index for multi-view rendering (default 0). "
            "max_vertices: maximum vertices to decode (default 50, max 100). "
            "Positions are clip-space (XYZW); SV_Position_ndc gives X/W, Y/W, Z/W. "
            "Returns error: no_post_vs_data when the draw does not support post-VS inspection."
        ),
        annotations={"readOnlyHint": False},
    )
    async def get_post_vs_geometry(
        event_id: int = 0,
        instance: int = 0,
        view: int = 0,
        stage: str = "vs_out",
        max_vertices: int = 50,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_post_vs_geometry",
                {"event_id": event_id, "instance": instance, "view": view,
                 "stage": stage, "max_vertices": max_vertices, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "post_vs_geometry",
            {"event_id": event_id, "instance": instance, "view": view,
             "stage": stage, "max_vertices": max_vertices},
        )

    @server.tool(
        name="get_mesh_statistics",
        description=(
            "Compute geometry statistics from a bounded vertex position sample for the selected draw call. "
            "Reports: axis-aligned bounding box (object-space, from vertex buffer input), "
            "NaN and infinity component counts, valid vertex count, and whether results are complete "
            "or from a sample. "
            "max_vertices: maximum vertices to analyze (default 200, max 500). "
            "The bounding box reflects vertex buffer data before vertex transformation. "
            "Use get_post_vs_geometry for clip-space bounds. "
            "event_id: optional EID sanity check."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_mesh_statistics(
        event_id: int = 0,
        max_vertices: int = 200,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_mesh_statistics",
                {"event_id": event_id, "max_vertices": max_vertices, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "mesh_statistics",
            {"event_id": event_id, "max_vertices": max_vertices},
        )

    @server.tool(
        name="get_pixel_history",
        description=(
            "Retrieve the modification history of a pixel in a texture across the current frame. "
            "Shows which draw calls modified the pixel, their fragment results, depth/stencil test outcomes, "
            "and pre/post pixel values. Uses RenderDoc PixelHistory replay — not read-only. "
            "resource_id: ResourceId of the target texture. "
            "x, y: pixel coordinates. "
            "mip: mip level (default 0). slice: array slice (default 0). sample: MSAA sample (default 0). "
            "max_modifications: maximum modifications to return (default 50, max 200). "
            "Returns error: pixel_history_failed if the API or texture format is unsupported."
        ),
        annotations={"readOnlyHint": False},
    )
    async def get_pixel_history(
        resource_id: str = "",
        x: int = 0,
        y: int = 0,
        mip: int = 0,
        slice: int = 0,
        sample: int = 0,
        max_modifications: int = 50,
        event_id: int = 0,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_pixel_history",
                {"resource_id": resource_id, "x": x, "y": y, "mip": mip,
                 "slice": slice, "sample": sample, "max_modifications": max_modifications,
                 "event_id": event_id, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        return await _conn_manager.request_capture_inspection(
            conn_id, "pixel_history",
            {"resource_id": resource_id, "x": x, "y": y, "mip": mip,
             "slice": slice, "sample": sample, "max_modifications": max_modifications,
             "event_id": event_id},
        )

    @server.tool(
        name="debug_pixel_shader",
        description=(
            "Collect a bounded pixel shader debug trace for a given pixel coordinate. "
            "Executes RenderDoc DebugPixel replay — not read-only and has GPU/CPU cost. "
            "Returns a debug_id for subsequent inspection with get_shader_debug_trace and "
            "get_shader_debug_variables. "
            "x, y: pixel to debug. event_id: draw event (0 = current selection). "
            "sample: MSAA sample index. primitive: fragment primitive ID (-1 = auto-select). "
            "max_steps: maximum trace steps to collect (default 200, max 500). "
            "Returns error: debug_pixel_unsupported if the API or shader is not debuggable."
        ),
        annotations={"readOnlyHint": False},
    )
    async def debug_pixel_shader(
        x: int = 0,
        y: int = 0,
        event_id: int = 0,
        sample: int = 0,
        primitive: int = -1,
        view: int = 0,
        max_steps: int = 200,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "debug_pixel_shader",
                {"x": x, "y": y, "event_id": event_id, "sample": sample,
                 "primitive": primitive, "view": view, "max_steps": max_steps,
                 "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        raw = await _conn_manager.request_capture_inspection(
            conn_id, "debug_pixel",
            {"x": x, "y": y, "event_id": event_id, "sample": sample,
             "primitive": primitive, "view": view, "max_steps": max_steps},
        )
        if "error" in raw:
            return raw
        import uuid as _uuid
        debug_id = "dbg_" + _uuid.uuid4().hex[:8]
        if _debug_store is not None:
            from rendereye_mcp.service.debug_store import DebugRecord
            record = DebugRecord(
                debug_id=debug_id,
                status="ready",
                stage=raw.get("stage", "pixel"),
                event_id=raw.get("event_id", event_id),
                capture_path=raw.get("_capture_path"),
                instance_id=conn_id,
                steps=raw.get("steps", []),
                initial_vars=raw.get("initial_vars", {}),
                metadata={"x": x, "y": y, "sample": sample, "primitive": primitive, "view": view,
                          "step_count": raw.get("step_count", 0), "truncated": raw.get("truncated", False)},
            )
            _debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": raw.get("stage", "pixel"),
            "event_id": raw.get("event_id", event_id),
            "step_count": raw.get("step_count", 0),
            "truncated": raw.get("truncated", False),
        }

    @server.tool(
        name="debug_vertex_shader",
        description=(
            "Collect a bounded vertex shader debug trace for a specific vertex invocation. "
            "Executes RenderDoc DebugVertex replay — not read-only. "
            "Returns a debug_id for inspection with get_shader_debug_trace. "
            "vert_id: vertex ID to debug. inst_id: instance ID. "
            "idx: for indexed draws, the index value. view: multi-view index. "
            "event_id: draw event (0 = current). max_steps: trace step limit (default 200, max 500). "
            "Returns error: debug_vertex_unsupported if the API or shader is not debuggable."
        ),
        annotations={"readOnlyHint": False},
    )
    async def debug_vertex_shader(
        vert_id: int = 0,
        inst_id: int = 0,
        idx: int = 0,
        view: int = 0,
        event_id: int = 0,
        max_steps: int = 200,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "debug_vertex_shader",
                {"vert_id": vert_id, "inst_id": inst_id, "idx": idx, "view": view,
                 "event_id": event_id, "max_steps": max_steps, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        raw = await _conn_manager.request_capture_inspection(
            conn_id, "debug_vertex",
            {"vert_id": vert_id, "inst_id": inst_id, "idx": idx, "view": view,
             "event_id": event_id, "max_steps": max_steps},
        )
        if "error" in raw:
            return raw
        import uuid as _uuid
        debug_id = "dbg_" + _uuid.uuid4().hex[:8]
        if _debug_store is not None:
            from rendereye_mcp.service.debug_store import DebugRecord
            record = DebugRecord(
                debug_id=debug_id,
                status="ready",
                stage=raw.get("stage", "vertex"),
                event_id=raw.get("event_id", event_id),
                capture_path=raw.get("_capture_path"),
                instance_id=conn_id,
                steps=raw.get("steps", []),
                initial_vars=raw.get("initial_vars", {}),
                metadata={"vert_id": vert_id, "inst_id": inst_id, "idx": idx, "view": view,
                          "step_count": raw.get("step_count", 0), "truncated": raw.get("truncated", False)},
            )
            _debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": raw.get("stage", "vertex"),
            "event_id": raw.get("event_id", event_id),
            "step_count": raw.get("step_count", 0),
            "truncated": raw.get("truncated", False),
        }

    @server.tool(
        name="debug_compute_shader",
        description=(
            "Collect a bounded compute shader debug trace for a specific thread invocation. "
            "Executes RenderDoc DebugThread replay — not read-only. "
            "Returns a debug_id for inspection with get_shader_debug_trace. "
            "group_x/y/z: workgroup indices. thread_x/y/z: thread within the workgroup. "
            "event_id: dispatch event (0 = current). max_steps: trace step limit (default 200, max 500). "
            "Note: only the targeted thread is debugged; cross-thread behavior is not observable. "
            "Returns error: debug_compute_unsupported if the API does not support compute debugging."
        ),
        annotations={"readOnlyHint": False},
    )
    async def debug_compute_shader(
        group_x: int = 0,
        group_y: int = 0,
        group_z: int = 0,
        thread_x: int = 0,
        thread_y: int = 0,
        thread_z: int = 0,
        event_id: int = 0,
        max_steps: int = 200,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "debug_compute_shader",
                {"group_x": group_x, "group_y": group_y, "group_z": group_z,
                 "thread_x": thread_x, "thread_y": thread_y, "thread_z": thread_z,
                 "event_id": event_id, "max_steps": max_steps, "instance_id": instance_id},
            )
        conn_id, err = _resolve_conn_standalone(instance_id)
        if err is not None:
            return err
        raw = await _conn_manager.request_capture_inspection(
            conn_id, "debug_compute",
            {"group_x": group_x, "group_y": group_y, "group_z": group_z,
             "thread_x": thread_x, "thread_y": thread_y, "thread_z": thread_z,
             "event_id": event_id, "max_steps": max_steps},
        )
        if "error" in raw:
            return raw
        import uuid as _uuid
        debug_id = "dbg_" + _uuid.uuid4().hex[:8]
        if _debug_store is not None:
            from rendereye_mcp.service.debug_store import DebugRecord
            record = DebugRecord(
                debug_id=debug_id,
                status="ready",
                stage=raw.get("stage", "compute"),
                event_id=raw.get("event_id", event_id),
                capture_path=raw.get("_capture_path"),
                instance_id=conn_id,
                steps=raw.get("steps", []),
                initial_vars=raw.get("initial_vars", {}),
                metadata={"group": [group_x, group_y, group_z], "thread": [thread_x, thread_y, thread_z],
                          "step_count": raw.get("step_count", 0), "truncated": raw.get("truncated", False)},
            )
            _debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": raw.get("stage", "compute"),
            "event_id": raw.get("event_id", event_id),
            "step_count": raw.get("step_count", 0),
            "truncated": raw.get("truncated", False),
        }

    @server.tool(
        name="get_shader_debug_trace",
        description=(
            "Retrieve bounded steps from a stored shader debug trace. "
            "Read-only — reads from the debug store populated by debug_pixel_shader, "
            "debug_vertex_shader, or debug_compute_shader. "
            "debug_id: the ID returned by a debug tool. "
            "first_step: starting step index (default 0). "
            "count: number of steps to return (default 50, max 500). "
            "Each step includes instruction index, variable changes (name + before/after values), "
            "and flags such as generated_nan_or_inf. "
            "Use get_shader_debug_variables to reconstruct the full variable state at a step."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_debug_trace(
        debug_id: str = "",
        first_step: int = 0,
        count: int = 50,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_debug_trace",
                {"debug_id": debug_id, "first_step": first_step, "count": count,
                 "instance_id": instance_id},
            )
        if _debug_store is None:
            return {"error": "debug_store_unavailable"}
        record = _debug_store.get(debug_id)
        if record is None:
            return {"error": "debug_id_not_found", "debug_id": debug_id}
        if record.status != "ready":
            return {"error": "debug_not_ready", "debug_id": debug_id, "status": record.status}
        count = min(max(1, count), 500)
        first_step = max(0, first_step)
        steps = record.steps[first_step: first_step + count]
        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "first_step": first_step,
            "returned_steps": len(steps),
            "total_steps": len(record.steps),
            "has_more": first_step + count < len(record.steps),
            "steps": steps,
        }

    @server.tool(
        name="get_shader_debug_variables",
        description=(
            "Inspect variable state at a specific step of a stored shader debug trace. "
            "Read-only — reconstructs variable values by applying all change deltas from the initial "
            "state up to and including the requested step. "
            "debug_id: the ID returned by a debug tool. "
            "step: the step index to inspect (0-based, default 0). "
            "variable_names: optional list of variable names to filter; null returns all. "
            "Returns the reconstructed variable state at the requested step."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_debug_variables(
        debug_id: str = "",
        step: int = 0,
        variable_names: Optional[List[str]] = None,
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_debug_variables",
                {"debug_id": debug_id, "step": step, "variable_names": variable_names,
                 "instance_id": instance_id},
            )
        if _debug_store is None:
            return {"error": "debug_store_unavailable"}
        record = _debug_store.get(debug_id)
        if record is None:
            return {"error": "debug_id_not_found", "debug_id": debug_id}
        if record.status != "ready":
            return {"error": "debug_not_ready", "debug_id": debug_id, "status": record.status}
        total = len(record.steps)
        if total == 0:
            return {
                "debug_id": debug_id,
                "step": step,
                "variables": record.initial_vars,
                "note": "no trace steps; showing initial state",
            }
        step = max(0, min(step, total - 1))
        var_state: dict = dict(record.initial_vars)
        for i in range(step + 1):
            for ch in record.steps[i].get("changes", []):
                after = ch.get("after", {})
                name = after.get("name", "")
                if name:
                    var_state[name] = after
        if variable_names:
            var_state = {k: v for k, v in var_state.items() if k in variable_names}
        items = list(var_state.items())[:50]
        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "step": step,
            "total_steps": total,
            "variables": dict(items),
        }

    @server.tool(
        name="get_shader_debug_status",
        description=(
            "Check the status of a shader debug trace stored in the debug store. "
            "Read-only — no replay required. "
            "debug_id: the ID to query; omit to list all stored debug IDs. "
            "Returns status (ready/failed/invalidated), stage, event_id, step_count, and metadata."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_shader_debug_status(
        debug_id: str = "",
        instance_id: str = "",
    ) -> dict:
        if service_client is not None:
            return await service_client.call_tool(
                "get_shader_debug_status",
                {"debug_id": debug_id, "instance_id": instance_id},
            )
        if _debug_store is None:
            return {"error": "debug_store_unavailable"}
        if not debug_id:
            ids = _debug_store.list_ids()
            return {"debug_ids": ids, "count": len(ids)}
        record = _debug_store.get(debug_id)
        if record is None:
            return {"error": "debug_id_not_found", "debug_id": debug_id}
        result = {
            "debug_id": debug_id,
            "status": record.status,
            "stage": record.stage,
            "event_id": record.event_id,
            "step_count": len(record.steps),
        }
        result.update(record.metadata)
        if record.error:
            result["error_detail"] = record.error
        return result

    logger.info("RenderEyeMCP server created (MCP SDK 2.x, MCPServer)")
    instance_id = uuid.uuid4().hex[:8]

    logger.info(
        "RenderEyeMCP starting: pid=%s instance=%s",
        os.getpid(),
        instance_id,
    )
    return server


def get_ipc_transport() -> Optional["IPCTransport"]:
    """Return the module-level IPC transport. Called from __main__.py."""
    return _ipc_transport


def set_registry(registry: "CaptureRegistry") -> None:
    """Set the module-level registry reference. Called from __main__.py."""
    global _registry
    _registry = registry


def set_session_manager(mgr: Optional["SessionManager"]) -> None:
    """Set the module-level session manager reference. Called from __main__.py."""
    global _session_manager
    _session_manager = mgr


def set_conn_manager(mgr: Optional["ExtensionConnectionManager"]) -> None:
    """Set the module-level extension connection manager reference."""
    global _conn_manager
    _conn_manager = mgr
    # Also wire the conn_manager into the IPC transport if it exists
    if _ipc_transport is not None and mgr is not None:
        _ipc_transport.set_conn_manager(mgr)
