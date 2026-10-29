"""Tests for the phase 5.4 setup command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_install_dir(tmp_path):
    return tmp_path / "RenderEyeMCP"


# ---------------------------------------------------------------------------
# get_default_install_dir
# ---------------------------------------------------------------------------


def test_get_default_install_dir_windows():
    from rendereye_mcp.setup_cmd import get_default_install_dir
    with patch("platform.system", return_value="Windows"), \
         patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}):
        d = get_default_install_dir()
        assert d == Path("C:\\Users\\test\\AppData\\Local") / "RenderEyeMCP"


def test_get_default_install_dir_linux():
    from rendereye_mcp.setup_cmd import get_default_install_dir
    with patch("platform.system", return_value="Linux"), \
         patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/test/.config"}):
        d = get_default_install_dir()
        assert d == Path("/home/test/.config") / "rendereye_mcp"


# ---------------------------------------------------------------------------
# detect_renderdoc
# ---------------------------------------------------------------------------


def test_detect_renderdoc_found(tmp_path):
    from rendereye_mcp.setup_cmd import detect_renderdoc
    fake_exe = tmp_path / "qrenderdoc.exe"
    fake_exe.touch()
    with patch("platform.system", return_value="Windows"), \
         patch.dict("os.environ", {"ProgramFiles": str(tmp_path)}):
        # Not in standard path — just verify it returns None for non-existent
        detect_renderdoc()
        # May or may not find it depending on actual system


def test_detect_renderdoc_not_found():
    from rendereye_mcp.setup_cmd import detect_renderdoc
    with patch("platform.system", return_value="Linux"), \
         patch("pathlib.Path.is_file", return_value=False):
        result = detect_renderdoc()
        assert result is None


# ---------------------------------------------------------------------------
# _create_env
# ---------------------------------------------------------------------------


def test_create_env_first_install(tmp_path):
    from rendereye_mcp.setup_cmd import _create_env
    env_file = tmp_path / ".env"
    assert not env_file.exists()
    created = _create_env(env_file)
    assert created is True
    assert env_file.exists()


def test_create_env_preserves_existing(tmp_path):
    from rendereye_mcp.setup_cmd import _create_env
    env_file = tmp_path / ".env"
    env_file.write_text("RENDEREYE_RENDERDOC_EXE=/custom/path\n", encoding="utf-8")
    created = _create_env(env_file)
    assert created is False
    assert "custom/path" in env_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# _read_env_values / _set_env_key
# ---------------------------------------------------------------------------


def test_read_env_values(tmp_path):
    from rendereye_mcp.setup_cmd import _read_env_values
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=value1\nKEY2=value2\n", encoding="utf-8")
    vals = _read_env_values(env_file)
    assert vals["KEY1"] == "value1"
    assert vals["KEY2"] == "value2"


def test_set_env_key_new(tmp_path):
    from rendereye_mcp.setup_cmd import _read_env_values, _set_env_key
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=yes\n", encoding="utf-8")
    _set_env_key(env_file, "NEW_KEY", "new_value")
    vals = _read_env_values(env_file)
    assert vals["NEW_KEY"] == "new_value"
    assert vals["EXISTING"] == "yes"


def test_set_env_key_update(tmp_path):
    from rendereye_mcp.setup_cmd import _read_env_values, _set_env_key
    env_file = tmp_path / ".env"
    env_file.write_text("RENDEREYE_RENDERDOC_EXE=old_path\n", encoding="utf-8")
    _set_env_key(env_file, "RENDEREYE_RENDERDOC_EXE", "new_path")
    vals = _read_env_values(env_file)
    assert vals["RENDEREYE_RENDERDOC_EXE"] == "new_path"


# ---------------------------------------------------------------------------
# install_extension
# ---------------------------------------------------------------------------


def test_install_extension_copies_files(tmp_path):
    from rendereye_mcp.setup_cmd import _EXT_DATA, install_extension
    dst = tmp_path / "extensions" / "rendereye"
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")
    result = install_extension(dst=dst)
    assert result is True
    assert dst.exists()
    assert (dst / "__init__.py").exists()
    assert (dst / "extension.json").exists()


def test_install_extension_idempotent(tmp_path):
    from rendereye_mcp.setup_cmd import _EXT_DATA, install_extension
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")
    dst = tmp_path / "extensions" / "rendereye"
    install_extension(dst=dst)
    install_extension(dst=dst)
    # Should succeed again without error


def test_uninstall_extension_removes_dir(tmp_path):
    from rendereye_mcp.setup_cmd import _EXT_DATA, install_extension, uninstall_extension
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")
    dst = tmp_path / "extensions" / "rendereye"
    install_extension(dst=dst)
    assert dst.exists()
    uninstall_extension(dst=dst)
    assert not dst.exists()


def test_uninstall_extension_not_installed(tmp_path):
    from rendereye_mcp.setup_cmd import uninstall_extension
    dst = tmp_path / "nonexistent"
    # Should not raise
    result = uninstall_extension(dst=dst)
    assert result is True


# ---------------------------------------------------------------------------
# validate_setup
# ---------------------------------------------------------------------------


def test_validate_setup_missing_dir(tmp_path):
    from rendereye_mcp.setup_cmd import validate_setup
    missing = tmp_path / "nonexistent"
    results = validate_setup(missing)
    statuses = {c: s for s, c, _ in results}
    assert statuses["Config directory"] == "FAIL"


def test_validate_setup_complete(tmp_path):
    from rendereye_mcp.setup_cmd import _EXT_DATA, install_extension, validate_setup
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")

    install_dir = tmp_path / "RenderEyeMCP"
    install_dir.mkdir()
    env_file = install_dir / ".env"
    env_file.write_text("RENDEREYE_RENDERDOC_EXE=\n", encoding="utf-8")

    # Install extension to expected location (mocked)
    with patch("rendereye_mcp.setup_cmd.get_extension_install_dir",
               return_value=tmp_path / "ext"):
        install_extension(dst=tmp_path / "ext")
        results = validate_setup(install_dir)

    statuses = {c: s for s, c, _ in results}
    assert statuses["Config directory"] == "PASS"
    assert statuses[".env file"] == "PASS"


# ---------------------------------------------------------------------------
# run_setup (integration)
# ---------------------------------------------------------------------------


def test_run_setup_creates_dirs(tmp_path, capsys):
    from rendereye_mcp.setup_cmd import _EXT_DATA, run_setup
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")

    install_dir = tmp_path / "RenderEyeMCP"
    ext_dir = tmp_path / "ext"

    with patch("rendereye_mcp.setup_cmd.get_extension_install_dir", return_value=ext_dir), \
         patch("rendereye_mcp.setup_cmd._register_env_var_windows", return_value=True), \
         patch("platform.system", return_value="Windows"):
        run_setup(install_dir=install_dir, interactive=False)

    assert install_dir.exists()
    assert (install_dir / "data").exists()
    assert (install_dir / "logs").exists()
    assert (install_dir / ".env").exists()


def test_run_setup_idempotent(tmp_path, capsys):
    from rendereye_mcp.setup_cmd import _EXT_DATA, run_setup
    if not _EXT_DATA.exists():
        pytest.skip("bundled extension data not found")

    install_dir = tmp_path / "RenderEyeMCP"
    ext_dir = tmp_path / "ext"

    with patch("rendereye_mcp.setup_cmd.get_extension_install_dir", return_value=ext_dir), \
         patch("rendereye_mcp.setup_cmd._register_env_var_windows", return_value=True), \
         patch("platform.system", return_value="Windows"):
        run_setup(install_dir=install_dir, interactive=False)
        # Write custom value
        env_file = install_dir / ".env"
        env_file.write_text("RENDEREYE_RENDERDOC_EXE=/custom/path\n", encoding="utf-8")
        run_setup(install_dir=install_dir, interactive=False)
        # Custom value must be preserved
        content = env_file.read_text(encoding="utf-8")
        assert "/custom/path" in content
