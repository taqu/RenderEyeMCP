"""Tests for Phase 13 — GPU Performance Analysis.

Covers:
- MeasurementStore: make_id, store/get, eviction, list_ids, invalidate_for_capture
- Analysis helpers: _resolve_timing_counter, _find_counter_desc, _sort_entries,
  _aggregate_passes, _sum_leaf_events
- ToolExecutor analysis methods: _get_gpu_measurement_status, _get_gpu_timings,
  _get_performance_summary, _get_pipeline_statistics
- GUIContext extension methods: _inspect_list_gpu_counters, _inspect_fetch_gpu_counters
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_executor():
    from rendereye_mcp.service.tools import ToolExecutor

    config = MagicMock()
    config.renderdoc_path = None
    return ToolExecutor(
        config=config,
        registry=None,
        session_manager=None,
        conn_manager=None,
        operation_tracker=None,
    )


def _make_record(results, counter_descriptions=None, counter_ids=None, created_at=1000.0,
                 status="completed", capture_path="/test.rdc"):
    from rendereye_mcp.service.measurement_store import MeasurementRecord, MeasurementStore

    store = MeasurementStore()
    mid = store.make_id()
    record = MeasurementRecord(
        measurement_id=mid,
        status=status,
        capture_path=capture_path,
        instance_id="inst1",
        counter_ids=counter_ids if counter_ids is not None else [1],
        counter_descriptions=counter_descriptions if counter_descriptions is not None else [
            {
                "counter_id": 1,
                "name": "GPU Duration",
                "unit": "Seconds",
                "result_type": "Float",
                "result_byte_width": 8,
            }
        ],
        results=results,
        created_at=created_at,
    )
    store.store(record)
    return store, mid


def _mock_context(loaded=True, path="/test.rdc"):
    ctx = MagicMock()
    ctx.IsCaptureLoaded = MagicMock(return_value=loaded)
    ctx.IsCaptureLoading = MagicMock(return_value=False)
    ctx.GetCaptureFilename = MagicMock(return_value=path)
    ctx.Extensions = MagicMock(return_value=[])
    return ctx


def _make_gui(ctx=None):
    from extensions.rendereye.gui_context import GUIContext

    if ctx is None:
        ctx = _mock_context()
    gui = GUIContext(ctx, "1.45")
    gui.thread_id = threading.get_ident()
    return gui, ctx


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# 1. MeasurementStore
# ===========================================================================


class TestMeasurementStore:
    def _make_store(self):
        from rendereye_mcp.service.measurement_store import MeasurementStore

        return MeasurementStore()

    def _make_rec(self, mid, created_at=1000.0, capture_path="/test.rdc", status="completed"):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        return MeasurementRecord(
            measurement_id=mid,
            status=status,
            capture_path=capture_path,
            instance_id="inst1",
            counter_ids=[1],
            counter_descriptions=[],
            results=[],
            created_at=created_at,
        )

    def test_make_id_returns_8_char_string(self):
        store = self._make_store()
        mid = store.make_id()
        assert isinstance(mid, str)
        assert len(mid) == 8

    def test_make_id_unique(self):
        store = self._make_store()
        ids = {store.make_id() for _ in range(50)}
        assert len(ids) == 50

    def test_store_then_get_retrieves_record(self):
        store = self._make_store()
        mid = store.make_id()
        rec = self._make_rec(mid)
        store.store(rec)
        got = store.get(mid)
        assert got is rec

    def test_get_unknown_returns_none(self):
        store = self._make_store()
        assert store.get("deadbeef") is None

    def test_eviction_oldest_record_removed(self):
        from rendereye_mcp.service.measurement_store import MeasurementStore

        store = MeasurementStore(max_measurements=3)
        ids = []
        for i in range(3):
            mid = store.make_id()
            ids.append(mid)
            store.store(self._make_rec(mid, created_at=float(i)))

        # Add one more → oldest (i=0) should be evicted
        extra = store.make_id()
        store.store(self._make_rec(extra, created_at=100.0))

        assert store.get(ids[0]) is None, "Oldest record should have been evicted"
        assert store.get(ids[1]) is not None
        assert store.get(ids[2]) is not None
        assert store.get(extra) is not None

    def test_eviction_keeps_max_records(self):
        from rendereye_mcp.service.measurement_store import MeasurementStore

        store = MeasurementStore(max_measurements=5)
        for i in range(8):
            mid = store.make_id()
            store.store(self._make_rec(mid, created_at=float(i)))
        assert len(store.list_ids()) == 5

    def test_list_ids_sorted_by_created_at_descending(self):
        from rendereye_mcp.service.measurement_store import MeasurementStore

        store = MeasurementStore()
        ids = []
        for i in range(5):
            mid = store.make_id()
            ids.append(mid)
            store.store(self._make_rec(mid, created_at=float(i)))

        listed = store.list_ids()
        # Most recent first
        assert listed[0] == ids[4]
        assert listed[-1] == ids[0]

    def test_invalidate_for_capture_marks_matching(self):
        store = self._make_store()
        mid1 = store.make_id()
        mid2 = store.make_id()
        store.store(self._make_rec(mid1, capture_path="/cap.rdc"))
        store.store(self._make_rec(mid2, capture_path="/other.rdc"))

        count = store.invalidate_for_capture("/cap.rdc")
        assert count == 1
        assert store.get(mid1).status == "invalidated"
        assert store.get(mid2).status == "completed"

    def test_invalidate_for_capture_skips_already_non_completed(self):
        store = self._make_store()
        mid = store.make_id()
        store.store(self._make_rec(mid, capture_path="/cap.rdc", status="failed"))
        count = store.invalidate_for_capture("/cap.rdc")
        assert count == 0
        assert store.get(mid).status == "failed"

    def test_invalidate_returns_zero_when_no_match(self):
        store = self._make_store()
        mid = store.make_id()
        store.store(self._make_rec(mid, capture_path="/cap.rdc"))
        count = store.invalidate_for_capture("/other.rdc")
        assert count == 0

    def test_replace_existing_record_does_not_increase_size(self):
        from rendereye_mcp.service.measurement_store import MeasurementStore

        store = MeasurementStore(max_measurements=2)
        mid = store.make_id()
        rec = self._make_rec(mid, created_at=1.0)
        store.store(rec)
        # Replace with updated record
        rec2 = self._make_rec(mid, created_at=2.0)
        store.store(rec2)
        assert len(store.list_ids()) == 1
        assert store.get(mid) is rec2


# ===========================================================================
# 2. Analysis helper functions
# ===========================================================================


class TestFindCounterDesc:
    def _fn(self):
        from rendereye_mcp.service.tools import _find_counter_desc

        return _find_counter_desc

    def test_returns_matching_dict(self):
        fn = self._fn()
        descs = [
            {"counter_id": 1, "name": "A"},
            {"counter_id": 2, "name": "B"},
        ]
        assert fn(1, descs) == {"counter_id": 1, "name": "A"}
        assert fn(2, descs) == {"counter_id": 2, "name": "B"}

    def test_returns_empty_dict_when_not_found(self):
        fn = self._fn()
        descs = [{"counter_id": 1, "name": "A"}]
        assert fn(999, descs) == {}

    def test_returns_empty_dict_for_empty_list(self):
        fn = self._fn()
        assert fn(1, []) == {}


class TestResolveTimingCounter:
    def _fn(self):
        from rendereye_mcp.service.tools import _resolve_timing_counter

        return _resolve_timing_counter

    def _rec(self, counter_descriptions, counter_ids=None):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        return MeasurementRecord(
            measurement_id="test1234",
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=counter_ids or [],
            counter_descriptions=counter_descriptions,
            results=[],
            created_at=1000.0,
        )

    def test_returns_explicit_counter_id(self):
        fn = self._fn()
        rec = self._rec([])
        assert fn(42, rec) == 42

    def test_finds_counter_with_duration_in_name(self):
        fn = self._fn()
        rec = self._rec([
            {"counter_id": 10, "name": "GPU Duration", "unit": "Absolute"},
            {"counter_id": 20, "name": "Vertex Count", "unit": "Absolute"},
        ], counter_ids=[10, 20])
        assert fn(None, rec) == 10

    def test_finds_counter_with_second_in_unit(self):
        fn = self._fn()
        rec = self._rec([
            {"counter_id": 5, "name": "Timing", "unit": "Seconds"},
        ], counter_ids=[5])
        assert fn(None, rec) == 5

    def test_finds_counter_with_time_in_name(self):
        fn = self._fn()
        rec = self._rec([
            {"counter_id": 7, "name": "RenderTime", "unit": "Absolute"},
        ], counter_ids=[7])
        assert fn(None, rec) == 7

    def test_falls_back_to_first_counter_id(self):
        fn = self._fn()
        rec = self._rec([
            {"counter_id": 99, "name": "SomeOtherCounter", "unit": "Absolute"},
        ], counter_ids=[99])
        assert fn(None, rec) == 99

    def test_returns_none_when_no_counters(self):
        fn = self._fn()
        rec = self._rec([], counter_ids=[])
        assert fn(None, rec) is None

    def test_explicit_zero_counter_id_returned(self):
        fn = self._fn()
        rec = self._rec([], counter_ids=[])
        # 0 is falsy but explicitly passed — should still return 0
        assert fn(0, rec) == 0


class TestSortEntries:
    def _fn(self):
        from rendereye_mcp.service.tools import _sort_entries

        return _sort_entries

    def _entries(self):
        return [
            {"event_id": 3, "value": 1.5},
            {"event_id": 1, "value": 3.0},
            {"event_id": 2, "value": 0.5},
        ]

    def test_value_desc_highest_first(self):
        fn = self._fn()
        result = fn(self._entries(), "value_desc")
        values = [r["value"] for r in result]
        assert values == sorted(values, reverse=True)

    def test_value_asc_lowest_first(self):
        fn = self._fn()
        result = fn(self._entries(), "value_asc")
        values = [r["value"] for r in result]
        assert values == sorted(values)

    def test_event_id_ascending(self):
        fn = self._fn()
        result = fn(self._entries(), "event_id")
        eids = [r["event_id"] for r in result]
        assert eids == sorted(eids)

    def test_default_is_value_desc(self):
        fn = self._fn()
        result = fn(self._entries(), "unknown_sort_key")
        values = [r["value"] for r in result]
        assert values == sorted(values, reverse=True)

    def test_none_values_treated_as_zero(self):
        fn = self._fn()
        entries = [
            {"event_id": 1, "value": None},
            {"event_id": 2, "value": 2.0},
            {"event_id": 3, "value": None},
        ]
        # Should not raise
        result = fn(entries, "value_desc")
        assert result[0]["value"] == 2.0

    def test_value_asc_none_values_treated_as_zero(self):
        fn = self._fn()
        entries = [
            {"event_id": 1, "value": 5.0},
            {"event_id": 2, "value": None},
        ]
        result = fn(entries, "value_asc")
        assert result[0]["value"] is None  # None → 0 sorts first in asc


class TestSumLeafEvents:
    def _fn(self):
        from rendereye_mcp.service.tools import _sum_leaf_events

        return _sum_leaf_events

    def test_sums_drawcall_values(self):
        fn = self._fn()
        actions = [
            {"action_type": "drawcall", "event_id": 10, "name": "A", "children": []},
            {"action_type": "drawcall", "event_id": 11, "name": "B", "children": []},
        ]
        total, measured, unmeasured, largest = fn(actions, {10: 1.0, 11: 2.0})
        assert total == pytest.approx(3.0)
        assert measured == 2
        assert unmeasured == 0
        assert largest["event_id"] == 11
        assert largest["value"] == pytest.approx(2.0)

    def test_counts_unmeasured_when_missing_from_value_map(self):
        fn = self._fn()
        actions = [
            {"action_type": "drawcall", "event_id": 10, "name": "A", "children": []},
            {"action_type": "drawcall", "event_id": 11, "name": "B", "children": []},
        ]
        total, measured, unmeasured, largest = fn(actions, {10: 1.0})
        assert total == pytest.approx(1.0)
        assert measured == 1
        assert unmeasured == 1

    def test_recurses_into_non_marker_children(self):
        fn = self._fn()
        actions = [
            {
                "action_type": "other",
                "event_id": 5,
                "name": "Wrapper",
                "children": [
                    {"action_type": "drawcall", "event_id": 10, "name": "A", "children": []},
                ],
            }
        ]
        total, measured, unmeasured, largest = fn(actions, {10: 0.5})
        assert total == pytest.approx(0.5)
        assert measured == 1

    def test_empty_actions(self):
        fn = self._fn()
        total, measured, unmeasured, largest = fn([], {})
        assert total == 0.0
        assert measured == 0
        assert unmeasured == 0
        assert largest is None

    def test_dispatch_counted_as_leaf(self):
        fn = self._fn()
        actions = [
            {"action_type": "dispatch", "event_id": 20, "name": "CS", "children": []},
        ]
        total, measured, unmeasured, largest = fn(actions, {20: 3.0})
        assert total == pytest.approx(3.0)
        assert measured == 1


class TestAggregatePasses:
    def _fn(self):
        from rendereye_mcp.service.tools import _aggregate_passes

        return _aggregate_passes

    def _standard_actions(self):
        return [
            {
                "action_type": "marker_begin",
                "event_id": 1,
                "name": "Shadow Pass",
                "children": [
                    {"action_type": "drawcall", "event_id": 10, "name": "Draw1", "children": []},
                    {"action_type": "drawcall", "event_id": 11, "name": "Draw2", "children": []},
                ],
            },
            {
                "action_type": "marker_begin",
                "event_id": 2,
                "name": "GBuffer Pass",
                "children": [
                    {"action_type": "drawcall", "event_id": 20, "name": "Draw3", "children": []},
                    {"action_type": "drawcall", "event_id": 21, "name": "Draw4", "children": []},
                ],
            },
        ]

    def _standard_value_map(self):
        return {10: 0.4, 11: 0.6, 20: 1.2, 21: 0.3}

    def test_returns_two_passes(self):
        fn = self._fn()
        passes = fn(self._standard_actions(), self._standard_value_map())
        assert len(passes) == 2

    def test_shadow_pass_aggregated_duration(self):
        fn = self._fn()
        passes = fn(self._standard_actions(), self._standard_value_map())
        shadow = next(p for p in passes if p["name"] == "Shadow Pass")
        assert shadow["aggregated_duration"] == pytest.approx(1.0)

    def test_gbuffer_pass_aggregated_duration(self):
        fn = self._fn()
        passes = fn(self._standard_actions(), self._standard_value_map())
        gbuf = next(p for p in passes if p["name"] == "GBuffer Pass")
        assert gbuf["aggregated_duration"] == pytest.approx(1.5)

    def test_largest_event_in_shadow_pass(self):
        fn = self._fn()
        passes = fn(self._standard_actions(), self._standard_value_map())
        shadow = next(p for p in passes if p["name"] == "Shadow Pass")
        assert shadow["largest_event"]["value"] == pytest.approx(0.6)
        assert shadow["largest_event"]["name"] == "Draw2"

    def test_no_double_counting_each_draw_once(self):
        fn = self._fn()
        passes = fn(self._standard_actions(), self._standard_value_map())
        total = sum(p["aggregated_duration"] for p in passes)
        expected = sum(self._standard_value_map().values())
        assert total == pytest.approx(expected)

    def test_nested_markers_no_double_counting(self):
        fn = self._fn()
        actions = [
            {
                "action_type": "marker_begin",
                "event_id": 1,
                "name": "Outer",
                "children": [
                    {
                        "action_type": "marker_begin",
                        "event_id": 2,
                        "name": "Inner",
                        "children": [
                            {
                                "action_type": "drawcall",
                                "event_id": 10,
                                "name": "D",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        value_map = {10: 1.0}
        passes = fn(actions, value_map)
        # Outer pass only — contains one sub_pass (Inner)
        assert len(passes) == 1
        outer = passes[0]
        assert outer["name"] == "Outer"
        # Outer should count only the leaf draw (via recursion into Inner's children)
        assert outer["aggregated_duration"] == pytest.approx(1.0), (
            "Outer should not double-count Inner's events"
        )

    def test_nested_markers_sub_passes_entry(self):
        fn = self._fn()
        actions = [
            {
                "action_type": "marker_begin",
                "event_id": 1,
                "name": "Outer",
                "children": [
                    {
                        "action_type": "marker_begin",
                        "event_id": 2,
                        "name": "Inner",
                        "children": [
                            {
                                "action_type": "drawcall",
                                "event_id": 10,
                                "name": "D",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        value_map = {10: 1.0}
        passes = fn(actions, value_map)
        outer = passes[0]
        assert "sub_passes" in outer
        assert len(outer["sub_passes"]) == 1
        inner = outer["sub_passes"][0]
        assert inner["name"] == "Inner"
        assert inner["aggregated_duration"] == pytest.approx(1.0)

    def test_unmeasured_event_count_when_missing_from_value_map(self):
        fn = self._fn()
        actions = [
            {
                "action_type": "marker_begin",
                "event_id": 1,
                "name": "Pass",
                "children": [
                    {"action_type": "drawcall", "event_id": 10, "name": "A", "children": []},
                    {"action_type": "drawcall", "event_id": 11, "name": "B", "children": []},
                ],
            }
        ]
        value_map = {10: 0.5}  # event 11 is missing
        passes = fn(actions, value_map)
        assert passes[0]["unmeasured_event_count"] == 1

    def test_empty_value_map_all_events_unmeasured(self):
        fn = self._fn()
        actions = [
            {
                "action_type": "marker_begin",
                "event_id": 1,
                "name": "Pass",
                "children": [
                    {"action_type": "drawcall", "event_id": 10, "name": "A", "children": []},
                    {"action_type": "drawcall", "event_id": 11, "name": "B", "children": []},
                    {"action_type": "drawcall", "event_id": 12, "name": "C", "children": []},
                ],
            }
        ]
        passes = fn(actions, {})
        p = passes[0]
        assert p["aggregated_duration"] == 0
        assert p["unmeasured_event_count"] == 3

    def test_non_marker_top_level_actions_recurse(self):
        fn = self._fn()
        # A top-level "other" action with marker children
        actions = [
            {
                "action_type": "other",
                "event_id": 0,
                "name": "Root",
                "children": [
                    {
                        "action_type": "marker_begin",
                        "event_id": 1,
                        "name": "Pass",
                        "children": [
                            {"action_type": "drawcall", "event_id": 10, "name": "D", "children": []},
                        ],
                    }
                ],
            }
        ]
        passes = fn(actions, {10: 2.0})
        assert len(passes) == 1
        assert passes[0]["name"] == "Pass"
        assert passes[0]["aggregated_duration"] == pytest.approx(2.0)

    def test_empty_actions_returns_empty_list(self):
        fn = self._fn()
        assert fn([], {}) == []


# ===========================================================================
# 3. ToolExecutor analysis methods
# ===========================================================================


class TestGetGpuMeasurementStatus:
    def test_returns_error_for_unknown_id(self):
        ex = _make_executor()
        result = _run(ex._get_gpu_measurement_status("notexist"))
        assert result.get("error") == "measurement_not_found"
        assert result.get("measurement_id") == "notexist"

    def test_returns_status_for_known_record(self):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        ex = _make_executor()
        mid = ex._measurement_store.make_id()
        rec = MeasurementRecord(
            measurement_id=mid,
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=[1],
            counter_descriptions=[{"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
                                   "result_type": "Float", "result_byte_width": 8}],
            results=[{"event_id": 1, "counter_id": 1, "value": 0.5}],
            created_at=1000.0,
        )
        ex._measurement_store.store(rec)

        result = _run(ex._get_gpu_measurement_status(mid))
        assert result.get("error") is None
        assert result["status"] == "completed"
        assert result["result_count"] == 1
        assert result["measurement_id"] == mid

    def test_result_count_zero_when_no_results(self):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        ex = _make_executor()
        mid = ex._measurement_store.make_id()
        rec = MeasurementRecord(
            measurement_id=mid,
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=[1],
            counter_descriptions=[],
            results=[],
            created_at=1000.0,
        )
        ex._measurement_store.store(rec)
        result = _run(ex._get_gpu_measurement_status(mid))
        assert result["result_count"] == 0


class TestGetGpuTimings:
    def _populate(self, ex, results, counter_descriptions=None, counter_ids=None):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        mid = ex._measurement_store.make_id()
        rec = MeasurementRecord(
            measurement_id=mid,
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=counter_ids or [1],
            counter_descriptions=counter_descriptions or [
                {"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
                 "result_type": "Float", "result_byte_width": 8}
            ],
            results=results,
            created_at=1000.0,
        )
        ex._measurement_store.store(rec)
        return mid

    def test_returns_error_for_unknown_id(self):
        ex = _make_executor()
        result = _run(ex._get_gpu_timings(measurement_id="notexist"))
        assert result.get("error") == "measurement_not_found"

    def test_returns_paginated_results(self):
        ex = _make_executor()
        results = [{"event_id": i, "counter_id": 1, "value": float(i)} for i in range(10)]
        mid = self._populate(ex, results)
        result = _run(ex._get_gpu_timings(measurement_id=mid, limit=5, offset=0))
        assert result.get("error") is None
        assert result["total"] == 10
        assert len(result["events"]) == 5

    def test_pagination_offset(self):
        ex = _make_executor()
        results = [{"event_id": i, "counter_id": 1, "value": float(i)} for i in range(10)]
        mid = self._populate(ex, results)
        result = _run(ex._get_gpu_timings(measurement_id=mid, limit=5, offset=7))
        assert len(result["events"]) == 3  # Only 3 remain after offset 7

    def test_sorted_value_desc_by_default(self):
        ex = _make_executor()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 0.3},
            {"event_id": 2, "counter_id": 1, "value": 1.5},
            {"event_id": 3, "counter_id": 1, "value": 0.8},
        ]
        mid = self._populate(ex, results)
        result = _run(ex._get_gpu_timings(measurement_id=mid))
        events = result["events"]
        vals = [e["value"] for e in events]
        assert vals == sorted(vals, reverse=True)

    def test_min_value_filter(self):
        ex = _make_executor()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 0.1},
            {"event_id": 2, "counter_id": 1, "value": 0.5},
            {"event_id": 3, "counter_id": 1, "value": 1.0},
        ]
        mid = self._populate(ex, results)
        result = _run(ex._get_gpu_timings(measurement_id=mid, min_value=0.4))
        assert result["total"] == 2
        for e in result["events"]:
            assert e["value"] >= 0.4

    def test_uses_first_timing_counter_when_counter_id_none(self):
        ex = _make_executor()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 0.5},
            {"event_id": 1, "counter_id": 2, "value": 100.0},
        ]
        mid = self._populate(
            ex,
            results,
            counter_descriptions=[
                {"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
                 "result_type": "Float", "result_byte_width": 8},
                {"counter_id": 2, "name": "Vertex Count", "unit": "Absolute",
                 "result_type": "UInt", "result_byte_width": 4},
            ],
            counter_ids=[1, 2],
        )
        result = _run(ex._get_gpu_timings(measurement_id=mid, counter_id=None))
        # Should auto-resolve to counter 1 (has "Duration" in name)
        assert result["counter_id"] == 1
        assert len(result["events"]) == 1
        assert result["events"][0]["value"] == pytest.approx(0.5)

    def test_explicit_counter_id_used(self):
        ex = _make_executor()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 0.5},
            {"event_id": 1, "counter_id": 2, "value": 100.0},
        ]
        mid = self._populate(
            ex,
            results,
            counter_descriptions=[
                {"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
                 "result_type": "Float", "result_byte_width": 8},
                {"counter_id": 2, "name": "Vertex Count", "unit": "Absolute",
                 "result_type": "UInt", "result_byte_width": 4},
            ],
            counter_ids=[1, 2],
        )
        result = _run(ex._get_gpu_timings(measurement_id=mid, counter_id=2))
        assert result["counter_id"] == 2
        assert len(result["events"]) == 1
        assert result["events"][0]["value"] == pytest.approx(100.0)


class TestGetPerformanceSummary:
    def _populate(self, ex, results, counter_descriptions=None, counter_ids=None):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        mid = ex._measurement_store.make_id()
        rec = MeasurementRecord(
            measurement_id=mid,
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=counter_ids or [1],
            counter_descriptions=counter_descriptions or [
                {"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
                 "result_type": "Float", "result_byte_width": 8}
            ],
            results=results,
            created_at=1000.0,
        )
        ex._measurement_store.store(rec)
        return mid

    def test_returns_error_for_unknown_id(self):
        ex = _make_executor()
        result = _run(ex._get_performance_summary(measurement_id="notexist"))
        assert result.get("error") == "measurement_not_found"

    def test_top_n_events_sorted_by_value_desc(self):
        ex = _make_executor()
        results = [{"event_id": i, "counter_id": 1, "value": float(i)} for i in range(20)]
        mid = self._populate(ex, results)
        result = _run(ex._get_performance_summary(measurement_id=mid, top_n=5))
        assert result.get("error") is None
        top = result["top_events"]
        assert len(top) == 5
        vals = [e["value"] for e in top]
        assert vals == sorted(vals, reverse=True)
        assert top[0]["value"] == pytest.approx(19.0)

    def test_total_value_equals_sum_of_all_counter_values(self):
        ex = _make_executor()
        vals = [0.1, 0.2, 0.5, 1.0, 2.0]
        results = [{"event_id": i, "counter_id": 1, "value": v} for i, v in enumerate(vals)]
        mid = self._populate(ex, results)
        result = _run(ex._get_performance_summary(measurement_id=mid))
        assert result["total_value"] == pytest.approx(sum(vals))

    def test_handles_empty_results(self):
        ex = _make_executor()
        mid = self._populate(ex, [])
        result = _run(ex._get_performance_summary(measurement_id=mid))
        assert result.get("error") is None
        assert result["total_value"] == pytest.approx(0.0)
        assert result["total_events_measured"] == 0
        assert result["top_events"] == []

    def test_total_events_measured_excludes_none_values(self):
        ex = _make_executor()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 1.0},
            {"event_id": 2, "counter_id": 1, "value": None},
            {"event_id": 3, "counter_id": 1, "value": 2.0},
        ]
        mid = self._populate(ex, results)
        result = _run(ex._get_performance_summary(measurement_id=mid))
        assert result["total_events_measured"] == 2


class TestGetPipelineStatistics:
    def _populate(self, ex, results, counter_descriptions):
        from rendereye_mcp.service.measurement_store import MeasurementRecord

        mid = ex._measurement_store.make_id()
        cids = [d["counter_id"] for d in counter_descriptions]
        rec = MeasurementRecord(
            measurement_id=mid,
            status="completed",
            capture_path="/test.rdc",
            instance_id="inst1",
            counter_ids=cids,
            counter_descriptions=counter_descriptions,
            results=results,
            created_at=1000.0,
        )
        ex._measurement_store.store(rec)
        return mid

    def _stats_descriptions(self):
        return [
            {"counter_id": 1, "name": "Vertex Shader Invocations", "unit": "Absolute",
             "result_type": "UInt", "result_byte_width": 8},
            {"counter_id": 2, "name": "GPU Duration", "unit": "Seconds",
             "result_type": "Float", "result_byte_width": 8},
            {"counter_id": 3, "name": "Primitives Rasterized", "unit": "Absolute",
             "result_type": "UInt", "result_byte_width": 8},
        ]

    def test_returns_error_for_unknown_id(self):
        ex = _make_executor()
        result = _run(ex._get_pipeline_statistics(measurement_id="notexist"))
        assert result.get("error") == "measurement_not_found"

    def test_filters_to_stats_counters_by_keyword(self):
        ex = _make_executor()
        descs = self._stats_descriptions()
        results = [
            {"event_id": 1, "counter_id": 1, "value": 1000},  # Vertex Shader → stats
            {"event_id": 1, "counter_id": 2, "value": 0.5},   # GPU Duration → NOT stats
            {"event_id": 1, "counter_id": 3, "value": 500},   # Primitives → stats
        ]
        mid = self._populate(ex, results, descs)
        result = _run(ex._get_pipeline_statistics(measurement_id=mid))
        assert result.get("error") is None
        # Only stats counters (1 and 3) should appear
        counter_ids_in_result = {r["counter_id"] for r in result["statistics"]}
        assert 2 not in counter_ids_in_result
        assert 1 in counter_ids_in_result or 3 in counter_ids_in_result

    def test_filters_by_event_id(self):
        ex = _make_executor()
        descs = [
            {"counter_id": 1, "name": "Vertex Shader Invocations", "unit": "Absolute",
             "result_type": "UInt", "result_byte_width": 8},
        ]
        results = [
            {"event_id": 10, "counter_id": 1, "value": 100},
            {"event_id": 20, "counter_id": 1, "value": 200},
            {"event_id": 30, "counter_id": 1, "value": 300},
        ]
        mid = self._populate(ex, results, descs)
        result = _run(ex._get_pipeline_statistics(measurement_id=mid, event_id=20))
        assert result["total"] == 1
        assert result["statistics"][0]["event_id"] == 20

    def test_returns_correct_total_count(self):
        ex = _make_executor()
        descs = [
            {"counter_id": 1, "name": "Vertex Shader Invocations", "unit": "Absolute",
             "result_type": "UInt", "result_byte_width": 8},
        ]
        results = [{"event_id": i, "counter_id": 1, "value": i * 10} for i in range(8)]
        mid = self._populate(ex, results, descs)
        result = _run(ex._get_pipeline_statistics(measurement_id=mid))
        assert result["total"] == 8

    def test_enriched_with_counter_name(self):
        ex = _make_executor()
        descs = [
            {"counter_id": 1, "name": "Vertex Shader Invocations", "unit": "Absolute",
             "result_type": "UInt", "result_byte_width": 8},
        ]
        results = [{"event_id": 1, "counter_id": 1, "value": 999}]
        mid = self._populate(ex, results, descs)
        result = _run(ex._get_pipeline_statistics(measurement_id=mid))
        assert result["statistics"][0]["counter_name"] == "Vertex Shader Invocations"

    def test_no_stats_counters_returns_all_results(self):
        """When no counter matches stats keywords, all results are returned."""
        ex = _make_executor()
        descs = [
            {"counter_id": 1, "name": "GPU Duration", "unit": "Seconds",
             "result_type": "Float", "result_byte_width": 8},
        ]
        results = [{"event_id": i, "counter_id": 1, "value": float(i)} for i in range(5)]
        mid = self._populate(ex, results, descs)
        result = _run(ex._get_pipeline_statistics(measurement_id=mid))
        # No stats keywords matched → stats_counter_ids is empty → all results returned
        assert result["total"] == 5


# ===========================================================================
# 4. GUIContext extension inspection methods
# ===========================================================================


class TestInspectListGpuCounters:
    def test_returns_replay_unavailable_when_controller_none(self):
        gui, ctx = _make_gui()
        ctx.GetBlockingController.return_value = None
        result = gui._inspect_list_gpu_counters(ctx, {})
        assert result.get("error") == "replay_unavailable"

    def test_returns_inspection_failed_when_enumerate_raises(self):
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller
        rd_mock = MagicMock()
        controller.EnumerateCounters.side_effect = RuntimeError("boom")
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_list_gpu_counters(ctx, {})
        assert result.get("error") == "inspection_failed"

    def test_skips_counter_where_describe_raises_and_continues(self):
        """If DescribeCounter raises for one counter, that counter is skipped."""
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        good_counter = MagicMock()
        bad_counter = MagicMock()
        controller.EnumerateCounters.return_value = [bad_counter, good_counter]

        good_desc = MagicMock()
        good_desc.name = "GPU Duration"
        good_desc.description = "Time"
        good_desc.unit = MagicMock(__str__=lambda s: "Seconds")
        good_desc.resultType = MagicMock(__str__=lambda s: "Float")
        good_desc.resultByteWidth = 8

        def describe_side_effect(c):
            if c is bad_counter:
                raise RuntimeError("bad counter")
            return good_desc

        controller.DescribeCounter.side_effect = describe_side_effect
        good_counter.__int__ = lambda s: 1
        bad_counter.__int__ = lambda s: 2

        rd_mock = MagicMock()
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_list_gpu_counters(ctx, {})

        # No error — inspection succeeded
        assert "error" not in result or result.get("error") is None
        # Only the good counter was added
        assert result.get("count") == 1
        assert result["counters"][0]["name"] == "GPU Duration"


class TestInspectFetchGpuCounters:
    def test_returns_missing_counter_ids_when_none(self):
        gui, ctx = _make_gui()
        result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": None})
        assert result.get("error") == "missing_counter_ids"

    def test_returns_missing_counter_ids_when_empty_list(self):
        gui, ctx = _make_gui()
        result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": []})
        assert result.get("error") == "missing_counter_ids"

    def test_returns_missing_counter_ids_when_not_a_list(self):
        gui, ctx = _make_gui()
        result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": 42})
        assert result.get("error") == "missing_counter_ids"

    def test_returns_missing_counter_ids_when_string(self):
        gui, ctx = _make_gui()
        result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": "1,2"})
        assert result.get("error") == "missing_counter_ids"

    def test_returns_replay_unavailable_when_controller_none(self):
        gui, ctx = _make_gui()
        ctx.GetBlockingController.return_value = None
        result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": [1]})
        assert result.get("error") == "replay_unavailable"

    def test_returns_no_valid_counters_when_all_ids_invalid(self):
        """All requested IDs are not in the available set → no_valid_counters.

        renderdoc is imported at the top of the try block before EnumerateCounters,
        so we must patch sys.modules to avoid ModuleNotFoundError.
        """
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        # Available counters: ids 1 and 2
        c1 = MagicMock()
        c1.__int__ = lambda s: 1
        c2 = MagicMock()
        c2.__int__ = lambda s: 2
        controller.EnumerateCounters.return_value = [c1, c2]

        rd_mock = MagicMock()
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": [999, 888]})
        assert result.get("error") == "no_valid_counters"

    def test_no_valid_counters_includes_invalid_list(self):
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        c1 = MagicMock()
        c1.__int__ = lambda s: 1
        controller.EnumerateCounters.return_value = [c1]

        rd_mock = MagicMock()
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": [999]})
        assert result.get("error") == "no_valid_counters"
        assert 999 in result.get("invalid_counter_ids", [])

    def test_non_integer_ids_go_to_invalid(self):
        """Non-castable IDs (e.g. strings that aren't numeric) end up in invalid."""
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        c1 = MagicMock()
        c1.__int__ = lambda s: 1
        controller.EnumerateCounters.return_value = [c1]

        rd_mock = MagicMock()
        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": ["notanumber"]})
        assert result.get("error") == "no_valid_counters"

    def test_returns_result_keys_when_counters_valid(self):
        """Happy-path: valid counter ID, controller works, FetchCounters returns data."""
        import sys
        from unittest.mock import patch

        gui, ctx = _make_gui()
        controller = MagicMock()
        ctx.GetBlockingController.return_value = controller

        c1 = MagicMock()
        c1.__int__ = lambda s: 1
        controller.EnumerateCounters.return_value = [c1]

        # Mock a counter result
        counter_result = MagicMock()
        counter_result.eventId = 10
        counter_result.counter.__int__ = lambda s: 1
        value_obj = MagicMock()
        value_obj.f = 0.5
        counter_result.value = value_obj
        controller.FetchCounters.return_value = [counter_result]

        # DescribeCounter returns a usable description
        desc = MagicMock()
        desc.name = "GPU Duration"
        desc.unit = MagicMock(__str__=lambda s: "Seconds")
        desc.resultType = MagicMock(__str__=lambda s: "Float")
        desc.resultByteWidth = 8
        controller.DescribeCounter.return_value = desc

        rd_mock = MagicMock()
        # rd.GPUCounter(c) just returns c itself for our purposes
        rd_mock.GPUCounter.side_effect = lambda x: x

        with patch.dict(sys.modules, {"renderdoc": rd_mock}):
            result = gui._inspect_fetch_gpu_counters(ctx, {"counter_ids": [1]})

        for key in ("result_count", "counters_fetched", "counters_invalid", "counter_descriptions"):
            assert key in result, f"Expected key '{key}' in result: {result}"
        assert result["counters_fetched"] == [1]
        assert result["counters_invalid"] == []
