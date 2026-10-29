"""Windows window control helpers: focus, close, validity checks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Windows message constants
WM_CLOSE = 0x0010
SW_RESTORE = 9
SW_SHOW = 5


@dataclass
class FocusResult:
    success: bool
    hwnd: int
    message: str  # e.g. "focused", "denied_by_windows", "window_not_found"


@dataclass
class CloseResult:
    success: bool
    hwnd: int
    confirmed: bool  # True if window actually disappeared
    message: str


def focus_window(hwnd: int) -> FocusResult:
    """Restore and focus a window by HWND.

    Uses: IsWindow, ShowWindow(SW_RESTORE), SetForegroundWindow.
    Windows may deny foreground activation — return FocusResult with
    success=False, message="denied_by_windows" in that case.
    Never raises.
    """
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        if not user32.IsWindow(hwnd):
            return FocusResult(success=False, hwnd=hwnd, message="window_not_found")

        user32.ShowWindow(hwnd, SW_RESTORE)
        result = user32.SetForegroundWindow(hwnd)

        if result:
            return FocusResult(success=True, hwnd=hwnd, message="focused")
        else:
            return FocusResult(success=False, hwnd=hwnd, message="denied_by_windows")

    except Exception as exc:
        logger.debug("focus_window(%d) failed: %s", hwnd, exc)
        return FocusResult(success=False, hwnd=hwnd, message=f"error: {exc}")


def close_window_graceful(hwnd: int, wait_ms: int = 3000) -> CloseResult:
    """Send WM_CLOSE to a window and wait up to wait_ms for it to disappear.

    Uses: IsWindow check, PostMessage(WM_CLOSE), then polls IsWindow
    every 100ms up to wait_ms.
    Returns CloseResult(confirmed=True) if window disappears.
    Returns CloseResult(confirmed=False) if window still exists after timeout.
    Never uses TerminateProcess.
    Never raises.
    """
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        if not user32.IsWindow(hwnd):
            return CloseResult(
                success=True, hwnd=hwnd, confirmed=True, message="window_already_gone"
            )

        # PostMessageW(hwnd, WM_CLOSE, 0, 0)
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

        # Poll until window disappears or timeout
        deadline = time.monotonic() + wait_ms / 1000.0
        while time.monotonic() < deadline:
            if not user32.IsWindow(hwnd):
                return CloseResult(
                    success=True, hwnd=hwnd, confirmed=True, message="window_closed"
                )
            time.sleep(0.1)

        # Final check
        if not user32.IsWindow(hwnd):
            return CloseResult(
                success=True, hwnd=hwnd, confirmed=True, message="window_closed"
            )

        return CloseResult(
            success=False,
            hwnd=hwnd,
            confirmed=False,
            message="timeout_window_still_exists",
        )

    except Exception as exc:
        logger.debug("close_window_graceful(%d) failed: %s", hwnd, exc)
        return CloseResult(success=False, hwnd=hwnd, confirmed=False, message=f"error: {exc}")


def is_window_valid(hwnd: int) -> bool:
    """Return True if hwnd is still a valid window handle."""
    try:
        import ctypes

        return bool(ctypes.WinDLL("user32").IsWindow(hwnd))
    except Exception:
        return False
