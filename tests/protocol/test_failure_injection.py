"""Failure injection tests for the IPC protocol.

Tests verify error paths at the serialize/deserialize layer and at the
connection handler layer using in-process socket pairs.
"""

from __future__ import annotations

import asyncio
import socket as _socket

import pytest

from rendereye_mcp.ipc.connection import ClientConnection
from rendereye_mcp.ipc.protocol import (
    ErrorMessage,
    GoodbyeMessage,
    deserialize,
    serialize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_stream_pair():
    """Return (reader_a, writer_a, reader_b, writer_b) via socketpair."""
    sock_a, sock_b = _socket.socketpair()
    reader_a, writer_a = await asyncio.open_connection(sock=sock_a)
    reader_b, writer_b = await asyncio.open_connection(sock=sock_b)
    return reader_a, writer_a, reader_b, writer_b


async def recv_msg(reader, timeout=2.0):
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    return deserialize(line)


async def send_raw(writer, raw: bytes):
    writer.write(raw)
    await writer.drain()


# ---------------------------------------------------------------------------
# Direct serialize/deserialize error path tests
# ---------------------------------------------------------------------------


def test_malformed_json_raises_value_error():
    """deserialize raises ValueError for non-JSON input."""
    with pytest.raises(ValueError, match="Invalid JSON"):
        deserialize(b"not-json\n")


def test_unknown_type_raises_value_error():
    """deserialize raises ValueError for an unknown message type."""
    with pytest.raises(ValueError, match="Unknown message type"):
        deserialize(b'{"type":"totally_unknown","request_id":"r"}\n')


def test_missing_type_raises_value_error():
    """deserialize raises ValueError when type field is absent."""
    with pytest.raises(ValueError, match="type"):
        deserialize(b'{"request_id":"r"}\n')


def test_json_array_raises_value_error():
    """deserialize raises ValueError when the message is a JSON array."""
    with pytest.raises(ValueError, match="JSON object"):
        deserialize(b'[1,2,3]\n')


def test_wrong_fields_raises_value_error():
    """deserialize raises ValueError when required fields are missing from message."""
    # HeartbeatMessage requires request_id; omit it
    with pytest.raises(ValueError):
        deserialize(b'{"type":"heartbeat"}\n')


# ---------------------------------------------------------------------------
# Connection-level tests using socket pairs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_json_returns_error_message():
    """Sending malformed JSON causes the server to reply with an ErrorMessage."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(reader=reader_b, writer=writer_b)
        task = asyncio.create_task(conn.run())

        # Send non-JSON
        await send_raw(writer_a, b"not-json\n")

        response = await recv_msg(reader_a)
        assert isinstance(response, ErrorMessage)
        assert response.code == "parse_error"
        assert "Invalid JSON" in response.message
    finally:
        writer_a.close()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_unknown_type_returns_error_message():
    """Sending an unknown message type causes the server to reply with ErrorMessage."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(reader=reader_b, writer=writer_b)
        task = asyncio.create_task(conn.run())

        # Send unknown type — deserialize raises ValueError("Unknown message type")
        # which the server catches and replies with parse_error
        await send_raw(writer_a, b'{"type":"totally_unknown","request_id":"r"}\n')

        response = await recv_msg(reader_a)
        assert isinstance(response, ErrorMessage)
        assert response.code == "parse_error"
    finally:
        writer_a.close()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_goodbye_closes_connection_cleanly():
    """Sending goodbye causes the server connection to close without error."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(reader=reader_b, writer=writer_b)
        task = asyncio.create_task(conn.run())

        await send_raw(writer_a, serialize(GoodbyeMessage(reason="test_done")))

        # Task should complete cleanly within a short timeout
        await asyncio.wait_for(task, timeout=2.0)
        assert conn._goodbye_received
    except asyncio.TimeoutError:
        pytest.fail("Connection did not close after goodbye within timeout")
    finally:
        writer_a.close()
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


@pytest.mark.asyncio
async def test_multiple_bad_messages_each_get_error():
    """Multiple malformed messages each receive a parse_error response."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(reader=reader_b, writer=writer_b)
        task = asyncio.create_task(conn.run())

        # Send two bad messages in sequence
        await send_raw(writer_a, b"bad-1\n")
        r1 = await recv_msg(reader_a)
        assert r1.code == "parse_error"

        await send_raw(writer_a, b"bad-2\n")
        r2 = await recv_msg(reader_a)
        assert r2.code == "parse_error"
    finally:
        writer_a.close()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_read_timeout_behavior_is_defined():
    """READ_TIMEOUT constant is defined and is a positive float."""
    from rendereye_mcp.ipc.connection import READ_TIMEOUT, READ_TIMEOUT_AUTHENTICATED

    assert isinstance(READ_TIMEOUT, float)
    assert READ_TIMEOUT > 0.0
    assert isinstance(READ_TIMEOUT_AUTHENTICATED, float)
    assert READ_TIMEOUT_AUTHENTICATED > READ_TIMEOUT
