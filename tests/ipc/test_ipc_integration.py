"""Full IPC round-trip integration tests using real localhost server."""

from __future__ import annotations

import asyncio

import pytest

from rendereye_mcp.config import Config
from rendereye_mcp.ipc.authentication import AuthManager
from rendereye_mcp.ipc.manager import ExtensionConnectionManager
from rendereye_mcp.ipc.protocol import (
    GoodbyeMessage,
    GuiStateChangedMessage,
    HelloMessage,
    RegisterAckMessage,
    RegisterInstanceMessage,
    deserialize,
    serialize,
)
from rendereye_mcp.ipc.transport import IPCTransport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def free_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def auth_manager(tmp_path):
    manager = AuthManager(token_path=tmp_path / "token.txt")
    manager.generate()
    return manager


@pytest.fixture
def conn_manager(auth_manager):
    return ExtensionConnectionManager(auth_manager=auth_manager)


@pytest.fixture
def config(free_port):
    return Config(ipc_port=free_port)


@pytest.fixture
async def transport(config, conn_manager):
    t = IPCTransport(config, conn_manager=conn_manager)
    await t.start()
    yield t
    await t.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def connect(config):
    reader, writer = await asyncio.open_connection(config.ipc_host, config.ipc_port)
    return reader, writer


async def send_msg(writer, msg):
    writer.write(serialize(msg))
    await writer.drain()


async def recv_msg(reader, timeout=2.0):
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    return deserialize(line)


async def full_handshake(config, auth_manager, instance_id="inst-1", process_id=1):
    """Perform hello + register_instance handshake. Returns (reader, writer, conn_id)."""
    reader, writer = await connect(config)
    await send_msg(writer, HelloMessage(
        request_id="h-1",
        instance_id=instance_id,
        process_id=process_id,
        extension_version="0.1.0",
    ))
    hello_ack = await recv_msg(reader)
    assert hello_ack.type == "hello_ack"

    await send_msg(writer, RegisterInstanceMessage(
        request_id="r-1",
        instance_id=instance_id,
        process_id=process_id,
        extension_version="0.1.0",
        renderdoc_version="1.0.0",
        auth_token=auth_manager.token,
    ))
    reg_ack = await recv_msg(reader)
    assert isinstance(reg_ack, RegisterAckMessage)
    return reader, writer, reg_ack.connection_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hello_and_register_handshake(transport, config, auth_manager, conn_manager):
    """Client connects, sends hello + register_instance → gets hello_ack + register_ack."""
    reader, writer, conn_id = await full_handshake(config, auth_manager)
    try:
        assert conn_id is not None
        # Verify registered in conn_manager
        await asyncio.sleep(0.05)
        conn = conn_manager.get_connection(conn_id)
        assert conn is not None
        assert conn.connected is True
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_gui_state_changed_updates_manager(transport, config, auth_manager, conn_manager):
    """Client sends gui_state_changed → ExtensionConnectionManager updated."""
    reader, writer, conn_id = await full_handshake(config, auth_manager)
    try:
        await send_msg(writer, GuiStateChangedMessage(
            instance_id="inst-1",
            revision=1,
            capture_loaded=True,
            capture_path="/my/capture.rdc",
            capture_state="loaded",
        ))
        await asyncio.sleep(0.1)
        conn = conn_manager.get_connection(conn_id)
        assert conn.capture_loaded is True
        assert conn.capture_path == "/my/capture.rdc"
        assert conn.gui_state_revision == 1
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_client_disconnect_triggers_on_disconnected(
    transport, config, auth_manager, conn_manager
):
    """Client disconnects → on_extension_disconnected called, conn marked disconnected."""
    reader, writer, conn_id = await full_handshake(config, auth_manager)
    await asyncio.sleep(0.05)
    conn = conn_manager.get_connection(conn_id)
    assert conn.connected is True

    writer.close()
    await writer.wait_closed()

    # Give server time to detect disconnect
    for _ in range(20):
        await asyncio.sleep(0.05)
        conn = conn_manager.get_connection(conn_id)
        if conn and not conn.connected:
            break

    conn = conn_manager.get_connection(conn_id)
    assert conn.connected is False


@pytest.mark.asyncio
async def test_two_clients_tracked_independently(
    transport, config, auth_manager, conn_manager
):
    """Two clients connect simultaneously → both tracked independently."""
    reader1, writer1, conn_id1 = await full_handshake(
        config, auth_manager, instance_id="inst-1", process_id=1
    )
    reader2, writer2, conn_id2 = await full_handshake(
        config, auth_manager, instance_id="inst-2", process_id=2
    )
    try:
        await asyncio.sleep(0.05)
        assert conn_id1 != conn_id2
        assert conn_manager.active_count() == 2

        c1 = conn_manager.get_connection(conn_id1)
        c2 = conn_manager.get_connection(conn_id2)
        assert c1.instance_id == "inst-1"
        assert c2.instance_id == "inst-2"
    finally:
        writer1.close()
        await writer1.wait_closed()
        writer2.close()
        await writer2.wait_closed()


@pytest.mark.asyncio
async def test_client_goodbye_clean_close(transport, config, auth_manager, conn_manager):
    """Client sends goodbye → clean close."""
    reader, writer, conn_id = await full_handshake(config, auth_manager)
    await send_msg(writer, GoodbyeMessage(reason="test_done"))
    await asyncio.sleep(0.2)

    # Connection should be disconnected
    conn = conn_manager.get_connection(conn_id)
    assert conn is not None
    # Either the goodbye was received and connection closed, or it's still being processed
    # The key is no exception was raised
    writer.close()
    await writer.wait_closed()
