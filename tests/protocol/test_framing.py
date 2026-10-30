"""Tests for TCP framing edge cases.

These tests verify the newline-delimited JSON framing behaviour using
in-process socket pairs (no real network required).
"""

from __future__ import annotations

import asyncio
import socket as _socket

import pytest

from rendereye_mcp.ipc.protocol import (
    MAX_MESSAGE_BYTES,
    HeartbeatMessage,
    StatusResponseMessage,
    ToolCallMessage,
    ToolResultMessage,
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


async def read_line(reader, timeout=2.0) -> bytes:
    return await asyncio.wait_for(reader.readline(), timeout=timeout)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_message():
    """One serialize() call produces exactly one readline-able message."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        msg = HeartbeatMessage(request_id="test-1")
        data = serialize(msg)
        writer_a.write(data)
        await writer_a.drain()

        line = await read_line(reader_b)
        decoded = deserialize(line)
        assert decoded.type == "heartbeat"
        assert decoded.request_id == "test-1"
    finally:
        writer_a.close()
        writer_b.close()


@pytest.mark.asyncio
async def test_multiple_messages_in_buffer():
    """Two messages written at once can each be read by separate readline calls."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        msg1 = HeartbeatMessage(request_id="hb-1")
        msg2 = HeartbeatMessage(request_id="hb-2")
        # Write both without awaiting between
        writer_a.write(serialize(msg1) + serialize(msg2))
        await writer_a.drain()

        line1 = await read_line(reader_b)
        line2 = await read_line(reader_b)

        decoded1 = deserialize(line1)
        decoded2 = deserialize(line2)

        assert decoded1.request_id == "hb-1"
        assert decoded2.request_id == "hb-2"
    finally:
        writer_a.close()
        writer_b.close()


@pytest.mark.asyncio
async def test_partial_write_reassembly():
    """Writing a message in two halves still produces a complete readline."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        msg = HeartbeatMessage(request_id="partial-1")
        data = serialize(msg)

        mid = len(data) // 2
        first_half = data[:mid]
        second_half = data[mid:]

        writer_a.write(first_half)
        await writer_a.drain()
        # Small pause to ensure partial delivery
        await asyncio.sleep(0.01)
        writer_a.write(second_half)
        await writer_a.drain()

        line = await read_line(reader_b)
        decoded = deserialize(line)
        assert decoded.request_id == "partial-1"
    finally:
        writer_a.close()
        writer_b.close()


@pytest.mark.asyncio
async def test_message_at_max_size():
    """A message near MAX_MESSAGE_BYTES is accepted by serialize/deserialize."""
    # Build a ToolResultMessage whose result string nearly fills the limit.
    # Reserve space for the fixed JSON envelope (~120 bytes).
    overhead = 150
    payload_size = MAX_MESSAGE_BYTES - overhead
    msg = ToolResultMessage(
        request_id="big-1",
        tool_name="dummy",
        result="x" * payload_size,
        error="",
    )
    data = serialize(msg)
    assert len(data) <= MAX_MESSAGE_BYTES

    decoded = deserialize(data)
    assert decoded.request_id == "big-1"
    assert len(decoded.result) == payload_size


def test_message_exceeds_max_size():
    """A raw line longer than MAX_MESSAGE_BYTES raises ValueError in deserialize."""
    # Craft a raw byte string that exceeds the limit (no valid JSON needed).
    oversized = b"x" * (MAX_MESSAGE_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds"):
        deserialize(oversized)


def test_empty_line_rejected():
    """Deserializing an empty byte string raises ValueError."""
    with pytest.raises(ValueError):
        deserialize(b"")


def test_empty_json_object_missing_type():
    """Deserializing {} raises ValueError because 'type' is missing."""
    with pytest.raises(ValueError, match="type"):
        deserialize(b"{}")


def test_unicode_preserved():
    """A message with Unicode content round-trips correctly."""
    msg = ToolResultMessage(
        request_id="uni-1",
        tool_name="dummy",
        result={"text": "\u4e2d\u6587\u5185\u5bb9\u3068\u65e5\u672c\u8a9e"},
        error="",
    )
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.result["text"] == "\u4e2d\u6587\u5185\u5bb9\u3068\u65e5\u672c\u8a9e"


def test_null_capture_path():
    """StatusResponseMessage with capture_path=None serializes null and deserializes back."""
    msg = StatusResponseMessage(
        request_id="status-1",
        process_id=1000,
        instance_id="inst-abc",
        extension_version="1.0.0",
        capture_path=None,
        connected=True,
    )
    data = serialize(msg)
    assert b'"capture_path":null' in data

    decoded = deserialize(data)
    assert decoded.capture_path is None


def test_serialize_raises_on_oversized():
    """serialize() raises ValueError when the encoded message exceeds MAX_MESSAGE_BYTES."""
    # Build a message that is definitely over the limit.
    huge = ToolResultMessage(
        request_id="huge-1",
        tool_name="dummy",
        result="y" * MAX_MESSAGE_BYTES,
        error="",
    )
    with pytest.raises(ValueError, match="exceeds"):
        serialize(huge)
