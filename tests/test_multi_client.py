"""Multi-process MCP client tests for Phase 6.

Tests the shared IPC service architecture:
- Service starts and accepts bridge connections
- Multiple bridge clients can connect simultaneously
- Port 37020 is bound only once (by the service)
- Tool calls are forwarded and results returned
- Bridge disconnect does not kill the service
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rendereye_mcp.ipc.protocol import (
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_config(port: int):
    """Create a Config-like object pointing at a specific port."""
    cfg = MagicMock()
    cfg.ipc_host = "127.0.0.1"
    cfg.ipc_port = port
    return cfg


async def _start_transport(port: int, tool_executor=None, service_instance_id="test-instance"):
    """Start an IPCTransport on a free port and return it."""
    from rendereye_mcp.ipc.transport import IPCTransport

    config = _make_config(port)
    auth_mock = MagicMock()
    auth_mock.validate.return_value = True

    conn_manager_mock = MagicMock()
    conn_manager_mock._auth = auth_mock

    transport = IPCTransport(
        config,
        conn_manager=conn_manager_mock,
        tool_executor=tool_executor,
        service_instance_id=service_instance_id,
    )
    await transport.start()
    return transport, config


async def _raw_connect(host: str, port: int):
    """Open a raw TCP connection; return (reader, writer)."""
    return await asyncio.open_connection(host, port)


async def _raw_send(writer, msg) -> None:
    writer.write(serialize(msg))
    await writer.drain()


async def _raw_recv(reader, timeout: float = 2.0):
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    return deserialize(line)


async def _full_bridge_handshake(config, token: str = "testtoken"):
    """Open a connection, perform service-info + bridge-register, return (reader, writer, conn_id)."""
    reader, writer = await _raw_connect(config.ipc_host, config.ipc_port)

    # Step 1: service info
    req_id = str(uuid.uuid4())
    await _raw_send(writer, ServiceInfoRequestMessage(request_id=req_id, client_type="mcp_bridge"))
    resp = await _raw_recv(reader)
    assert isinstance(resp, ServiceInfoResponseMessage), f"Expected ServiceInfoResponseMessage, got {type(resp).__name__}"
    assert resp.service_name == "RenderEyeMCP"

    # Step 2: bridge register
    reg_id = str(uuid.uuid4())
    await _raw_send(
        writer,
        BridgeRegisterMessage(
            request_id=reg_id,
            bridge_id=str(uuid.uuid4()),
            process_id=1234,
            bridge_version="1.0.0",
            auth_token=token,
        ),
    )
    ack = await _raw_recv(reader)
    assert isinstance(ack, BridgeRegisterAckMessage), f"Expected BridgeRegisterAckMessage, got {type(ack).__name__}"
    return reader, writer, ack.bridge_connection_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_bridge_client():
    """One bridge client can connect to the service."""
    port = _free_port()
    transport, config = await _start_transport(port)
    try:
        reader, writer, conn_id = await _full_bridge_handshake(config)
        assert conn_id is not None
        assert len(conn_id) > 0
        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_two_concurrent_bridge_clients():
    """Two bridge clients can connect to the same service simultaneously."""
    port = _free_port()
    transport, config = await _start_transport(port)
    try:
        reader_a, writer_a, conn_id_a = await _full_bridge_handshake(config)
        reader_b, writer_b, conn_id_b = await _full_bridge_handshake(config)

        # Both connections should have distinct IDs
        assert conn_id_a != conn_id_b

        # Both should still be functional — send heartbeats
        for reader, writer in [(reader_a, writer_a), (reader_b, writer_b)]:
            hb_id = str(uuid.uuid4())
            await _raw_send(writer, HeartbeatMessage(request_id=hb_id))
            hb_resp = await _raw_recv(reader)
            assert isinstance(hb_resp, HeartbeatAckMessage)
            assert hb_resp.request_id == hb_id

        writer_a.close()
        await writer_a.wait_closed()
        writer_b.close()
        await writer_b.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_only_one_port_binding():
    """Only one server can bind a given port; the second attempt fails with OSError."""
    port = _free_port()
    transport1, config = await _start_transport(port)
    try:
        from rendereye_mcp.ipc.transport import IPCTransport

        config2 = _make_config(port)
        transport2 = IPCTransport(config2)
        with pytest.raises(OSError):
            await transport2.start()
    finally:
        await transport1.stop()


@pytest.mark.asyncio
async def test_tool_forwarding():
    """Bridge client tool calls return results from the service's ToolExecutor."""
    port = _free_port()
    expected_result = {"server_name": "RenderEyeMCP", "ok": True}

    # Create a mock tool executor
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=expected_result)

    transport, config = await _start_transport(port, tool_executor=mock_executor)
    try:
        reader, writer, conn_id = await _full_bridge_handshake(config)

        tool_req_id = str(uuid.uuid4())
        await _raw_send(
            writer,
            ToolCallMessage(
                request_id=tool_req_id,
                bridge_connection_id=conn_id,
                tool_name="server_status",
                arguments={},
            ),
        )
        result_msg = await _raw_recv(reader, timeout=5.0)
        assert isinstance(result_msg, ToolResultMessage), f"Got {type(result_msg).__name__}"
        assert result_msg.request_id == tool_req_id
        assert result_msg.tool_name == "server_status"
        assert result_msg.result == expected_result
        assert result_msg.error == ""

        mock_executor.execute.assert_called_once_with("server_status", {})

        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_client_disconnect_preserves_service():
    """Service stays accepting connections after a bridge client disconnects."""
    port = _free_port()
    transport, config = await _start_transport(port)
    try:
        # Connect and disconnect first client
        reader_a, writer_a, conn_id_a = await _full_bridge_handshake(config)
        await _raw_send(writer_a, GoodbyeMessage(reason="test_done"))
        writer_a.close()
        await writer_a.wait_closed()

        # Give the server time to process the disconnect
        await asyncio.sleep(0.05)

        # Second client should still be able to connect
        reader_b, writer_b, conn_id_b = await _full_bridge_handshake(config)
        assert conn_id_b is not None

        writer_b.close()
        await writer_b.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_service_info_before_registration():
    """ServiceInfoRequest must be answered even without prior hello/registration."""
    port = _free_port()
    service_instance_id = str(uuid.uuid4())
    transport, config = await _start_transport(
        port, service_instance_id=service_instance_id
    )
    try:
        reader, writer = await _raw_connect(config.ipc_host, config.ipc_port)
        req_id = str(uuid.uuid4())
        await _raw_send(
            writer,
            ServiceInfoRequestMessage(request_id=req_id, client_type="probe"),
        )
        resp = await _raw_recv(reader)
        assert isinstance(resp, ServiceInfoResponseMessage)
        assert resp.service_name == "RenderEyeMCP"
        assert resp.service_instance_id == service_instance_id
        assert resp.request_id == req_id

        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_tool_call_without_bridge_registration_rejected():
    """A ToolCallMessage from an unregistered connection gets an error response."""
    port = _free_port()
    transport, config = await _start_transport(port)
    try:
        reader, writer = await _raw_connect(config.ipc_host, config.ipc_port)

        tool_req_id = str(uuid.uuid4())
        await _raw_send(
            writer,
            ToolCallMessage(
                request_id=tool_req_id,
                bridge_connection_id="fake-id",
                tool_name="server_status",
                arguments={},
            ),
        )
        from rendereye_mcp.ipc.protocol import ErrorMessage
        resp = await _raw_recv(reader, timeout=3.0)
        assert isinstance(resp, ErrorMessage)
        assert resp.code == "not_a_bridge"

        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_heartbeat_round_trip():
    """Heartbeat messages from a registered bridge receive HeartbeatAck."""
    port = _free_port()
    transport, config = await _start_transport(port)
    try:
        reader, writer, conn_id = await _full_bridge_handshake(config)

        for _ in range(3):
            hb_id = str(uuid.uuid4())
            await _raw_send(writer, HeartbeatMessage(request_id=hb_id))
            resp = await _raw_recv(reader)
            assert isinstance(resp, HeartbeatAckMessage)
            assert resp.request_id == hb_id

        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


def test_service_status_reports_stale_ready_file(tmp_path, monkeypatch, capsys):
    import json

    from rendereye_mcp.service import main as service_main

    ready = tmp_path / "rendereye_mcp_service.json"
    ready.write_text(json.dumps({"pid": 999999, "host": "127.0.0.1", "port": 1}))
    monkeypatch.setattr(service_main, "SERVICE_READY_FILE", ready)
    monkeypatch.setattr(service_main, "_is_service_running", lambda config: False)
    service_main._show_status()
    assert "stale ready file" in capsys.readouterr().out
