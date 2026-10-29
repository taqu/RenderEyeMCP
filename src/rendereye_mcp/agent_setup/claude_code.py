"""Claude Code MCP configuration adapter."""

from __future__ import annotations

from pathlib import Path

from rendereye_mcp.agent_setup.base import AgentAdapter


class Adapter(AgentAdapter):
    """Adapter for Claude Code (claude.ai/code) MCP configuration.

    User scope:   ~/.claude.json  (global MCP servers)
    Project scope: <project>/.mcp.json
    """

    NAME = "Claude Code"
    SUPPORTS_USER_SCOPE = True
    SUPPORTS_PROJECT_SCOPE = True

    def config_path(self, scope: str, project_path: Path | None = None) -> Path:
        if scope == "user":
            return Path.home() / ".claude.json"
        if project_path is None:
            project_path = Path.cwd()
        return project_path / ".mcp.json"

    def get_servers_key(self) -> list[str]:
        return ["mcpServers"]

    def build_server_entry(self, executable: Path) -> dict:
        return {"type": "stdio", **super().build_server_entry(executable)}

    def print_restart_instructions(self) -> None:
        print("  Restart Claude Code to apply the new MCP configuration.")
        print("  Or run: claude mcp list  to verify the server is registered.")
