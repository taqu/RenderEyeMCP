"""Tests for the upgraded ClientConnection handling Phase 3 messages."""

from __future__ import annotations

import asyncio

import pytest

from rendereye_mcp.ipc.authentication import AuthManager
from rendereye_mcp.ipc.connection import ClientConnection
from rendereye_mcp.ipc.manager import ExtensionConnectionManager
from rendereye_mcp.ipc.protocol import (
    ExecuteGuiCommandMessage,
    GetGuiStateMessage,
    GoodbyeMessage,
    GuiCommandResultMessage,
    GuiStateChangedMessage,
    GuiStateResponseMessage,
    HelloMessage,
    RegisterAckMessage,
    RegisterInstanceMessage,
    deserialize,
    serialize,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_pipe():
    """Create an in-memory async reader/writer pair."""
    reader = asyncio.StreamReader()
    # Create a transport/protocol pair for the writer
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    transport, _ = loop.run_until_complete(
        loop.create_connection(lambda: protocol, sock=None)
    ) if False else (None, None)
    return reader


async def make_stream_pair():
    """Create a bidirectional in-memory stream pair using a socket."""
    import socket as _socket

    # Use socketpair for in-memory communication
    sock_a, sock_b = _socket.socketpair()
    reader_a, writer_a = await asyncio.open_connection(sock=sock_a)
    reader_b, writer_b = await asyncio.open_connection(sock=sock_b)
    return reader_a, writer_a, reader_b, writer_b


async def recv_msg(reader, timeout=2.0):
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    return deserialize(line)


async def send_msg(writer, msg):
    writer.write(serialize(msg))
    await writer.drain()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_manager(tmp_path):
    manager = AuthManager(token_path=tmp_path / "token.txt")
    manager.generate()
    return manager


@pytest.fixture
def conn_manager(auth_manager):
    return ExtensionConnectionManager(auth_manager=auth_manager)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_instance_valid_auth(auth_manager, conn_manager):
    """register_instance with valid auth → register_ack sent."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        # Send hello first
        await send_msg(writer_a, HelloMessage(
            request_id="hello-1",
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
        ))
        ack = await recv_msg(reader_a)
        assert ack.type == "hello_ack"

        # Send register_instance
        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="reg-1",
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token=auth_manager.token,
        ))
        reg_ack = await recv_msg(reader_a)
        assert isinstance(reg_ack, RegisterAckMessage)
        assert reg_ack.request_id == "reg-1"
        assert reg_ack.connection_id is not None
        assert reg_ack.connection_id != "unauthenticated"
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_register_instance_invalid_auth(auth_manager, conn_manager):
    """register_instance with invalid auth → error sent."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        # Send hello first
        await send_msg(writer_a, HelloMessage(
            request_id="hello-1",
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
        ))
        await recv_msg(reader_a)  # consume hello_ack

        # Send register_instance with wrong token
        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="reg-1",
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token="wrong_token",
        ))
        err = await recv_msg(reader_a)
        assert err.type == "error"
        assert err.code == "auth_failed"
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_gui_state_changed_higher_revision(auth_manager, conn_manager):
    """gui_state_changed with higher revision → state updated."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        # Hello + register
        await send_msg(writer_a, HelloMessage(
            request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
        ))
        await recv_msg(reader_a)  # hello_ack

        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="r1", instance_id="inst-1", process_id=1,
            extension_version="0.1.0", renderdoc_version="unknown",
            auth_token=auth_manager.token,
        ))
        reg_ack = await recv_msg(reader_a)  # register_ack
        conn_id = reg_ack.connection_id

        # Send gui_state_changed
        await send_msg(writer_a, GuiStateChangedMessage(
            instance_id="inst-1",
            revision=3,
            capture_loaded=True,
            capture_path="/foo.rdc",
            capture_state="loaded",
        ))
        await asyncio.sleep(0.05)

        # Verify state updated in connection manager
        ec = conn_manager.get_connection(conn_id)
        assert ec is not None
        assert ec.gui_state_revision == 3
        assert ec.capture_loaded is True
        assert ec.capture_path == "/foo.rdc"
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_gui_state_changed_stale_revision_ignored(auth_manager, conn_manager):
    """gui_state_changed with stale revision → ignored."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        await send_msg(writer_a, HelloMessage(
            request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
        ))
        await recv_msg(reader_a)

        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="r1", instance_id="inst-1", process_id=1,
            extension_version="0.1.0", renderdoc_version="unknown",
            auth_token=auth_manager.token,
        ))
        reg_ack = await recv_msg(reader_a)
        conn_id = reg_ack.connection_id

        # Send higher revision first
        await send_msg(writer_a, GuiStateChangedMessage(
            instance_id="inst-1", revision=10, capture_loaded=True,
            capture_path="/new.rdc", capture_state="loaded",
        ))
        await asyncio.sleep(0.05)

        # Send stale revision
        await send_msg(writer_a, GuiStateChangedMessage(
            instance_id="inst-1", revision=2, capture_loaded=False,
            capture_path=None, capture_state="unloaded",
        ))
        await asyncio.sleep(0.05)

        # State should still reflect the higher revision
        ec = conn_manager.get_connection(conn_id)
        assert ec.gui_state_revision == 10
        assert ec.capture_loaded is True
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_gui_state_response_resolves_future(auth_manager, conn_manager):
    """gui_state_response resolves pending future."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        await send_msg(writer_a, HelloMessage(
            request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
        ))
        await recv_msg(reader_a)  # hello_ack

        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="r1", instance_id="inst-1", process_id=1,
            extension_version="0.1.0", renderdoc_version="unknown",
            auth_token=auth_manager.token,
        ))
        await recv_msg(reader_a)  # register_ack

        # Server sends get_gui_state request
        req_task = asyncio.create_task(
            conn.send_request(GetGuiStateMessage(request_id="gs-1"), timeout=2.0)
        )
        # Client reads the get_gui_state request from its end
        await asyncio.sleep(0.05)
        server_msg = await recv_msg(reader_a)
        assert server_msg.type == "get_gui_state"

        # Client sends back gui_state_response
        await send_msg(writer_a, GuiStateResponseMessage(
            request_id="gs-1",
            instance_id="inst-1",
            revision=5,
            capture_loaded=True,
            capture_path="/bar.rdc",
            capture_state="loaded",
        ))

        result = await req_task
        assert isinstance(result, GuiStateResponseMessage)
        assert result.request_id == "gs-1"
        assert result.capture_path == "/bar.rdc"
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_gui_command_result_resolves_future(auth_manager, conn_manager):
    """gui_command_result resolves pending future."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        await send_msg(writer_a, HelloMessage(
            request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
        ))
        await recv_msg(reader_a)  # hello_ack

        await send_msg(writer_a, RegisterInstanceMessage(
            request_id="r1", instance_id="inst-1", process_id=1,
            extension_version="0.1.0", renderdoc_version="unknown",
            auth_token=auth_manager.token,
        ))
        await recv_msg(reader_a)  # register_ack

        # Server sends execute_gui_command
        req_task = asyncio.create_task(
            conn.send_request(
                ExecuteGuiCommandMessage(
                    request_id="cmd-1",
                    command="open_capture",
                    params={"path": "/foo.rdc"},
                ),
                timeout=2.0,
            )
        )
        await asyncio.sleep(0.05)
        server_msg = await recv_msg(reader_a)
        assert server_msg.type == "execute_gui_command"

        # Client sends back gui_command_result
        await send_msg(writer_a, GuiCommandResultMessage(
            request_id="cmd-1",
            command="open_capture",
            success=True,
            outcome="success",
        ))

        result = await req_task
        assert isinstance(result, GuiCommandResultMessage)
        assert result.success is True
        assert result.outcome == "success"
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_goodbye_closes_connection_cleanly(conn_manager):
    """goodbye received → connection closes cleanly."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
            conn_manager=conn_manager,
        )
        task = asyncio.create_task(conn.run())

        await send_msg(writer_a, HelloMessage(
            request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
        ))
        await recv_msg(reader_a)  # hello_ack

        # Send goodbye
        await send_msg(writer_a, GoodbyeMessage(reason="test_done"))
        await asyncio.sleep(0.1)

        # Task should complete
        assert task.done() or conn._goodbye_received
    finally:
        writer_a.close()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


@pytest.mark.asyncio
async def test_send_request_timeout():
    """send_request raises TimeoutError on timeout."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    try:
        conn = ClientConnection(
            reader=reader_b,
            writer=writer_b,
        )
        task = asyncio.create_task(conn.run())

        # Don't send any response — should timeout
        with pytest.raises(asyncio.TimeoutError):
            await conn.send_request(
                GetGuiStateMessage(request_id="timeout-1"),
                timeout=0.1,
            )
    finally:
        writer_a.close()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_disconnect_notifies_conn_manager(auth_manager, conn_manager):
    """Connection close notifies ExtensionConnectionManager."""
    reader_a, writer_a, reader_b, writer_b = await make_stream_pair()
    conn = ClientConnection(
        reader=reader_b,
        writer=writer_b,
        conn_manager=conn_manager,
    )
    task = asyncio.create_task(conn.run())

    await send_msg(writer_a, HelloMessage(
        request_id="h1", instance_id="inst-1", process_id=1, extension_version="0.1.0",
    ))
    await recv_msg(reader_a)  # hello_ack

    await send_msg(writer_a, RegisterInstanceMessage(
        request_id="r1", instance_id="inst-1", process_id=1,
        extension_version="0.1.0", renderdoc_version="unknown",
        auth_token=auth_manager.token,
    ))
    reg_ack = await recv_msg(reader_a)
    conn_id = reg_ack.connection_id

    ec = conn_manager.get_connection(conn_id)
    assert ec is not None
    assert ec.connected is True

    # Close the client side
    writer_a.close()
    await asyncio.wait_for(task, timeout=2.0)

    ec = conn_manager.get_connection(conn_id)
    assert ec.connected is False
