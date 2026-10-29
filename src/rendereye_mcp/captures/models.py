"""Data models for capture records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class CaptureStatus(str, Enum):
    DISCOVERED = "discovered"
    PENDING = "pending"
    READY = "ready"
    MISSING = "missing"
    INACCESSIBLE = "inaccessible"
    INVALID = "invalid"
    STALE = "stale"


@dataclass
class CaptureRecord:
    capture_id: str  # "cap-000001" format, assigned by registry
    path: str  # canonical absolute path string
    filename: str  # basename
    file_size: int
    fs_created_at: Optional[datetime]  # filesystem creation time (may be unreliable)
    fs_modified_at: Optional[datetime]  # filesystem modification time
    discovered_at: datetime  # when first seen by registry
    last_seen_at: datetime  # last time file was observed present
    readiness_confirmed_at: Optional[datetime]  # when readiness check passed
    status: CaptureStatus
    selection_basis: str = "filesystem_modification_time"
    ordering_confidence: str = "heuristic"
    source_directory: str = ""  # which configured directory this came from
    error_message: str = ""

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "capture_id": self.capture_id,
            "path": self.path,
            "filename": self.filename,
            "file_size": self.file_size,
            "fs_created_at": self.fs_created_at.isoformat() if self.fs_created_at else None,
            "fs_modified_at": self.fs_modified_at.isoformat() if self.fs_modified_at else None,
            "discovered_at": self.discovered_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "readiness_confirmed_at": (
                self.readiness_confirmed_at.isoformat()
                if self.readiness_confirmed_at
                else None
            ),
            "status": self.status.value,
            "selection_basis": self.selection_basis,
            "ordering_confidence": self.ordering_confidence,
            "source_directory": self.source_directory,
            "error_message": self.error_message,
        }
