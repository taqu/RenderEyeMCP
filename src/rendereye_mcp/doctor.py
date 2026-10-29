"""Diagnostic command: rendereye-mcp doctor."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STATUS_ICONS = {
    "PASS": "✓",
    "WARNING": "!",
    "FAIL": "✗",
    "NOT_TESTED": "?",
}


def _fmt(status: str, component: str, detail: str) -> str:
    icon = _STATUS_ICONS.get(status, "?")
    return f"  [{icon}] {component:<30} {detail}"


def _check_version() -> tuple[str, str, str]:
    try:
        from rendereye_mcp import __version__

        return ("PASS", "Version", __version__)
    except Exception as exc:
        return ("FAIL", "Version", str(exc))


def _check_executable() -> tuple[str, str, str]:
    try:
        from rendereye_mcp.agent_setup import find_executable

        exe = find_executable()
        if exe.is_file():
            return ("PASS", "Executable", str(exe))
        return ("WARNING", "Executable", f"Path found but not a file: {exe}")
    except RuntimeError as exc:
        return ("FAIL", "Executable", str(exc))


def _check_python() -> tuple[str, str, str]:
    v = sys.version.split()[0]
    return ("PASS", "Python", f"{v} ({sys.executable})")


def _check_config_dir() -> tuple[str, str, str]:
    from rendereye_mcp.setup_cmd import get_default_install_dir

    d = get_default_install_dir()
    if d.exists():
        return ("PASS", "Config directory", str(d))
    return ("FAIL", "Config directory", f"Missing: {d}")


def _check_env_file() -> tuple[str, str, str]:
    from rendereye_mcp.setup_cmd import get_default_install_dir

    env_file = get_default_install_dir() / ".env"
    if env_file.exists():
        return ("PASS", ".env file", str(env_file))
    return ("FAIL", ".env file", f"Missing: {env_file}")


def _check_env_var() -> tuple[str, str, str]:
    val = os.environ.get("RENDEREYE_ENV_FILE", "")
    if not val:
        return ("WARNING", "RENDEREYE_ENV_FILE", "Not set in current process environment")
    p = Path(val)
    if p.exists():
        return ("PASS", "RENDEREYE_ENV_FILE", val)
    return ("WARNING", "RENDEREYE_ENV_FILE", f"Set but file missing: {val}")


def _check_renderdoc() -> tuple[str, str, str]:
    from rendereye_mcp.setup_cmd import _read_env_values, get_default_install_dir

    env_file = get_default_install_dir() / ".env"
    if not env_file.exists():
        return ("NOT_TESTED", "RenderDoc executable", "No .env file")
    vals = _read_env_values(env_file)
    rdoc = vals.get("RENDEREYE_RENDERDOC_EXE", "")
    if not rdoc:
        return ("WARNING", "RenderDoc executable", "Not configured in .env")
    if Path(rdoc).is_file():
        return ("PASS", "RenderDoc executable", rdoc)
    return ("FAIL", "RenderDoc executable", f"Not found: {rdoc}")


def _check_extension() -> tuple[str, str, str]:
    from rendereye_mcp.setup_cmd import get_extension_install_dir

    ext_dir = get_extension_install_dir()
    init = ext_dir / "__init__.py"
    ext_json = ext_dir / "extension.json"
    if ext_dir.exists() and init.exists() and ext_json.exists():
        return ("PASS", "RenderDoc extension", str(ext_dir))
    if ext_dir.exists():
        return ("WARNING", "RenderDoc extension", f"Incomplete install: {ext_dir}")
    return ("FAIL", "RenderDoc extension", f"Not installed: {ext_dir}")


def _check_ipc() -> tuple[str, str, str]:
    from rendereye_mcp.setup_cmd import _read_env_values, get_default_install_dir

    env_file = get_default_install_dir() / ".env"
    if not env_file.exists():
        return ("NOT_TESTED", "IPC configuration", "No .env file")
    vals = _read_env_values(env_file)
    host = vals.get("RENDEREYE_IPC_HOST", "127.0.0.1")
    port = vals.get("RENDEREYE_IPC_PORT", "37020")
    return ("PASS", "IPC configuration", f"{host}:{port}")


def _check_service() -> tuple[str, str, str]:
    """Check whether the shared IPC service is reachable."""
    import asyncio
    import json
    import os
    from pathlib import Path

    from rendereye_mcp.bootstrap import initialize_environment
    from rendereye_mcp.config import Config

    initialize_environment()

    try:
        config = Config.from_env()
    except Exception as exc:
        return ("WARNING", "Shared service", f"Config error: {exc}")

    # Check ready file first
    ready_file = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "rendereye_mcp_service.json"
    ready_data = None
    if ready_file.exists():
        try:
            ready_data = json.loads(ready_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Try to connect and get service info
    async def _probe():
        from rendereye_mcp.bridge.client import ServiceClient
        client = ServiceClient(config)
        try:
            await asyncio.wait_for(client.connect(), timeout=2.0)
            instance_id = client.service_instance_id
            return instance_id
        except Exception:
            return None
        finally:
            try:
                await client.close()
            except Exception:
                pass

    try:
        instance_id = asyncio.run(_probe())
    except Exception:
        instance_id = None

    if instance_id is not None:
        pid_info = f" pid={ready_data.get('pid', '?')}" if ready_data else ""
        return ("PASS", "Shared service", f"Running — instance={instance_id}{pid_info}")

    if ready_data:
        return (
            "WARNING",
            "Shared service",
            f"Ready file present (pid={ready_data.get('pid', '?')}) but TCP connection failed",
        )

    return ("WARNING", "Shared service", "Not running — will auto-start on first MCP bridge connection")


# ---------------------------------------------------------------------------
# Per-agent checks
# ---------------------------------------------------------------------------


def _check_agent(name: str) -> list[tuple[str, str, str]]:
    from rendereye_mcp.agent_setup import _load_adapter

    results: list[tuple[str, str, str]] = []

    adapter = _load_adapter(name)

    cfg_path = adapter.config_path(scope="user")
    results.append(
        (
            "PASS" if cfg_path.parent.exists() else "WARNING",
            f"{name} config dir",
            str(cfg_path.parent),
        )
    )

    if not cfg_path.exists():
        results.append(("WARNING", f"{name} config file", f"Missing: {cfg_path}"))
        return results

    results.append(("PASS", f"{name} config file", str(cfg_path)))

    config = adapter.read_config(cfg_path)
    if not config:
        results.append(("WARNING", f"{name} config syntax", "Empty or invalid"))
        return results

    results.append(("PASS", f"{name} config syntax", "Valid"))

    # Navigate to servers
    servers = config
    for key in adapter.get_servers_key():
        servers = servers.get(key, {})

    if "rendereye" not in servers:
        results.append(("FAIL", f"{name} rendereye entry", "Not found"))
        return results

    results.append(("PASS", f"{name} rendereye entry", "Present"))

    entry = servers["rendereye"]
    cmd = entry.get("command", "")
    if cmd:
        exe = Path(cmd)
        if exe.is_file():
            results.append(("PASS", f"{name} executable", cmd))
        else:
            results.append(("FAIL", f"{name} executable", f"Not found: {cmd}"))
    else:
        results.append(("FAIL", f"{name} executable", "command not set"))

    args = entry.get("args", [])
    if "serve" in args:
        results.append(("PASS", f"{name} startup args", str(args)))
    else:
        results.append(("WARNING", f"{name} startup args", f"'serve' not in args: {args}"))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_doctor(agent: str | None = None) -> None:
    """Run installation diagnostics."""
    print("RenderEyeMCP — doctor")
    print()

    app_checks = [
        _check_version(),
        _check_executable(),
        _check_python(),
        _check_config_dir(),
        _check_env_file(),
        _check_env_var(),
        _check_renderdoc(),
        _check_extension(),
        _check_ipc(),
        _check_service(),
    ]

    print("Application checks:")
    for item in app_checks:
        print(_fmt(*item))

    if agent:
        print()
        print(f"Agent checks ({agent}):")
        try:
            agent_checks = _check_agent(agent)
        except Exception as exc:
            agent_checks = [("FAIL", agent, str(exc))]
        for item in agent_checks:
            print(_fmt(*item))

    print()
    counts = {s: 0 for s in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    all_checks = app_checks + (agent_checks if agent else [])
    for status, _, _ in all_checks:
        counts[status] = counts.get(status, 0) + 1

    summary = ", ".join(f"{s}: {n}" for s, n in counts.items() if n > 0)
    print(f"Summary: {summary}")

    fail_count = counts.get("FAIL", 0)
    if fail_count:
        print(f"\n{fail_count} check(s) failed. Run 'rendereye-mcp setup' to fix.")
    else:
        print("\nAll critical checks passed.")
