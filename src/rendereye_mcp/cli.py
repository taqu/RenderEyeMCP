"""Command-line interface for RenderEyeMCP."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_AGENTS = ["claude-code", "codex", "cursor", "vscode", "gemini", "code", "copilot", "gemini-cli"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rendereye-mcp",
        description="RenderEyeMCP — MCP server for RenderDoc GPU frame debugging",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # serve
    sub.add_parser("serve", help="Start MCP server (stdio transport)")

    # setup
    p = sub.add_parser("setup", help="Configure RenderEyeMCP and RenderDoc integration")
    p.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Override configuration directory",
    )
    p.add_argument("--non-interactive", action="store_true", help="Skip interactive prompts")

    # setup-agent
    p = sub.add_parser("setup-agent", help="Configure a coding agent MCP integration")
    p.add_argument(
        "agent", nargs="?", choices=_AGENTS, metavar="AGENT", help=f"Agent: {', '.join(_AGENTS)}"
    )
    p.add_argument(
        "--scope",
        choices=["user", "project"],
        default="user",
        help="Configuration scope (default: user)",
    )
    p.add_argument(
        "--project-path",
        type=Path,
        default=None,
        metavar="PATH",
        help="Project directory for project-scope configuration",
    )
    p.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    p.add_argument("--force", action="store_true", help="Overwrite existing rendereye entry")
    p.add_argument(
        "--remove", action="store_true", help="Remove rendereye entry from agent configuration"
    )
    p.add_argument(
        "--all", dest="all_agents", action="store_true", help="Configure all detected agents"
    )

    # doctor
    p = sub.add_parser("doctor", help="Diagnose installation and connectivity")
    p.add_argument(
        "--agent",
        choices=_AGENTS,
        default=None,
        metavar="AGENT",
        help="Also check a specific agent configuration",
    )

    # uninstall-setup
    p = sub.add_parser("uninstall-setup", help="Remove RenderEye-managed integration")
    p.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Override configuration directory",
    )

    # service
    p = sub.add_parser("service", help="Manage the shared IPC service")
    service_sub = p.add_subparsers(dest="service_command")
    service_sub.add_parser("run", help="Run the shared service in the foreground")
    service_sub.add_parser("start", help="Start the shared service in the background")
    service_sub.add_parser("stop", help="Stop the shared service")
    service_sub.add_parser("status", help="Show shared service status")

    return parser


def _tolerate_console_encoding() -> None:
    """Avoid UnicodeEncodeError for "—"/"✓" on legacy code pages (e.g. cp932) when piped."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def main() -> None:
    """Entry point for the rendereye-mcp command."""
    _tolerate_console_encoding()
    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        from rendereye_mcp import __version__

        print(f"rendereye-mcp {__version__}")
        return

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        from rendereye_mcp.__main__ import main as _serve

        _serve()

    elif args.command == "setup":
        from rendereye_mcp.setup_cmd import run_setup

        run_setup(install_dir=args.install_dir, interactive=not args.non_interactive)

    elif args.command == "setup-agent":
        from rendereye_mcp.agent_setup import run_setup_agent

        try:
            run_setup_agent(
                agent=args.agent,
                scope=args.scope,
                project_path=args.project_path,
                dry_run=args.dry_run,
                force=args.force,
                remove=args.remove,
                all_agents=args.all_agents,
            )
        except (ValueError, OSError, RuntimeError) as exc:
            parser.exit(1, f"Error: {exc}\n")

    elif args.command == "doctor":
        from rendereye_mcp.doctor import run_doctor

        run_doctor(agent=args.agent)

    elif args.command == "uninstall-setup":
        from rendereye_mcp.setup_cmd import run_uninstall

        run_uninstall(install_dir=args.install_dir)

    elif args.command == "service":
        from rendereye_mcp.service.main import run_service_command

        run_service_command(args.service_command or "status")


if __name__ == "__main__":
    main()
