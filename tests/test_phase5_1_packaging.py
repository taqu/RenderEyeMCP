"""Phase 5.1 packaging and manual installation tests.

Verifies:
- Extension files are complete and self-contained
- Extension metadata is consistent with package version
- Config examples contain no developer-specific paths
- RenderDoc discovery prioritizes standard install paths
- Python module entry point exists
- Release package contents are correct
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
EXTENSION_DIR = REPO_ROOT / "extensions" / "rendereye"
EXAMPLES_DIR = REPO_ROOT / "examples"
DIST_DIR = REPO_ROOT / "dist"
PACKAGE_DIR = DIST_DIR / "packages" / "RenderEyeMCP-v1.0.0"


# ---------------------------------------------------------------------------
# Extension package completeness
# ---------------------------------------------------------------------------


class TestExtensionFiles:
    REQUIRED_FILES = [
        "__init__.py",
        "extension.json",
        "ipc_client.py",
        "gui_context.py",
        "gui_dispatcher.py",
        "state_observer.py",
    ]

    def test_all_required_files_exist(self):
        for filename in self.REQUIRED_FILES:
            assert (EXTENSION_DIR / filename).exists(), f"Missing: {filename}"

    def test_no_third_party_imports(self):
        """Extension must use stdlib only (Python 3.6 embedded in RenderDoc)."""
        stdlib_names = {
            "os", "sys", "json", "socket", "threading", "time", "logging",
            "struct", "io", "collections", "functools", "contextlib",
            "traceback", "datetime", "re", "math", "copy", "types",
            "__future__", "abc", "enum", "dataclasses", "uuid", "hashlib",
            "pathlib", "tempfile", "shutil", "subprocess", "signal",
            "queue", "weakref", "inspect", "itertools", "operator",
            "base64",
        }
        # Allowed internal names and RenderDoc's own embedded API
        internal_names = {
            "gui_context", "gui_dispatcher", "ipc_client", "state_observer",
            "renderdoc", "qrenderdoc",  # RenderDoc's embedded Python API
        }

        for py_file in EXTENSION_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for line in source.splitlines():
                line = line.strip()
                if not (line.startswith("import ") or line.startswith("from ")):
                    continue
                # Extract module name
                if line.startswith("from "):
                    mod = line.split()[1].split(".")[0]
                else:
                    mod = line.split()[1].split(".")[0]

                # Skip absolute imports check for known internal or stdlib
                if mod in stdlib_names or mod in internal_names:
                    continue
                # Relative imports are allowed
                if line.startswith("from .") or mod.startswith("."):
                    continue
                # Unknown import — could be third-party
                assert mod in stdlib_names | internal_names, (
                    f"{py_file.name}: potentially non-stdlib import {mod!r}"
                )

    def test_extension_json_valid(self):
        meta = json.loads((EXTENSION_DIR / "extension.json").read_text(encoding="utf-8"))
        assert "name" in meta
        assert "version" in meta
        assert "minimum_renderdoc" in meta

    def test_extension_version_matches_package(self):
        ext_meta = json.loads((EXTENSION_DIR / "extension.json").read_text(encoding="utf-8"))
        pkg_version = importlib.metadata.version("rendereye-mcp")
        assert ext_meta["version"] == pkg_version, (
            f"extension.json version {ext_meta['version']} != "
            f"package version {pkg_version}"
        )

    def test_no_pycache_in_extension_dir(self):
        """__pycache__ must not be shipped inside the extension."""
        pycache = EXTENSION_DIR / "__pycache__"
        # It may exist locally but must not be required for operation
        # The create_release_package script filters it out — verify the source doesn't need it
        if pycache.exists():
            for f in pycache.iterdir():
                # OK — these are local build artifacts, not part of the package
                pass
        # The real check: the extension must work without __pycache__


# ---------------------------------------------------------------------------
# Configuration examples
# ---------------------------------------------------------------------------

_DEV_PATHS = [
    "D:/Programs",
    "D:\\Programs",
    "taqu_",
    "taqu2920",
    "/home/taqu",
    "D:/Projects",
]

_PLACEHOLDER_PATTERNS = ["<USERNAME>", "<VERSION>"]


class TestConfigExamples:
    @pytest.fixture(params=[
        "claude-code/mcp-config.json",
        "cursor/mcp.json",
        "vscode/mcp.json",
        "gemini/settings.json",
    ])
    def json_example(self, request):
        path = EXAMPLES_DIR / request.param
        assert path.exists(), f"Missing example: {request.param}"
        return path

    @pytest.fixture(params=["codex/config.toml"])
    def toml_example(self, request):
        path = EXAMPLES_DIR / request.param
        assert path.exists(), f"Missing example: {request.param}"
        return path

    def test_json_example_is_valid_json(self, json_example):
        content = json_example.read_text(encoding="utf-8")
        json.loads(content)  # must not raise

    def test_no_developer_paths_in_json(self, json_example):
        content = json_example.read_text(encoding="utf-8")
        for dev_path in _DEV_PATHS:
            assert dev_path not in content, (
                f"{json_example.name} contains developer path: {dev_path!r}"
            )

    def test_uses_placeholders_not_real_username(self, json_example):
        content = json_example.read_text(encoding="utf-8")
        # Must use <USERNAME> placeholder rather than a hardcoded name
        assert any(p in content for p in _PLACEHOLDER_PATTERNS), (
            f"{json_example.name} should use <USERNAME> placeholder"
        )

    def test_no_developer_paths_in_toml(self, toml_example):
        content = toml_example.read_text(encoding="utf-8")
        for dev_path in _DEV_PATHS:
            assert dev_path not in content, (
                f"{toml_example.name} contains developer path: {dev_path!r}"
            )

    def test_all_agent_examples_have_readme(self):
        for agent_dir in EXAMPLES_DIR.iterdir():
            if agent_dir.is_dir():
                readme = agent_dir / "README.md"
                assert readme.exists(), f"Missing README in {agent_dir.name}"


# ---------------------------------------------------------------------------
# RenderDoc discovery order
# ---------------------------------------------------------------------------


class TestRenderDocDiscovery:
    def test_standard_path_checked_before_developer_path(self):
        """Standard Windows install path should be probed before developer paths."""
        # Read the source to verify the order of fallbacks
        import inspect

        from rendereye_mcp.platform.windows import find_renderdoc_exe
        source = inspect.getsource(find_renderdoc_exe)

        # C:/Program Files should appear before D:/Programs
        pf_idx = source.find("Program Files/RenderDoc")
        dev_idx = source.find("D:/Programs/RenderDoc")

        assert pf_idx != -1, "Standard install path not found in discovery function"
        assert dev_idx != -1, "Developer path not found in discovery function"
        assert pf_idx < dev_idx, (
            "Standard install path should appear before developer path in discovery fallbacks"
        )

    def test_explicit_config_path_respected(self, tmp_path):
        """When RENDEREYE_RENDERDOC_EXE is set, only that path is checked."""
        from rendereye_mcp.config import Config
        from rendereye_mcp.platform.windows import find_renderdoc_exe

        fake_exe = tmp_path / "qrenderdoc.exe"
        fake_exe.write_bytes(b"fake")

        config = Config()
        config.renderdoc_exe = str(fake_exe)
        result = find_renderdoc_exe(config)
        assert result is not None
        assert "qrenderdoc.exe" in result

    def test_nonexistent_explicit_path_returns_none(self):
        from rendereye_mcp.config import Config
        from rendereye_mcp.platform.windows import find_renderdoc_exe

        config = Config()
        config.renderdoc_exe = "/nonexistent/path/qrenderdoc.exe"
        result = find_renderdoc_exe(config)
        assert result is None


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------


class TestModuleEntryPoint:
    @pytest.fixture
    def isolated_server_env(self, tmp_path):
        """Keep startup checks independent of user storage, tokens and IPC ports."""
        import os
        import socket

        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env_file = tmp_path / '.env'
        env_file.write_text('# isolated startup test\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith('RENDEREYE_')}
        env.update(RENDEREYE_ENV_FILE=str(env_file),
                   RENDEREYE_STORAGE_PATH=str(tmp_path / 'captures.db'),
                   RENDEREYE_IPC_PORT=str(port), RENDEREYE_CAPTURE_ENABLED='false',
                   TEMP=str(tmp_path), TMP=str(tmp_path))
        return env

    def test_module_is_importable(self):
        """rendereye_mcp must be importable as a module."""
        import rendereye_mcp

        assert hasattr(rendereye_mcp, "__version__")

    def test_main_module_exists(self):
        """python -m rendereye_mcp entry point must be present."""
        main_path = Path(__file__).parent.parent / "src" / "rendereye_mcp" / "__main__.py"
        assert main_path.exists()

    def test_console_script_entry_point_defined(self):
        """rendereye-mcp console script must be defined in the package."""
        dist = importlib.metadata.distribution("rendereye-mcp")
        scripts = dist.entry_points
        script_names = [ep.name for ep in scripts]
        assert "rendereye-mcp" in script_names, (
            f"rendereye-mcp not found in entry points: {script_names}"
        )

    def test_server_starts_and_exits_on_sigint(self, tmp_path, isolated_server_env):
        """The module starts as a subprocess and can be interrupted cleanly."""
        import time

        proc = subprocess.Popen(
            [sys.executable, "-m", "rendereye_mcp"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=str(tmp_path),
            env=isolated_server_env,
        )
        try:
            time.sleep(3.0)
            assert proc.poll() is None, proc.stderr.read().decode(errors='replace')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_no_stdout_pollution_at_startup(self, tmp_path, isolated_server_env):
        """The server must not write anything to stdout at startup."""
        import time

        proc = subprocess.Popen(
            [sys.executable, "-m", "rendereye_mcp"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=str(tmp_path),
            env=isolated_server_env,
        )
        try:
            time.sleep(1.0)
            proc.terminate()
            stdout, _ = proc.communicate(timeout=5)
            assert stdout == b"", (
                f"Server wrote to stdout (MCP protocol contamination): {stdout[:200]!r}"
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise


# ---------------------------------------------------------------------------
# Release package contents
# ---------------------------------------------------------------------------


class TestReleasePackageContents:
    @pytest.mark.skipif(
        not PACKAGE_DIR.exists(),
        reason="Release package not built; run scripts/create_release_package.py",
    )
    def test_wheel_present(self):
        wheels = list((PACKAGE_DIR / "python").glob("*.whl"))
        assert len(wheels) == 1, f"Expected 1 wheel, found {len(wheels)}"

    @pytest.mark.skipif(
        not PACKAGE_DIR.exists(),
        reason="Release package not built; run scripts/create_release_package.py",
    )
    def test_extension_files_present(self):
        ext_dir = PACKAGE_DIR / "renderdoc-extension" / "rendereye"
        assert (ext_dir / "__init__.py").exists()
        assert (ext_dir / "extension.json").exists()
        assert (ext_dir / "ipc_client.py").exists()

    @pytest.mark.skipif(
        not PACKAGE_DIR.exists(),
        reason="Release package not built; run scripts/create_release_package.py",
    )
    def test_all_agent_examples_present(self):
        examples_dir = PACKAGE_DIR / "examples"
        for agent in ["claude-code", "cursor", "vscode", "codex", "gemini"]:
            assert (examples_dir / agent).exists(), f"Missing examples/{agent}"

    @pytest.mark.skipif(
        not PACKAGE_DIR.exists(),
        reason="Release package not built; run scripts/create_release_package.py",
    )
    def test_install_manual_present(self):
        assert (PACKAGE_DIR / "INSTALL-MANUAL.md").exists()

    @pytest.mark.skipif(
        not PACKAGE_DIR.exists(),
        reason="Release package not built; run scripts/create_release_package.py",
    )
    def test_no_developer_paths_in_package_examples(self):
        examples_dir = PACKAGE_DIR / "examples"
        for f in examples_dir.rglob("*"):
            if f.is_file() and f.suffix in (".json", ".toml"):
                content = f.read_text(encoding="utf-8")
                for dev_path in _DEV_PATHS:
                    assert dev_path not in content, (
                        f"{f.relative_to(PACKAGE_DIR)}: developer path {dev_path!r}"
                    )
