"""Validate agent editing from a built wheel in an isolated temporary profile.

Run: python scripts/verify_agent_config_wheel.py dist/phase5.7/<wheel>.whl
Uses the current environment's dependencies, never real user agent configuration.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

CHECK = r"""
import copy
import os
import subprocess
from pathlib import Path
import rendereye_mcp.agent_setup
from rendereye_mcp.agent_setup import _load_adapter, find_executable

root = Path(os.environ['RENDEREYE_WHEEL_CHECK_ROOT'])
assert root / 'wheel' in Path(rendereye_mcp.agent_setup.__file__).parents
launcher = find_executable()
for name in ('claude-code', 'codex', 'cursor', 'vscode', 'gemini'):
    adapter = _load_adapter(name)
    project = root / 'projects' / name
    target = adapter.config_path('project', project)
    target.parent.mkdir(parents=True)
    suffix = '.toml' if name == 'codex' else '.jsonc' if name == 'vscode' else '.json'
    original = (root / 'fixtures' / (name + suffix)).read_bytes()
    target.write_bytes(original)
    before = adapter.read_config(target)
    command = [str(launcher), 'setup-agent', name, '--scope', 'project', '--project-path', str(project)]
    def run(*flags):
        result = subprocess.run([*command, *flags], cwd=root, env=os.environ.copy(),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    run('--dry-run')
    assert target.read_bytes() == original
    run()
    added = adapter.read_config(target)
    key = adapter.get_servers_key()[0]
    added[key].pop('rendereye')
    assert added == before
    current = target.read_bytes()
    run()
    assert target.read_bytes() == current
    run('--remove')
    assert adapter.read_config(target) == before
    current = target.read_bytes()
    run('--remove')
    assert target.read_bytes() == current
    assert target.with_suffix(target.suffix + '.bak').read_bytes() == original
    print(name + ': packaged preview/add/idempotency/remove/preservation OK')
"""


def main():
    wheel = Path(sys.argv[1]).resolve()
    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "agents"
    with tempfile.TemporaryDirectory(prefix="rendereye-wheel-config-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(wheel) as archive:
            metadata = next(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            assert "Requires-Dist: tomlkit" in archive.read(metadata).decode()
            assert "rendereye_mcp/agent_setup/json_edit.py" in archive.namelist()
            archive.extractall(root / "wheel")
        (root / "fixtures").mkdir()
        for source in fixtures.iterdir():
            if source.is_file():
                (root / "fixtures" / source.name).write_bytes(source.read_bytes())
        env = {k: v for k, v in os.environ.items() if not k.startswith("RENDEREYE_")}
        env.update(
            HOME=temp,
            USERPROFILE=temp,
            APPDATA=temp,
            LOCALAPPDATA=temp,
            TEMP=temp,
            TMP=temp,
            CODEX_HOME=str(root / ".codex"),
            PYTHONPATH=str(root / "wheel"),
            RENDEREYE_WHEEL_CHECK_ROOT=temp,
        )
        subprocess.run([sys.executable, "-c", CHECK], cwd=root, env=env, check=True, timeout=120)
    print("Wheel resources, dependency metadata and all five packaged adapters verified.")


if __name__ == "__main__":
    main()
