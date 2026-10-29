"""Asyncio TCP loopback server for IPC with RenderDoc extensions."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from rendereye_mcp.ipc.connection import ClientConnection
from rendereye_mcp.ipc.protocol import MAX_MESSAGE_BYTES

if TYPE_CHECKING:
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager

logger = logging.getLogger(__name__)


class IPCTransport:
    """Manages the asyncio TCP server that RenderDoc extensions connect to.

    Binds exclusively to 127.0.0.1 (never 0.0.0.0) to limit exposure to
    the local machine only.
    """

    def __init__(
        self,
        config,
        conn_manager: Optional["ExtensionConnectionManager"] = None,
        tool_executor=None,
        service_instance_id: str = "",
    ) -> None:
        self._config = config
        self._conn_manager = conn_manager
        self._tool_executor = tool_executor
        self._service_instance_id = service_instance_id
        self._server: Optional[asyncio.AbstractServer] = None
        self._connections: list[ClientConnection] = []
        self._running = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the TCP server is actively listening."""
        return self._running and self._server is not None

    @property
    def connection_count(self) -> int:
        """Number of currently active client connections."""
        return len(self._connections)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the TCP listener.  Must be called from an asyncio event loop."""
        if self._running:
            logger.warning("IPCTransport.start() called but transport is already running.")
            return

        host = self._config.ipc_host
        port = self._config.ipc_port

        # Safety: always bind to loopback only
        if host == "0.0.0.0":
            logger.error("Refusing to bind IPC transport to 0.0.0.0 — using 127.0.0.1.")
            host = "127.0.0.1"

        self._server = await asyncio.start_server(
            self._handle_client,
            host=host,
            port=port,
            limit=MAX_MESSAGE_BYTES + 1,
        )
        self._running = True
        logger.info("IPC transport listening on %s:%s", host, port)

    async def stop(self) -> None:
        """Stop the TCP listener and close all open connections."""
        self._running = False
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("IPC transport stopped.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def set_conn_manager(self, conn_manager: "ExtensionConnectionManager") -> None:
        """Set the connection manager (can be called after construction)."""
        self._conn_manager = conn_manager

    def set_tool_executor(self, tool_executor, service_instance_id: str = "") -> None:
        """Set the tool executor and service instance ID (can be called after construction)."""
        self._tool_executor = tool_executor
        self._service_instance_id = service_instance_id

    _MAX_CONNECTIONS = 64

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Called by asyncio for each new incoming connection."""
        if len(self._connections) >= self._MAX_CONNECTIONS:
            logger.warning(
                "Connection limit (%d) reached; rejecting new client.", self._MAX_CONNECTIONS
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return

        conn = ClientConnection(
            reader=reader,
            writer=writer,
            on_disconnect=self._remove_connection,
            conn_manager=self._conn_manager,
            tool_executor=self._tool_executor,
            service_instance_id=self._service_instance_id,
        )
        self._connections.append(conn)
        logger.debug(
            "New connection accepted. Active connections: %d", len(self._connections)
        )
        # run() blocks until the connection closes
        await conn.run()

    def _remove_connection(self, conn: ClientConnection) -> None:
        """Remove a connection from the active list."""
        try:
            self._connections.remove(conn)
        except ValueError:
            pass
        logger.debug(
            "Connection removed. Active connections: %d", len(self._connections)
        )
