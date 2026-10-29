"""Safety regression tests use synthetic files and isolated profiles exclusively."""

from __future__ import annotations

import copy
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from rendereye_mcp.agent_setup import (
    _load_adapter,
    _setup_all,
    _setup_single,
    base,
    find_executable,
)

AGENTS = ["claude-code", "codex", "cursor", "vscode", "gemini"]
EXE = Path("D:/Synthetic 日本語/Program Files/rendereye-mcp.exe")
FIXTURES = Path(__file__).parent / "fixtures" / "agents"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("RENDEREYE_ENV_FILE", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))


@pytest.fixture(params=AGENTS)
def configured(request, tmp_path):
    name = request.param
    adapter = _load_adapter(name)
    suffix = ".toml" if name == "codex" else ".jsonc" if name == "vscode" else ".json"
    path = tmp_path / "日本語 with spaces" / ("config" + suffix)
    path.parent.mkdir()
    path.write_bytes((FIXTURES / (name + suffix)).read_bytes())
    return adapter, path


def stripped(adapter, config):
    result = copy.deepcopy(dict(config))
    key = adapter.get_servers_key()[0]
    result.get(key, {}).pop("rendereye", None)
    return result


def test_add_update_remove_preservation(configured):
    adapter, path = configured
    raw = path.read_bytes()
    before = adapter.read_config(path)
    added, action = adapter.apply(before, EXE)
    assert action == "added"
    assert before == adapter.read_config(path)  # pure in-memory edit
    adapter.write_config(path, added)
    after = adapter.read_config(path)
    assert stripped(adapter, after) == before
    assert path.with_suffix(path.suffix + ".bak").read_bytes() == raw
    # Other config text, comments, quoting and indentation survive insertion.
    if adapter.NAME == "Codex":
        assert raw in path.read_bytes()
    elif adapter.NAME.startswith("VS Code"):
        assert "// Preserve this comment." in path.read_text(encoding="utf-8")
        assert "// Other server and environment remain untouched." in path.read_text(
            encoding="utf-8"
        )
    current = path.read_bytes()
    unchanged, action = adapter.apply(after, EXE)
    assert action == "unchanged"
    adapter.write_config(path, unchanged)
    assert path.read_bytes() == current
    with pytest.raises(ValueError, match="conflict"):
        adapter.apply(after, Path("D:/New/rendereye-mcp.exe"))
    update, action = adapter.apply(after, Path("D:/New/rendereye-mcp.exe"), force=True)
    assert action == "updated"
    adapter.write_config(path, update)
    assert stripped(adapter, adapter.read_config(path)) == before
    removed, yes = adapter.remove(adapter.read_config(path))
    assert yes
    adapter.write_config(path, removed)
    assert adapter.read_config(path) == before
    current = path.read_bytes()
    removed, yes = adapter.remove(adapter.read_config(path))
    assert not yes
    adapter.write_config(path, removed)
    assert path.read_bytes() == current


def test_targeted_write_guard(configured):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    config["unrelated"] = "must never be written"
    with pytest.raises(ValueError, match="outside"):
        adapter.write_config(path, config)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("content", [b"", b"not valid", b"[]", b'{"a":1,"a":2}', b'{"a":NaN}'])
def test_malformed_fails_closed(configured, content):
    adapter, path = configured
    if adapter.NAME == "Codex" and content == b"":
        # Empty TOML is valid; empty JSON is not.
        assert adapter.parse("") == {}
        return
    path.write_bytes(content)
    with pytest.raises(ValueError):
        config = adapter.read_config(path)
        config, _ = adapter.apply(config, EXE, force=True)
        adapter.write_config(path, config)
    assert path.read_bytes() == content


def test_bad_container_fails_closed(configured):
    adapter, path = configured
    key = adapter.get_servers_key()[0]
    text = f'{key} = "invalid"' if adapter.NAME == "Codex" else '{"' + key + '":[]}'
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="object/table"):
        adapter.read_config(path)
    assert path.read_text(encoding="utf-8") == text


def test_missing_file(configured):
    adapter, path = configured
    path.unlink()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    assert adapter._servers(adapter.read_config(path))["rendereye"]["command"] == str(EXE)


def test_concurrent_change(configured):
    adapter, path = configured
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    external = b"# edited externally" if adapter.NAME == "Codex" else b'{"external":true}'
    path.write_bytes(external)
    with pytest.raises(ValueError, match="concurrently"):
        adapter.write_config(path, config)
    assert path.read_bytes() == external


@pytest.mark.parametrize("failure", ["replace", "fsync", "mkstemp"])
def test_failed_write_preserves_original(configured, failure):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    target = {"replace": "os.replace", "fsync": "os.fsync", "mkstemp": "tempfile.mkstemp"}[failure]
    with patch("rendereye_mcp.agent_setup.base." + target, side_effect=OSError("injected failure")):
        with pytest.raises(OSError, match="injected"):
            adapter.write_config(path, config)
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.tmp"))
    assert not list(path.parent.glob("*.lock"))


def test_interrupt_preserves_original(configured):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    with patch("rendereye_mcp.agent_setup.base.os.replace", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            adapter.write_config(path, config)
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.tmp"))
    assert not list(path.parent.glob("*.lock"))


def test_read_only(configured):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    mode = path.stat().st_mode
    path.chmod(stat.S_IREAD)
    try:
        with pytest.raises(PermissionError):
            adapter.write_config(path, config)
        assert path.read_bytes() == raw
    finally:
        path.chmod(mode)


def test_dry_run_is_write_free(configured, monkeypatch, capsys):
    adapter, path = configured
    raw = path.read_bytes()
    monkeypatch.setattr("rendereye_mcp.agent_setup._load_adapter", lambda _: adapter)
    monkeypatch.setattr(adapter, "config_path", lambda **_: path)
    monkeypatch.setattr("rendereye_mcp.agent_setup.find_executable", lambda: EXE)
    _setup_single(
        agent="synthetic", scope="user", project_path=None, dry_run=True, force=False, remove=False
    )
    assert path.read_bytes() == raw
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]
    output = capsys.readouterr().out
    assert "Unrelated settings preserved: yes" in output
    assert "+++ " in output
    assert "test-only" not in output


@pytest.mark.parametrize("name", AGENTS)
def test_remove_does_not_require_launcher(name, tmp_path, monkeypatch):
    adapter = _load_adapter(name)
    path = adapter.config_path("project", tmp_path)
    monkeypatch.setattr(
        "rendereye_mcp.agent_setup.find_executable", lambda: pytest.fail("launcher requested")
    )
    _setup_single(
        agent=name, scope="project", project_path=tmp_path, dry_run=False, force=False, remove=True
    )
    assert not path.exists()


@pytest.mark.parametrize("name", AGENTS)
def test_custom_namesake_requires_force(name):
    adapter = _load_adapter(name)
    key = adapter.get_servers_key()[0]
    config = {key: {"rendereye": {"command": "custom", "args": []}}}
    with pytest.raises(ValueError):
        adapter.apply(config, EXE)
    with pytest.raises(ValueError):
        adapter.remove(config)
    assert adapter.remove(config, force=True)[1]


def test_source_file_is_never_launcher(tmp_path, monkeypatch):
    source = tmp_path / "__main__.py"
    source.touch()
    monkeypatch.setattr("sys.argv", [str(source)])
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr("sys.executable", str(tmp_path / "python.exe"))
    with pytest.raises(RuntimeError):
        find_executable()


@pytest.mark.parametrize(
    "alias,name", [("code", "codex"), ("copilot", "vscode"), ("gemini-cli", "gemini")]
)
def test_aliases(alias, name):
    assert type(_load_adapter(alias)) is type(_load_adapter(name))


@pytest.mark.parametrize(
    "text",
    [
        '{"servers":{"rendereye":{"command":"old"},}}',
        '{"servers":{"other":{},"rendereye":{"command":"old"},}}',
        '{"servers":{"rendereye":{"command":"old"},"other":{},}}',
        '{"servers":{/*before*/"rendereye":{"command":"old"}/*after*/,/*tail*/}}',
        '{"servers":{/*empty*/},"a":[1,2,],}',
        "//root\n{}",
    ],
)
def test_jsonc_all_positions(tmp_path, text):
    adapter = _load_adapter("vscode")
    path = tmp_path / "mcp.json"
    path.write_text(text)
    original = adapter.read_config(path)
    added, _ = adapter.apply(original, EXE, force=True)
    adapter.write_config(path, added)
    removed, _ = adapter.remove(adapter.read_config(path))
    adapter.write_config(path, removed)
    expected = copy.deepcopy(original)
    expected.setdefault("servers", {}).pop("rendereye", None)
    assert adapter.read_config(path) == expected
    for comment in ("/*before*/", "/*after*/", "/*tail*/", "/*empty*/", "//root"):
        if comment in text:
            assert comment in path.read_text()


def test_external_edit_during_temp_write(configured, monkeypatch):
    adapter, path = configured
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    external = b"# concurrently changed" if adapter.NAME == "Codex" else b'{"external":true}'
    real_fsync = os.fsync

    def changed(fd):
        path.write_bytes(external)
        real_fsync(fd)

    monkeypatch.setattr(base.os, "fsync", changed)
    with pytest.raises(ValueError, match="concurrently"):
        adapter.write_config(path, config)
    assert path.read_bytes() == external


def test_all_dry_run_isolated_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr("rendereye_mcp.agent_setup.find_executable", lambda: EXE)
    # Project scope computes all five previews without creating directories.
    _setup_all(scope="project", project_path=tmp_path, dry_run=True, force=False, remove=False)
    assert not list(tmp_path.iterdir())


def test_all_failure_is_reported_without_touching_bad_file(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("rendereye_mcp.agent_setup.find_executable", lambda: EXE)
    bad = tmp_path / ".cursor" / "mcp.json"
    bad.parent.mkdir()
    bad.write_bytes(b"invalid")
    with pytest.raises(ValueError, match="cursor"):
        _setup_all(scope="project", project_path=tmp_path, dry_run=False, force=True, remove=False)
    assert bad.read_bytes() == b"invalid"
    for name in ("claude-code", "codex", "vscode", "gemini"):
        adapter = _load_adapter(name)
        assert "rendereye" in adapter._servers(
            adapter.read_config(adapter.config_path("project", tmp_path))
        )


def test_gemini_comments_preserved_and_trailing_commas_refused(tmp_path):
    adapter = _load_adapter("gemini")
    path = tmp_path / "settings.json"
    raw = b'// user preference\n{"general":{"theme":"Default"},"mcpServers":{}}'
    path.write_bytes(raw)
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    assert b"// user preference" in path.read_bytes()
    path.write_bytes(b'{"mcpServers":{},}')
    with pytest.raises(ValueError):
        adapter.read_config(path)


def test_empty_toml(tmp_path):
    adapter = _load_adapter("codex")
    path = tmp_path / "config.toml"
    path.touch()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    assert "rendereye" in adapter.read_config(path)["mcp_servers"]


def test_backup_versions_are_never_overwritten(configured):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    first = path.with_suffix(path.suffix + ".bak")
    config, _ = adapter.remove(adapter.read_config(path))
    adapter.write_config(path, config)
    assert first.read_bytes() == raw
    assert path.with_name(path.name + ".bak.1").exists()


def test_lock_blocks_second_writer(configured):
    adapter, path = configured
    raw = path.read_bytes()
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    lock = path.with_name(path.name + ".rendereye.lock")
    lock.touch()
    with pytest.raises(FileExistsError):
        adapter.write_config(path, config)
    assert path.read_bytes() == raw
    assert lock.exists()  # A writer must not remove another writer's lock.


def test_env_file_only(monkeypatch):
    monkeypatch.setenv("RENDEREYE_ENV_FILE", "D:/Synthetic/日本語/.env")
    monkeypatch.setenv("RENDEREYE_SECRET", "must-not-copy")
    for name in AGENTS:
        entry = _load_adapter(name).build_server_entry(EXE)
        assert entry["env"] == {"RENDEREYE_ENV_FILE": "D:/Synthetic/日本語/.env"}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", AGENTS)
async def test_generated_command_initializes_real_mcp(name, tmp_path):
    import asyncio
    import shutil
    import socket

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    executable = find_executable()
    spaced = tmp_path / '日本語 Program Files'
    spaced.mkdir()
    copied_launcher = spaced / executable.name
    shutil.copy2(executable, copied_launcher)
    executable = copied_launcher
    adapter = _load_adapter(name)
    path = adapter.config_path("project", tmp_path)
    config, _ = adapter.apply(adapter.read_config(path), executable)
    adapter.write_config(path, config)
    entry = adapter._servers(adapter.read_config(path))["rendereye"]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("RENDEREYE_")}
    env.update(
        HOME=str(tmp_path),
        USERPROFILE=str(tmp_path),
        APPDATA=str(tmp_path),
        LOCALAPPDATA=str(tmp_path),
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
        RENDEREYE_STORAGE_PATH=str(tmp_path / "captures.db"),
        RENDEREYE_IPC_PORT=str(port),
        RENDEREYE_CAPTURE_ENABLED="false",
    )
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated MCP test\n")
    env["RENDEREYE_ENV_FILE"] = str(env_file)
    server = StdioServerParameters(
        command=entry["command"], args=entry["args"], env=env, cwd=tmp_path
    )
    async with asyncio.timeout(30):
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()
                assert result.server_info.name == "RenderEyeMCP"
                tools = await session.list_tools()
                assert "server_status" in {tool.name for tool in tools.tools}


@pytest.mark.parametrize("client", ["codex", "claude"])
def test_installed_client_loads_isolated_config(client, tmp_path):
    import json
    import shutil
    import socket
    import subprocess

    binary = shutil.which(client)
    if binary is None:
        pytest.skip(f"{client} is not installed")
    name = "claude-code" if client == "claude" else "codex"
    adapter = _load_adapter(name)
    path = tmp_path / ".mcp.json" if client == "claude" else tmp_path / ".codex" / "config.toml"
    if client == "codex":
        path.parent.mkdir()
        path.write_bytes((FIXTURES / "codex.toml").read_bytes())
    config, _ = adapter.apply(adapter.read_config(path), find_executable())
    adapter.write_config(path, config)
    env = {k: v for k, v in os.environ.items() if not k.startswith("RENDEREYE_")}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env.update(
        HOME=str(tmp_path),
        USERPROFILE=str(tmp_path),
        APPDATA=str(tmp_path),
        LOCALAPPDATA=str(tmp_path),
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
        CODEX_HOME=str(tmp_path / ".codex"),
        CLAUDE_CONFIG_DIR=str(tmp_path / ".claude"),
        RENDEREYE_STORAGE_PATH=str(tmp_path / "captures.db"),
        RENDEREYE_IPC_PORT=str(port),
        RENDEREYE_CAPTURE_ENABLED="false",
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
        DISABLE_AUTOUPDATER="1",
    )
    if client == "claude":
        # Claude Code requires approval for project-scope servers; pre-approve so
        # `claude mcp get` performs a real connection check.
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text(json.dumps({"enableAllProjectMcpServers": True}))
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated client check\n")
    env["RENDEREYE_ENV_FILE"] = str(env_file)
    arguments = ["mcp", "get", "rendereye"] if client == "claude" else ["mcp", "list", "--json"]
    result = subprocess.run(
        [binary, *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    if client == "codex":
        servers = json.loads(result.stdout)
        assert {s["name"] for s in servers} >= {"rendereye", "other"}
        assert adapter.read_config(path)["projects"] == config["projects"]
    else:
        assert "rendereye" in result.stdout
        assert "Connected" in result.stdout
    assert adapter.read_config(path) == config


def test_dry_run_conflict_previews_without_force(configured, monkeypatch, capsys):
    adapter, path = configured
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    raw = path.read_bytes()
    monkeypatch.setattr("rendereye_mcp.agent_setup._load_adapter", lambda _: adapter)
    monkeypatch.setattr(adapter, "config_path", lambda **_: path)
    monkeypatch.setattr(
        "rendereye_mcp.agent_setup.find_executable", lambda: Path("D:/New/rendereye-mcp.exe")
    )
    _setup_single(
        agent="synthetic", scope="user", project_path=None, dry_run=True, force=False, remove=False
    )
    assert "requires --force" in capsys.readouterr().out
    assert path.read_bytes() == raw


def test_toml_dates_arrays_and_special_floats_preserved(tmp_path):
    adapter = _load_adapter("codex")
    path = tmp_path / "config.toml"
    original = b"# unknown TOML types\ndate = 2026-10-28\nvalue = nan\n[[future]]\nvalue = 1\n[[future]]\nvalue = 2\n"
    path.write_bytes(original)
    config, _ = adapter.apply(adapter.read_config(path), EXE)
    adapter.write_config(path, config)
    assert original in path.read_bytes()
    assert base.same_values(
        stripped(adapter, adapter.read_config(path)),
        {"mcp_servers": {}, **dict(adapter.parse(original.decode()))},
    )


def test_preservation_check_distinguishes_bool_from_int(configured):
    adapter, path = configured
    config = adapter.read_config(path)
    # This is outside RenderEye and must be rejected even though True == 1 in Python.
    raw = path.read_bytes()
    config["future_test"] = True
    with pytest.raises(ValueError, match="outside"):
        adapter.write_config(path, config)
    assert path.read_bytes() == raw
    assert not base.same_values({"value": True}, {"value": 1})
