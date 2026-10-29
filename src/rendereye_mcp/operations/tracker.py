"""Thread-safe in-memory operation registry with bounded size."""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from .models import OperationRecord, OperationStatus

_MAX_OPERATIONS = 200


class OperationTracker:
    """Thread-safe in-memory operation registry with bounded size."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ops: OrderedDict[str, OperationRecord] = OrderedDict()
        self._counter = 0

    def create(self, operation_type: str, **kwargs) -> OperationRecord:
        with self._lock:
            self._counter += 1
            op_id = f"op-{self._counter:06d}"
            op = OperationRecord(
                operation_id=op_id,
                operation_type=operation_type,
                status=OperationStatus.REQUESTED,
                **kwargs,
            )
            self._ops[op_id] = op
            # Evict oldest if over limit
            while len(self._ops) > _MAX_OPERATIONS:
                self._ops.popitem(last=False)
            return op

    def update(self, op: OperationRecord) -> None:
        op.updated_at = datetime.now(timezone.utc)
        with self._lock:
            self._ops[op.operation_id] = op

    def get(self, operation_id: str) -> Optional[OperationRecord]:
        with self._lock:
            return self._ops.get(operation_id)
