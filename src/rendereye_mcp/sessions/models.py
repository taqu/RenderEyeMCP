"""Data models for session records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SessionStatus(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    RECOVERING = "recovering"
    CLOSING = "closing"
    CLOSED = "closed"


class AssociationStatus(str, Enum):
    CONFIRMED = "confirmed"  # we launched it and tracked the window
    INFERRED = "inferred"  # based on timing/title heuristics
    UNKNOWN = "unknown"  # no window correlated yet
    LOST = "lost"  # window no longer found


@dataclass
class SessionRecord:
    session_id: str  # "session-000001"
    capture_id: str  # from Phase 1 registry
    capture_path: str  # last known path (snapshot at session creation)
    instance_id: Optional[str]
    window_id: Optional[str]
    process_id: Optional[int]
    status: SessionStatus
    managed: bool  # True = we launched it
    protected: bool  # True = cannot be closed/replaced implicitly
    association_status: AssociationStatus
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    error_message: str = ""
    gui_capture_path: Optional[str] = None       # actual loaded capture per extension
    gui_verified_at: Optional[datetime] = None   # when GUI state was last verified

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "capture_id": self.capture_id,
            "capture_path": self.capture_path,
            "instance_id": self.instance_id,
            "window_id": self.window_id,
            "process_id": self.process_id,
            "status": self.status.value,
            "managed": self.managed,
            "protected": self.protected,
            "association_status": self.association_status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "error_message": self.error_message,
            "gui_capture_path": self.gui_capture_path,
            "gui_verified_at": self.gui_verified_at.isoformat() if self.gui_verified_at else None,
        }
