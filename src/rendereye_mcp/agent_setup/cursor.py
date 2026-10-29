"""Cursor MCP configuration adapter."""

from __future__ import annotations

import platform
from pathlib import Path

from rendereye_mcp.agent_setup.base import AgentAdapter


class Adapter(AgentAdapter):
    """Adapter for Cursor MCP configuration.

    User scope:    ~/.cursor/mcp.json
    Project scope: <project>/.cursor/mcp.json
    """

    NAME = "Cursor"
    SUPPORTS_USER_SCOPE = True
    SUPPORTS_PROJECT_SCOPE = True

    def config_path(self, scope: str, project_path: Path | None = None) -> Path:
        if scope == "user":
            if platform.system() == "Windows":
                base = Path.home()
            else:
                base = Path.home()
            return base / ".cursor" / "mcp.json"
        if project_path is None:
            project_path = Path.cwd()
        return project_path / ".cursor" / "mcp.json"

    def get_servers_key(self) -> list[str]:
        return ["mcpServers"]

    def print_restart_instructions(self) -> None:
        print("  Restart Cursor to apply the new MCP configuration.")
