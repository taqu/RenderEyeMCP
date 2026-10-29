"""RenderDoc process launcher."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LaunchResult:
    success: bool
    process_id: Optional[int]
    process_create_time: Optional[float]
    exe_path: str
    error: str = ""
    note: str = ""  # e.g. "RenderDoc may reuse existing instance"


def launch_renderdoc(
    exe_path: str,
    capture_path: str,
    timeout_seconds: float = 5.0,
) -> LaunchResult:
    """Launch qrenderdoc.exe with a capture file path.

    Uses subprocess.Popen (NOT shell=True).
    Handles paths with spaces.
    Records the launched PID and create_time via psutil.
    Returns LaunchResult(success=False, error=...) on failure.
    Does NOT wait for the process to fully load — just checks it started.

    IMPORTANT NOTE: RenderDoc may reuse an existing process/window rather than
    creating a new one. The LaunchResult.note field documents this uncertainty.
    """
    note = (
        "RenderDoc may route to an existing window; "
        "window association requires post-launch discovery."
    )

    exe = Path(exe_path)
    if not exe.is_file():
        return LaunchResult(
            success=False,
            process_id=None,
            process_create_time=None,
            exe_path=exe_path,
            error=f"Executable not found: {exe_path}",
            note=note,
        )

    cap = Path(capture_path)
    if not cap.is_file():
        return LaunchResult(
            success=False,
            process_id=None,
            process_create_time=None,
            exe_path=exe_path,
            error=f"Capture file not found: {capture_path}",
            note=note,
        )

    try:
        proc = subprocess.Popen(
            [str(exe), str(cap)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid

        # Get create_time via psutil for stable identity tracking
        create_time: Optional[float] = None
        try:
            import psutil

            ps_proc = psutil.Process(pid)
            create_time = ps_proc.create_time()
        except Exception as exc:
            logger.debug("Could not get create_time for pid %d: %s", pid, exc)

        logger.info("Launched RenderDoc pid=%d exe=%s capture=%s", pid, exe_path, capture_path)
        return LaunchResult(
            success=True,
            process_id=pid,
            process_create_time=create_time,
            exe_path=exe_path,
            note=note,
        )

    except OSError as exc:
        logger.warning("Failed to launch RenderDoc: %s", exc)
        return LaunchResult(
            success=False,
            process_id=None,
            process_create_time=None,
            exe_path=exe_path,
            error=str(exc),
            note=note,
        )
