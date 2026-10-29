"""Gemini CLI MCP configuration adapter."""

from __future__ import annotations

from pathlib import Path

from rendereye_mcp.agent_setup.base import AgentAdapter


class Adapter(AgentAdapter):
    """Adapter for Gemini CLI MCP configuration.

    User scope:    ~/.gemini/settings.json
    Project scope: <project>/.gemini/settings.json
    """

    NAME = "Gemini CLI"
    # Gemini strips comments before JSON.parse; trailing commas remain invalid.
    JSONC = "comments"
    SUPPORTS_USER_SCOPE = True
    SUPPORTS_PROJECT_SCOPE = True

    def config_path(self, scope: str, project_path: Path | None = None) -> Path:
        if scope == "user":
            return Path.home() / ".gemini" / "settings.json"
        if project_path is None:
            project_path = Path.cwd()
        return project_path / ".gemini" / "settings.json"

    def get_servers_key(self) -> list[str]:
        return ["mcpServers"]

    def print_restart_instructions(self) -> None:
        print("  Restart the Gemini CLI to apply the new MCP configuration.")
