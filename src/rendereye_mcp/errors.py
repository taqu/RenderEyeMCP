"""Standard error codes and response builder for RenderEyeMCP."""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    CAPTURE_NOT_FOUND = "capture_not_found"
    CAPTURE_NOT_READY = "capture_not_ready"
    CAPTURE_UNAVAILABLE = "capture_unavailable"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_PROTECTED = "session_protected"
    SESSION_UNMANAGED = "session_unmanaged"
    INSTANCE_NOT_FOUND = "instance_not_found"
    WINDOW_NOT_FOUND = "window_not_found"
    WINDOW_AMBIGUOUS = "window_ambiguous"
    EXTENSION_UNAVAILABLE = "extension_unavailable"
    IPC_DISCONNECTED = "ipc_disconnected"
    OPERATION_UNSUPPORTED = "operation_unsupported"
    OPERATION_TIMEOUT = "operation_timeout"
    OPERATION_UNKNOWN_OUTCOME = "operation_unknown_outcome"
    STATE_CONFLICT = "state_conflict"
    INTERNAL_ERROR = "internal_error"


# Codes that are safe to retry (won't create duplicate windows)
_RETRYABLE = {
    ErrorCode.OPERATION_TIMEOUT,
    ErrorCode.IPC_DISCONNECTED,
    ErrorCode.EXTENSION_UNAVAILABLE,
}


def error_response(code: ErrorCode, message: str, **extra) -> dict:
    """Build a standard error response dict."""
    return {
        "status": "failed",
        "error": {
            "code": code.value,
            "message": message,
            "retryable": code in _RETRYABLE,
        },
        **extra,
    }
