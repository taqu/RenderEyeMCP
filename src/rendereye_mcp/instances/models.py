"""Data models for RenderDoc instance and window records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class InstanceOwnership(str, Enum):
    MANAGED = "managed"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class InstanceStatus(str, Enum):
    RUNNING = "running"
    EXITED = "exited"
    UNKNOWN = "unknown"


@dataclass
class WindowRecord:
    window_id: str  # "window-000001"
    hwnd: int  # native HWND (do NOT use as persistent ID)
    instance_id: str  # owning instance
    process_id: int
    title: str
    visible: bool
    last_seen_at: datetime
    session_id: Optional[str] = None  # if associated with a session

    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "hwnd": self.hwnd,
            "instance_id": self.instance_id,
            "process_id": self.process_id,
            "title": self.title,
            "visible": self.visible,
            "last_seen_at": self.last_seen_at.isoformat(),
            "session_id": self.session_id,
        }


@dataclass
class InstanceRecord:
    instance_id: str  # "instance-000001"
    process_id: int
    process_create_time: float  # from psutil — used with pid for uniqueness
    exe_path: str
    ownership: InstanceOwnership
    status: InstanceStatus
    windows: list[WindowRecord] = field(default_factory=list)
    last_seen_at: Optional[datetime] = None
    command_line: str = ""

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "process_id": self.process_id,
            "process_create_time": self.process_create_time,
            "exe_path": self.exe_path,
            "ownership": self.ownership.value,
            "status": self.status.value,
            "windows": [w.to_dict() for w in self.windows],
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "command_line": self.command_line,
        }

    def is_alive(self) -> bool:
        """Check if the process still matches pid + create_time."""
        try:
            import psutil

            proc = psutil.Process(self.process_id)
            return abs(proc.create_time() - self.process_create_time) < 1.0
        except Exception:
            return False
