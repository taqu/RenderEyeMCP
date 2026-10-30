"""Tests for binary and large payload handling in the protocol."""

from __future__ import annotations

import base64

import pytest

from rendereye_mcp.ipc.protocol import (
    MAX_MESSAGE_BYTES,
    ToolResultMessage,
    deserialize,
    serialize,
)


def test_base64_in_result():
    """ToolResultMessage with base64-encoded binary data round-trips field for field."""
    raw_bytes = bytes([0x00, 0x01, 0x02, 0xFF])
    b64 = base64.b64encode(raw_bytes).decode("ascii")  # "AAEC/w=="

    msg = ToolResultMessage(
        request_id="bin-1",
        tool_name="get_texture_image",
        result={"data": b64, "encoding": "base64", "size": 4},
        error="",
    )
    data = serialize(msg)
    decoded = deserialize(data)

    assert decoded.request_id == "bin-1"
    assert decoded.result["data"] == "AAEC/w=="
    assert decoded.result["encoding"] == "base64"
    assert decoded.result["size"] == 4

    # Verify the base64 decodes back to the original bytes
    assert base64.b64decode(decoded.result["data"]) == raw_bytes


def test_result_with_nested_dict():
    """ToolResultMessage with a complex nested result dict round-trips correctly."""
    nested = {
        "pipeline": {
            "vertex_shader": {"name": "vs_main", "stage": "vertex"},
            "pixel_shader": {"name": "ps_main", "stage": "pixel"},
        },
        "draw_calls": [1, 2, 3],
        "flags": {"depth_test": True, "blend": False},
    }
    msg = ToolResultMessage(
        request_id="nested-1",
        tool_name="get_pipeline_state",
        result=nested,
        error="",
    )
    data = serialize(msg)
    decoded = deserialize(data)

    assert decoded.result["pipeline"]["vertex_shader"]["name"] == "vs_main"
    assert decoded.result["draw_calls"] == [1, 2, 3]
    assert decoded.result["flags"]["depth_test"] is True
    assert decoded.result["flags"]["blend"] is False


def test_error_string_preserved():
    """ToolResultMessage with a non-ASCII error message preserves the string."""
    error_msg = "Fehler: Ressource nicht gefunden \u2014 \u30ea\u30bd\u30fc\u30b9\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093"
    msg = ToolResultMessage(
        request_id="err-1",
        tool_name="dummy",
        result=None,
        error=error_msg,
    )
    data = serialize(msg)
    decoded = deserialize(data)

    assert decoded.error == error_msg
    assert decoded.result is None


def test_large_result_accepted():
    """ToolResultMessage with ~100 KB string result serializes within 16 MiB limit."""
    large_str = "A" * (100 * 1024)  # 100 KB
    msg = ToolResultMessage(
        request_id="large-1",
        tool_name="dummy",
        result=large_str,
        error="",
    )
    data = serialize(msg)
    assert len(data) < MAX_MESSAGE_BYTES

    decoded = deserialize(data)
    assert len(decoded.result) == 100 * 1024


def test_oversized_message_rejected():
    """serialize() raises ValueError when the message exceeds MAX_MESSAGE_BYTES."""
    # A result string of MAX_MESSAGE_BYTES characters will exceed the limit once
    # the JSON envelope and escaping are added.
    huge_result = "Z" * MAX_MESSAGE_BYTES
    msg = ToolResultMessage(
        request_id="oversized-1",
        tool_name="dummy",
        result=huge_result,
        error="",
    )
    with pytest.raises(ValueError, match="exceeds"):
        serialize(msg)


def test_result_none_serializes_null():
    """ToolResultMessage with result=None serializes as JSON null."""
    msg = ToolResultMessage(
        request_id="null-1",
        tool_name="dummy",
        result=None,
        error="some error",
    )
    data = serialize(msg)
    assert b'"result":null' in data

    decoded = deserialize(data)
    assert decoded.result is None


def test_result_list_of_dicts():
    """ToolResultMessage with a list of dicts as result round-trips correctly."""
    sessions = [
        {"id": "sess-1", "pid": 1234, "capture": "/foo.rdc"},
        {"id": "sess-2", "pid": 5678, "capture": None},
    ]
    msg = ToolResultMessage(
        request_id="list-1",
        tool_name="list_renderdoc_sessions",
        result=sessions,
        error="",
    )
    data = serialize(msg)
    decoded = deserialize(data)

    assert len(decoded.result) == 2
    assert decoded.result[0]["pid"] == 1234
    assert decoded.result[1]["capture"] is None
