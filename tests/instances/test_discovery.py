"""Tests for instance discovery module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rendereye_mcp.instances.discovery import (
    discover_renderdoc_instances,
    enumerate_windows_for_pid,
)


def _make_proc(pid: int, name: str, create_time: float = 1.0, exe: str = "") -> MagicMock:
    mock_proc = MagicMock()
    mock_proc.info = {"pid": pid, "name": name, "create_time": create_time, "exe": exe}
    return mock_proc


def test_no_renderdoc_processes():
    with patch("psutil.process_iter", return_value=[]):
        result = discover_renderdoc_instances()
    assert result == []


def test_one_renderdoc_process():
    mock_proc = _make_proc(1234, "qrenderdoc.exe", 1.0, "C:/Program Files/RenderDoc/qrenderdoc.exe")
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances()
    assert len(result) == 1
    assert result[0].process_id == 1234


def test_managed_classification():
    mock_proc = _make_proc(1234, "qrenderdoc.exe", 1.0, "C:/Program Files/RenderDoc/qrenderdoc.exe")
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances(known_managed_pids={1234})
    assert result[0].ownership.value == "managed"


def test_external_classification():
    mock_proc = _make_proc(1234, "qrenderdoc.exe", 1.0, "C:/Program Files/RenderDoc/qrenderdoc.exe")
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances(known_managed_pids={9999})
    assert result[0].ownership.value == "external"


def test_non_gui_excluded():
    mock_proc = _make_proc(999, "renderdoccmd.exe", 1.0, "")
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances()
    assert len(result) == 0


def test_renderdocui_included():
    mock_proc = _make_proc(1234, "renderdocui.exe", 1.0, "")
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances()
    assert len(result) == 1


def test_process_exit_during_enumeration():
    """NoSuchProcess raised — should be caught, not crash."""
    import psutil

    mock_proc = MagicMock()
    type(mock_proc).info = property(
        lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(pid=1))
    )
    with patch("psutil.process_iter", return_value=[mock_proc]):
        # Should not raise
        result = discover_renderdoc_instances()
    assert isinstance(result, list)


def test_access_denied_during_enumeration():
    """AccessDenied raised — should be caught, not crash."""
    import psutil

    mock_proc = MagicMock()
    type(mock_proc).info = property(
        lambda self: (_ for _ in ()).throw(psutil.AccessDenied(pid=1))
    )
    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = discover_renderdoc_instances()
    assert isinstance(result, list)


def test_enumerate_windows_no_ctypes_error():
    """Should return empty list if ctypes call fails, never raise."""
    with patch("ctypes.WinDLL", side_effect=OSError("no dll")):
        result = enumerate_windows_for_pid(1234)
    assert result == []


def test_enumerate_windows_returns_list():
    """enumerate_windows_for_pid always returns a list."""
    with patch("ctypes.WinDLL", side_effect=Exception("test error")):
        result = enumerate_windows_for_pid(9999)
    assert isinstance(result, list)


def test_multiple_processes():
    procs = [
        _make_proc(1001, "qrenderdoc.exe", 1.0),
        _make_proc(1002, "qrenderdoc.exe", 2.0),
        _make_proc(1003, "renderdoccmd.exe", 3.0),  # excluded
    ]
    with patch("psutil.process_iter", return_value=procs):
        result = discover_renderdoc_instances()
    assert len(result) == 2
    pids = {r.process_id for r in result}
    assert pids == {1001, 1002}
