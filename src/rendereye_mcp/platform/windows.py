"""Windows-specific helpers: RenderDoc process and executable discovery."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_RENDERDOC_EXE_NAME = "qrenderdoc.exe"
_RENDERDOCCMD_EXE_NAME = "renderdoccmd.exe"

# Names that identify a RenderDoc process in the process list.
_RENDERDOC_PROCESS_NAMES = {
    "qrenderdoc.exe",
    "renderdoccmd.exe",
    "renderdocui.exe",
}


def find_renderdoc_exe(config) -> Optional[str]:
    """Return the absolute path to qrenderdoc.exe if found, else None.

    If *config.renderdoc_exe* is set (non-empty), only that path is checked.
    If it is empty (the default), common installation locations are probed.

    Args:
        config: A :class:`~rendereye_mcp.config.Config` instance.

    Returns:
        Absolute path string (forward-slash style) or ``None``.
    """
    if config.renderdoc_exe:
        # Explicit path configured — check only that path.
        candidate = Path(config.renderdoc_exe)
        try:
            if candidate.is_file():
                resolved = candidate.resolve()
                logger.debug("Found RenderDoc at: %s", resolved)
                return resolved.as_posix()
        except (OSError, ValueError):
            pass
        logger.debug("Configured RenderDoc exe not found: %s", config.renderdoc_exe)
        return None

    # No path configured — probe common installation locations.
    # Standard installer paths are checked first; developer-specific paths last.
    fallbacks: list[Path] = [
        Path("C:/Program Files/RenderDoc/qrenderdoc.exe"),
        Path("C:/Program Files (x86)/RenderDoc/qrenderdoc.exe"),
        Path("D:/Programs/RenderDoc/qrenderdoc.exe"),  # common developer location
    ]

    for candidate in fallbacks:
        try:
            if candidate.is_file():
                resolved = candidate.resolve()
                logger.debug("Found RenderDoc at: %s", resolved)
                return resolved.as_posix()
        except (OSError, ValueError):
            continue

    logger.debug("RenderDoc executable not found in any candidate path.")
    return None


def get_running_renderdoc_processes() -> list[dict]:
    """Return a list of running RenderDoc process descriptors.

    Each element is a dict with keys:
    - ``pid``:         int  — process ID
    - ``name``:        str  — executable name
    - ``create_time``: float — Unix timestamp of process creation
    - ``exe``:         str  — full path to the executable (may be empty)

    Uses *psutil* if available; falls back to *wmic* or *tasklist* via
    subprocess when psutil is not installed.
    """
    try:
        import psutil  # type: ignore[import]

        return _via_psutil(psutil)
    except ImportError:
        logger.debug("psutil not available — falling back to wmic/tasklist.")
        return _via_subprocess()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _via_psutil(psutil) -> list[dict]:
    results: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "create_time", "exe"]):
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            if name in _RENDERDOC_PROCESS_NAMES:
                results.append(
                    {
                        "pid": info["pid"],
                        "name": info.get("name") or "",
                        "create_time": info.get("create_time") or 0.0,
                        "exe": info.get("exe") or "",
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def _via_subprocess() -> list[dict]:
    """Fallback: parse tasklist /FO CSV output."""
    results: list[dict] = []
    try:
        raw = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            timeout=10,
            stderr=subprocess.DEVNULL,
        )
        for line in raw.splitlines():
            line = line.strip().strip('"')
            if not line:
                continue
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) < 2:
                continue
            name = parts[0].lower()
            if name in _RENDERDOC_PROCESS_NAMES:
                try:
                    pid = int(parts[1])
                except ValueError:
                    pid = 0
                results.append(
                    {
                        "pid": pid,
                        "name": parts[0],
                        "create_time": 0.0,
                        "exe": "",
                    }
                )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        logger.warning("tasklist subprocess failed: %s", exc)
    return results
