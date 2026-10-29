"""Tests for rendereye_mcp.config."""

from __future__ import annotations

import pytest

from rendereye_mcp.config import Config


class TestDefaults:
    def test_default_renderdoc_exe(self):
        config = Config()
        assert config.renderdoc_exe == "C:/Program Files/RenderDoc/qrenderdoc.exe"

    def test_default_ipc_transport(self):
        config = Config()
        assert config.ipc_transport == "tcp"

    def test_default_ipc_host(self):
        config = Config()
        assert config.ipc_host == "127.0.0.1"

    def test_default_ipc_port(self):
        config = Config()
        assert config.ipc_port == 37020

    def test_default_connection_timeout(self):
        config = Config()
        assert config.connection_timeout == 10.0

    def test_default_log_level(self):
        config = Config()
        assert config.log_level == "INFO"

    def test_default_extension_path(self):
        config = Config()
        assert config.extension_path == ""


class TestEnvOverrides:
    """Verify that RENDEREYE_* environment variables override defaults."""

    def test_ipc_port_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_IPC_PORT", "12345")
        config = Config.from_env()
        assert config.ipc_port == 12345

    def test_log_level_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_LOG_LEVEL", "DEBUG")
        config = Config.from_env()
        assert config.log_level == "DEBUG"

    def test_renderdoc_exe_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_RENDERDOC_EXE", "C:/Tools/RenderDoc/qrenderdoc.exe")
        config = Config.from_env()
        assert config.renderdoc_exe == "C:/Tools/RenderDoc/qrenderdoc.exe"

    def test_ipc_host_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_IPC_HOST", "127.0.0.1")
        config = Config.from_env()
        assert config.ipc_host == "127.0.0.1"

    def test_connection_timeout_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_CONNECTION_TIMEOUT", "30.5")
        config = Config.from_env()
        assert config.connection_timeout == pytest.approx(30.5)

    def test_extension_path_override(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_EXTENSION_PATH", "C:/extensions/rendereye")
        config = Config.from_env()
        assert config.extension_path == "C:/extensions/rendereye"

    def test_capture_dirs_split_on_os_pathsep(self, monkeypatch):
        import os

        first = "C:/captures/a" if os.name == "nt" else "/captures/a"
        second = "D:/captures/b" if os.name == "nt" else "/captures/b"
        monkeypatch.setenv("RENDEREYE_CAPTURE_DIRS", f"{first}{os.pathsep}{second}")
        config = Config.from_env()
        assert [d.path for d in config.capture.directories] == [first, second]

    def test_unset_env_uses_defaults(self, monkeypatch):
        """Ensure no RENDEREYE_ vars are set so we get pure defaults."""
        for key in ["RENDEREYE_IPC_PORT", "RENDEREYE_LOG_LEVEL", "RENDEREYE_IPC_HOST"]:
            monkeypatch.delenv(key, raising=False)
        config = Config.from_env()
        assert config.ipc_port == 37020
        assert config.log_level == "INFO"


class TestValidation:
    def test_invalid_log_level_raises(self):
        with pytest.raises(ValueError, match="log_level"):
            Config(log_level="VERBOSE")

    def test_invalid_ipc_transport_raises(self):
        with pytest.raises(ValueError, match="ipc_transport"):
            Config(ipc_transport="udp")

    def test_invalid_ipc_port_zero_raises(self):
        with pytest.raises(ValueError, match="ipc_port"):
            Config(ipc_port=0)

    def test_invalid_ipc_port_too_high_raises(self):
        with pytest.raises(ValueError, match="ipc_port"):
            Config(ipc_port=70000)

    def test_invalid_connection_timeout_raises(self):
        with pytest.raises(ValueError, match="connection_timeout"):
            Config(connection_timeout=-1.0)

    def test_invalid_ipc_port_env_raises(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_IPC_PORT", "not_a_number")
        with pytest.raises(ValueError):
            Config.from_env()

    def test_invalid_connection_timeout_env_raises(self, monkeypatch):
        monkeypatch.setenv("RENDEREYE_CONNECTION_TIMEOUT", "abc")
        with pytest.raises(ValueError):
            Config.from_env()
