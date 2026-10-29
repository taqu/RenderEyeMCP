"""Tests for rendereye_mcp.bootstrap.initialize_environment()."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rendereye_mcp.bootstrap import initialize_environment

# ---------------------------------------------------------------------------
# No env file at all
# ---------------------------------------------------------------------------


class TestNoEnvFile:
    def test_returns_none_when_nothing_configured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("RENDEREYE_ENV_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        assert initialize_environment() is None

    def test_does_not_inject_env_vars(self, monkeypatch, tmp_path):
        monkeypatch.delenv("RENDEREYE_ENV_FILE", raising=False)
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        monkeypatch.chdir(tmp_path)
        initialize_environment()
        assert os.environ.get("RENDEREYE_LOG_LEVEL") is None


# ---------------------------------------------------------------------------
# Explicit env_file argument
# ---------------------------------------------------------------------------


class TestExplicitArgument:
    def test_loads_values(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        result = initialize_environment(env_file=env_file)
        assert result == env_file
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "DEBUG"

    def test_raises_on_relative_path(self):
        with pytest.raises(ValueError, match="absolute"):
            initialize_environment(env_file=Path("relative/.env"))

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            initialize_environment(env_file=tmp_path / "nonexistent.env")

    def test_does_not_override_existing_env(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_LOG_LEVEL", "WARNING")
        initialize_environment(env_file=env_file)
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "WARNING"

    def test_default_value_set_when_var_absent(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=ERROR\n", encoding="utf-8")
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        initialize_environment(env_file=env_file)
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "ERROR"


# ---------------------------------------------------------------------------
# RENDEREYE_ENV_FILE environment variable
# ---------------------------------------------------------------------------


class TestEnvFileVar:
    def test_loads_from_env_var(self, monkeypatch, tmp_path):
        env_file = tmp_path / "config.env"
        env_file.write_text("RENDEREYE_IPC_PORT=12345\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_file))
        monkeypatch.delenv("RENDEREYE_IPC_PORT", raising=False)
        result = initialize_environment()
        assert result == env_file
        assert os.environ.get("RENDEREYE_IPC_PORT") == "12345"

    def test_raises_on_missing_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(tmp_path / "missing.env"))
        with pytest.raises(FileNotFoundError):
            initialize_environment()

    def test_raises_on_relative_path(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_ENV_FILE", "relative/.env")
        with pytest.raises(ValueError, match="absolute"):
            initialize_environment()

    def test_does_not_override_existing_env(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_file))
        monkeypatch.setenv("RENDEREYE_LOG_LEVEL", "ERROR")
        initialize_environment()
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "ERROR"

    def test_unicode_path(self, monkeypatch, tmp_path):
        unicode_dir = tmp_path / "café"
        unicode_dir.mkdir()
        env_file = unicode_dir / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_file))
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        result = initialize_environment()
        assert result is not None
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "DEBUG"

    def test_path_with_spaces(self, monkeypatch, tmp_path):
        spaced_dir = tmp_path / "my config dir"
        spaced_dir.mkdir()
        env_file = spaced_dir / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=WARNING\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_file))
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        initialize_environment()
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "WARNING"

    def test_explicit_arg_takes_priority_over_env_var(self, monkeypatch, tmp_path):
        env_var_file = tmp_path / "from_env_var.env"
        env_var_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        arg_file = tmp_path / "from_arg.env"
        arg_file.write_text("RENDEREYE_LOG_LEVEL=ERROR\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_var_file))
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        result = initialize_environment(env_file=arg_file)
        assert result == arg_file
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "ERROR"


# ---------------------------------------------------------------------------
# CWD fallback (development convenience)
# ---------------------------------------------------------------------------


class TestCwdFallback:
    def test_loads_cwd_env_when_present(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.delenv("RENDEREYE_ENV_FILE", raising=False)
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)
        monkeypatch.chdir(tmp_path)
        result = initialize_environment()
        assert result == env_file
        assert os.environ.get("RENDEREYE_LOG_LEVEL") == "DEBUG"

    def test_skips_silently_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.delenv("RENDEREYE_ENV_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        result = initialize_environment()
        assert result is None


# ---------------------------------------------------------------------------
# Config initialization order
# ---------------------------------------------------------------------------


class TestConfigInitOrder:
    def test_env_loaded_before_config(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RENDEREYE_LOG_LEVEL=DEBUG\n", encoding="utf-8")
        monkeypatch.setenv("RENDEREYE_ENV_FILE", str(env_file))
        monkeypatch.delenv("RENDEREYE_LOG_LEVEL", raising=False)

        initialize_environment()

        from rendereye_mcp.config import Config

        config = Config.from_env()
        assert config.log_level == "DEBUG"
