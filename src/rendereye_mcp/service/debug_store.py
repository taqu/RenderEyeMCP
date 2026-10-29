"""In-memory store for shader debug trace results.

Debug traces are expensive to collect (requires GPU replay) and must be
reusable across multiple inspection tool calls without repeating GPU work.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_MAX_DEBUG_RECORDS = 10


@dataclass
class DebugRecord:
    """A single completed shader debug trace."""

    debug_id: str
    status: str  # "ready" | "failed"
    stage: str   # "pixel" | "vertex" | "compute"
    event_id: int
    capture_path: Optional[str]
    instance_id: str
    steps: List[dict]  # collected ShaderDebugState dicts
    initial_vars: dict
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class DebugStore:
    """Bounded in-memory store for shader debug trace records."""

    def __init__(self, max_records: int = _MAX_DEBUG_RECORDS) -> None:
        self._records: Dict[str, DebugRecord] = {}
        self._max = max_records

    def make_id(self) -> str:
        return "dbg_" + str(uuid.uuid4())[:8]

    def store(self, record: DebugRecord) -> None:
        if len(self._records) >= self._max and record.debug_id not in self._records:
            oldest_id = min(
                self._records,
                key=lambda k: self._records[k].created_at,
            )
            del self._records[oldest_id]
        self._records[record.debug_id] = record

    def get(self, debug_id: str) -> Optional[DebugRecord]:
        return self._records.get(debug_id)

    def list_ids(self) -> List[str]:
        return sorted(
            self._records.keys(),
            key=lambda k: self._records[k].created_at,
            reverse=True,
        )

    def invalidate_for_capture(self, capture_path: str) -> int:
        count = 0
        for record in self._records.values():
            if record.capture_path == capture_path and record.status == "ready":
                record.status = "invalidated"
                count += 1
        return count
