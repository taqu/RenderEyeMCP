"""Shared IPC service entry point for RenderEyeMCP.

This process is the single long-lived owner of port 37020.
MCP bridge processes connect to it and forward tool calls via IPC.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_READY_FILE = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "rendereye_mcp_service.json"


def _get_default_storage_path(config) -> Path:
    from pathlib import Path

    if config.storage_path:
        return Path(config.storage_path)
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "rendereye_mcp" / "captures.db"


async def _run_service(config, service_instance_id: str) -> None:
    """Main async entry point for the shared service."""
    from rendereye_mcp.captures.registry import CaptureRegistry
    from rendereye_mcp.captures.storage import CaptureStorage
    from rendereye_mcp.instances.manager import InstanceManager
    from rendereye_mcp.ipc.authentication import AuthManager
    from rendereye_mcp.ipc.manager import ExtensionConnectionManager
    from rendereye_mcp.ipc.transport import IPCTransport
    from rendereye_mcp.operations.tracker import OperationTracker
    from rendereye_mcp.sessions.manager import SessionManager
    from rendereye_mcp.sessions.storage import SessionStorage

    from .tools import ToolExecutor

    db_path = _get_default_storage_path(config)
    storage = CaptureStorage(db_path)
    registry = CaptureRegistry(config, storage)

    session_storage = SessionStorage(db_path)
    instance_manager = InstanceManager()
    session_manager = SessionManager(config, session_storage, instance_manager, registry)

    auth_manager = AuthManager()
    auth_manager.generate()

    conn_manager = ExtensionConnectionManager(
        auth_manager=auth_manager,
        instance_manager=instance_manager,
        session_manager=session_manager,
    )

    operation_tracker = OperationTracker()

    # Create transport BEFORE tool_executor so we can pass it in
    transport = IPCTransport(
        config,
        conn_manager=conn_manager,
        service_instance_id=service_instance_id,
    )

    tool_executor = ToolExecutor(
        config=config,
        registry=registry,
        session_manager=session_manager,
        conn_manager=conn_manager,
        operation_tracker=operation_tracker,
        ipc_transport=transport,
    )

    transport.set_tool_executor(tool_executor, service_instance_id)

    ipc_started = False
    registry_started = False
    session_started = False

    shutdown_event = asyncio.Event()

    def _handle_signal(*_) -> None:
        logger.info("[SERVICE] Shutdown signal received")
        shutdown_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal)

    try:
        await transport.start()
        ipc_started = True
        logger.info(
            "[SERVICE] pid=%d instance=%s listening on %s:%d",
            os.getpid(),
            service_instance_id,
            config.ipc_host,
            config.ipc_port,
        )

        await registry.start()
        registry_started = True

        session_manager.start()
        session_started = True

        session_manager.reconcile()

        # Write ready file so bridge processes know we are up
        _write_ready_file(service_instance_id, config)

        logger.info("[SERVICE] Ready — waiting for connections")
        await shutdown_event.wait()

    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            logger.info(
                "[SERVICE] Port %d already bound — another service is running; exiting cleanly",
                config.ipc_port,
            )
            return
        raise

    finally:
        logger.info("[SERVICE] Shutdown started")
        _remove_ready_file()

        try:
            auth_manager.cleanup()
        except Exception:
            logger.exception("Auth manager cleanup failed")

        if session_started:
            try:
                session_manager.stop()
            except Exception:
                logger.exception("Session manager shutdown failed")

        if registry_started:
            try:
                await registry.stop()
            except Exception:
                logger.exception("Registry shutdown failed")

        if ipc_started:
            try:
                await transport.stop()
            except Exception:
                logger.exception("IPC transport shutdown failed")

        try:
            storage.close()
        except Exception:
            logger.exception("Storage shutdown failed")

        logger.info("[SERVICE] Shutdown finished")


def _write_ready_file(service_instance_id: str, config) -> None:
    data = {
        "pid": os.getpid(),
        "instance_id": service_instance_id,
        "port": config.ipc_port,
        "host": config.ipc_host,
    }
    try:
        SERVICE_READY_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _remove_ready_file() -> None:
    try:
        if SERVICE_READY_FILE.exists():
            SERVICE_READY_FILE.unlink()
    except OSError:
        pass


def run_service_command(subcommand: str) -> None:
    """Handle 'rendereye-mcp service <subcommand>'."""
    if subcommand == "run":
        _run_foreground()
    elif subcommand == "start":
        _start_background()
    elif subcommand == "stop":
        _stop_service()
    elif subcommand == "status":
        _show_status()
    else:
        print(f"Unknown service subcommand: {subcommand!r}")
        print("Available subcommands: run, start, stop, status")


def _run_foreground() -> None:
    """Run the service in the foreground (blocking)."""
    from rendereye_mcp.bootstrap import initialize_environment
    from rendereye_mcp.config import Config
    from rendereye_mcp.logging_setup import configure_logging

    initialize_environment()
    config = Config.from_env()
    configure_logging(config.log_level)

    # Check if another service instance is already running
    if _is_service_running(config):
        logger.info("[SERVICE] Another service instance is already running — exiting")
        return

    service_instance_id = str(uuid.uuid4())
    logger.info(
        "[SERVICE] Starting shared service pid=%d instance=%s",
        os.getpid(),
        service_instance_id,
    )

    asyncio.run(_run_service(config, service_instance_id))


def _start_background() -> None:
    """Start the service as a background process."""
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "-m", "rendereye_mcp", "service", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"Service started (pid={proc.pid})")


def _stop_service() -> None:
    """Stop a running service by PID from the ready file."""
    if not SERVICE_READY_FILE.exists():
        print("Service does not appear to be running (no ready file).")
        return

    try:
        data = json.loads(SERVICE_READY_FILE.read_text(encoding="utf-8"))
        pid = data.get("pid")
    except Exception as exc:
        print(f"Could not read service ready file: {exc}")
        return

    if not pid:
        print("Service PID not found in ready file.")
        return

    try:
        import psutil

        proc = psutil.Process(pid)
        proc.terminate()
        # On Windows terminate() skips the service's own cleanup, so remove the ready file here.
        proc.wait(timeout=5)
        _remove_ready_file()
        print(f"Service (pid={pid}) terminated.")
    except psutil.NoSuchProcess:
        _remove_ready_file()
        print(f"Service pid={pid} was not running; removed stale ready file.")
    except Exception as exc:
        print(f"Could not terminate service pid={pid}: {exc}")


def _show_status() -> None:
    """Print current service status."""
    from rendereye_mcp.bootstrap import initialize_environment
    from rendereye_mcp.config import Config

    initialize_environment()
    config = Config.from_env()

    if not SERVICE_READY_FILE.exists():
        print("Service: not running (no ready file)")
        return

    try:
        data = json.loads(SERVICE_READY_FILE.read_text(encoding="utf-8"))
    except Exception:
        print("Service: ready file unreadable")
        return

    if not _is_service_running(config):
        print(f"Service: not running (stale ready file from pid={data.get('pid', '?')})")
        return

    print("Service: running")
    print(f"  PID:         {data.get('pid', '?')}")
    print(f"  Instance ID: {data.get('instance_id', '?')}")
    print(f"  Listening:   {data.get('host', '?')}:{data.get('port', '?')}")


def _is_service_running(config) -> bool:
    """Return True if the service appears to be running (TCP port is bound)."""
    import socket

    try:
        with socket.create_connection((config.ipc_host, config.ipc_port), timeout=1.0):
            return True
    except OSError:
        return False
