"""Tests for phase 5.4 agent configuration adapters."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

FAKE_EXE = Path("/usr/local/bin/rendereye-mcp")


# ---------------------------------------------------------------------------
# Base adapter helpers
# ---------------------------------------------------------------------------


def test_base_write_json_atomic(tmp_path):
    from rendereye_mcp.agent_setup.base import read_json, write_json
    p = tmp_path / "config.json"
    write_json(p, {"mcpServers": {}})
    assert p.exists()
    data = read_json(p)
    assert "mcpServers" in data


def test_base_write_json_backup(tmp_path):
    from rendereye_mcp.agent_setup.base import write_json
    p = tmp_path / "config.json"
    p.write_text('{"old": true}', encoding="utf-8")
    write_json(p, {"old": True, "mcpServers": {"rendereye": {"command": "test"}}})
    backup = p.with_suffix(".json.bak")
    assert backup.exists()
    assert json.loads(backup.read_text())["old"] is True


def test_base_read_json_missing(tmp_path):
    from rendereye_mcp.agent_setup.base import read_json
    result = read_json(tmp_path / "nonexistent.json")
    assert result == {}


def test_base_read_json_invalid(tmp_path):
    from rendereye_mcp.agent_setup.base import read_json
    p = tmp_path / "bad.json"
    p.write_text("not valid json {{", encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(p)


# ---------------------------------------------------------------------------
# apply / remove via base
# ---------------------------------------------------------------------------


def _make_adapter(name: str):
    import importlib
    mod = importlib.import_module(f"rendereye_mcp.agent_setup.{name.replace('-', '_')}")
    return mod.Adapter()


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "vscode", "gemini"])
def test_apply_adds_entry(agent):
    adapter = _make_adapter(agent)
    config, action = adapter.apply({}, FAKE_EXE)
    assert action == "added"
    servers = config
    for key in adapter.get_servers_key():
        servers = servers.get(key, {})
    # vscode may use servers or mcpServers; check both
    if agent == "vscode":
        servers = config.get("mcpServers", config.get("servers", {}))
    assert "rendereye" in servers


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "gemini"])
def test_apply_unchanged(agent):
    adapter = _make_adapter(agent)
    config, _ = adapter.apply({}, FAKE_EXE)
    _, action = adapter.apply(config, FAKE_EXE)
    assert action == "unchanged"


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "gemini"])
def test_apply_force_updates(agent):
    adapter = _make_adapter(agent)
    config, _ = adapter.apply({}, FAKE_EXE)
    new_exe = Path("/other/rendereye-mcp")
    _, action = adapter.apply(config, new_exe, force=True)
    assert action == "updated"


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "gemini"])
def test_remove_entry(agent):
    adapter = _make_adapter(agent)
    config, _ = adapter.apply({}, FAKE_EXE)
    new_config, removed = adapter.remove(config)
    assert removed is True
    servers = new_config
    for key in adapter.get_servers_key():
        servers = servers.get(key, {})
    assert "rendereye" not in servers


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "gemini"])
def test_remove_nonexistent(agent):
    adapter = _make_adapter(agent)
    _, removed = adapter.remove({})
    assert removed is False


@pytest.mark.parametrize("agent", ["claude_code", "cursor", "gemini"])
def test_preserves_other_servers(agent):
    adapter = _make_adapter(agent)
    existing_key = adapter.get_servers_key()[0]
    config = {existing_key: {"other-server": {"command": "other", "args": []}}}
    new_config, action = adapter.apply(config, FAKE_EXE)
    servers = new_config[existing_key]
    assert "other-server" in servers
    assert "rendereye" in servers


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------


def test_claude_code_user_config_path():
    from rendereye_mcp.agent_setup.claude_code import Adapter
    a = Adapter()
    p = a.config_path("user")
    assert p.name == ".claude.json"
    assert p.parent == Path.home()


def test_claude_code_project_config_path():
    from rendereye_mcp.agent_setup.claude_code import Adapter
    a = Adapter()
    p = a.config_path("project", project_path=Path("/my/project"))
    assert p == Path("/my/project/.mcp.json")


def test_claude_code_server_entry():
    from rendereye_mcp.agent_setup.claude_code import Adapter
    a = Adapter()
    entry = a.build_server_entry(FAKE_EXE)
    assert entry["type"] == "stdio"
    assert entry["command"] == str(FAKE_EXE)
    assert "serve" in entry["args"]


def test_claude_code_roundtrip(tmp_path):
    from rendereye_mcp.agent_setup.claude_code import Adapter
    a = Adapter()
    cfg_path = tmp_path / ".claude.json"
    config = a.read_config(cfg_path)
    config, _ = a.apply(config, FAKE_EXE)
    a.write_config(cfg_path, config)
    loaded = a.read_config(cfg_path)
    assert loaded["mcpServers"]["rendereye"]["command"] == str(FAKE_EXE)


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------


def test_cursor_user_config_path():
    from rendereye_mcp.agent_setup.cursor import Adapter
    a = Adapter()
    p = a.config_path("user")
    assert p.name == "mcp.json"
    assert p.parent.name == ".cursor"


def test_cursor_project_config_path():
    from rendereye_mcp.agent_setup.cursor import Adapter
    a = Adapter()
    p = a.config_path("project", project_path=Path("/my/project"))
    assert p == Path("/my/project/.cursor/mcp.json")


# ---------------------------------------------------------------------------
# VS Code
# ---------------------------------------------------------------------------


def test_vscode_project_config_path():
    from rendereye_mcp.agent_setup.vscode import Adapter
    a = Adapter()
    p = a.config_path("project", project_path=Path("/my/project"))
    assert p == Path("/my/project/.vscode/mcp.json")


def test_vscode_user_config_path():
    from rendereye_mcp.agent_setup.vscode import Adapter
    a = Adapter()
    p = a.config_path("user", project_path=Path("/my/project"))
    assert p.name == "mcp.json"
    assert p.parent.name == "User"


def test_vscode_servers_key_for_existing_vscode_format():
    from rendereye_mcp.agent_setup.vscode import Adapter
    a = Adapter()
    config = {"servers": {"existing": {}}}
    new_config, action = a.apply(config, FAKE_EXE)
    assert "servers" in new_config
    assert "rendereye" in new_config["servers"]


def test_vscode_mcpservers_key_for_copilot_format():
    from rendereye_mcp.agent_setup.vscode import Adapter
    a = Adapter()
    config = {"mcpServers": {"existing": {}}}
    new_config, action = a.apply(config, FAKE_EXE)
    assert "mcpServers" in new_config
    assert "rendereye" in new_config["servers"]
    assert new_config["mcpServers"] == config["mcpServers"]


def test_vscode_remove_from_either_key():
    from rendereye_mcp.agent_setup.vscode import Adapter
    a = Adapter()
    config = {"servers": {"rendereye": {"command": "x", "args": ["serve"]}}}
    new_config, removed = a.remove(config, force=True)
    assert removed is True
    assert "rendereye" not in new_config.get("servers", {})


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def test_gemini_user_config_path():
    from rendereye_mcp.agent_setup.gemini import Adapter
    a = Adapter()
    p = a.config_path("user")
    assert p == Path.home() / ".gemini" / "settings.json"


def test_gemini_project_config_path():
    from rendereye_mcp.agent_setup.gemini import Adapter
    a = Adapter()
    p = a.config_path("project", project_path=Path("/my/project"))
    assert p == Path("/my/project/.gemini/settings.json")


# ---------------------------------------------------------------------------
# Codex (TOML)
# ---------------------------------------------------------------------------


def test_codex_config_path():
    from rendereye_mcp.agent_setup.codex import Adapter
    a = Adapter()
    p = a.config_path("user")
    assert p == Path.home() / ".codex" / "config.toml"


def test_codex_no_project_scope():
    from rendereye_mcp.agent_setup.codex import Adapter
    a = Adapter()
    assert a.SUPPORTS_PROJECT_SCOPE
    assert a.config_path('project', Path('/project')) == Path('/project/.codex/config.toml')


def test_codex_write_and_read(tmp_path):
    from rendereye_mcp.agent_setup.codex import _read_toml, _write_toml
    config = {"mcp_servers": {"rendereye": {"command": str(FAKE_EXE), "args": ["serve"]}}}
    p = tmp_path / "config.toml"
    _write_toml(p, config)
    assert p.exists()
    loaded = _read_toml(p)
    assert "mcp_servers" in loaded
    assert "rendereye" in loaded["mcp_servers"]
    assert loaded["mcp_servers"]["rendereye"]["command"] == str(FAKE_EXE)


def test_codex_apply_adds(tmp_path):
    from rendereye_mcp.agent_setup.codex import Adapter
    a = Adapter()
    config, action = a.apply({}, FAKE_EXE)
    assert action == "added"
    assert "rendereye" in config["mcp_servers"]


def test_codex_remove(tmp_path):
    from rendereye_mcp.agent_setup.codex import Adapter
    a = Adapter()
    config, _ = a.apply({}, FAKE_EXE)
    config, removed = a.remove(config)
    assert removed is True
    assert "rendereye" not in config.get("mcp_servers", {})


def test_codex_preserves_other_entries(tmp_path):
    from rendereye_mcp.agent_setup.codex import Adapter
    a = Adapter()
    config = {"mcp_servers": {"other": {"command": "other-cmd", "args": []}}}
    new_config, _ = a.apply(config, FAKE_EXE)
    assert "other" in new_config["mcp_servers"]
    assert "rendereye" in new_config["mcp_servers"]


# ---------------------------------------------------------------------------
# find_executable
# ---------------------------------------------------------------------------


def test_find_executable_from_argv(tmp_path):
    from rendereye_mcp.agent_setup import find_executable
    fake_exe = tmp_path / "rendereye-mcp"
    fake_exe.touch()
    with patch("sys.argv", [str(fake_exe)]):
        result = find_executable()
        assert result.is_absolute()


def test_find_executable_via_which(tmp_path):
    from rendereye_mcp.agent_setup import find_executable
    fake_exe = tmp_path / "rendereye-mcp"
    fake_exe.touch()
    with patch("sys.argv", ["non-absolute"]), \
         patch("sys.executable", str(tmp_path / "py" / "python.exe")), \
         patch("shutil.which", return_value=str(fake_exe)):
        result = find_executable()
        assert result == fake_exe.resolve()


def test_find_executable_relative_argv(tmp_path, monkeypatch):
    from rendereye_mcp.agent_setup import find_executable
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "rendereye-mcp.exe").touch()
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["venv/Scripts/rendereye-mcp"]):
        assert find_executable() == (scripts / "rendereye-mcp.exe").resolve()


def test_find_executable_prefers_running_environment_over_path(tmp_path):
    from rendereye_mcp.agent_setup import find_executable
    own = tmp_path / "own"
    own.mkdir()
    (own / "rendereye-mcp.exe").touch()
    other = tmp_path / "other" / "rendereye-mcp.exe"
    other.parent.mkdir()
    other.touch()
    with patch("sys.argv", ["python", "-m", "rendereye_mcp"]), \
         patch("sys.executable", str(own / "python.exe")), \
         patch("shutil.which", return_value=str(other)):
        assert find_executable() == (own / "rendereye-mcp.exe").resolve()


def test_find_executable_not_found():
    from rendereye_mcp.agent_setup import find_executable
    with patch("sys.argv", ["non-absolute"]), \
         patch("shutil.which", return_value=None), \
         patch("pathlib.Path.is_file", return_value=False):
        with pytest.raises(RuntimeError):
            find_executable()


# ---------------------------------------------------------------------------
# dry-run integration
# ---------------------------------------------------------------------------


def test_setup_single_dry_run(tmp_path, capsys):
    from rendereye_mcp.agent_setup import _setup_single
    fake_exe = tmp_path / "rendereye-mcp"
    fake_exe.touch()
    with patch("rendereye_mcp.agent_setup.find_executable", return_value=fake_exe), \
         patch('pathlib.Path.home', return_value=tmp_path):
        _setup_single(
            agent="cursor",
            scope="user",
            project_path=None,
            dry_run=True,
            force=False,
            remove=False,
        )
    captured = capsys.readouterr()
    assert "dry-run" in captured.out.lower()
    assert "rendereye" in captured.out.lower()


# ---------------------------------------------------------------------------
# Unicode and spaces in paths
# ---------------------------------------------------------------------------


def test_write_config_with_spaces_in_path(tmp_path):
    from rendereye_mcp.agent_setup.base import read_json, write_json
    p = tmp_path / "dir with spaces" / "config.json"
    p.parent.mkdir(parents=True)
    write_json(p, {"mcpServers": {"rendereye": {"command": "/path/with spaces/exe"}}})
    loaded = read_json(p)
    assert loaded["mcpServers"]["rendereye"]["command"] == "/path/with spaces/exe"


def test_build_server_entry_with_spaces(tmp_path):
    from rendereye_mcp.agent_setup.claude_code import Adapter
    a = Adapter()
    exe = Path("/path/with spaces/rendereye-mcp")
    entry = a.build_server_entry(exe)
    assert " " in entry["command"]
    assert entry["command"] == str(exe)
