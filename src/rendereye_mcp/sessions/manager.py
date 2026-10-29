"""SessionManager: orchestrates capture opening, session lifecycle, and reconciliation."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from rendereye_mcp.instances.launcher import launch_renderdoc
from rendereye_mcp.instances.manager import InstanceManager
from rendereye_mcp.platform.window_control import close_window_graceful, focus_window
from rendereye_mcp.platform.windows import find_renderdoc_exe

from .models import AssociationStatus, SessionRecord, SessionStatus
from .storage import SessionStorage

if TYPE_CHECKING:
    from rendereye_mcp.captures.registry import CaptureRegistry
    from rendereye_mcp.config import Config
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager
    from rendereye_mcp.operations.tracker import OperationTracker

logger = logging.getLogger(__name__)

# How long to poll for window after launch (seconds)
_WINDOW_POLL_TIMEOUT = 5.0
_WINDOW_POLL_INTERVAL = 0.5

# How long to wait for extension GUI command result
_GUI_COMMAND_TIMEOUT = 10.0


class SessionManager:
    def __init__(
        self,
        config: "Config",
        storage: SessionStorage,
        instance_manager: InstanceManager,
        capture_registry: Optional["CaptureRegistry"] = None,
        conn_manager: Optional["ExtensionConnectionManager"] = None,
    ) -> None:
        self._config = config
        self._storage = storage
        self._instances = instance_manager
        self._registry = capture_registry
        self._conn_manager = conn_manager
        self._lock = threading.Lock()

    def set_conn_manager(self, mgr: "ExtensionConnectionManager") -> None:
        """Set the extension connection manager (can be called after construction)."""
        self._conn_manager = mgr

    def start(self) -> None:
        """Initialize storage, load persisted sessions."""
        self._storage.initialize()
        logger.info("SessionManager started")

    def stop(self) -> None:
        """Clean up resources."""
        logger.info("SessionManager stopped")

    def create_session(
        self,
        capture_id: str,
        open_mode: str = "new_window",
        target_session_id: Optional[str] = None,
    ) -> dict:
        """Open a capture and create/return a session (sync wrapper).

        Resolves capture_id (supports "latest").
        For "new_window": launch RenderDoc, create session with CREATING->ACTIVE.
        For "reuse": find existing session for capture_id, return it (or create new).
        For "replace": requires extension connection via async open_capture.
        """
        # Resolve capture
        resolved = self._resolve_capture(capture_id)
        if resolved is None:
            return {"error": "capture_not_found", "message": f"Capture not found: {capture_id}"}

        resolved_id, resolved_path = resolved

        if open_mode == "replace":
            return {
                "error": "not_supported",
                "message": "replace mode requires Phase 4 extension (use capture_open tool)",
            }

        if open_mode == "reuse":
            # Find an existing active session for this capture
            existing, total = self._storage.list_sessions(
                status=SessionStatus.ACTIVE, capture_id=resolved_id, limit=1
            )
            if existing:
                return existing[0].to_dict()

        # Find RenderDoc exe
        exe_path = find_renderdoc_exe(self._config)
        if not exe_path:
            return {
                "error": "renderdoc_not_found",
                "message": "RenderDoc executable not found",
            }

        # Launch RenderDoc
        launch_result = launch_renderdoc(exe_path, resolved_path)
        if not launch_result.success:
            return {
                "error": "launch_failed",
                "message": launch_result.error,
            }

        # Register the launched instance
        create_time = launch_result.process_create_time or 0.0
        inst = self._instances.register_launched(
            pid=launch_result.process_id,
            create_time=create_time,
            exe_path=exe_path,
        )

        now = datetime.now(timezone.utc)
        session_id = self._storage.get_next_session_id()

        record = SessionRecord(
            session_id=session_id,
            capture_id=resolved_id,
            capture_path=resolved_path,
            instance_id=inst.instance_id,
            window_id=None,  # window association requires post-launch discovery
            process_id=launch_result.process_id,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.UNKNOWN,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self._storage.upsert_session(record)

        result = record.to_dict()
        result["note"] = launch_result.note
        return result

    async def open_capture(
        self,
        capture_id: str,
        open_mode: str = "new_window",
        target_session_id: Optional[str] = None,
        operation_tracker: Optional["OperationTracker"] = None,
    ) -> dict:
        """Async capture open with operation tracking.

        Returns a dict with operation_id and status.
        Modes: new_window, reuse, replace.
        """
        from rendereye_mcp.errors import ErrorCode, error_response
        from rendereye_mcp.operations.models import OperationStatus

        # Create operation record
        op = None
        if operation_tracker is not None:
            op = operation_tracker.create(
                "capture_open",
                capture_id=capture_id,
                open_mode=open_mode,
            )

        def _update_op(status, **kwargs):
            if op is None:
                return
            op.status = status
            for k, v in kwargs.items():
                setattr(op, k, v)
            operation_tracker.update(op)

        # VALIDATING
        _update_op(OperationStatus.VALIDATING)

        # Resolve capture
        resolved = self._resolve_capture(capture_id)
        if resolved is None:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.CAPTURE_NOT_FOUND.value,
                error_message=f"Capture not found: {capture_id}",
            )
            resp = error_response(
                ErrorCode.CAPTURE_NOT_FOUND,
                f"Capture not found: {capture_id}",
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        resolved_id, resolved_path = resolved

        if op:
            op.capture_id = resolved_id

        # REUSE mode
        if open_mode == "reuse":
            existing, _ = self._storage.list_sessions(
                status=SessionStatus.ACTIVE, capture_id=resolved_id, limit=1
            )
            if existing:
                sess = existing[0]
                _update_op(
                    OperationStatus.CONFIRMED,
                    session_id=sess.session_id,
                    instance_id=sess.instance_id,
                    window_id=sess.window_id,
                )
                result = sess.to_dict()
                result["status"] = "confirmed"
                if op:
                    result["operation_id"] = op.operation_id
                return result
            # Fall through to new_window if no existing session
            open_mode = "new_window"

        # REPLACE mode
        if open_mode == "replace":
            return await self._open_capture_replace(
                resolved_id, resolved_path, target_session_id, op, operation_tracker
            )

        # NEW_WINDOW mode
        return await self._open_capture_new_window(
            resolved_id, resolved_path, op, operation_tracker
        )

    async def _open_capture_new_window(
        self, capture_id: str, capture_path: str, op, operation_tracker
    ) -> dict:
        """Launch a new RenderDoc window with the given capture."""
        from rendereye_mcp.errors import ErrorCode, error_response
        from rendereye_mcp.operations.models import OperationStatus

        def _update_op(status, **kwargs):
            if op is None:
                return
            op.status = status
            for k, v in kwargs.items():
                setattr(op, k, v)
            if operation_tracker:
                operation_tracker.update(op)

        # Find RenderDoc exe
        exe_path = find_renderdoc_exe(self._config)
        if not exe_path:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.INSTANCE_NOT_FOUND.value,
                error_message="RenderDoc executable not found",
            )
            resp = error_response(
                ErrorCode.INSTANCE_NOT_FOUND,
                "RenderDoc executable not found",
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # LAUNCHING
        _update_op(OperationStatus.LAUNCHING)

        launch_result = launch_renderdoc(exe_path, capture_path)
        if not launch_result.success:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.INTERNAL_ERROR.value,
                error_message=launch_result.error or "Launch failed",
            )
            resp = error_response(
                ErrorCode.INTERNAL_ERROR,
                launch_result.error or "Launch failed",
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # Register instance
        create_time = launch_result.process_create_time or 0.0
        inst = self._instances.register_launched(
            pid=launch_result.process_id,
            create_time=create_time,
            exe_path=exe_path,
        )

        now = datetime.now(timezone.utc)
        session_id = self._storage.get_next_session_id()

        record = SessionRecord(
            session_id=session_id,
            capture_id=capture_id,
            capture_path=capture_path,
            instance_id=inst.instance_id,
            window_id=None,
            process_id=launch_result.process_id,
            status=SessionStatus.ACTIVE,
            managed=True,
            protected=False,
            association_status=AssociationStatus.UNKNOWN,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self._storage.upsert_session(record)

        if op:
            op.session_id = session_id
            op.instance_id = inst.instance_id

        # WAITING_FOR_GUI — poll for window discovery
        _update_op(OperationStatus.WAITING_FOR_GUI)

        window_id = await self._poll_for_window(inst.instance_id, _WINDOW_POLL_TIMEOUT)
        if window_id:
            record.window_id = window_id
            record.association_status = AssociationStatus.CONFIRMED
            record.updated_at = datetime.now(timezone.utc)
            self._storage.upsert_session(record)
            if op:
                op.window_id = window_id

        # VERIFYING — check extension connection
        _update_op(OperationStatus.VERIFYING)

        ext_conn = None
        if self._conn_manager is not None:
            ext_conn = self._conn_manager.get_connection_for_instance(inst.instance_id)

        if ext_conn is not None and ext_conn.capture_path:
            _update_op(
                OperationStatus.CONFIRMED,
                loaded_capture_verified=True,
                window_id=record.window_id,
            )
            result = record.to_dict()
            result["status"] = "confirmed"
            result["note"] = launch_result.note
            if op:
                result["operation_id"] = op.operation_id
            return result

        # Could not verify via extension — UNKNOWN_OUTCOME (not a failure, just unverified)
        _update_op(
            OperationStatus.UNKNOWN_OUTCOME,
            window_id=record.window_id,
        )
        result = record.to_dict()
        result["status"] = "unknown_outcome"
        result["note"] = launch_result.note
        result["message"] = "Session created but GUI state not yet verified by extension"
        if op:
            result["operation_id"] = op.operation_id
        return result

    async def _open_capture_replace(
        self,
        capture_id: str,
        capture_path: str,
        target_session_id: Optional[str],
        op,
        operation_tracker,
    ) -> dict:
        """Replace the capture in an existing managed session."""
        from rendereye_mcp.errors import ErrorCode, error_response
        from rendereye_mcp.operations.models import OperationStatus

        def _update_op(status, **kwargs):
            if op is None:
                return
            op.status = status
            for k, v in kwargs.items():
                setattr(op, k, v)
            if operation_tracker:
                operation_tracker.update(op)

        if not target_session_id:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.SESSION_NOT_FOUND.value,
                error_message="replace mode requires target_session_id",
            )
            resp = error_response(
                ErrorCode.SESSION_NOT_FOUND,
                "replace mode requires target_session_id",
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        record = self._storage.get_session(target_session_id)
        if record is None:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.SESSION_NOT_FOUND.value,
                error_message=f"Session not found: {target_session_id}",
            )
            resp = error_response(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session not found: {target_session_id}",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        if not record.managed:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.SESSION_UNMANAGED.value,
                error_message="Session is not managed",
            )
            resp = error_response(
                ErrorCode.SESSION_UNMANAGED,
                "Session is not managed",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        if record.protected:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.SESSION_PROTECTED.value,
                error_message="Session is protected",
            )
            resp = error_response(
                ErrorCode.SESSION_PROTECTED,
                "Session is protected",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        if self._conn_manager is None:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.EXTENSION_UNAVAILABLE.value,
                error_message="No extension connection manager",
            )
            resp = error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "No extension connection manager",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # Find extension connection for this session's instance
        conn = None
        connection_id = None
        if record.instance_id:
            conn = self._conn_manager.get_connection_for_instance(record.instance_id)
            if conn:
                connection_id = conn.connection_id

        if conn is None or not conn.connected:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.EXTENSION_UNAVAILABLE.value,
                error_message="No active extension connection for this session",
            )
            resp = error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                "No active extension connection for this session",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # Send execute_gui_command to extension
        _update_op(OperationStatus.WAITING_FOR_GUI)

        result_msg, err = await self._conn_manager.execute_gui_command(
            connection_id=connection_id,
            command="open_capture",
            params={"path": capture_path},
            timeout=_GUI_COMMAND_TIMEOUT,
        )

        if err == "timeout":
            _update_op(
                OperationStatus.TIMED_OUT,
                error_code=ErrorCode.OPERATION_TIMEOUT.value,
                error_message="Timed out waiting for extension to open capture",
            )
            resp = error_response(
                ErrorCode.OPERATION_TIMEOUT,
                "Timed out waiting for extension to open capture",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        if err or result_msg is None:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.EXTENSION_UNAVAILABLE.value,
                error_message=f"Extension command failed: {err}",
            )
            resp = error_response(
                ErrorCode.EXTENSION_UNAVAILABLE,
                f"Extension command failed: {err}",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # VERIFYING
        _update_op(OperationStatus.VERIFYING)

        if not result_msg.success:
            _update_op(
                OperationStatus.FAILED,
                error_code=ErrorCode.INTERNAL_ERROR.value,
                error_message=result_msg.error or "Extension reported failure",
            )
            resp = error_response(
                ErrorCode.INTERNAL_ERROR,
                result_msg.error or "Extension reported failure",
                session_id=target_session_id,
            )
            if op:
                resp["operation_id"] = op.operation_id
            return resp

        # Update session record
        now = datetime.now(timezone.utc)
        record.capture_id = capture_id
        record.capture_path = capture_path
        record.gui_capture_path = capture_path
        record.gui_verified_at = now
        record.updated_at = now
        record.last_activity_at = now
        self._storage.upsert_session(record)

        _update_op(
            OperationStatus.CONFIRMED,
            session_id=target_session_id,
            instance_id=record.instance_id,
            window_id=record.window_id,
            loaded_capture_verified=True,
        )

        result = record.to_dict()
        result["status"] = "confirmed"
        if op:
            result["operation_id"] = op.operation_id
        return result

    async def _poll_for_window(
        self, instance_id: str, timeout: float
    ) -> Optional[str]:
        """Poll for a window associated with the given instance."""
        from rendereye_mcp.instances.models import InstanceStatus

        elapsed = 0.0
        while elapsed < timeout:
            self._instances.refresh()
            inst = self._instances.get_instance(instance_id)
            if inst is not None and inst.status == InstanceStatus.EXITED:
                return None  # Process died; no point polling further
            windows = self._instances.find_windows_for_instance(instance_id)
            if windows:
                return windows[0].window_id
            await asyncio.sleep(_WINDOW_POLL_INTERVAL)
            elapsed += _WINDOW_POLL_INTERVAL
        return None

    def list_sessions(
        self,
        status: Optional[str] = None,
        managed_only: bool = False,
        capture_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        status_filter: Optional[SessionStatus] = None
        if status:
            try:
                status_filter = SessionStatus(status)
            except ValueError:
                return {
                    "error": "invalid_status",
                    "message": f"Unknown status: {status!r}",
                    "valid_statuses": [s.value for s in SessionStatus],
                }

        records, total = self._storage.list_sessions(
            status=status_filter,
            managed_only=managed_only,
            capture_id=capture_id if capture_id else None,
            limit=limit,
            offset=offset,
        )
        return {
            "sessions": [r.to_dict() for r in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        return self._storage.get_session(session_id)

    def focus_session(self, session_id: str) -> dict:
        """Focus a session's window."""
        record = self._storage.get_session(session_id)
        if record is None:
            return {"error": "session_not_found", "session_id": session_id}

        if record.window_id is None:
            # Try to find a window via instance
            self._instances.refresh()
            if record.instance_id:
                windows = self._instances.find_windows_for_instance(record.instance_id)
                if windows:
                    record.window_id = windows[0].window_id
                    record.updated_at = datetime.now(timezone.utc)
                    self._storage.upsert_session(record)

        if record.window_id is None:
            return {
                "success": False,
                "session_id": session_id,
                "message": "no_window_associated",
            }

        # Find the window
        self._instances.refresh()
        window = self._instances.get_window(record.window_id)
        if window is None:
            return {
                "success": False,
                "session_id": session_id,
                "message": "window_not_found",
            }

        result = focus_window(window.hwnd)
        return {
            "success": result.success,
            "session_id": session_id,
            "message": result.message,
        }

    def close_session(self, session_id: str) -> dict:
        """Gracefully close a managed, unprotected session."""
        from rendereye_mcp.errors import ErrorCode, error_response

        record = self._storage.get_session(session_id)
        if record is None:
            return error_response(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session not found: {session_id}",
                session_id=session_id,
            )

        if not record.managed:
            return error_response(
                ErrorCode.SESSION_UNMANAGED,
                "Session is not managed by this server",
                session_id=session_id,
            )

        if record.protected:
            return error_response(
                ErrorCode.SESSION_PROTECTED,
                "Session is protected and cannot be closed",
                session_id=session_id,
            )

        # Find window
        if record.window_id is not None:
            self._instances.refresh()
            window = self._instances.get_window(record.window_id)
            if window is not None:
                # Update status to closing
                now = datetime.now(timezone.utc)
                record.status = SessionStatus.CLOSING
                record.updated_at = now
                self._storage.upsert_session(record)

                close_result = close_window_graceful(window.hwnd)

                record = self._storage.get_session(session_id)
                if record is None:
                    return {"success": True, "session_id": session_id, "message": "closed"}

                now = datetime.now(timezone.utc)
                record.status = SessionStatus.CLOSED
                record.updated_at = now
                self._storage.upsert_session(record)

                return {
                    "success": close_result.success,
                    "session_id": session_id,
                    "confirmed": close_result.confirmed,
                    "message": close_result.message,
                }

        # No window — just mark as closed
        now = datetime.now(timezone.utc)
        record.status = SessionStatus.CLOSED
        record.updated_at = now
        self._storage.upsert_session(record)
        return {"success": True, "session_id": session_id, "message": "closed_no_window"}

    def protect_session(self, session_id: str, protected: bool) -> dict:
        """Set/unset protection flag. Returns updated session dict."""
        record = self._storage.get_session(session_id)
        if record is None:
            return {"error": "session_not_found", "session_id": session_id}

        record.protected = protected
        record.updated_at = datetime.now(timezone.utc)
        self._storage.upsert_session(record)
        return record.to_dict()

    def reconcile(self) -> dict:
        """Reconcile persisted sessions with running processes."""
        import psutil

        active_records, _ = self._storage.list_sessions(
            status=SessionStatus.ACTIVE, limit=1000
        )
        disconnected_records, _ = self._storage.list_sessions(
            status=SessionStatus.DISCONNECTED, limit=1000
        )
        to_check = active_records + disconnected_records

        reconciled = 0
        recovered = 0
        lost = 0

        now = datetime.now(timezone.utc)

        for record in to_check:
            changed = False

            # Check process still running
            process_alive = False
            if record.process_id is not None:
                try:
                    proc = psutil.Process(record.process_id)
                    process_alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_alive = False

            if not process_alive:
                if record.status == SessionStatus.ACTIVE:
                    record.status = SessionStatus.DISCONNECTED
                    record.association_status = AssociationStatus.LOST
                    record.updated_at = now
                    changed = True
                    lost += 1
            else:
                if record.status == SessionStatus.DISCONNECTED:
                    record.status = SessionStatus.ACTIVE
                    record.updated_at = now
                    changed = True
                    recovered += 1

            # Check window still valid
            if record.window_id is not None:
                from rendereye_mcp.platform.window_control import is_window_valid

                window = self._instances.get_window(record.window_id)
                if window is None or not is_window_valid(window.hwnd):
                    if record.association_status not in (
                        AssociationStatus.LOST,
                        AssociationStatus.UNKNOWN,
                    ):
                        record.association_status = AssociationStatus.LOST
                        record.updated_at = now
                        changed = True

            if changed:
                self._storage.upsert_session(record)
                reconciled += 1

        return {"reconciled": reconciled, "recovered": recovered, "lost": lost}

    def _resolve_capture(self, capture_id: str) -> Optional[tuple[str, str]]:
        """Resolve capture_id (or "latest") to (capture_id, capture_path).
        Returns None if not found or capture is not READY."""
        if self._registry is None:
            return None

        if capture_id == "latest":
            record = self._registry.get_latest_capture()
        else:
            record = self._registry.get_capture(capture_id)

        if record is None:
            return None

        from rendereye_mcp.captures.models import CaptureStatus

        if record.status != CaptureStatus.READY:
            logger.warning(
                "Capture %s is not ready (status=%s); refusing to open",
                record.capture_id,
                record.status.value,
            )
            return None

        return (record.capture_id, record.path)

    def on_gui_state_changed(
        self,
        connection_id: str,
        capture_path: Optional[str],
        capture_loaded: bool,
    ) -> None:
        """Called when an extension reports a GUI state change.

        Updates sessions associated with this connection's instance.
        """
        # Find the instance_id for this connection
        instance_id = None
        if self._conn_manager is not None:
            conn = self._conn_manager.get_connection(connection_id)
            if conn is not None:
                instance_id = conn.instance_id

        if instance_id is None:
            logger.debug(
                "GUI state changed for connection %s: no instance_id found",
                connection_id,
            )
            return

        # Find active sessions for this instance
        active_records, _ = self._storage.list_sessions(
            status=SessionStatus.ACTIVE, limit=1000
        )
        now = datetime.now(timezone.utc)
        for record in active_records:
            if record.instance_id == instance_id:
                record.gui_capture_path = capture_path if capture_loaded else None
                record.gui_verified_at = now
                record.updated_at = now
                self._storage.upsert_session(record)

        logger.debug(
            "GUI state changed for connection %s (instance=%s): loaded=%s path=%s",
            connection_id,
            instance_id,
            capture_loaded,
            capture_path,
        )

    def on_extension_disconnected(self, connection_id: str) -> None:
        """Called when an extension IPC connection is lost.

        Does NOT close the RenderDoc process or session.
        Marks affected session association as STALE.
        """
        # Find the instance_id for this connection
        instance_id = None
        if self._conn_manager is not None:
            conn = self._conn_manager.get_connection(connection_id)
            if conn is not None:
                instance_id = conn.instance_id

        if instance_id is not None:
            active_records, _ = self._storage.list_sessions(
                status=SessionStatus.ACTIVE, limit=1000
            )
            now = datetime.now(timezone.utc)
            for record in active_records:
                if record.instance_id == instance_id:
                    record.status = SessionStatus.DISCONNECTED
                    record.updated_at = now
                    self._storage.upsert_session(record)
                    logger.info(
                        "Session %s marked DISCONNECTED (extension %s disconnected)",
                        record.session_id,
                        connection_id,
                    )

        logger.info("Extension disconnected: connection_id=%s", connection_id)

    def get_active_session_count(self) -> int:
        """Return count of non-closed sessions."""
        _, total = self._storage.list_sessions(status=SessionStatus.ACTIVE, limit=0)
        return total
