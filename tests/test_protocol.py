"""Tests for rendereye_mcp.ipc.protocol."""

from __future__ import annotations

import json

import pytest

from rendereye_mcp.ipc.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    ErrorMessage,
    GetStatusMessage,
    HeartbeatAckMessage,
    HeartbeatMessage,
    HelloAckMessage,
    HelloMessage,
    StatusResponseMessage,
    deserialize,
    serialize,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def roundtrip(msg):
    """Serialize then deserialize a message and return the result."""
    data = serialize(msg)
    return deserialize(data)


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_hello_roundtrip(self):
        msg = HelloMessage(
            request_id="r1",
            instance_id="inst-abc",
            process_id=1234,
            extension_version="0.1.0",
        )
        result = roundtrip(msg)
        assert isinstance(result, HelloMessage)
        assert result.request_id == "r1"
        assert result.instance_id == "inst-abc"
        assert result.process_id == 1234
        assert result.extension_version == "0.1.0"
        assert result.type == "hello"
        assert result.protocol_version == PROTOCOL_VERSION

    def test_hello_ack_roundtrip(self):
        msg = HelloAckMessage(request_id="r2", server_version="0.1.0")
        result = roundtrip(msg)
        assert isinstance(result, HelloAckMessage)
        assert result.request_id == "r2"
        assert result.server_version == "0.1.0"

    def test_heartbeat_roundtrip(self):
        msg = HeartbeatMessage(request_id="hb-1")
        result = roundtrip(msg)
        assert isinstance(result, HeartbeatMessage)
        assert result.request_id == "hb-1"

    def test_heartbeat_ack_roundtrip(self):
        msg = HeartbeatAckMessage(request_id="hb-1")
        result = roundtrip(msg)
        assert isinstance(result, HeartbeatAckMessage)
        assert result.request_id == "hb-1"

    def test_get_status_roundtrip(self):
        msg = GetStatusMessage(request_id="gs-1")
        result = roundtrip(msg)
        assert isinstance(result, GetStatusMessage)
        assert result.request_id == "gs-1"

    def test_status_response_roundtrip(self):
        msg = StatusResponseMessage(
            request_id="sr-1",
            process_id=5678,
            instance_id="inst-xyz",
            extension_version="0.1.0",
            capture_path="/tmp/capture.rdc",
            connected=True,
        )
        result = roundtrip(msg)
        assert isinstance(result, StatusResponseMessage)
        assert result.process_id == 5678
        assert result.capture_path == "/tmp/capture.rdc"
        assert result.connected is True

    def test_status_response_no_capture_roundtrip(self):
        msg = StatusResponseMessage(
            request_id="sr-2",
            process_id=0,
            instance_id="",
            extension_version="0.1.0",
            capture_path=None,
            connected=False,
        )
        result = roundtrip(msg)
        assert result.capture_path is None
        assert result.connected is False

    def test_error_roundtrip(self):
        msg = ErrorMessage(request_id="e-1", code="test_error", message="Something failed")
        result = roundtrip(msg)
        assert isinstance(result, ErrorMessage)
        assert result.code == "test_error"
        assert result.message == "Something failed"


# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------


class TestProtocolVersion:
    def test_hello_contains_protocol_version(self):
        msg = HelloMessage(
            request_id="pv-1",
            instance_id="inst",
            process_id=1,
            extension_version="0.1.0",
        )
        data = serialize(msg)
        obj = json.loads(data.decode("utf-8"))
        assert obj["protocol_version"] == PROTOCOL_VERSION

    def test_deserialize_ignores_higher_protocol_version(self):
        """We accept messages with a higher protocol_version (forward compat)."""
        raw = json.dumps({
            "type": "heartbeat",
            "protocol_version": 99,
            "request_id": "pv-2",
        })
        result = deserialize(raw)
        assert isinstance(result, HeartbeatMessage)

    def test_deserialize_missing_protocol_version_still_works(self):
        raw = json.dumps({"type": "heartbeat", "request_id": "pv-3"})
        result = deserialize(raw)
        assert isinstance(result, HeartbeatMessage)


# ---------------------------------------------------------------------------
# Oversized message rejection
# ---------------------------------------------------------------------------


class TestOversizeRejection:
    def test_serialize_oversized_raises(self):
        """serialize() must raise ValueError for messages > 64 KB."""
        msg = ErrorMessage(
            request_id="big",
            code="test",
            message="x" * (MAX_MESSAGE_BYTES + 1),
        )
        with pytest.raises(ValueError, match="MAX_MESSAGE_BYTES"):
            serialize(msg)

    def test_deserialize_oversized_bytes_raises(self):
        """deserialize() must raise ValueError for raw bytes > 64 KB."""
        oversized = b"x" * (MAX_MESSAGE_BYTES + 1)
        with pytest.raises(ValueError, match="MAX_MESSAGE_BYTES"):
            deserialize(oversized)


# ---------------------------------------------------------------------------
# Invalid JSON
# ---------------------------------------------------------------------------


class TestInvalidInput:
    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            deserialize("not json at all")

    def test_json_array_raises(self):
        with pytest.raises(ValueError, match="JSON object"):
            deserialize("[1, 2, 3]")

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="type"):
            deserialize(json.dumps({"request_id": "r1"}))

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown message type"):
            deserialize(json.dumps({"type": "unknown_xyz", "request_id": "r1"}))

    def test_missing_required_field_raises(self):
        """HelloMessage requires instance_id, process_id, extension_version."""
        with pytest.raises(ValueError, match="Cannot construct HelloMessage"):
            deserialize(json.dumps({"type": "hello", "request_id": "r1"}))
