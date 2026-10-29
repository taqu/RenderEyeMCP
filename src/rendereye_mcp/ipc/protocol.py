"""JSON message types for the RenderEyeMCP IPC protocol.

Messages are newline-delimited JSON objects (one JSON object per line).
The protocol uses a ``type`` field to distinguish message kinds and
``request_id`` for correlating requests with responses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Maximum permitted message size (bytes, enforced by transport).
# Large enough for base64 PNG results from get_texture_image (max_dim 1024 by default).
MAX_MESSAGE_BYTES: int = 16 * 1024 * 1024  # 16 MiB

# Current protocol version advertised in HelloMessage / HelloAckMessage.
PROTOCOL_VERSION: int = 1


# ---------------------------------------------------------------------------
# Message dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HelloMessage:
    """Sent by the RenderDoc extension immediately after connecting."""

    request_id: str
    instance_id: str
    process_id: int
    extension_version: str
    type: str = field(default="hello", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class HelloAckMessage:
    """Server acknowledgement of a HelloMessage."""

    request_id: str
    server_version: str
    type: str = field(default="hello_ack", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class HeartbeatMessage:
    """Periodic keep-alive sent by the extension."""

    request_id: str
    type: str = field(default="heartbeat", init=False)


@dataclass
class HeartbeatAckMessage:
    """Server acknowledgement of a HeartbeatMessage."""

    request_id: str
    type: str = field(default="heartbeat_ack", init=False)


@dataclass
class GetStatusMessage:
    """Request current extension/capture status."""

    request_id: str
    type: str = field(default="get_status", init=False)


@dataclass
class StatusResponseMessage:
    """Extension response to a GetStatusMessage."""

    request_id: str
    process_id: int
    instance_id: str
    extension_version: str
    capture_path: Optional[str]
    connected: bool
    type: str = field(default="status_response", init=False)


@dataclass
class ErrorMessage:
    """Generic error response."""

    request_id: str
    code: str
    message: str
    type: str = field(default="error", init=False)


@dataclass
class RegisterInstanceMessage:
    """Extension registers itself with the server after hello."""

    request_id: str
    instance_id: str
    process_id: int
    extension_version: str
    renderdoc_version: str
    auth_token: str
    type: str = field(default="register_instance", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class RegisterAckMessage:
    """Server acknowledgement of a RegisterInstanceMessage."""

    request_id: str
    connection_id: str
    server_version: str
    type: str = field(default="register_ack", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class GuiStateChangedMessage:
    """Extension pushes GUI state change to server."""

    instance_id: str
    revision: int
    capture_loaded: bool
    capture_path: Optional[str]
    capture_state: str
    type: str = field(default="gui_state_changed", init=False)


@dataclass
class GetGuiStateMessage:
    """Server requests current GUI state snapshot from extension."""

    request_id: str
    type: str = field(default="get_gui_state", init=False)


@dataclass
class GuiStateResponseMessage:
    """Extension responds to get_gui_state with full state snapshot."""

    request_id: str
    instance_id: str
    revision: int
    capture_loaded: bool
    capture_path: Optional[str]
    capture_state: str
    type: str = field(default="gui_state_response", init=False)


@dataclass
class ExecuteGuiCommandMessage:
    """Server requests extension to execute a GUI command."""

    request_id: str
    command: str
    params: dict = field(default_factory=dict)
    type: str = field(default="execute_gui_command", init=False)


@dataclass
class GuiCommandResultMessage:
    """Extension reports result of a GUI command."""

    request_id: str
    command: str
    success: bool
    outcome: str
    error: str = ""
    state_revision: int = 0
    type: str = field(default="gui_command_result", init=False)


@dataclass
class GoodbyeMessage:
    """Sent by either side before intentional disconnection."""

    reason: str = ""
    type: str = field(default="goodbye", init=False)


# ---------------------------------------------------------------------------
# Phase 6: Bridge / Service message types
# ---------------------------------------------------------------------------


@dataclass
class ServiceInfoRequestMessage:
    """Sent by a bridge client to identify the service before registration."""

    request_id: str
    client_type: str = "unknown"
    type: str = field(default="service_info_request", init=False)


@dataclass
class ServiceInfoResponseMessage:
    """Service response with identity information."""

    request_id: str
    service_name: str
    service_version: str
    service_pid: int
    service_instance_id: str
    type: str = field(default="service_info_response", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class BridgeRegisterMessage:
    """MCP bridge process registers itself with the shared service."""

    request_id: str
    bridge_id: str
    process_id: int
    bridge_version: str
    auth_token: str
    type: str = field(default="bridge_register", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class BridgeRegisterAckMessage:
    """Service acknowledges bridge registration."""

    request_id: str
    bridge_connection_id: str
    service_version: str
    type: str = field(default="bridge_register_ack", init=False)
    protocol_version: int = field(default=PROTOCOL_VERSION, init=False)


@dataclass
class ToolCallMessage:
    """Bridge forwards an MCP tool call to the service for execution."""

    request_id: str
    bridge_connection_id: str
    tool_name: str
    arguments: dict = field(default_factory=dict)
    type: str = field(default="tool_call", init=False)


@dataclass
class ToolResultMessage:
    """Service returns the result of a tool call to the bridge."""

    request_id: str
    tool_name: str
    result: Any
    error: str = ""
    type: str = field(default="tool_result", init=False)


# ---------------------------------------------------------------------------
# Phase 8: Capture inspection message types
# ---------------------------------------------------------------------------


@dataclass
class InspectCaptureRequestMessage:
    """Server requests capture inspection from the extension."""

    request_id: str
    operation: str
    params: dict = field(default_factory=dict)
    type: str = field(default="inspect_capture", init=False)


@dataclass
class InspectCaptureResultMessage:
    """Extension returns inspection result to the server."""

    request_id: str
    operation: str
    result: Any
    error: str = ""
    type: str = field(default="inspect_capture_result", init=False)


# Mapping from ``type`` string to dataclass for deserialization.
_TYPE_MAP: dict[str, type] = {
    "hello": HelloMessage,
    "hello_ack": HelloAckMessage,
    "heartbeat": HeartbeatMessage,
    "heartbeat_ack": HeartbeatAckMessage,
    "get_status": GetStatusMessage,
    "status_response": StatusResponseMessage,
    "error": ErrorMessage,
    "register_instance": RegisterInstanceMessage,
    "register_ack": RegisterAckMessage,
    "gui_state_changed": GuiStateChangedMessage,
    "get_gui_state": GetGuiStateMessage,
    "gui_state_response": GuiStateResponseMessage,
    "execute_gui_command": ExecuteGuiCommandMessage,
    "gui_command_result": GuiCommandResultMessage,
    "goodbye": GoodbyeMessage,
    # Phase 6
    "service_info_request": ServiceInfoRequestMessage,
    "service_info_response": ServiceInfoResponseMessage,
    "bridge_register": BridgeRegisterMessage,
    "bridge_register_ack": BridgeRegisterAckMessage,
    "tool_call": ToolCallMessage,
    "tool_result": ToolResultMessage,
    # Phase 8
    "inspect_capture": InspectCaptureRequestMessage,
    "inspect_capture_result": InspectCaptureResultMessage,
}

# Fields that are set via ``init=False`` and must be excluded when
# constructing a dataclass from deserialized data.
_READONLY_FIELDS: set[str] = {"type", "protocol_version"}

MessageType = (
    HelloMessage
    | HelloAckMessage
    | HeartbeatMessage
    | HeartbeatAckMessage
    | GetStatusMessage
    | StatusResponseMessage
    | ErrorMessage
    | RegisterInstanceMessage
    | RegisterAckMessage
    | GuiStateChangedMessage
    | GetGuiStateMessage
    | GuiStateResponseMessage
    | ExecuteGuiCommandMessage
    | GuiCommandResultMessage
    | GoodbyeMessage
    | ServiceInfoRequestMessage
    | ServiceInfoResponseMessage
    | BridgeRegisterMessage
    | BridgeRegisterAckMessage
    | ToolCallMessage
    | ToolResultMessage
    | InspectCaptureRequestMessage
    | InspectCaptureResultMessage
)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def serialize(msg: Any) -> bytes:
    """Serialize a message dataclass to a newline-terminated JSON bytes object.

    Args:
        msg: A message dataclass instance.

    Returns:
        UTF-8 encoded JSON followed by a newline character.

    Raises:
        ValueError: If the serialized message exceeds MAX_MESSAGE_BYTES.
    """
    data = asdict(msg)
    line = json.dumps(data, separators=(",", ":")) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ValueError(
            f"Serialized message size {len(encoded)} exceeds "
            f"MAX_MESSAGE_BYTES ({MAX_MESSAGE_BYTES})."
        )
    return encoded


def deserialize(raw: str | bytes) -> MessageType:
    """Deserialize a JSON line into the appropriate message dataclass.

    Args:
        raw: A single JSON line (with or without trailing newline).

    Returns:
        A typed message dataclass.

    Raises:
        ValueError: If JSON is invalid, the ``type`` field is missing or
                    unknown, or the message is too large.
    """
    if isinstance(raw, bytes):
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ValueError(
                f"Incoming message size {len(raw)} exceeds "
                f"MAX_MESSAGE_BYTES ({MAX_MESSAGE_BYTES})."
            )
        raw = raw.decode("utf-8")

    raw = raw.strip()

    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Message must be a JSON object.")

    msg_type = data.get("type")
    if not msg_type:
        raise ValueError("Message missing required 'type' field.")

    cls = _TYPE_MAP.get(msg_type)
    if cls is None:
        raise ValueError(f"Unknown message type: {msg_type!r}.")

    # Filter out fields that are set by __post_init__ / field(init=False)
    init_data = {k: v for k, v in data.items() if k not in _READONLY_FIELDS}

    try:
        return cls(**init_data)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"Cannot construct {cls.__name__}: {exc}") from exc
