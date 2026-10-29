"""Tests for the phase 5.4 doctor command."""

from __future__ import annotations

from unittest.mock import patch


def test_doctor_importable():
    from rendereye_mcp import doctor
    assert callable(doctor.run_doctor)


def test_check_version():
    from rendereye_mcp.doctor import _check_version
    status, component, detail = _check_version()
    assert status == "PASS"
    assert "Version" in component
    from rendereye_mcp import __version__
    assert __version__ in detail


def test_check_python():
    from rendereye_mcp.doctor import _check_python
    status, component, detail = _check_python()
    assert status == "PASS"
    import sys
    assert sys.version.split()[0] in detail


def test_check_config_dir_missing(tmp_path):
    from rendereye_mcp.doctor import _check_config_dir
    with patch("rendereye_mcp.setup_cmd.get_default_install_dir",
               return_value=tmp_path / "nonexistent"):
        status, _, _ = _check_config_dir()
        assert status == "FAIL"


def test_check_config_dir_exists(tmp_path):
    from rendereye_mcp.doctor import _check_config_dir
    d = tmp_path / "RenderEyeMCP"
    d.mkdir()
    with patch("rendereye_mcp.setup_cmd.get_default_install_dir", return_value=d):
        status, _, _ = _check_config_dir()
        assert status == "PASS"


def test_check_env_file_missing(tmp_path):
    from rendereye_mcp.doctor import _check_env_file
    with patch("rendereye_mcp.setup_cmd.get_default_install_dir",
               return_value=tmp_path / "nonexistent"):
        status, _, _ = _check_env_file()
        assert status == "FAIL"


def test_check_env_var_not_set():
    from rendereye_mcp.doctor import _check_env_var
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("RENDEREYE_ENV_FILE", None)
        status, _, _ = _check_env_var()
        assert status == "WARNING"


def test_check_env_var_set_valid(tmp_path):
    from rendereye_mcp.doctor import _check_env_var
    env_file = tmp_path / ".env"
    env_file.touch()
    with patch.dict("os.environ", {"RENDEREYE_ENV_FILE": str(env_file)}):
        status, _, detail = _check_env_var()
        assert status == "PASS"


def test_check_extension_not_installed(tmp_path):
    from rendereye_mcp.doctor import _check_extension
    with patch("rendereye_mcp.setup_cmd.get_extension_install_dir",
               return_value=tmp_path / "nonexistent"):
        status, _, _ = _check_extension()
        assert status == "FAIL"


def test_check_extension_installed(tmp_path):
    from rendereye_mcp.doctor import _check_extension
    ext_dir = tmp_path / "rendereye"
    ext_dir.mkdir()
    (ext_dir / "__init__.py").touch()
    (ext_dir / "extension.json").touch()
    with patch("rendereye_mcp.setup_cmd.get_extension_install_dir", return_value=ext_dir):
        status, _, _ = _check_extension()
        assert status == "PASS"


def test_run_doctor_no_crash(capsys):
    from rendereye_mcp.doctor import run_doctor
    # Should complete without raising
    run_doctor(agent=None)
    captured = capsys.readouterr()
    assert "doctor" in captured.out.lower()
    assert "Summary" in captured.out


def test_run_doctor_with_agent(capsys):
    from rendereye_mcp.doctor import run_doctor
    run_doctor(agent="cursor")
    captured = capsys.readouterr()
    assert "cursor" in captured.out.lower()


def test_run_doctor_output_format(capsys):
    from rendereye_mcp.doctor import run_doctor
    run_doctor()
    captured = capsys.readouterr()
    # Should contain status icons
    assert any(icon in captured.out for icon in ["✓", "!", "✗", "?"])
