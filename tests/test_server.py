"""Tests for the MCP server and the server_status tool."""

from __future__ import annotations

import sys

from rendereye_mcp.config import Config
from rendereye_mcp.server import create_server

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _call_server_status(config: Config) -> dict:
    """Invoke the server_status tool and return the result as a dict."""
    import asyncio
    import json

    server = create_server(config)
    result = asyncio.run(server.call_tool("server_status", {}))
    # mcp 2.x returns a CallToolResult with a content list of TextContent objects.
    for item in result.content:
        if hasattr(item, "text"):
            return json.loads(item.text)
    # Structured output case — result.structured_content is a dict
    if result.structured_content is not None:
        return result.structured_content
    return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestServerCreation:
    def test_create_server_returns_mcpserver(self):
        from mcp.server.mcpserver import MCPServer

        config = Config()
        server = create_server(config)
        assert isinstance(server, MCPServer)

    def test_server_name(self):
        config = Config()
        server = create_server(config)
        assert server.name == "RenderEyeMCP"

    def test_server_version(self):
        from rendereye_mcp import __version__

        config = Config()
        server = create_server(config)
        assert server.version == __version__


class TestServerStatusTool:
    def test_returns_required_fields(self):
        config = Config()
        status = _call_server_status(config)
        required_keys = [
            "server_name",
            "server_version",
            "os",
            "python_version",
            "renderdoc_detected",
            "renderdoc_path",
            "ipc_listener_status",
            "extension_connections",
        ]
        for key in required_keys:
            assert key in status, f"Missing key: {key}"

    def test_server_name_value(self):
        config = Config()
        status = _call_server_status(config)
        assert status["server_name"] == "RenderEyeMCP"

    def test_server_version_value(self):
        from rendereye_mcp import __version__

        config = Config()
        status = _call_server_status(config)
        assert status["server_version"] == __version__

    def test_python_version_present(self):
        config = Config()
        status = _call_server_status(config)
        assert sys.version in status["python_version"]

    def test_renderdoc_detected_false_when_not_found(self):
        """With a non-existent path, renderdoc_detected should be False."""
        config = Config(renderdoc_exe="Z:/does/not/exist/qrenderdoc.exe")
        status = _call_server_status(config)
        assert status["renderdoc_detected"] is False
        assert status["renderdoc_path"] is None

    def test_renderdoc_detected_true_when_found(self, tmp_path):
        """If the executable exists, renderdoc_detected should be True."""
        fake_exe = tmp_path / "qrenderdoc.exe"
        fake_exe.write_bytes(b"")
        config = Config(renderdoc_exe=str(fake_exe))
        status = _call_server_status(config)
        assert status["renderdoc_detected"] is True
        assert status["renderdoc_path"] is not None

    def test_ipc_listener_status_field(self):
        config = Config()
        status = _call_server_status(config)
        assert status["ipc_listener_status"] in ("running", "stopped")

    def test_extension_connections_is_int(self):
        config = Config()
        status = _call_server_status(config)
        assert isinstance(status["extension_connections"], int)
        assert status["extension_connections"] >= 0
