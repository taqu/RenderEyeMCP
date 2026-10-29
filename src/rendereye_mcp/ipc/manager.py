"""Manages authenticated extension connections and bridges to Instance/Session managers."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from rendereye_mcp.ipc.protocol import GuiCommandResultMessage

logger = logging.getLogger(__name__)


@dataclass
class ExtensionConnection:
    connection_id: str
    instance_id: Optional[str]
    process_id: Optional[int]
    extension_version: str
    renderdoc_version: str
    authenticated: bool
    connected: bool
    gui_state_revision: int = 0
    capture_loaded: bool = False
    capture_path: Optional[str] = None
    capture_state: str = "unknown"
    last_state_at: Optional[datetime] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: Optional[datetime] = None

    @property
    def connection_state(self) -> str:
        """Tri-state connection status: connected / disconnected / unknown."""
        if self.connected:
            return "connected"
        if self.last_state_at is not None:
            return "disconnected"
        return "unknown"

    def to_dict(self) -> dict:
        return {
            "connection_id": self.connection_id,
            "instance_id": self.instance_id,
            "process_id": self.process_id,
            "extension_version": self.extension_version,
            "renderdoc_version": self.renderdoc_version,
            "authenticated": self.authenticated,
            "connected": self.connected,
            "connection_state": self.connection_state,
            "capture_loaded": self.capture_loaded,
            "capture_path": self.capture_path,
            "capture_state": self.capture_state,
            "gui_state_revision": self.gui_state_revision,
            "last_state_at": self.last_state_at.isoformat() if self.last_state_at else None,
        }

    def to_gui_session_dict(self) -> dict:
        """Phase 7 GUI-session view — clearly separates current vs last-known capture."""
        entry: dict = {
            "instance_id": self.instance_id,
            "process_id": self.process_id,
            "connection_state": self.connection_state,
            "renderdoc_version": self.renderdoc_version,
            "state_version": self.gui_state_revision,
        }
        if self.connected:
            entry["capture"] = {"state": self.capture_state, "path": self.capture_path}
            entry["last_known_capture"] = None
        else:
            entry["capture"] = None
            if self.last_state_at is not None:
                entry["last_known_capture"] = {
                    "state": self.capture_state,
                    "path": self.capture_path,
                }
            else:
                entry["last_known_capture"] = None
        return entry


class ExtensionConnectionManager:
    """Thread-safe registry of authenticated extension connections.

    Called from asyncio context (connection handlers) and from
    MCP tool handlers.
    """

    def __init__(self, auth_manager=None, instance_manager=None, session_manager=None):
        self._auth = auth_manager
        self._instances = instance_manager
        self._sessions = session_manager
        self._connections: dict[str, ExtensionConnection] = {}  # conn_id -> conn
        self._send_callbacks: dict[str, Any] = {}  # conn_id -> async callable
        self._lock = threading.Lock()

    def register_connection(
        self,
        instance_id: str,
        process_id: int,
        extension_version: str,
        renderdoc_version: str,
        auth_token: str,
    ) -> tuple[Optional[str], str]:
        """Authenticate and register a connection.

        Returns (connection_id, error_message).
        connection_id is None on failure.
        """
        # Validate auth token
        if self._auth is not None and not self._auth.validate(auth_token):
            return None, "authentication_failed"

        conn_id = str(uuid.uuid4())
        conn = ExtensionConnection(
            connection_id=conn_id,
            instance_id=instance_id,
            process_id=process_id,
            extension_version=extension_version,
            renderdoc_version=renderdoc_version,
            authenticated=True,
            connected=True,
            last_seen_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._connections[conn_id] = conn

        # Notify instance manager
        if self._instances is not None:
            try:
                self._instances.refresh()
            except Exception:
                pass

        return conn_id, ""

    def update_gui_state(
        self,
        connection_id: str,
        revision: int,
        capture_loaded: bool,
        capture_path: Optional[str],
        capture_state: str,
    ) -> bool:
        """Update GUI state for a connection. Returns False if revision is stale."""
        with self._lock:
            conn = self._connections.get(connection_id)
            if conn is None:
                return False
            if revision <= conn.gui_state_revision:
                return False  # stale update
            conn.gui_state_revision = revision
            conn.capture_loaded = capture_loaded
            conn.capture_path = capture_path
            conn.capture_state = capture_state
            conn.last_state_at = datetime.now(timezone.utc)
            conn.last_seen_at = datetime.now(timezone.utc)

        # Notify session manager about state change
        if self._sessions is not None:
            try:
                self._sessions.on_gui_state_changed(
                    connection_id=connection_id,
                    capture_path=capture_path,
                    capture_loaded=capture_loaded,
                )
            except Exception:
                pass
        return True

    def register_send_callback(self, connection_id: str, cb: Callable) -> None:
        """Register an async callable for sending requests to a connection."""
        with self._lock:
            self._send_callbacks[connection_id] = cb

    def unregister_send_callback(self, connection_id: str) -> None:
        """Remove the send callback for a connection."""
        with self._lock:
            self._send_callbacks.pop(connection_id, None)

    async def execute_gui_command(
        self,
        connection_id: str,
        command: str,
        params: dict,
        timeout: float = 10.0,
    ) -> tuple[Optional["GuiCommandResultMessage"], str]:
        """Send an execute_gui_command to the extension and wait for the result.

        Returns (result_message, error_string). error_string is empty on success.
        """
        from rendereye_mcp.ipc.protocol import ExecuteGuiCommandMessage

        cb = None
        with self._lock:
            cb = self._send_callbacks.get(connection_id)
        if cb is None:
            return None, "no_connection"

        msg = ExecuteGuiCommandMessage(
            request_id=str(uuid.uuid4()),
            command=command,
            params=params,
        )
        try:
            result = await asyncio.wait_for(cb(msg), timeout=timeout)
            return result, ""
        except asyncio.TimeoutError:
            return None, "timeout"
        except Exception as e:
            return None, str(e)

    def disconnect_connection(self, connection_id: str) -> None:
        self.unregister_send_callback(connection_id)
        with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                conn.connected = False
        if self._sessions is not None:
            try:
                self._sessions.on_extension_disconnected(connection_id)
            except Exception:
                pass

    def get_connection(self, connection_id: str) -> Optional[ExtensionConnection]:
        with self._lock:
            return self._connections.get(connection_id)

    def list_connections(self) -> list[ExtensionConnection]:
        with self._lock:
            return list(self._connections.values())

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for c in self._connections.values() if c.connected)

    def get_connection_for_instance(self, instance_id: str) -> Optional[ExtensionConnection]:
        with self._lock:
            for conn in self._connections.values():
                if conn.instance_id == instance_id and conn.connected:
                    return conn
        return None

    def get_any_connection_for_instance(self, instance_id: str) -> Optional[ExtensionConnection]:
        """Return a connection for instance_id: connected first, otherwise most-recently-seen."""
        with self._lock:
            connected = None
            last_disconnected: Optional[ExtensionConnection] = None
            for conn in self._connections.values():
                if conn.instance_id != instance_id:
                    continue
                if conn.connected:
                    connected = conn
                elif last_disconnected is None or (
                    conn.last_state_at is not None
                    and last_disconnected.last_state_at is not None
                    and conn.last_state_at > last_disconnected.last_state_at
                ):
                    last_disconnected = conn
        return connected or last_disconnected

    async def request_capture_inspection(
        self,
        connection_id: str,
        operation: str,
        params: dict,
        timeout: float = 30.0,
    ) -> dict:
        """Request capture inspection from the extension. Returns result dict."""
        from rendereye_mcp.ipc.protocol import InspectCaptureRequestMessage

        cb = None
        with self._lock:
            cb = self._send_callbacks.get(connection_id)
        if cb is None:
            return {"error": "no_connection", "message": "No send callback for connection"}

        msg = InspectCaptureRequestMessage(
            request_id=str(uuid.uuid4()),
            operation=operation,
            params=params,
        )
        try:
            result_msg = await asyncio.wait_for(cb(msg), timeout=timeout)
            if result_msg.error:
                return {"error": "extension_error", "message": result_msg.error}
            return result_msg.result or {}
        except asyncio.TimeoutError:
            return {
                "error": "timeout",
                "message": f"Inspection request '{operation}' timed out after {timeout}s",
            }
        except Exception as exc:
            return {"error": "request_failed", "message": str(exc)}
