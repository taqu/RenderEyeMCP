"""VS Code Local harness MCP configuration (JSONC, servers schema)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import AgentAdapter


class Adapter(AgentAdapter):
    NAME = "VS Code / GitHub Copilot"
    JSONC = True

    def config_path(self, scope, project_path=None):
        if scope == "project":
            return (project_path or Path.cwd()) / ".vscode" / "mcp.json"
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        return base / "Code" / "User" / "mcp.json"

    def get_servers_key(self):
        return ["servers"]

    def build_server_entry(self, executable):
        return {"type": "stdio", **super().build_server_entry(executable)}
