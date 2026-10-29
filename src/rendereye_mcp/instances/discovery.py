"""Discovery of running RenderDoc GUI processes and their windows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import InstanceOwnership, InstanceRecord, InstanceStatus, WindowRecord

logger = logging.getLogger(__name__)

_RENDERDOC_GUI_EXE_NAMES = {"qrenderdoc.exe", "renderdocui.exe"}


def discover_renderdoc_instances(
    known_managed_pids: set[int] | None = None,
) -> list[InstanceRecord]:
    """Enumerate running RenderDoc GUI processes via psutil.

    Uses pid + create_time for identity. Classifies as MANAGED if pid is in
    known_managed_pids, else EXTERNAL.

    Handles NoSuchProcess, AccessDenied gracefully.
    Only returns qrenderdoc.exe / renderdocui.exe (not renderdoccmd.exe).
    """
    import psutil

    if known_managed_pids is None:
        known_managed_pids = set()

    results: list[InstanceRecord] = []
    now = datetime.now(timezone.utc)

    for proc in psutil.process_iter(["pid", "name", "create_time", "exe"]):
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            if name not in _RENDERDOC_GUI_EXE_NAMES:
                continue

            pid = info["pid"]
            create_time = info.get("create_time") or 0.0
            exe_path = info.get("exe") or ""

            ownership = (
                InstanceOwnership.MANAGED
                if pid in known_managed_pids
                else InstanceOwnership.EXTERNAL
            )

            record = InstanceRecord(
                instance_id="",  # assigned by manager
                process_id=pid,
                process_create_time=create_time,
                exe_path=exe_path,
                ownership=ownership,
                status=InstanceStatus.RUNNING,
                last_seen_at=now,
            )
            results.append(record)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception as exc:
            logger.debug("Error enumerating process: %s", exc)
            continue

    return results


def enumerate_windows_for_pid(pid: int) -> list[tuple[int, str, bool]]:
    """Return list of (hwnd, title, visible) for top-level windows owned by pid.

    Uses ctypes EnumWindows + GetWindowThreadProcessId + GetWindowTextW + IsWindowVisible.
    Returns empty list on any error. Never raises.
    """
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )

        windows: list[tuple[int, str, bool]] = []

        def _enum_windows_callback(hwnd: int, lparam: int) -> bool:
            try:
                pid_buf = ctypes.wintypes.DWORD(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buf))
                if pid_buf.value != pid:
                    return True
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                title = buf.value
                visible = bool(user32.IsWindowVisible(hwnd))
                windows.append((hwnd, title, visible))
            except Exception:
                pass
            return True

        user32.EnumWindows(EnumWindowsProc(_enum_windows_callback), 0)
        return windows
    except Exception as exc:
        logger.debug("enumerate_windows_for_pid(%d) failed: %s", pid, exc)
        return []


def discover_all_windows(
    instances: list[InstanceRecord], id_counter_start: int = 1
) -> list[WindowRecord]:
    """For each instance, enumerate windows and assign window IDs."""
    all_windows: list[WindowRecord] = []
    counter = id_counter_start
    now = datetime.now(timezone.utc)

    for inst in instances:
        for hwnd, title, visible in enumerate_windows_for_pid(inst.process_id):
            wid = f"window-{counter:06d}"
            counter += 1
            wr = WindowRecord(
                window_id=wid,
                hwnd=hwnd,
                instance_id=inst.instance_id,
                process_id=inst.process_id,
                title=title,
                visible=visible,
                last_seen_at=now,
            )
            all_windows.append(wr)

    return all_windows
