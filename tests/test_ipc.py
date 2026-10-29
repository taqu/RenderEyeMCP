"""Tests for IPC server transport and connection handling."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from rendereye_mcp.config import Config
from rendereye_mcp.ipc.protocol import (
    HeartbeatMessage,
    HelloMessage,
    deserialize,
    serialize,
)
from rendereye_mcp.ipc.transport import IPCTransport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def free_port():
    """Return a free TCP port on the loopback interface."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def config(free_port):
    return Config(ipc_port=free_port)


@pytest_asyncio.fixture
async def transport(config):
    t = IPCTransport(config)
    await t.start()
    yield t
    await t.stop()


# ---------------------------------------------------------------------------
# Helper coroutines
# ---------------------------------------------------------------------------


async def connect(config):
    """Open a raw asyncio connection to the IPC transport."""
    reader, writer = await asyncio.open_connection(config.ipc_host, config.ipc_port)
    return reader, writer


async def send_msg(writer, msg):
    data = serialize(msg)
    writer.write(data)
    await writer.drain()


async def recv_line(reader, timeout=2.0):
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    return deserialize(line)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_starts_and_accepts_connections(transport, config):
    """The transport should be running and accept at least one TCP connection."""
    assert transport.is_running
    reader, writer = await connect(config)
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_hello_handshake(transport, config):
    """Client can send hello and receive hello_ack."""
    reader, writer = await connect(config)
    try:
        hello = HelloMessage(
            request_id="test-req-1",
            instance_id="test-inst",
            process_id=9999,
            extension_version="0.1.0",
        )
        await send_msg(writer, hello)
        ack = await recv_line(reader)
        assert ack.type == "hello_ack"
        assert ack.request_id == "test-req-1"
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_heartbeat_exchange(transport, config):
    """Client can exchange heartbeats after the hello handshake."""
    reader, writer = await connect(config)
    try:
        # Handshake first
        await send_msg(
            writer,
            HelloMessage(
                request_id="hb-hello",
                instance_id="inst-hb",
                process_id=1,
                extension_version="0.1.0",
            ),
        )
        await recv_line(reader)  # consume hello_ack

        # Send heartbeat
        await send_msg(writer, HeartbeatMessage(request_id="hb-1"))
        ack = await recv_line(reader)
        assert ack.type == "heartbeat_ack"
        assert ack.request_id == "hb-1"
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_multiple_simultaneous_clients(transport, config):
    """The server must handle multiple clients concurrently."""
    clients = []
    n = 3
    try:
        for i in range(n):
            reader, writer = await connect(config)
            clients.append((reader, writer))

        # Allow the event loop to process connections
        await asyncio.sleep(0.05)

        # All clients do a hello handshake
        for i, (reader, writer) in enumerate(clients):
            await send_msg(
                writer,
                HelloMessage(
                    request_id=f"req-{i}",
                    instance_id=f"inst-{i}",
                    process_id=1000 + i,
                    extension_version="0.1.0",
                ),
            )

        for i, (reader, writer) in enumerate(clients):
            ack = await recv_line(reader)
            assert ack.type == "hello_ack"
            assert ack.request_id == f"req-{i}"

        await asyncio.sleep(0.05)
        assert transport.connection_count >= n
    finally:
        for reader, writer in clients:
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_client_disconnect_detected(transport, config):
    """The transport should decrement connection count on disconnect."""
    reader, writer = await connect(config)

    # Handshake
    await send_msg(
        writer,
        HelloMessage(
            request_id="dc-req",
            instance_id="dc-inst",
            process_id=42,
            extension_version="0.1.0",
        ),
    )
    await recv_line(reader)  # consume hello_ack

    count_before = transport.connection_count
    writer.close()
    await writer.wait_closed()

    # Give the server coroutine time to detect the EOF
    for _ in range(20):
        await asyncio.sleep(0.05)
        if transport.connection_count < count_before:
            break

    assert transport.connection_count < count_before


@pytest.mark.asyncio
async def test_invalid_json_returns_error(transport, config):
    """Sending garbage JSON should result in an error message."""
    reader, writer = await connect(config)
    try:
        writer.write(b"this is not json\n")
        await writer.drain()
        response = await recv_line(reader)
        assert response.type == "error"
        assert response.code == "parse_error"
    finally:
        writer.close()
        await writer.wait_closed()
