"""Service discovery and startup coordination for RenderEyeMCP bridge mode."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rendereye_mcp.bridge.client import ServiceClient
    from rendereye_mcp.config import Config

logger = logging.getLogger(__name__)

SERVICE_READY_FILE = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "rendereye_mcp_service.json"
STARTUP_POLL_INTERVAL = 0.25  # seconds
STARTUP_TIMEOUT = 30.0  # seconds


async def ensure_service_running(config: "Config") -> "ServiceClient":
    """Connect to running service or start it, then return connected client.

    Fast-path: if the service is already running we connect immediately.
    If not, we take the startup coordination lock, check again, start the
    service subprocess if still absent, then poll until it is ready.
    """
    # 1. Fast path: try to connect without acquiring any lock
    client = await _try_connect(config)
    if client is not None:
        return client

    # 2. Coordinate startup so only one bridge process launches the service
    from rendereye_mcp.service.lock import ServiceStartupLock

    logger.info("[MCP] pid=%d acquiring service startup lock", os.getpid())
    with ServiceStartupLock(timeout=STARTUP_TIMEOUT):
        # Check again — another bridge may have started the service while we waited
        client = await _try_connect(config)
        if client is not None:
            return client

        # We hold the lock and the service is not running — start it
        logger.info("[MCP] pid=%d launching shared service subprocess", os.getpid())
        _launch_service_process()

        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(STARTUP_POLL_INTERVAL)
            client = await _try_connect(config)
            if client is not None:
                logger.info("[MCP] pid=%d connected to newly started service", os.getpid())
                return client

    raise RuntimeError(
        f"Shared service failed to start within {STARTUP_TIMEOUT}s"
    )


def _port_open(host: str, port: int) -> bool:
    """Return True if a TCP listener is accepting connections on host:port.

    Uses select() after a non-blocking connect to determine port state without
    waiting for the OS default timeout.  Windows returns WSAEWOULDBLOCK for
    non-blocking connects on both open and closed ports, so we wait briefly
    with select() to distinguish them.
    """
    import select
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(False)
    try:
        err = s.connect_ex((host, port))
        if err == 0:
            return True  # immediately connected
        # WSAEWOULDBLOCK (10035) or EINPROGRESS (115) — pending; wait briefly
        if err in (10035, 115):
            _, writable, _ = select.select([], [s], [s], 0.2)
            if writable:
                # Check actual connect result
                final_err = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                return final_err == 0
        return False
    except OSError:
        return False
    finally:
        s.close()


async def _try_connect(config: "Config") -> Optional["ServiceClient"]:
    """Try to connect to the service; return None on any failure.

    Uses a fast synchronous TCP probe first so we don't spend 2s waiting
    for Windows to report ECONNREFUSED on a non-listening port.
    """
    if not _port_open(config.ipc_host, config.ipc_port):
        return None
    try:
        from rendereye_mcp.bridge.client import ServiceClient

        client = ServiceClient(config)
        await asyncio.wait_for(client.connect(), timeout=5.0)
        return client
    except Exception:
        return None


def _launch_service_process() -> None:
    """Launch the shared service as a detached background subprocess."""
    import subprocess

    subprocess.Popen(
        [sys.executable, "-m", "rendereye_mcp", "service", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
