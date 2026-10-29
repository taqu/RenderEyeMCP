"""ServiceClient — MCP bridge connection to the shared RenderEyeMCP service."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING, Optional

from rendereye_mcp import __version__
from rendereye_mcp.ipc.protocol import (
    MAX_MESSAGE_BYTES,
    BridgeRegisterAckMessage,
    BridgeRegisterMessage,
    GoodbyeMessage,
    HeartbeatAckMessage,
    HeartbeatMessage,
    ServiceInfoRequestMessage,
    ServiceInfoResponseMessage,
    ToolCallMessage,
    ToolResultMessage,
    deserialize,
    serialize,
)

if TYPE_CHECKING:
    from rendereye_mcp.config import Config

logger = logging.getLogger(__name__)

TOOL_CALL_TIMEOUT = 60.0
HEARTBEAT_INTERVAL = 15.0


class ServiceClient:
    """Connects an MCP bridge process to the shared RenderEyeMCP service.

    Handles:
    - Service identity verification (ServiceInfoRequest/Response)
    - Bridge registration with auth token
    - Tool call forwarding (ToolCallMessage / ToolResultMessage)
    - Heartbeat keep-alive
    """

    def __init__(self, config: "Config") -> None:
        self._config = config
        self._bridge_id = str(uuid.uuid4())
        self._bridge_connection_id: Optional[str] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._service_instance_id: Optional[str] = None

    @property
    def service_instance_id(self) -> Optional[str]:
        return self._service_instance_id

    @property
    def bridge_connection_id(self) -> Optional[str]:
        return self._bridge_connection_id

    async def connect(self) -> None:
        """Open TCP connection and perform full handshake with the service."""
        self._reader, self._writer = await asyncio.open_connection(
            self._config.ipc_host, self._config.ipc_port, limit=MAX_MESSAGE_BYTES + 1
        )

        # 1. Verify service identity — read/write directly (no receive_loop yet)
        info_resp = await self._handshake_send_recv(
            ServiceInfoRequestMessage(
                request_id=str(uuid.uuid4()),
                client_type="mcp_bridge",
            ),
            timeout=5.0,
        )
        if not isinstance(info_resp, ServiceInfoResponseMessage):
            raise ValueError(
                f"Service identity check failed: got {type(info_resp).__name__}"
            )
        if info_resp.service_name != "RenderEyeMCP":
            raise ValueError(
                f"Unknown service at port {self._config.ipc_port}: "
                f"service_name={info_resp.service_name!r}"
            )
        self._service_instance_id = info_resp.service_instance_id
        logger.debug(
            "[MCP] Service identified: version=%s instance=%s pid=%d",
            info_resp.service_version,
            info_resp.service_instance_id,
            info_resp.service_pid,
        )

        # 2. Read auth token from the file written by AuthManager
        from rendereye_mcp.ipc.authentication import AuthManager

        token_path = AuthManager().get_token_path()
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(
                f"Could not read auth token from {token_path}: {exc}"
            ) from exc

        # 3. Register this bridge process
        reg_resp = await self._handshake_send_recv(
            BridgeRegisterMessage(
                request_id=str(uuid.uuid4()),
                bridge_id=self._bridge_id,
                process_id=os.getpid(),
                bridge_version=__version__,
                auth_token=token,
            ),
            timeout=5.0,
        )
        if not isinstance(reg_resp, BridgeRegisterAckMessage):
            raise ValueError(
                f"Bridge registration failed: got {type(reg_resp).__name__}"
            )
        self._bridge_connection_id = reg_resp.bridge_connection_id
        logger.info(
            "[MCP] Bridge registered: bridge_conn=%s",
            self._bridge_connection_id,
        )

        # 4. Start background tasks
        self._receive_task = asyncio.create_task(
            self._receive_loop(), name="service-client-receive"
        )
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="service-client-heartbeat"
        )

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Forward an MCP tool call to the service and return the result."""
        if self._bridge_connection_id is None:
            return {"error": "not_connected"}

        resp = await self._send_and_wait(
            ToolCallMessage(
                request_id=str(uuid.uuid4()),
                bridge_connection_id=self._bridge_connection_id,
                tool_name=tool_name,
                arguments=arguments,
            ),
            timeout=TOOL_CALL_TIMEOUT,
        )
        if isinstance(resp, ToolResultMessage):
            if resp.error:
                return {"error": resp.error}
            return resp.result if resp.result is not None else {}
        return {"error": f"unexpected_response:{type(resp).__name__}"}

    async def close(self) -> None:
        """Gracefully disconnect from the service."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._writer:
            try:
                self._writer.write(serialize(GoodbyeMessage(reason="bridge_shutdown")))
                await self._writer.drain()
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """Continuously read responses from the service and resolve pending futures."""
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    logger.info("[MCP] Service connection closed (EOF)")
                    break
                try:
                    msg = deserialize(line)
                except ValueError as exc:
                    logger.warning("[MCP] Could not deserialize service message: %s", exc)
                    continue

                request_id = getattr(msg, "request_id", None)
                if request_id and request_id in self._pending:
                    fut = self._pending.pop(request_id)
                    if not fut.done():
                        fut.set_result(msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("[MCP] Receive loop error: %s", exc)
        finally:
            # Cancel all outstanding futures
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    async def _heartbeat_loop(self) -> None:
        """Periodically send heartbeats to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    resp = await self._send_and_wait(
                        HeartbeatMessage(request_id=str(uuid.uuid4())),
                        timeout=5.0,
                    )
                    if not isinstance(resp, HeartbeatAckMessage):
                        logger.warning("[MCP] Unexpected heartbeat response: %s", type(resp).__name__)
                except asyncio.TimeoutError:
                    logger.warning("[MCP] Heartbeat timed out — service may be unreachable")
                    break
                except Exception as exc:
                    logger.warning("[MCP] Heartbeat error: %s", exc)
                    break
        except asyncio.CancelledError:
            pass

    async def _handshake_send_recv(self, msg, timeout: float = 10.0):
        """Send a message and directly read the response during handshake.

        Used during connect() before the receive_loop is started.
        Reads the next line from the reader directly rather than waiting for
        a future to be resolved by the background receive loop.
        """
        data = serialize(msg)
        self._writer.write(data)
        await self._writer.drain()

        line = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
        if not line:
            raise ConnectionError("Service closed connection during handshake")
        return deserialize(line)

    async def _send_and_wait(self, msg, timeout: float = 10.0):
        """Serialize *msg*, send it, and wait for the response with the same request_id.

        Requires the receive_loop to be running (i.e., called after connect() completes).
        """
        request_id = getattr(msg, "request_id", None)
        if request_id is None:
            raise ValueError("Message has no request_id")

        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending[request_id] = fut

        data = serialize(msg)
        self._writer.write(data)
        await self._writer.drain()

        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise
