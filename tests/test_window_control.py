"""Tests for window control helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_focus_window_invalid_hwnd():
    from rendereye_mcp.platform.window_control import focus_window

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 0  # invalid
        mock_dll.return_value = mock_user32
        result = focus_window(99999)
    assert not result.success
    assert result.message == "window_not_found"


def test_focus_window_success():
    from rendereye_mcp.platform.window_control import focus_window

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1
        mock_user32.ShowWindow.return_value = 1
        mock_user32.SetForegroundWindow.return_value = 1
        mock_dll.return_value = mock_user32
        result = focus_window(12345)
    assert result.success
    assert result.message == "focused"


def test_focus_window_denied():
    from rendereye_mcp.platform.window_control import focus_window

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1
        mock_user32.ShowWindow.return_value = 1
        mock_user32.SetForegroundWindow.return_value = 0  # denied
        mock_dll.return_value = mock_user32
        result = focus_window(12345)
    assert not result.success
    assert result.message == "denied_by_windows"


def test_focus_window_exception():
    from rendereye_mcp.platform.window_control import focus_window

    with patch("ctypes.WinDLL", side_effect=OSError("no dll")):
        result = focus_window(12345)
    assert not result.success
    assert "error" in result.message


def test_close_window_graceful_confirmed():
    from rendereye_mcp.platform.window_control import close_window_graceful

    call_count = [0]

    def is_window_side_effect(hwnd):
        call_count[0] += 1
        return 1 if call_count[0] == 1 else 0  # first call valid, then gone

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.side_effect = is_window_side_effect
        mock_user32.PostMessageW.return_value = 1
        mock_dll.return_value = mock_user32
        result = close_window_graceful(12345, wait_ms=500)
    assert result.confirmed


def test_close_window_timeout():
    from rendereye_mcp.platform.window_control import close_window_graceful

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1  # always valid (never closes)
        mock_user32.PostMessageW.return_value = 1
        mock_dll.return_value = mock_user32
        result = close_window_graceful(12345, wait_ms=100)  # short timeout
    assert not result.confirmed


def test_close_window_already_gone():
    from rendereye_mcp.platform.window_control import close_window_graceful

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 0  # already gone
        mock_dll.return_value = mock_user32
        result = close_window_graceful(12345, wait_ms=500)
    assert result.confirmed
    assert result.success


def test_close_window_exception():
    from rendereye_mcp.platform.window_control import close_window_graceful

    with patch("ctypes.WinDLL", side_effect=OSError("no dll")):
        result = close_window_graceful(12345, wait_ms=100)
    assert not result.confirmed


def test_is_window_valid_false():
    from rendereye_mcp.platform.window_control import is_window_valid

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 0
        mock_dll.return_value = mock_user32
        assert not is_window_valid(99999)


def test_is_window_valid_true():
    from rendereye_mcp.platform.window_control import is_window_valid

    with patch("ctypes.WinDLL") as mock_dll:
        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1
        mock_dll.return_value = mock_user32
        assert is_window_valid(12345)


def test_is_window_valid_exception():
    from rendereye_mcp.platform.window_control import is_window_valid

    with patch("ctypes.WinDLL", side_effect=Exception("fail")):
        assert not is_window_valid(12345)
