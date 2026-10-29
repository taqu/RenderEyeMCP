"""Tests for new Phase 3 message types in rendereye_mcp.ipc.protocol."""

from __future__ import annotations

import json

import pytest

from rendereye_mcp.ipc.protocol import (
    PROTOCOL_VERSION,
    ExecuteGuiCommandMessage,
    GetGuiStateMessage,
    GoodbyeMessage,
    GuiCommandResultMessage,
    GuiStateChangedMessage,
    GuiStateResponseMessage,
    RegisterAckMessage,
    RegisterInstanceMessage,
    deserialize,
    serialize,
)


def roundtrip(msg):
    data = serialize(msg)
    return deserialize(data)


class TestRegisterInstanceRoundtrip:
    def test_register_instance_roundtrip(self):
        msg = RegisterInstanceMessage(
            request_id="r1",
            instance_id="inst-abc",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token="deadbeef" * 8,
        )
        result = roundtrip(msg)
        assert isinstance(result, RegisterInstanceMessage)
        assert result.request_id == "r1"
        assert result.instance_id == "inst-abc"
        assert result.process_id == 1234
        assert result.extension_version == "0.1.0"
        assert result.renderdoc_version == "1.1.2"
        assert result.auth_token == "deadbeef" * 8
        assert result.type == "register_instance"

    def test_register_instance_protocol_version(self):
        msg = RegisterInstanceMessage(
            request_id="r2",
            instance_id="inst",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token="token",
        )
        data = serialize(msg)
        obj = json.loads(data.decode("utf-8"))
        assert obj["protocol_version"] == PROTOCOL_VERSION


class TestRegisterAckRoundtrip:
    def test_register_ack_roundtrip(self):
        msg = RegisterAckMessage(
            request_id="r1",
            connection_id="conn-uuid-123",
            server_version="0.1.0",
        )
        result = roundtrip(msg)
        assert isinstance(result, RegisterAckMessage)
        assert result.request_id == "r1"
        assert result.connection_id == "conn-uuid-123"
        assert result.server_version == "0.1.0"
        assert result.type == "register_ack"

    def test_register_ack_protocol_version(self):
        msg = RegisterAckMessage(
            request_id="r1",
            connection_id="c",
            server_version="0.1.0",
        )
        data = serialize(msg)
        obj = json.loads(data.decode("utf-8"))
        assert obj["protocol_version"] == PROTOCOL_VERSION


class TestGuiStateChangedRoundtrip:
    def test_gui_state_changed_loaded(self):
        msg = GuiStateChangedMessage(
            instance_id="inst-1",
            revision=5,
            capture_loaded=True,
            capture_path="/path/to/capture.rdc",
            capture_state="loaded",
        )
        result = roundtrip(msg)
        assert isinstance(result, GuiStateChangedMessage)
        assert result.instance_id == "inst-1"
        assert result.revision == 5
        assert result.capture_loaded is True
        assert result.capture_path == "/path/to/capture.rdc"
        assert result.capture_state == "loaded"
        assert result.type == "gui_state_changed"

    def test_gui_state_changed_unloaded(self):
        msg = GuiStateChangedMessage(
            instance_id="inst-2",
            revision=1,
            capture_loaded=False,
            capture_path=None,
            capture_state="unloaded",
        )
        result = roundtrip(msg)
        assert isinstance(result, GuiStateChangedMessage)
        assert result.capture_loaded is False
        assert result.capture_path is None


class TestGetGuiStateRoundtrip:
    def test_get_gui_state_roundtrip(self):
        msg = GetGuiStateMessage(request_id="gs-1")
        result = roundtrip(msg)
        assert isinstance(result, GetGuiStateMessage)
        assert result.request_id == "gs-1"
        assert result.type == "get_gui_state"


class TestGuiStateResponseRoundtrip:
    def test_gui_state_response_roundtrip(self):
        msg = GuiStateResponseMessage(
            request_id="gs-1",
            instance_id="inst-1",
            revision=3,
            capture_loaded=True,
            capture_path="/foo/bar.rdc",
            capture_state="loaded",
        )
        result = roundtrip(msg)
        assert isinstance(result, GuiStateResponseMessage)
        assert result.request_id == "gs-1"
        assert result.instance_id == "inst-1"
        assert result.revision == 3
        assert result.capture_loaded is True
        assert result.capture_path == "/foo/bar.rdc"
        assert result.capture_state == "loaded"

    def test_gui_state_response_no_capture(self):
        msg = GuiStateResponseMessage(
            request_id="gs-2",
            instance_id="inst-2",
            revision=0,
            capture_loaded=False,
            capture_path=None,
            capture_state="unloaded",
        )
        result = roundtrip(msg)
        assert result.capture_path is None


class TestExecuteGuiCommandRoundtrip:
    def test_execute_gui_command_roundtrip(self):
        msg = ExecuteGuiCommandMessage(
            request_id="cmd-1",
            command="open_capture",
            params={"path": "/some/capture.rdc"},
        )
        result = roundtrip(msg)
        assert isinstance(result, ExecuteGuiCommandMessage)
        assert result.request_id == "cmd-1"
        assert result.command == "open_capture"
        assert result.params == {"path": "/some/capture.rdc"}
        assert result.type == "execute_gui_command"

    def test_execute_gui_command_default_params(self):
        msg = ExecuteGuiCommandMessage(
            request_id="cmd-2",
            command="close_capture",
        )
        result = roundtrip(msg)
        assert result.params == {}

    def test_execute_gui_command_nested_params(self):
        msg = ExecuteGuiCommandMessage(
            request_id="cmd-3",
            command="focus_window",
            params={"window_id": "w-1", "nested": {"key": "value"}},
        )
        result = roundtrip(msg)
        assert result.params["nested"]["key"] == "value"


class TestGuiCommandResultRoundtrip:
    def test_gui_command_result_success(self):
        msg = GuiCommandResultMessage(
            request_id="cmd-1",
            command="open_capture",
            success=True,
            outcome="success",
        )
        result = roundtrip(msg)
        assert isinstance(result, GuiCommandResultMessage)
        assert result.request_id == "cmd-1"
        assert result.command == "open_capture"
        assert result.success is True
        assert result.outcome == "success"
        assert result.error == ""
        assert result.state_revision == 0
        assert result.type == "gui_command_result"

    def test_gui_command_result_failure(self):
        msg = GuiCommandResultMessage(
            request_id="cmd-2",
            command="focus_window",
            success=False,
            outcome="unsupported",
            error="focus_window not supported via extension",
            state_revision=7,
        )
        result = roundtrip(msg)
        assert result.success is False
        assert result.outcome == "unsupported"
        assert result.error == "focus_window not supported via extension"
        assert result.state_revision == 7


class TestGoodbyeRoundtrip:
    def test_goodbye_with_reason(self):
        msg = GoodbyeMessage(reason="extension_unregistered")
        result = roundtrip(msg)
        assert isinstance(result, GoodbyeMessage)
        assert result.reason == "extension_unregistered"
        assert result.type == "goodbye"

    def test_goodbye_default_reason(self):
        msg = GoodbyeMessage()
        result = roundtrip(msg)
        assert isinstance(result, GoodbyeMessage)
        assert result.reason == ""


class TestProtocolVersionPreserved:
    def test_register_instance_has_protocol_version(self):
        msg = RegisterInstanceMessage(
            request_id="r",
            instance_id="i",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token="t",
        )
        data = serialize(msg)
        obj = json.loads(data.decode("utf-8"))
        assert obj["protocol_version"] == PROTOCOL_VERSION

    def test_register_ack_has_protocol_version(self):
        msg = RegisterAckMessage(request_id="r", connection_id="c", server_version="0.1.0")
        data = serialize(msg)
        obj = json.loads(data.decode("utf-8"))
        assert obj["protocol_version"] == PROTOCOL_VERSION


class TestUnknownTypeRegression:
    def test_unknown_message_type_raises(self):
        with pytest.raises(ValueError, match="Unknown message type"):
            deserialize(json.dumps({"type": "totally_unknown", "request_id": "r"}))
