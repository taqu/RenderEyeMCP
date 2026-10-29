"""Tests for the phase 5.4 CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "rendereye_mcp", *args],
        capture_output=True,
        text=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# CLI structure
# ---------------------------------------------------------------------------


def test_cli_help_survives_legacy_console_encoding():
    import os

    env = {**os.environ, "PYTHONIOENCODING": "cp932"}
    result = _run("--help", env=env, encoding="cp932")
    assert result.returncode == 0, result.stderr
    assert "setup-agent" in result.stdout


def test_cli_module_importable():
    from rendereye_mcp import cli
    assert callable(cli.main)


def test_cli_version_flag(capsys):
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["--version"])
    assert args.version is True


def test_cli_subcommands_exist():
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    # Verify no error on valid subcommands
    for cmd in ["serve", "setup", "doctor", "uninstall-setup"]:
        args = parser.parse_args([cmd])
        assert args.command == cmd


def test_cli_setup_agent_args():
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["setup-agent", "claude-code", "--scope", "user", "--dry-run"])
    assert args.agent == "claude-code"
    assert args.scope == "user"
    assert args.dry_run is True


def test_cli_setup_agent_remove():
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["setup-agent", "cursor", "--remove"])
    assert args.remove is True


def test_cli_setup_agent_all():
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["setup-agent", "--all"])
    assert args.all_agents is True


def test_cli_doctor_agent():
    from rendereye_mcp.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["doctor", "--agent", "cursor"])
    assert args.agent == "cursor"


def test_cli_version_output(capsys):
    import sys

    from rendereye_mcp import __version__
    from rendereye_mcp.cli import main
    sys.argv = ["rendereye-mcp", "--version"]
    try:
        main()
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_no_args_exits_zero(capsys):
    import sys

    from rendereye_mcp.cli import main
    sys.argv = ["rendereye-mcp"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
