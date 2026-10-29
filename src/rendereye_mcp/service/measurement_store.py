"""In-memory store for GPU performance measurement results.

Measurement results are expensive to collect (requires GPU replay) and must be
reusable across multiple analysis tool calls without repeating the GPU work.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_MAX_MEASUREMENTS = 20


@dataclass
class MeasurementRecord:
    """A single completed GPU counter collection result."""

    measurement_id: str
    status: str  # "completed" | "failed"
    capture_path: Optional[str]
    instance_id: str
    counter_ids: List[int]
    counter_descriptions: List[dict]  # [{counter_id, name, unit, result_type, result_byte_width}]
    results: List[dict]  # [{event_id, counter_id, value}]
    created_at: float
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None


class MeasurementStore:
    """Bounded in-memory store for GPU counter measurement records."""

    def __init__(self, max_measurements: int = _MAX_MEASUREMENTS) -> None:
        self._measurements: Dict[str, MeasurementRecord] = {}
        self._max = max_measurements

    def make_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def store(self, record: MeasurementRecord) -> None:
        """Add or replace a record, evicting the oldest entry when at capacity."""
        if len(self._measurements) >= self._max and record.measurement_id not in self._measurements:
            oldest_id = min(
                self._measurements,
                key=lambda k: self._measurements[k].created_at,
            )
            del self._measurements[oldest_id]
        self._measurements[record.measurement_id] = record

    def get(self, measurement_id: str) -> Optional[MeasurementRecord]:
        return self._measurements.get(measurement_id)

    def list_ids(self) -> List[str]:
        return sorted(
            self._measurements.keys(),
            key=lambda k: self._measurements[k].created_at,
            reverse=True,
        )

    def invalidate_for_capture(self, capture_path: str) -> int:
        """Mark measurements for a specific capture as invalidated. Returns count."""
        count = 0
        for record in self._measurements.values():
            if record.capture_path == capture_path and record.status == "completed":
                record.status = "invalidated"
                count += 1
        return count
