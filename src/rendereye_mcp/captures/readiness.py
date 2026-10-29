"""Readiness checking for .rdc capture files."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReadinessCheckResult:
    path: Path
    passed: bool
    reason: str  # e.g. "stable", "growing", "missing", "too_small", "inaccessible"
    file_size: int


async def check_readiness(
    path: Path,
    stability_seconds: float = 2.0,
    min_size: int = 4,
    poll_interval: float = 0.5,
) -> ReadinessCheckResult:
    """Check if a .rdc file is stable enough to be considered ready.

    Algorithm:
    1. Check file exists and is readable
    2. Check file size >= min_size
    3. Record size and mtime
    4. Wait stability_seconds / 2
    5. Record size and mtime again
    6. If both unchanged, passed=True
    7. Wait again and check one more time
    """
    # Step 1: Check exists and readable
    try:
        stat1 = path.stat()
        # Try opening to confirm readability
        with open(path, "rb"):
            pass
    except (OSError, PermissionError):
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="missing" if not path.exists() else "inaccessible",
            file_size=0,
        )

    # Step 2: Check size
    if stat1.st_size < min_size:
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="too_small",
            file_size=stat1.st_size,
        )

    size1 = stat1.st_size
    mtime1 = stat1.st_mtime

    # Step 4: Wait stability_seconds / 2
    half = stability_seconds / 2
    await asyncio.sleep(half)

    # Step 5: Record size and mtime again
    try:
        stat2 = path.stat()
    except OSError:
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="missing",
            file_size=size1,
        )

    size2 = stat2.st_size
    mtime2 = stat2.st_mtime

    # Step 6: If changed, not stable
    if size2 != size1 or mtime2 != mtime1:
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="growing",
            file_size=size2,
        )

    # Step 7: Wait again and check one more time
    await asyncio.sleep(half)

    try:
        stat3 = path.stat()
    except OSError:
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="missing",
            file_size=size2,
        )

    size3 = stat3.st_size
    mtime3 = stat3.st_mtime

    if size3 != size2 or mtime3 != mtime2:
        return ReadinessCheckResult(
            path=path,
            passed=False,
            reason="growing",
            file_size=size3,
        )

    return ReadinessCheckResult(
        path=path,
        passed=True,
        reason="stable",
        file_size=size3,
    )
