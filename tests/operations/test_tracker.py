"""Tests for OperationTracker."""

from __future__ import annotations

import time

from rendereye_mcp.operations.models import OperationStatus
from rendereye_mcp.operations.tracker import _MAX_OPERATIONS, OperationTracker


class TestOperationTracker:
    def test_create_assigns_unique_ids(self):
        tracker = OperationTracker()
        op1 = tracker.create("capture_open")
        op2 = tracker.create("capture_open")
        assert op1.operation_id != op2.operation_id
        assert op1.operation_id == "op-000001"
        assert op2.operation_id == "op-000002"

    def test_create_sets_requested_status(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open")
        assert op.status == OperationStatus.REQUESTED

    def test_create_passes_kwargs(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open", capture_id="cap-000001", open_mode="new_window")
        assert op.capture_id == "cap-000001"
        assert op.open_mode == "new_window"

    def test_get_retrieves_by_id(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open")
        retrieved = tracker.get(op.operation_id)
        assert retrieved is not None
        assert retrieved.operation_id == op.operation_id

    def test_get_returns_none_for_unknown(self):
        tracker = OperationTracker()
        result = tracker.get("op-999999")
        assert result is None

    def test_update_changes_status_and_timestamp(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open")
        original_ts = op.updated_at
        time.sleep(0.01)
        op.status = OperationStatus.CONFIRMED
        tracker.update(op)

        retrieved = tracker.get(op.operation_id)
        assert retrieved.status == OperationStatus.CONFIRMED
        assert retrieved.updated_at >= original_ts

    def test_update_stores_extra_fields(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open")
        op.session_id = "session-000001"
        op.window_id = "win-abc"
        tracker.update(op)

        retrieved = tracker.get(op.operation_id)
        assert retrieved.session_id == "session-000001"
        assert retrieved.window_id == "win-abc"

    def test_bounded_eviction_when_over_limit(self):
        tracker = OperationTracker()
        ops = []
        for _ in range(_MAX_OPERATIONS + 5):
            ops.append(tracker.create("capture_open"))

        # Total stored should be exactly _MAX_OPERATIONS
        with tracker._lock:
            assert len(tracker._ops) == _MAX_OPERATIONS

        # Oldest ops should have been evicted
        first_id = ops[0].operation_id
        assert tracker.get(first_id) is None

        # Newest ops should still be present
        last_id = ops[-1].operation_id
        assert tracker.get(last_id) is not None

    def test_to_dict_has_expected_keys(self):
        tracker = OperationTracker()
        op = tracker.create("capture_open", capture_id="cap-000001")
        d = op.to_dict()
        expected_keys = {
            "operation_id", "operation_type", "status", "capture_id",
            "session_id", "instance_id", "window_id", "open_mode",
            "loaded_capture_verified", "error_code", "error_message",
            "created_at", "updated_at",
        }
        assert expected_keys.issubset(d.keys())
        assert d["operation_id"] == "op-000001"
        assert d["status"] == "requested"
        assert d["capture_id"] == "cap-000001"
