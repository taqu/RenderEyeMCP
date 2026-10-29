"""Data models for operation tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OperationStatus(str, Enum):
    REQUESTED = "requested"
    VALIDATING = "validating"
    LAUNCHING = "launching"
    WAITING_FOR_GUI = "waiting_for_gui"
    VERIFYING = "verifying"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    UNKNOWN_OUTCOME = "unknown_outcome"


@dataclass
class OperationRecord:
    operation_id: str          # "op-000001"
    operation_type: str        # "capture_open"
    status: OperationStatus
    capture_id: Optional[str] = None
    session_id: Optional[str] = None
    instance_id: Optional[str] = None
    window_id: Optional[str] = None
    open_mode: Optional[str] = None
    loaded_capture_verified: bool = False
    error_code: Optional[str] = None
    error_message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "capture_id": self.capture_id,
            "session_id": self.session_id,
            "instance_id": self.instance_id,
            "window_id": self.window_id,
            "open_mode": self.open_mode,
            "loaded_capture_verified": self.loaded_capture_verified,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
