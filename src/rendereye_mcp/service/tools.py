"""Tool executor for the shared IPC service.

Mirrors the MCP tools registered in server.py but takes explicit manager
references rather than relying on module-level globals.
"""

from __future__ import annotations

import logging
import platform
import sys
import time
from typing import TYPE_CHECKING, List, Optional

from rendereye_mcp import __version__
from rendereye_mcp.service.debug_store import DebugRecord, DebugStore
from rendereye_mcp.service.measurement_store import MeasurementRecord, MeasurementStore

if TYPE_CHECKING:
    from rendereye_mcp.captures.registry import CaptureRegistry
    from rendereye_mcp.config import Config
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager
    from rendereye_mcp.ipc.transport import IPCTransport
    from rendereye_mcp.operations.tracker import OperationTracker
    from rendereye_mcp.sessions.manager import SessionManager

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes MCP tool calls on behalf of bridge clients."""

    def __init__(
        self,
        config: "Config",
        registry: Optional["CaptureRegistry"],
        session_manager: Optional["SessionManager"],
        conn_manager: Optional["ExtensionConnectionManager"],
        operation_tracker: Optional["OperationTracker"],
        ipc_transport: Optional["IPCTransport"] = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._session_manager = session_manager
        self._conn_manager = conn_manager
        self._operation_tracker = operation_tracker
        self._ipc_transport = ipc_transport
        self._measurement_store = MeasurementStore()
        self._debug_store = DebugStore()

        self._dispatch = {
            "server_status": self._server_status,
            "capture_list": self._capture_list,
            "capture_get": self._capture_get,
            "capture_latest": self._capture_latest,
            "capture_rescan": self._capture_rescan,
            "capture_registry_status": self._capture_registry_status,
            "instance_list": self._instance_list,
            "instance_gui_state": self._instance_gui_state,
            "capture_open": self._capture_open,
            "operation_get": self._operation_get,
            "session_list": self._session_list,
            "session_get": self._session_get,
            "session_focus": self._session_focus,
            "session_close": self._session_close,
            "session_protect": self._session_protect,
            # Phase 7: GUI state discovery
            "list_renderdoc_sessions": self._list_renderdoc_sessions,
            "get_renderdoc_session_state": self._get_renderdoc_session_state,
            "get_current_capture": self._get_current_capture,
            # Phase 8: Active capture inspection
            "get_current_capture_info": self._get_current_capture_info,
            "list_capture_events": self._list_capture_events,
            "get_capture_event": self._get_capture_event,
            "get_selected_event": self._get_selected_event,
            "get_pipeline_state": self._get_pipeline_state,
            # Phase 9: GPU resource metadata & buffer inspection
            "list_resources": self._list_resources,
            "get_resource_info": self._get_resource_info,
            "get_texture_info": self._get_texture_info,
            "get_buffer_info": self._get_buffer_info,
            "read_buffer_data": self._read_buffer_data,
            # Phase 10: Shader inspection & reflection
            "list_shaders": self._list_shaders,
            "get_shader_info": self._get_shader_info,
            "get_shader_reflection": self._get_shader_reflection,
            "get_shader_bindings": self._get_shader_bindings,
            "get_shader_disassembly": self._get_shader_disassembly,
            "get_shader_debug_info": self._get_shader_debug_info,
            # Phase 11: Render target & pixel inspection
            "get_render_targets": self._get_render_targets,
            "get_texture_image": self._get_texture_image,
            "get_pixel_value": self._get_pixel_value,
            "get_texture_statistics": self._get_texture_statistics,
            # Phase 13: GPU performance analysis
            "list_gpu_counters": self._list_gpu_counters,
            "collect_gpu_counters": self._collect_gpu_counters,
            "get_gpu_measurement_status": self._get_gpu_measurement_status,
            "get_gpu_timings": self._get_gpu_timings,
            "get_performance_summary": self._get_performance_summary,
            "get_render_pass_performance": self._get_render_pass_performance,
            "get_pipeline_statistics": self._get_pipeline_statistics,
            # Phase 14: Geometry & mesh inspection
            "get_draw_geometry_info": self._get_draw_geometry_info,
            "get_vertex_input_layout": self._get_vertex_input_layout,
            "get_mesh_indices": self._get_mesh_indices,
            "get_mesh_vertices": self._get_mesh_vertices,
            "get_post_vs_geometry": self._get_post_vs_geometry,
            "get_mesh_statistics": self._get_mesh_statistics,
            # Phase 15: Pixel History & Shader Debugging
            "get_pixel_history": self._get_pixel_history,
            "debug_pixel_shader": self._debug_pixel_shader,
            "debug_vertex_shader": self._debug_vertex_shader,
            "debug_compute_shader": self._debug_compute_shader,
            "get_shader_debug_trace": self._get_shader_debug_trace,
            "get_shader_debug_variables": self._get_shader_debug_variables,
            "get_shader_debug_status": self._get_shader_debug_status,
        }

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Dispatch a tool call by name and return its result."""
        handler = self._dispatch.get(tool_name)
        if handler is None:
            return {"error": "unknown_tool", "tool_name": tool_name}
        try:
            return await handler(**arguments)
        except TypeError as exc:
            # Argument mismatch
            return {"error": "invalid_arguments", "message": str(exc)}
        except Exception as exc:
            logger.exception("[SERVICE] Tool execution error tool=%s: %s", tool_name, exc)
            return {"error": "execution_error", "message": str(exc)}

    # ------------------------------------------------------------------
    # Tool implementations (mirrors server.py, uses self._ references)
    # ------------------------------------------------------------------

    async def _server_status(self) -> dict:
        from rendereye_mcp.platform.windows import find_renderdoc_exe

        rdoc_path = find_renderdoc_exe(self._config)
        rdoc_detected = rdoc_path is not None

        ipc_running = self._ipc_transport is not None and self._ipc_transport.is_running
        ext_connections = (
            self._ipc_transport.connection_count if self._ipc_transport is not None else 0
        )

        active_sessions = 0
        if self._session_manager is not None:
            try:
                active_sessions = self._session_manager.get_active_session_count()
            except Exception:
                pass

        active_ext_connections = 0
        if self._conn_manager is not None:
            try:
                active_ext_connections = self._conn_manager.active_count()
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

    async def _capture_list(
        self,
        status: str = "",
        directory: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        from rendereye_mcp.captures.models import CaptureStatus

        if self._registry is None:
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

        records, total = self._registry.list_captures(
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

    async def _capture_get(self, capture_id: str) -> dict:
        if self._registry is None:
            return {"error": "not_found", "capture_id": capture_id}
        record = self._registry.get_capture(capture_id)
        if record is None:
            return {"error": "not_found", "capture_id": capture_id}
        return record.to_dict()

    async def _capture_latest(
        self,
        directory: str = "",
        include_pending: bool = False,
    ) -> dict:
        from rendereye_mcp.captures.models import CaptureStatus

        if self._registry is None:
            return {"error": "no_capture_available"}

        record = self._registry.get_latest_capture(
            directory=directory if directory else None
        )

        if record is None and include_pending:
            records, _ = self._registry.list_captures(
                status=CaptureStatus.PENDING,
                directory=directory if directory else None,
                limit=1,
            )
            record = records[0] if records else None

        if record is None:
            return {"error": "no_capture_available"}
        return record.to_dict()

    async def _capture_rescan(self) -> dict:
        if self._registry is None:
            return {"status": "unavailable", "message": "Registry not initialized"}
        result = await self._registry.rescan()
        return {
            "status": "completed",
            "scanned": result.get("scanned", 0),
            "new": result.get("new", 0),
            "updated": result.get("updated", 0),
        }

    async def _capture_registry_status(self) -> dict:
        if self._registry is None:
            return {"enabled": False, "running": False, "message": "Registry not initialized"}
        return self._registry.get_status()

    async def _instance_list(self) -> dict:
        if self._session_manager is None:
            return {"instances": [], "windows": []}
        self._session_manager._instances.refresh()
        instances = self._session_manager._instances.list_instances()
        windows = self._session_manager._instances.list_windows()
        inst_dicts = []
        for inst in instances:
            inst_dict = inst.to_dict()
            if self._conn_manager is not None:
                ext_conn = self._conn_manager.get_connection_for_instance(inst.instance_id)
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

    async def _instance_gui_state(self, instance_id: str) -> dict:
        if self._conn_manager is None:
            return {"error": "conn_manager_unavailable"}
        conn = self._conn_manager.get_connection_for_instance(instance_id)
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

    async def _capture_open(
        self,
        capture_id: str = "latest",
        open_mode: str = "new_window",
        target_session_id: str = "",
    ) -> dict:
        from rendereye_mcp.errors import ErrorCode, error_response

        if self._session_manager is None:
            return error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "Session manager not initialized",
            )
        return await self._session_manager.open_capture(
            capture_id=capture_id,
            open_mode=open_mode,
            target_session_id=target_session_id if target_session_id else None,
            operation_tracker=self._operation_tracker,
        )

    async def _operation_get(self, operation_id: str) -> dict:
        from rendereye_mcp.errors import ErrorCode, error_response

        if self._operation_tracker is None:
            return error_response(
                ErrorCode.INTERNAL_ERROR,
                "Operation tracker not initialized",
                operation_id=operation_id,
            )
        op = self._operation_tracker.get(operation_id)
        if op is None:
            return error_response(
                ErrorCode.OPERATION_UNSUPPORTED,
                f"Operation not found: {operation_id}",
                operation_id=operation_id,
            )
        return op.to_dict()

    async def _session_list(
        self,
        status: str = "",
        managed_only: bool = False,
        capture_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if self._session_manager is None:
            return {"sessions": [], "total": 0, "limit": limit, "offset": offset}
        return self._session_manager.list_sessions(
            status=status if status else None,
            managed_only=managed_only,
            capture_id=capture_id if capture_id else None,
            limit=limit,
            offset=offset,
        )

    async def _session_get(self, session_id: str) -> dict:
        if self._session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        record = self._session_manager.get_session(session_id)
        if record is None:
            return {"error": "not_found", "session_id": session_id}
        return record.to_dict()

    async def _session_focus(self, session_id: str) -> dict:
        if self._session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        return self._session_manager.focus_session(session_id)

    async def _session_close(self, session_id: str) -> dict:
        from rendereye_mcp.errors import ErrorCode, error_response

        if self._session_manager is None:
            return error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "Session manager not initialized",
                session_id=session_id,
            )
        return self._session_manager.close_session(session_id)

    async def _session_protect(self, session_id: str, protected: bool) -> dict:
        if self._session_manager is None:
            return {"error": "session_manager_unavailable", "session_id": session_id}
        return self._session_manager.protect_session(session_id, protected)

    # ------------------------------------------------------------------
    # Phase 7: GUI state discovery tools
    # ------------------------------------------------------------------

    async def _list_renderdoc_sessions(self) -> dict:
        if self._conn_manager is None:
            return {"sessions": [], "total": 0}
        connections = self._conn_manager.list_connections()
        sessions = [c.to_gui_session_dict() for c in connections]
        return {"sessions": sessions, "total": len(sessions)}

    async def _get_renderdoc_session_state(self, instance_id: str) -> dict:
        if self._conn_manager is None:
            return {
                "error": "conn_manager_unavailable",
                "instance_id": instance_id,
            }
        conn = self._conn_manager.get_any_connection_for_instance(instance_id)
        if conn is None:
            return {
                "error": "session_not_found",
                "instance_id": instance_id,
                "message": f"No RenderDoc GUI session found with instance_id={instance_id!r}",
            }
        return conn.to_gui_session_dict()

    async def _get_current_capture(self, instance_id: str = "") -> dict:
        if self._conn_manager is None:
            return {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }

        if instance_id:
            conn = self._conn_manager.get_any_connection_for_instance(instance_id)
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
        all_conns = self._conn_manager.list_connections()
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

        # Multiple loaded captures — require explicit instance_id
        return {
            "status": "ambiguous",
            "message": (
                f"Multiple RenderDoc GUI sessions have a capture loaded ({len(loaded)}). "
                "Specify instance_id to target a specific session."
            ),
            "sessions": [c.to_gui_session_dict() for c in loaded],
        }

    # ------------------------------------------------------------------
    # Phase 8: Active capture inspection tools
    # ------------------------------------------------------------------

    async def _resolve_inspection_connection(self, instance_id: str = "") -> tuple:
        """Resolve the extension connection to inspect.

        Returns (connection_id, error_dict_or_None).
        error_dict_or_None is None on success, or a dict with 'error' key on failure.
        """
        if self._conn_manager is None:
            return None, {
                "status": "no_renderdoc_connected",
                "message": "Extension connection manager unavailable",
            }

        if instance_id:
            conn = self._conn_manager.get_any_connection_for_instance(instance_id)
            if conn is None:
                return None, {
                    "status": "session_not_found",
                    "instance_id": instance_id,
                    "message": f"No RenderDoc GUI session found with instance_id={instance_id!r}",
                }
            if not conn.connected:
                return None, {
                    "status": "session_disconnected",
                    "instance_id": instance_id,
                    "connection_state": conn.connection_state,
                    "message": "The specified RenderDoc GUI session is not currently connected",
                }
            return conn.connection_id, None

        all_conns = self._conn_manager.list_connections()
        connected = [c for c in all_conns if c.connected]
        if not connected:
            return None, {
                "status": "no_renderdoc_connected",
                "message": "No RenderDoc GUI instances are currently connected",
            }
        if len(connected) == 1:
            return connected[0].connection_id, None

        # Multiple connected: prefer one with a loaded capture
        loaded = [c for c in connected if c.capture_loaded]
        if len(loaded) == 1:
            return loaded[0].connection_id, None
        if len(loaded) > 1:
            return None, {
                "status": "ambiguous",
                "message": (
                    f"Multiple RenderDoc GUI sessions are connected ({len(loaded)} with loaded captures). "
                    "Specify instance_id to target a specific session."
                ),
                "sessions": [c.to_gui_session_dict() for c in loaded],
            }

        return None, {
            "status": "ambiguous",
            "message": (
                f"Multiple RenderDoc GUI sessions are connected ({len(connected)}). "
                "Specify instance_id to target a specific session."
            ),
            "sessions": [c.to_gui_session_dict() for c in connected],
        }

    async def _get_current_capture_info(self, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "capture_info", {}
        )

    async def _list_capture_events(
        self,
        instance_id: str = "",
        limit: int = 50,
        offset: int = 0,
        include_markers: bool = True,
        flags_filter: str = "",
        parent_event_id: int = 0,
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "list_events",
            {
                "limit": limit,
                "offset": offset,
                "include_markers": include_markers,
                "flags_filter": flags_filter,
                "parent_event_id": parent_event_id,
            },
        )

    async def _get_capture_event(self, event_id: int, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_event", {"event_id": event_id}
        )

    async def _get_selected_event(self, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "selected_event", {}
        )

    async def _get_pipeline_state(
        self,
        instance_id: str = "",
        event_id: int = 0,
        section: str = "summary",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "pipeline_state",
            {"event_id": event_id, "section": section},
        )

    # ------------------------------------------------------------------
    # Phase 9: GPU resource metadata & buffer inspection
    # ------------------------------------------------------------------

    async def _list_resources(
        self,
        instance_id: str = "",
        resource_type: str = "all",
        name_filter: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "list_resources",
            {
                "resource_type": resource_type,
                "name_filter": name_filter,
                "limit": limit,
                "offset": offset,
            },
        )

    async def _get_resource_info(self, resource_id: str, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_resource_info", {"resource_id": resource_id}
        )

    async def _get_texture_info(self, resource_id: str, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_texture_info", {"resource_id": resource_id}
        )

    async def _get_buffer_info(self, resource_id: str, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_buffer_info", {"resource_id": resource_id}
        )

    async def _read_buffer_data(
        self,
        resource_id: str,
        offset: int = 0,
        length: int = 256,
        output_format: str = "hex",
        decode_layout: Optional[dict] = None,
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        params: dict = {
            "resource_id": resource_id,
            "offset": offset,
            "length": length,
            "output_format": output_format,
        }
        if decode_layout is not None:
            params["decode_layout"] = decode_layout
        return await self._conn_manager.request_capture_inspection(
            connection_id, "read_buffer_data", params
        )

    # ------------------------------------------------------------------
    # Phase 10: Shader inspection & reflection
    # ------------------------------------------------------------------

    async def _list_shaders(self, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "list_shaders", {}
        )

    async def _get_shader_info(self, stage: str, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_shader_info", {"stage": stage}
        )

    async def _get_shader_reflection(
        self,
        stage: str,
        section: str = "all",
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "get_shader_reflection",
            {"stage": stage, "section": section},
        )

    async def _get_shader_bindings(self, stage: str, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_shader_bindings", {"stage": stage}
        )

    async def _get_shader_disassembly(
        self,
        stage: str,
        target: str = "",
        offset: int = 0,
        limit: int = 200,
        search: str = "",
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "get_shader_disassembly",
            {
                "stage": stage,
                "target": target,
                "offset": offset,
                "limit": limit,
                "search": search,
            },
        )

    async def _get_shader_debug_info(
        self,
        stage: str,
        file_index: int = 0,
        start_line: int = 0,
        max_lines: int = 100,
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "get_shader_debug_info",
            {
                "stage": stage,
                "file_index": file_index,
                "start_line": start_line,
                "max_lines": max_lines,
            },
        )

    # ------------------------------------------------------------------
    # Phase 11: Render target & pixel inspection
    # ------------------------------------------------------------------

    async def _get_render_targets(self, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_render_targets", {}
        )

    async def _get_texture_image(
        self,
        resource_id: str,
        mip: int = 0,
        array_slice: int = 0,
        max_dim: int = 1024,
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
            "get_texture_image",
            {
                "resource_id": resource_id,
                "mip": mip,
                "array_slice": array_slice,
                "max_dim": max_dim,
            },
        )

    async def _get_pixel_value(
        self,
        resource_id: str,
        x: int = 0,
        y: int = 0,
        mip: int = 0,
        array_slice: int = 0,
        sample: int = 0,
        coords: "Optional[list]" = None,
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        params: dict = {
            "resource_id": resource_id,
            "mip": mip,
            "array_slice": array_slice,
            "sample": sample,
        }
        if coords is not None:
            params["coords"] = coords
        else:
            params["x"] = x
            params["y"] = y
        return await self._conn_manager.request_capture_inspection(
            connection_id, "get_pixel_value", params
        )

    async def _get_texture_statistics(
        self,
        resource_id: str,
        mip: int = 0,
        array_slice: int = 0,
        include_histogram: bool = False,
        hist_min: float = 0.0,
        hist_max: float = 1.0,
        instance_id: str = "",
    ) -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id,
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

    # ------------------------------------------------------------------
    # Phase 13: GPU performance analysis
    # ------------------------------------------------------------------

    async def _list_gpu_counters(self, instance_id: str = "") -> dict:
        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            connection_id, "list_gpu_counters", {}
        )

    async def _collect_gpu_counters(
        self,
        counter_ids: List[int],
        instance_id: str = "",
        repeats: int = 1,
    ) -> dict:
        if not counter_ids:
            return {"error": "missing_counter_ids", "message": "counter_ids must be a non-empty list"}
        repeats = max(1, min(int(repeats), 5))

        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err

        capture_path = ""
        cap_info = await self._conn_manager.request_capture_inspection(
            connection_id, "capture_info", {}
        )
        if "error" not in cap_info:
            capture_path = cap_info.get("_capture_path", "") or ""

        all_run_results = []
        last_raw: dict = {}
        for _run in range(repeats):
            raw = await self._conn_manager.request_capture_inspection(
                connection_id, "fetch_gpu_counters", {"counter_ids": list(counter_ids)}
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
            for (event_id, counter_id), values in sums.items():
                if values:
                    if all(isinstance(v, int) for v in values):
                        avg: object = int(sum(values) // len(values))
                    else:
                        avg = sum(float(v) for v in values) / len(values)
                    results.append({"event_id": event_id, "counter_id": counter_id, "value": avg})

        measurement_id = self._measurement_store.make_id()
        record = MeasurementRecord(
            measurement_id=measurement_id,
            status="completed",
            capture_path=capture_path or None,
            instance_id=connection_id,
            counter_ids=counters_fetched,
            counter_descriptions=counter_descriptions,
            results=results,
            created_at=time.time(),
            metadata={
                "counters_invalid": counters_invalid,
                "repeats": repeats,
                "result_count": len(results),
            },
        )
        self._measurement_store.store(record)

        return {
            "measurement_id": measurement_id,
            "status": "completed",
            "capture_path": capture_path,
            "counters_fetched": counters_fetched,
            "counters_invalid": counters_invalid,
            "result_count": len(results),
            "repeats": repeats,
        }

    async def _get_gpu_measurement_status(self, measurement_id: str) -> dict:
        record = self._measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}
        return {
            "measurement_id": record.measurement_id,
            "status": record.status,
            "capture_path": record.capture_path,
            "counter_ids": record.counter_ids,
            "counter_descriptions": record.counter_descriptions,
            "result_count": len(record.results) if record.results else 0,
            "created_at": record.created_at,
            "metadata": record.metadata,
            "error": record.error,
        }

    async def _get_gpu_timings(
        self,
        measurement_id: str,
        counter_id: int = None,
        min_value: float = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "value_desc",
    ) -> dict:
        record = self._measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}

        resolved_counter_id = _resolve_timing_counter(counter_id, record)
        if resolved_counter_id is None:
            return {
                "error": "no_timing_counter",
                "message": "No timing counter found in measurement. Specify counter_id.",
            }

        entries = [
            r for r in (record.results or [])
            if r.get("counter_id") == resolved_counter_id
        ]
        if min_value is not None:
            entries = [r for r in entries if r.get("value") is not None and r["value"] >= min_value]

        entries = _sort_entries(entries, sort_by)
        total = len(entries)
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        page = entries[offset: offset + limit]

        counter_desc = _find_counter_desc(resolved_counter_id, record.counter_descriptions)
        return {
            "measurement_id": measurement_id,
            "counter_id": resolved_counter_id,
            "counter_name": counter_desc.get("name", ""),
            "unit": counter_desc.get("unit", ""),
            "total": total,
            "offset": offset,
            "limit": limit,
            "events": page,
        }

    async def _get_performance_summary(
        self,
        measurement_id: str,
        counter_id: int = None,
        top_n: int = 20,
    ) -> dict:
        record = self._measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}

        resolved_counter_id = _resolve_timing_counter(counter_id, record)
        if resolved_counter_id is None:
            return {"error": "no_counter", "message": "No counter available. Specify counter_id."}

        counter_desc = _find_counter_desc(resolved_counter_id, record.counter_descriptions)
        entries = [
            r for r in (record.results or [])
            if r.get("counter_id") == resolved_counter_id and r.get("value") is not None
        ]
        entries.sort(key=lambda r: r.get("value", 0), reverse=True)

        top_n = max(1, min(int(top_n), 100))
        top = entries[:top_n]
        total_value = sum(r["value"] for r in entries if r.get("value") is not None)

        return {
            "measurement_id": measurement_id,
            "counter_id": resolved_counter_id,
            "counter_name": counter_desc.get("name", ""),
            "unit": counter_desc.get("unit", ""),
            "top_n": len(top),
            "total_events_measured": len(entries),
            "total_value": total_value,
            "top_events": top,
        }

    async def _get_render_pass_performance(
        self,
        measurement_id: str,
        counter_id: int = None,
        instance_id: str = "",
    ) -> dict:
        record = self._measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}

        resolved_counter_id = _resolve_timing_counter(counter_id, record)
        if resolved_counter_id is None:
            return {"error": "no_counter", "message": "No counter available. Specify counter_id."}

        counter_desc = _find_counter_desc(resolved_counter_id, record.counter_descriptions)

        value_map = {
            r["event_id"]: r["value"]
            for r in (record.results or [])
            if r.get("counter_id") == resolved_counter_id and r.get("value") is not None
        }

        connection_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return {
                "measurement_id": measurement_id,
                "warning": "Could not connect to RenderDoc for event hierarchy: " + str(err.get("message", "")),
                "passes": [],
            }

        events_result = await self._conn_manager.request_capture_inspection(
            connection_id, "list_events", {"include_children": True, "limit": 10000}
        )
        if "error" in events_result:
            return {
                "measurement_id": measurement_id,
                "warning": "Could not retrieve event hierarchy: " + events_result.get("message", ""),
                "passes": [],
            }

        passes = _aggregate_passes(events_result.get("events", []), value_map)
        passes.sort(key=lambda p: p.get("aggregated_duration", 0), reverse=True)

        return {
            "measurement_id": measurement_id,
            "counter_id": resolved_counter_id,
            "counter_name": counter_desc.get("name", ""),
            "unit": counter_desc.get("unit", ""),
            "passes": passes,
            "pass_count": len(passes),
            "aggregation_note": (
                "aggregated_duration is the sum of leaf draw/dispatch event durations. "
                "It is not the GPU elapsed wall-clock time of the pass."
            ),
        }

    async def _get_pipeline_statistics(
        self,
        measurement_id: str,
        event_id: int = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        record = self._measurement_store.get(measurement_id)
        if record is None:
            return {"error": "measurement_not_found", "measurement_id": measurement_id}

        _STATS_KEYWORDS = (
            "vertices", "primitives", "invocations", "samples", "rasterizer",
            "vertex shader", "pixel shader", "fragment shader", "geometry shader",
            "hull shader", "domain shader", "compute shader", "tessellation",
            "input assembl",
        )
        stats_counter_ids = {
            d["counter_id"]
            for d in record.counter_descriptions
            if any(kw in d.get("name", "").lower() for kw in _STATS_KEYWORDS)
        }

        results = record.results or []
        if stats_counter_ids:
            results = [r for r in results if r.get("counter_id") in stats_counter_ids]
        if event_id is not None:
            results = [r for r in results if r.get("event_id") == event_id]

        total = len(results)
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        page = results[offset: offset + limit]

        name_map = {d["counter_id"]: d.get("name", "") for d in record.counter_descriptions}
        enriched = [{**r, "counter_name": name_map.get(r.get("counter_id"), "")} for r in page]

        return {
            "measurement_id": measurement_id,
            "total": total,
            "offset": offset,
            "limit": limit,
            "statistics": enriched,
            "stats_counter_ids": list(stats_counter_ids),
        }


    # ------------------------------------------------------------------
    # Phase 14: Geometry & mesh inspection
    # ------------------------------------------------------------------

    async def _get_draw_geometry_info(self, event_id: int = 0, instance_id: str = "") -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "draw_geometry_info", {"event_id": event_id}
        )

    async def _get_vertex_input_layout(self, event_id: int = 0, instance_id: str = "") -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "vertex_input_layout", {"event_id": event_id}
        )

    async def _get_mesh_indices(
        self,
        event_id: int = 0,
        first_index: int = 0,
        count: int = 100,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "mesh_indices",
            {"event_id": event_id, "first_index": first_index, "count": count},
        )

    async def _get_mesh_vertices(
        self,
        event_id: int = 0,
        first_vertex: int = 0,
        count: int = 10,
        attributes: Optional[List[str]] = None,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        params: dict = {"event_id": event_id, "first_vertex": first_vertex, "count": count}
        if attributes:
            params["attributes"] = attributes
        return await self._conn_manager.request_capture_inspection(conn_id, "mesh_vertices", params)

    async def _get_post_vs_geometry(
        self,
        event_id: int = 0,
        instance: int = 0,
        view: int = 0,
        stage: str = "vs_out",
        max_vertices: int = 50,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "post_vs_geometry",
            {"event_id": event_id, "instance": instance, "view": view,
             "stage": stage, "max_vertices": max_vertices},
        )

    async def _get_mesh_statistics(
        self,
        event_id: int = 0,
        max_vertices: int = 200,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "mesh_statistics",
            {"event_id": event_id, "max_vertices": max_vertices},
        )

    async def _get_pixel_history(
        self,
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
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        return await self._conn_manager.request_capture_inspection(
            conn_id, "pixel_history",
            {
                "resource_id": resource_id,
                "x": x,
                "y": y,
                "mip": mip,
                "slice": slice,
                "sample": sample,
                "max_modifications": max_modifications,
                "event_id": event_id,
            },
        )

    async def _debug_pixel_shader(
        self,
        x: int = 0,
        y: int = 0,
        event_id: int = 0,
        sample: int = 0,
        primitive: int = -1,
        view: int = 0,
        max_steps: int = 200,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        raw = await self._conn_manager.request_capture_inspection(
            conn_id, "debug_pixel",
            {
                "x": x, "y": y, "event_id": event_id, "sample": sample,
                "primitive": primitive, "view": view, "max_steps": max_steps,
            },
        )
        if "error" in raw:
            return raw
        debug_id = self._debug_store.make_id()
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
        if raw.get("collection_warning"):
            record.metadata["collection_warning"] = raw["collection_warning"]
        self._debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "step_count": record.metadata.get("step_count", 0),
            "truncated": record.metadata.get("truncated", False),
        }

    async def _debug_vertex_shader(
        self,
        vert_id: int = 0,
        inst_id: int = 0,
        idx: int = 0,
        view: int = 0,
        event_id: int = 0,
        max_steps: int = 200,
        instance_id: str = "",
    ) -> dict:
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        raw = await self._conn_manager.request_capture_inspection(
            conn_id, "debug_vertex",
            {
                "vert_id": vert_id, "inst_id": inst_id, "idx": idx,
                "view": view, "event_id": event_id, "max_steps": max_steps,
            },
        )
        if "error" in raw:
            return raw
        debug_id = self._debug_store.make_id()
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
        if raw.get("collection_warning"):
            record.metadata["collection_warning"] = raw["collection_warning"]
        self._debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "step_count": record.metadata.get("step_count", 0),
            "truncated": record.metadata.get("truncated", False),
        }

    async def _debug_compute_shader(
        self,
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
        conn_id, err = await self._resolve_inspection_connection(instance_id)
        if err is not None:
            return err
        raw = await self._conn_manager.request_capture_inspection(
            conn_id, "debug_compute",
            {
                "group_x": group_x, "group_y": group_y, "group_z": group_z,
                "thread_x": thread_x, "thread_y": thread_y, "thread_z": thread_z,
                "event_id": event_id, "max_steps": max_steps,
            },
        )
        if "error" in raw:
            return raw
        debug_id = self._debug_store.make_id()
        record = DebugRecord(
            debug_id=debug_id,
            status="ready",
            stage=raw.get("stage", "compute"),
            event_id=raw.get("event_id", event_id),
            capture_path=raw.get("_capture_path"),
            instance_id=conn_id,
            steps=raw.get("steps", []),
            initial_vars=raw.get("initial_vars", {}),
            metadata={
                "group": [group_x, group_y, group_z],
                "thread": [thread_x, thread_y, thread_z],
                "step_count": raw.get("step_count", 0),
                "truncated": raw.get("truncated", False),
            },
        )
        if raw.get("collection_warning"):
            record.metadata["collection_warning"] = raw["collection_warning"]
        self._debug_store.store(record)
        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "step_count": record.metadata.get("step_count", 0),
            "truncated": record.metadata.get("truncated", False),
        }

    async def _get_shader_debug_trace(
        self,
        debug_id: str = "",
        first_step: int = 0,
        count: int = 50,
        instance_id: str = "",
    ) -> dict:
        if not debug_id:
            return {"error": "debug_id is required"}
        record = self._debug_store.get(debug_id)
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

    async def _get_shader_debug_variables(
        self,
        debug_id: str = "",
        step: int = 0,
        variable_names: Optional[List[str]] = None,
        instance_id: str = "",
    ) -> dict:
        if not debug_id:
            return {"error": "debug_id is required"}
        record = self._debug_store.get(debug_id)
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
                "note": "no trace steps available; showing initial state",
            }

        step = max(0, min(step, total - 1))

        # Reconstruct variable state at step from initial + deltas
        # Start from initial_vars, apply all changes up to and including `step`
        var_state: dict = {}
        # Initial vars
        for name, val in record.initial_vars.items():
            var_state[name] = val

        for i in range(step + 1):
            s = record.steps[i]
            for ch in s.get("changes", []):
                after = ch.get("after", {})
                name = after.get("name", "")
                if name:
                    var_state[name] = after

        # Filter by requested names
        if variable_names:
            var_state = {k: v for k, v in var_state.items() if k in variable_names}

        # Limit output size
        items = list(var_state.items())[:50]

        return {
            "debug_id": debug_id,
            "stage": record.stage,
            "event_id": record.event_id,
            "step": step,
            "total_steps": total,
            "variables": dict(items),
        }

    async def _get_shader_debug_status(
        self,
        debug_id: str = "",
        instance_id: str = "",
    ) -> dict:
        if not debug_id:
            # List all
            ids = self._debug_store.list_ids()
            return {
                "debug_ids": ids,
                "count": len(ids),
            }
        record = self._debug_store.get(debug_id)
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


# ---------------------------------------------------------------------------
# Analysis helpers (module-level, pure functions — easier to test)
# ---------------------------------------------------------------------------


def _find_counter_desc(counter_id: int, counter_descriptions: list) -> dict:
    return next(
        (d for d in counter_descriptions if d.get("counter_id") == counter_id), {}
    )


def _resolve_timing_counter(counter_id, record: "MeasurementRecord") -> Optional[int]:
    if counter_id is not None:
        return int(counter_id)
    for desc in record.counter_descriptions:
        name_lower = desc.get("name", "").lower()
        unit_lower = desc.get("unit", "").lower()
        if "duration" in name_lower or "second" in unit_lower or "time" in name_lower:
            return desc.get("counter_id")
    if record.counter_ids:
        return record.counter_ids[0]
    return None


def _sort_entries(entries: list, sort_by: str) -> list:
    if sort_by == "value_asc":
        return sorted(entries, key=lambda r: (r.get("value") or 0))
    if sort_by == "event_id":
        return sorted(entries, key=lambda r: r.get("event_id", 0))
    if sort_by == "event_id_desc":
        return sorted(entries, key=lambda r: r.get("event_id", 0), reverse=True)
    # default: value_desc
    return sorted(entries, key=lambda r: (r.get("value") or 0), reverse=True)


def _aggregate_passes(actions: list, value_map: dict, depth: int = 0) -> list:
    """Recursively aggregate marker groups into pass summaries."""
    passes = []
    for action in actions:
        atype = action.get("action_type", "")
        children = action.get("children", [])
        if atype == "marker_begin":
            leaf_sum, leaf_count, unmeasured, largest = _sum_leaf_events(children, value_map)
            child_passes = _aggregate_passes(children, value_map, depth + 1)
            entry = {
                "name": action.get("name", ""),
                "event_id": action.get("event_id", 0),
                "depth": depth,
                "event_count": leaf_count,
                "aggregated_duration": leaf_sum,
                "unmeasured_event_count": unmeasured,
                "aggregation": "sum_of_leaf_event_durations",
            }
            if largest:
                entry["largest_event"] = largest
            if child_passes:
                entry["sub_passes"] = child_passes
            passes.append(entry)
        elif children:
            passes.extend(_aggregate_passes(children, value_map, depth))
    return passes


def _sum_leaf_events(actions: list, value_map: dict):
    """Return (total_duration, measured_count, unmeasured_count, largest_entry)."""
    total = 0.0
    measured = 0
    unmeasured = 0
    largest = None
    for action in actions:
        atype = action.get("action_type", "")
        children = action.get("children", [])
        if atype in ("drawcall", "dispatch"):
            eid = action.get("event_id", 0)
            val = value_map.get(eid)
            if val is not None:
                total += val
                measured += 1
                if largest is None or val > largest.get("value", 0):
                    largest = {"event_id": eid, "name": action.get("name", ""), "value": val}
            else:
                unmeasured += 1
        elif children:
            sub_total, sub_measured, sub_unmeasured, sub_largest = _sum_leaf_events(children, value_map)
            total += sub_total
            measured += sub_measured
            unmeasured += sub_unmeasured
            if sub_largest and (largest is None or sub_largest.get("value", 0) > largest.get("value", 0)):
                largest = sub_largest
    return total, measured, unmeasured, largest
