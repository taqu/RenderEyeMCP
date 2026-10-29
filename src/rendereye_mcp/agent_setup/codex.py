"""Lossless Codex TOML adapter, independently validated with tomllib."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomlkit

from .base import AgentAdapter, Config, atomic_write, read_bytes


def _read_toml(path: Path) -> dict:
    raw = read_bytes(path)
    data = {} if raw is None else tomllib.loads(raw.decode("utf-8-sig"))
    return Config(data, path, raw)


def _write_toml(path: Path, config: dict) -> None:
    # Retained for internal compatibility; adapter enforces targeted updates.
    adapter = Adapter()
    content, expected = adapter.render(path, config)
    atomic_write(path, content, expected)


class Adapter(AgentAdapter):
    NAME = "Codex"

    def config_path(self, scope, project_path=None):
        if scope == "project":
            return (project_path or Path.cwd()) / ".codex" / "config.toml"
        return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"

    def get_servers_key(self):
        return ["mcp_servers"]

    def read_config(self, path):
        config = _read_toml(path)
        self._servers(config)
        return config

    def parse(self, text):
        return tomllib.loads(text)

    def serialize(self, snapshot, config):
        text = (snapshot.raw or b"").decode("utf-8-sig")
        document = tomlkit.parse(text)
        servers = config.get("mcp_servers", {})
        if "mcp_servers" not in document:
            document["mcp_servers"] = tomlkit.table()
        if "rendereye" in servers:
            document["mcp_servers"]["rendereye"] = servers["rendereye"]
        elif "rendereye" in document["mcp_servers"]:
            del document["mcp_servers"]["rendereye"]
        content = tomlkit.dumps(document).encode()
        if snapshot.raw and snapshot.raw.startswith(b"\xef\xbb\xbf"):
            content = b"\xef\xbb\xbf" + content
        return content
