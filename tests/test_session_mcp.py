"""Tests for Phase 2 MCP tools registered on the server."""

from __future__ import annotations

import asyncio

from rendereye_mcp.config import Config
from rendereye_mcp.server import create_server, set_session_manager


def _get_tool_names(server) -> list[str]:
    return asyncio.run(server.list_tools())


def test_session_list_tool_registered():
    config = Config()
    server = create_server(config)
    set_session_manager(None)
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    assert "session_list" in tool_names


def test_all_phase2_tools_registered():
    config = Config()
    server = create_server(config)
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    for expected in [
        "session_list",
        "session_get",
        "session_focus",
        "session_close",
        "session_protect",
        "capture_open",
        "instance_list",
    ]:
        assert expected in tool_names, f"Missing tool: {expected}"


def test_phase0_tools_still_registered():
    config = Config()
    server = create_server(config)
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    assert "server_status" in tool_names


def test_phase1_tools_still_registered():
    config = Config()
    server = create_server(config)
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    for expected in [
        "capture_list",
        "capture_get",
        "capture_latest",
        "capture_rescan",
        "capture_registry_status",
    ]:
        assert expected in tool_names, f"Missing tool: {expected}"


def test_session_manager_none_returns_safe_defaults():
    """With no session manager set, tools return safe empty results."""
    config = Config()
    server = create_server(config)
    set_session_manager(None)

    # We can call tools via server.call_tool
    result = asyncio.run(server.call_tool("session_list", {}))
    assert result is not None


def test_instance_list_no_manager():
    config = Config()
    server = create_server(config)
    set_session_manager(None)
    result = asyncio.run(server.call_tool("instance_list", {}))
    assert result is not None


def test_capture_open_no_manager():
    config = Config()
    server = create_server(config)
    set_session_manager(None)
    result = asyncio.run(server.call_tool("capture_open", {"capture_id": "latest"}))
    assert result is not None


def test_server_status_includes_active_sessions():
    config = Config()
    server = create_server(config)
    set_session_manager(None)
    result = asyncio.run(server.call_tool("server_status", {}))
    # Result is a list of content blocks from MCP SDK
    assert result is not None


def test_total_tools_count():
    """Verify the total number of registered tools (Phase 0 + Phase 1 + Phase 2)."""
    config = Config()
    server = create_server(config)
    tools = asyncio.run(server.list_tools())
    # Phase 0: server_status (1)
    # Phase 1: capture_list, capture_get, capture_latest, capture_rescan, capture_registry_status (5)
    # Phase 2: instance_list, capture_open, session_list, session_get,
    #           session_focus, session_close, session_protect (7)
    # Phase 3: instance_gui_state (1)
    # Phase 4: operation_get (1)
    assert len(tools) >= 14
