"""Tests for the RenderDoc launcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rendereye_mcp.instances.launcher import LaunchResult, launch_renderdoc


def test_launch_missing_exe():
    result = launch_renderdoc("/nonexistent/qrenderdoc.exe", "/tmp/test.rdc")
    assert not result.success
    assert result.error


def test_launch_missing_capture():
    """Exe exists but capture path doesn't."""
    with patch("pathlib.Path.is_file", side_effect=[True, False]):
        result = launch_renderdoc(
            "C:/Program Files/RenderDoc/qrenderdoc.exe", "/nonexistent.rdc"
        )
    assert not result.success
    assert "Capture file not found" in result.error


def test_launch_success_returns_pid():
    mock_proc = MagicMock()
    mock_proc.pid = 5678

    mock_ps_proc = MagicMock()
    mock_ps_proc.create_time.return_value = 100.0

    with patch("pathlib.Path.is_file", return_value=True), patch(
        "subprocess.Popen", return_value=mock_proc
    ), patch("psutil.Process", return_value=mock_ps_proc):
        result = launch_renderdoc(
            "C:/Program Files/RenderDoc/qrenderdoc.exe", "test.rdc"
        )

    assert result.success
    assert result.process_id == 5678


def test_launch_note_about_reuse():
    """Result always includes note about possible window reuse."""
    mock_proc = MagicMock()
    mock_proc.pid = 5678

    with patch("pathlib.Path.is_file", return_value=True), patch(
        "subprocess.Popen", return_value=mock_proc
    ), patch("psutil.Process"):
        result = launch_renderdoc(
            "C:/Program Files/RenderDoc/qrenderdoc.exe", "test.rdc"
        )
    assert result.note  # non-empty note about window reuse
    assert "window" in result.note.lower() or "reuse" in result.note.lower()


def test_launch_subprocess_failure():
    with patch("pathlib.Path.is_file", return_value=True), patch(
        "subprocess.Popen", side_effect=OSError("not found")
    ):
        result = launch_renderdoc(
            "C:/Program Files/RenderDoc/qrenderdoc.exe", "test.rdc"
        )
    assert not result.success
    assert "not found" in result.error


def test_launch_result_fields():
    """LaunchResult has all expected fields."""
    r = LaunchResult(
        success=True,
        process_id=123,
        process_create_time=1.0,
        exe_path="test.exe",
        note="some note",
    )
    assert r.success
    assert r.process_id == 123
    assert r.error == ""
    assert r.note == "some note"


def test_launch_create_time_captured():
    mock_proc = MagicMock()
    mock_proc.pid = 9999

    mock_ps_proc = MagicMock()
    mock_ps_proc.create_time.return_value = 42.0

    with patch("pathlib.Path.is_file", return_value=True), patch(
        "subprocess.Popen", return_value=mock_proc
    ), patch("psutil.Process", return_value=mock_ps_proc):
        result = launch_renderdoc("D:/test/qrenderdoc.exe", "cap.rdc")

    assert result.success
    assert result.process_create_time == 42.0
