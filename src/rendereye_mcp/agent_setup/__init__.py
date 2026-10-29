"""Coding agent MCP configuration adapters."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rendereye_mcp.agent_setup.base import AgentAdapter

_AGENT_MAP: dict[str, str] = {
    "claude-code": "rendereye_mcp.agent_setup.claude_code",
    "codex": "rendereye_mcp.agent_setup.codex",
    "cursor": "rendereye_mcp.agent_setup.cursor",
    "vscode": "rendereye_mcp.agent_setup.vscode",
    "gemini": "rendereye_mcp.agent_setup.gemini",
}


# `code` follows the reported setup-agent usage and means Codex.
_ALIASES = {"code": "codex", "copilot": "vscode", "gemini-cli": "gemini"}


def _load_adapter(name: str) -> AgentAdapter:
    import importlib

    name = _ALIASES.get(name, name)
    mod = importlib.import_module(_AGENT_MAP[name])
    return mod.Adapter()


def find_executable() -> Path:
    """Return the absolute path to the installed rendereye-mcp executable."""
    # When called as an installed console script, sys.argv[0] is the script path
    # (possibly relative, and without ".exe" on Windows).
    argv0 = Path(sys.argv[0])
    if argv0.name.lower() in ("rendereye-mcp", "rendereye-mcp.exe"):
        for candidate in (argv0, argv0.with_name("rendereye-mcp.exe")):
            if candidate.is_file():
                # Resolve symlinks so we get the real exe
                return candidate.resolve()

    # Prefer the environment that is running this code over whatever PATH finds
    # first, so a second installation on PATH is never written into agent configs.
    python_dir = Path(sys.executable).parent
    for name in ("rendereye-mcp", "rendereye-mcp.exe"):
        candidate = python_dir / name
        if candidate.is_file():
            return candidate.resolve()

    # Try PATH lookup
    found = shutil.which("rendereye-mcp")
    if (
        found
        and Path(found).is_file()
        and Path(found).name.lower() in ("rendereye-mcp", "rendereye-mcp.exe")
    ):
        return Path(found).resolve()

    raise RuntimeError(
        "Cannot locate the rendereye-mcp executable. "
        "Run 'uv tool update-shell' or ensure the install directory is on PATH."
    )


def run_setup_agent(
    *,
    agent: str | None,
    scope: str,
    project_path: Path | None,
    dry_run: bool,
    force: bool,
    remove: bool,
    all_agents: bool,
) -> None:
    """Main entry point for the setup-agent command."""
    if all_agents:
        _setup_all(
            scope=scope, project_path=project_path, dry_run=dry_run, force=force, remove=remove
        )
        return

    if agent is None:
        _interactive_select(
            scope=scope, project_path=project_path, dry_run=dry_run, force=force, remove=remove
        )
        return

    _setup_single(
        agent=agent,
        scope=scope,
        project_path=project_path,
        dry_run=dry_run,
        force=force,
        remove=remove,
    )


def _setup_single(
    *,
    agent: str,
    scope: str,
    project_path: Path | None,
    dry_run: bool,
    force: bool,
    remove: bool,
) -> None:
    adapter = _load_adapter(agent)

    if scope == "user" and not adapter.SUPPORTS_USER_SCOPE:
        print(f"  Error: {agent} does not support user scope.")
        return
    if scope == "project" and not adapter.SUPPORTS_PROJECT_SCOPE:
        print(f"  Error: {agent} does not support project scope.")
        return
    if scope == "project" and project_path is None:
        project_path = Path.cwd()

    cfg_path = adapter.config_path(scope=scope, project_path=project_path)
    print(f"Agent: {agent} | Scope: {scope} | Config: {cfg_path}")
    if dry_run:
        print("(dry-run — no files will be written)")
    config = adapter.read_config(cfg_path)
    if remove:
        new_config, removed = adapter.remove(config, force=force)
        action = "removed" if removed else "unchanged"
    else:
        exe = find_executable()
        print(f"Executable: {exe}")
        try:
            new_config, action = adapter.apply(config, exe, force=force)
        except ValueError:
            if not dry_run or force:
                raise
            # A preview may show the replacement, but never authorizes it.
            new_config, action = adapter.apply(config, exe, force=True)
            print("Conflict: existing entry differs. Applying this replacement requires --force.")
    print(f"Proposed action: {action}")
    if action == "unchanged":
        if dry_run:
            print("Unrelated settings preserved: yes (validated; no changes)")
        return
    if dry_run:
        adapter.preview(cfg_path, new_config)
        return
    adapter.write_config(cfg_path, new_config)
    print(f"Configuration {action}; validated. Original preserved in a .bak file if it existed.")
    adapter.print_restart_instructions()


def _setup_all(
    *,
    scope: str,
    project_path: Path | None,
    dry_run: bool,
    force: bool,
    remove: bool,
) -> None:
    failed = []
    for name in _AGENT_MAP:
        adapter = _load_adapter(name)
        if scope == "user" and not adapter.SUPPORTS_USER_SCOPE:
            continue
        if scope == "project" and not adapter.SUPPORTS_PROJECT_SCOPE:
            continue
        cfg_path = adapter.config_path(scope=scope, project_path=project_path or Path.cwd())
        if scope == "user" and not cfg_path.parent.exists():
            print(f"[{name}] Skipped (not detected)")
            continue
        try:
            _setup_single(
                agent=name,
                scope=scope,
                project_path=project_path,
                dry_run=dry_run,
                force=force,
                remove=remove,
            )
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"[{name}] Error: {exc}")
            failed.append(name)
    if failed:
        raise ValueError("Setup failed for: " + ", ".join(failed))


def _interactive_select(
    *,
    scope: str,
    project_path: Path | None,
    dry_run: bool,
    force: bool,
    remove: bool,
) -> None:
    print("Available agents:")
    agents = list(_AGENT_MAP.keys())
    for i, name in enumerate(agents, 1):
        print(f"  {i}. {name}")
    print()
    try:
        raw = input("Select agent (number or name, or 'all'): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if raw.lower() == "all":
        _setup_all(
            scope=scope, project_path=project_path, dry_run=dry_run, force=force, remove=remove
        )
        return

    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(agents):
            raw = agents[idx]
        else:
            print("Invalid selection.")
            return

    raw = _ALIASES.get(raw, raw)
    if raw not in _AGENT_MAP:
        print(f"Unknown agent: {raw}")
        return

    _setup_single(
        agent=raw,
        scope=scope,
        project_path=project_path,
        dry_run=dry_run,
        force=force,
        remove=remove,
    )
