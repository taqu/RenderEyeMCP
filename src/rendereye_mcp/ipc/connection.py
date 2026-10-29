"""Per-client connection handler for the IPC server."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING, Callable, Optional

from rendereye_mcp import __version__
from rendereye_mcp.ipc.protocol import (
    MAX_MESSAGE_BYTES,
    BridgeRegisterAckMessage,
    BridgeRegisterMessage,
    ErrorMessage,
    GetStatusMessage,
    GoodbyeMessage,
    GuiCommandResultMessage,
    GuiStateChangedMessage,
    GuiStateResponseMessage,
    HeartbeatAckMessage,
    HeartbeatMessage,
    HelloAckMessage,
    HelloMessage,
    InspectCaptureResultMessage,
    RegisterAckMessage,
    RegisterInstanceMessage,
    ServiceInfoRequestMessage,
    ServiceInfoResponseMessage,
    ToolCallMessage,
    ToolResultMessage,
    deserialize,
    serialize,
)

if TYPE_CHECKING:
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager

logger = logging.getLogger(__name__)

# How long to wait for data from a client before closing the connection (seconds).
READ_TIMEOUT: float = 10.0
# Extended timeout for authenticated connections (bridges send heartbeats every 15s).
READ_TIMEOUT_AUTHENTICATED: float = 60.0


class ClientConnection:
    """Manages a single client TCP connection.

    Reads newline-delimited JSON messages from the client, dispatches them
    to the appropriate handler, and writes responses back.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        on_disconnect: Optional[Callable[["ClientConnection"], None]] = None,
        conn_manager: Optional["ExtensionConnectionManager"] = None,
        tool_executor=None,
        service_instance_id: str = "",
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._on_disconnect = on_disconnect
        self._conn_manager = conn_manager
        self._tool_executor = tool_executor
        self._service_instance_id = service_instance_id
        self._peer = writer.get_extra_info("peername", ("?", 0))
        self._instance_id: Optional[str] = None
        self._process_id: Optional[int] = None
        self._extension_version: Optional[str] = None
        self._greeted = False
        self._connection_id: Optional[str] = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._gui_state_revision: int = 0
        self._goodbye_received = False
        # Bridge-specific state
        self._is_bridge: bool = False
        self._bridge_connection_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def peer(self) -> tuple:
        return self._peer

    @property
    def instance_id(self) -> Optional[str]:
        return self._instance_id

    @property
    def connection_id(self) -> Optional[str]:
        return self._connection_id

    async def run(self) -> None:
        """Read and dispatch messages until the connection closes or errors."""
        logger.info("Client connected from %s:%s", *self._peer)
        try:
            while True:
                # Use extended timeout once the connection is authenticated
                timeout = READ_TIMEOUT_AUTHENTICATED if (self._greeted or self._is_bridge) else READ_TIMEOUT
                try:
                    line = await asyncio.wait_for(
                        self._reader.readline(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Read timeout for client %s:%s — closing connection.",
                        *self._peer,
                    )
                    break

                if not line:
                    # EOF — client disconnected.
                    logger.info("Client %s:%s disconnected (EOF).", *self._peer)
                    break

                if len(line) > MAX_MESSAGE_BYTES:
                    logger.warning(
                        "Oversized message (%d bytes) from %s:%s — closing.",
                        len(line),
                        *self._peer,
                    )
                    await self._send(
                        ErrorMessage(
                            request_id="",
                            code="message_too_large",
                            message=(
                                f"Message exceeds maximum size of {MAX_MESSAGE_BYTES} bytes."
                            ),
                        )
                    )
                    break

                await self._handle_line(line)

                if self._goodbye_received:
                    break

        except ConnectionResetError:
            logger.info("Client %s:%s reset connection.", *self._peer)
        except Exception as exc:
            logger.exception("Unexpected error for client %s:%s: %s", *self._peer, exc)
        finally:
            await self._close()

    async def send_request(self, msg, timeout: float = 5.0):
        """Send a message and wait for a response with matching request_id."""
        request_id = getattr(msg, "request_id", None)
        if request_id is None:
            raise ValueError("Message has no request_id")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_requests[request_id] = fut
        await self._send(msg)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_line(self, line: bytes) -> None:
        """Parse one JSON line and dispatch to the matching handler."""
        try:
            msg = deserialize(line)
        except ValueError as exc:
            logger.warning("Bad message from %s:%s: %s", *self._peer, exc)
            await self._send(
                ErrorMessage(
                    request_id="",
                    code="parse_error",
                    message=str(exc),
                )
            )
            return

        # ServiceInfoRequestMessage is handled BEFORE the greeting check so
        # clients can probe service identity without authenticating first.
        if isinstance(msg, ServiceInfoRequestMessage):
            await self._handle_service_info_request(msg)
            return

        if isinstance(msg, BridgeRegisterMessage):
            await self._handle_bridge_register(msg)
            return

        if isinstance(msg, ToolCallMessage):
            if self._is_bridge:
                await self._handle_tool_call(msg)
            else:
                await self._send(
                    ErrorMessage(
                        request_id=msg.request_id,
                        code="not_a_bridge",
                        message="tool_call requires bridge registration first.",
                    )
                )
            return

        if isinstance(msg, HelloMessage):
            await self._handle_hello(msg)
        elif isinstance(msg, HeartbeatMessage):
            await self._handle_heartbeat(msg)
        elif isinstance(msg, GetStatusMessage):
            await self._handle_get_status(msg)
        elif isinstance(msg, RegisterInstanceMessage):
            await self._handle_register_instance(msg)
        elif isinstance(msg, GuiStateChangedMessage):
            await self._handle_gui_state_changed(msg)
        elif isinstance(msg, GuiStateResponseMessage):
            await self._handle_gui_state_response(msg)
        elif isinstance(msg, GuiCommandResultMessage):
            await self._handle_gui_command_result(msg)
        elif isinstance(msg, InspectCaptureResultMessage):
            await self._handle_inspect_capture_result(msg)
        elif isinstance(msg, GoodbyeMessage):
            await self._handle_goodbye(msg)
        else:
            logger.warning(
                "Unexpected message type %r from %s:%s",
                type(msg).__name__,
                *self._peer,
            )
            await self._send(
                ErrorMessage(
                    request_id=getattr(msg, "request_id", ""),
                    code="unexpected_message",
                    message=f"Server does not expect {type(msg).__name__} from clients.",
                )
            )

    async def _handle_service_info_request(self, msg: ServiceInfoRequestMessage) -> None:
        """Respond to a service identity probe (allowed before authentication)."""
        logger.debug(
            "ServiceInfoRequest from %s:%s client_type=%s",
            *self._peer,
            msg.client_type,
        )
        await self._send(
            ServiceInfoResponseMessage(
                request_id=msg.request_id,
                service_name="RenderEyeMCP",
                service_version=__version__,
                service_pid=os.getpid(),
                service_instance_id=self._service_instance_id,
            )
        )

    async def _handle_bridge_register(self, msg: BridgeRegisterMessage) -> None:
        """Authenticate and register an MCP bridge process."""
        # Validate auth token
        if self._conn_manager is not None and self._conn_manager._auth is not None:
            if not self._conn_manager._auth.validate(msg.auth_token):
                logger.warning(
                    "Bridge registration auth failed from %s:%s bridge_id=%s",
                    *self._peer,
                    msg.bridge_id,
                )
                await self._send(
                    ErrorMessage(
                        request_id=msg.request_id,
                        code="auth_failed",
                        message="Bridge authentication failed.",
                    )
                )
                return

        bridge_conn_id = str(uuid.uuid4())
        self._is_bridge = True
        self._bridge_connection_id = bridge_conn_id
        self._process_id = msg.process_id

        logger.info(
            "[SERVICE] Bridge registered: bridge_id=%s pid=%d conn_id=%s",
            msg.bridge_id,
            msg.process_id,
            bridge_conn_id,
        )
        await self._send(
            BridgeRegisterAckMessage(
                request_id=msg.request_id,
                bridge_connection_id=bridge_conn_id,
                service_version=__version__,
            )
        )

    async def _handle_tool_call(self, msg: ToolCallMessage) -> None:
        """Execute a tool call forwarded from a bridge and return the result."""
        logger.debug(
            "[SERVICE] ToolCall tool=%s bridge_conn=%s request_id=%s",
            msg.tool_name,
            msg.bridge_connection_id,
            msg.request_id,
        )
        if self._tool_executor is None:
            result = None
            error = "tool_executor_unavailable"
        else:
            try:
                result = await self._tool_executor.execute(msg.tool_name, msg.arguments)
                error = ""
            except Exception as exc:
                result = None
                error = str(exc)

        try:
            await self._send(
                ToolResultMessage(
                    request_id=msg.request_id,
                    tool_name=msg.tool_name,
                    result=result,
                    error=error,
                )
            )
        except ValueError as exc:
            # Oversized result: reply with an error instead of leaving the bridge waiting.
            await self._send(
                ToolResultMessage(
                    request_id=msg.request_id,
                    tool_name=msg.tool_name,
                    result=None,
                    error=f"result_too_large: {exc}",
                )
            )

    async def _handle_hello(self, msg: HelloMessage) -> None:
        self._instance_id = msg.instance_id
        self._process_id = msg.process_id
        self._extension_version = msg.extension_version
        self._greeted = True
        logger.info(
            "Hello from instance=%s pid=%s version=%s",
            msg.instance_id,
            msg.process_id,
            msg.extension_version,
        )
        await self._send(
            HelloAckMessage(
                request_id=msg.request_id,
                server_version=__version__,
            )
        )

    async def _handle_heartbeat(self, msg: HeartbeatMessage) -> None:
        logger.debug("Heartbeat from %s:%s (request_id=%s)", *self._peer, msg.request_id)
        await self._send(HeartbeatAckMessage(request_id=msg.request_id))

    async def _handle_get_status(self, msg: GetStatusMessage) -> None:
        from rendereye_mcp.ipc.protocol import StatusResponseMessage

        logger.debug("GetStatus from %s:%s", *self._peer)
        await self._send(
            StatusResponseMessage(
                request_id=msg.request_id,
                process_id=self._process_id or 0,
                instance_id=self._instance_id or "",
                extension_version=self._extension_version or "",
                capture_path=None,
                connected=self._greeted,
            )
        )

    async def _handle_register_instance(self, msg: RegisterInstanceMessage) -> None:
        if self._conn_manager is not None:
            conn_id, error = self._conn_manager.register_connection(
                instance_id=msg.instance_id,
                process_id=msg.process_id,
                extension_version=msg.extension_version,
                renderdoc_version=msg.renderdoc_version,
                auth_token=msg.auth_token,
            )
            if conn_id is None:
                await self._send(
                    ErrorMessage(
                        request_id=msg.request_id,
                        code="auth_failed",
                        message=error,
                    )
                )
                return
            self._connection_id = conn_id
            self._conn_manager.register_send_callback(conn_id, self.send_request)
            await self._send(
                RegisterAckMessage(
                    request_id=msg.request_id,
                    connection_id=conn_id,
                    server_version=__version__,
                )
            )
        else:
            # No connection manager — accept but assign a placeholder
            self._connection_id = "unauthenticated"
            await self._send(
                RegisterAckMessage(
                    request_id=msg.request_id,
                    connection_id=self._connection_id,
                    server_version=__version__,
                )
            )

    async def _handle_gui_state_changed(self, msg: GuiStateChangedMessage) -> None:
        if msg.revision <= self._gui_state_revision:
            return  # stale
        self._gui_state_revision = msg.revision
        if self._conn_manager and self._connection_id:
            self._conn_manager.update_gui_state(
                connection_id=self._connection_id,
                revision=msg.revision,
                capture_loaded=msg.capture_loaded,
                capture_path=msg.capture_path,
                capture_state=msg.capture_state,
            )

    async def _handle_gui_state_response(self, msg: GuiStateResponseMessage) -> None:
        # Resolve pending future for this request_id
        fut = self._pending_requests.pop(msg.request_id, None)
        if fut and not fut.done():
            fut.set_result(msg)
        # Also update state if newer
        if msg.revision > self._gui_state_revision:
            self._gui_state_revision = msg.revision
            if self._conn_manager and self._connection_id:
                self._conn_manager.update_gui_state(
                    connection_id=self._connection_id,
                    revision=msg.revision,
                    capture_loaded=msg.capture_loaded,
                    capture_path=msg.capture_path,
                    capture_state=msg.capture_state,
                )

    async def _handle_gui_command_result(self, msg: GuiCommandResultMessage) -> None:
        fut = self._pending_requests.pop(msg.request_id, None)
        if fut and not fut.done():
            fut.set_result(msg)

    async def _handle_inspect_capture_result(self, msg: InspectCaptureResultMessage) -> None:
        fut = self._pending_requests.pop(msg.request_id, None)
        if fut and not fut.done():
            fut.set_result(msg)

    async def _handle_goodbye(self, msg: GoodbyeMessage) -> None:
        logger.info("Client %s:%s sent goodbye: %s", *self._peer, msg.reason)
        self._goodbye_received = True

    async def _send(self, msg) -> None:
        """Serialize and send a message to the client."""
        try:
            data = serialize(msg)
            self._writer.write(data)
            await self._writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            logger.debug("Send failed to %s:%s: %s", *self._peer, exc)

    async def _close(self) -> None:
        """Close the writer and notify the transport."""
        # Notify connection manager about disconnect
        if self._conn_manager is not None and self._connection_id is not None:
            self._conn_manager.disconnect_connection(self._connection_id)

        # Cancel any pending futures
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()

        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass
        if self._on_disconnect:
            self._on_disconnect(self)
        logger.info("Connection to %s:%s closed.", *self._peer)
