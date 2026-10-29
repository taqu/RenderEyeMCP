"""Cross-platform startup coordination lock for the shared IPC service."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_LOCK_PATH = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "rendereye_mcp_startup.lock"

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    WAIT_OBJECT_0 = 0x00000000
    WAIT_ABANDONED_0 = 0x00000080
    WAIT_TIMEOUT = 0x00000102
    INFINITE = 0xFFFFFFFF

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    _kernel32.CreateMutexW.argtypes = [
        ctypes.wintypes.LPVOID,  # lpMutexAttributes
        ctypes.wintypes.BOOL,    # bInitialOwner
        ctypes.wintypes.LPCWSTR, # lpName
    ]
    _kernel32.WaitForSingleObject.restype = ctypes.wintypes.DWORD
    _kernel32.WaitForSingleObject.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
    ]
    _kernel32.ReleaseMutex.restype = ctypes.wintypes.BOOL
    _kernel32.ReleaseMutex.argtypes = [ctypes.wintypes.HANDLE]
    _kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    class ServiceStartupLock:
        """Windows named mutex for coordinating service startup."""

        MUTEX_NAME = "Local\\RenderEyeMCPServiceStartup"

        def __init__(self, timeout: float = 30.0) -> None:
            self._timeout = timeout
            self._handle = None

        def __enter__(self) -> "ServiceStartupLock":
            handle = _kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
            if not handle:
                raise OSError(f"CreateMutexW failed: {ctypes.get_last_error()}")
            self._handle = handle
            timeout_ms = int(self._timeout * 1000)
            result = _kernel32.WaitForSingleObject(handle, timeout_ms)
            if result == WAIT_TIMEOUT:
                _kernel32.CloseHandle(handle)
                self._handle = None
                raise TimeoutError(
                    f"Could not acquire service startup lock within {self._timeout}s"
                )
            if result not in (WAIT_OBJECT_0, WAIT_ABANDONED_0):
                _kernel32.CloseHandle(handle)
                self._handle = None
                raise OSError(f"WaitForSingleObject failed: result={result:#x}")
            # WAIT_ABANDONED_0 means previous owner crashed — we now own the mutex.
            return self

        def __exit__(self, *args) -> None:
            if self._handle is not None:
                _kernel32.ReleaseMutex(self._handle)
                _kernel32.CloseHandle(self._handle)
                self._handle = None

else:
    import fcntl
    import time

    class ServiceStartupLock:  # type: ignore[no-redef]
        """File-based flock for coordinating service startup on Linux/macOS."""

        def __init__(self, timeout: float = 30.0) -> None:
            self._timeout = timeout
            self._fp = None

        def __enter__(self) -> "ServiceStartupLock":
            _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
            fp = open(_LOCK_PATH, "w")
            deadline = time.monotonic() + self._timeout
            while True:
                try:
                    fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._fp = fp
                    return self
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        fp.close()
                        raise TimeoutError(
                            f"Could not acquire service startup lock within {self._timeout}s"
                        )
                    time.sleep(0.1)

        def __exit__(self, *args) -> None:
            if self._fp is not None:
                try:
                    fcntl.flock(self._fp, fcntl.LOCK_UN)
                    self._fp.close()
                except Exception:
                    pass
                self._fp = None
