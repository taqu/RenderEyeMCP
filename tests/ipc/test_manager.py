"""Tests for rendereye_mcp.ipc.manager (ExtensionConnectionManager)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rendereye_mcp.ipc.authentication import AuthManager
from rendereye_mcp.ipc.manager import ExtensionConnectionManager


@pytest.fixture
def auth_manager(tmp_path):
    manager = AuthManager(token_path=tmp_path / "token.txt")
    manager.generate()
    return manager


@pytest.fixture
def conn_manager(auth_manager):
    return ExtensionConnectionManager(auth_manager=auth_manager)


class TestRegisterConnection:
    def test_valid_token_returns_connection_id(self, conn_manager, auth_manager):
        conn_id, error = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token=auth_manager.token,
        )
        assert conn_id is not None
        assert error == ""

    def test_invalid_token_returns_none(self, conn_manager):
        conn_id, error = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token="invalid_token",
        )
        assert conn_id is None
        assert error == "authentication_failed"

    def test_no_auth_manager_accepts_any_token(self):
        manager = ExtensionConnectionManager(auth_manager=None)
        conn_id, error = manager.register_connection(
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token="any_token",
        )
        assert conn_id is not None
        assert error == ""

    def test_connection_stored_after_registration(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1234,
            extension_version="0.1.0",
            renderdoc_version="1.1.2",
            auth_token=auth_manager.token,
        )
        conn = conn_manager.get_connection(conn_id)
        assert conn is not None
        assert conn.instance_id == "inst-1"
        assert conn.process_id == 1234
        assert conn.connected is True
        assert conn.authenticated is True

    def test_instance_manager_refreshed_on_register(self, auth_manager, tmp_path):
        instance_mgr = MagicMock()
        manager = ExtensionConnectionManager(
            auth_manager=auth_manager,
            instance_manager=instance_mgr,
        )
        manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        instance_mgr.refresh.assert_called_once()


class TestUpdateGuiState:
    def test_update_with_higher_revision_succeeds(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        result = conn_manager.update_gui_state(
            connection_id=conn_id,
            revision=5,
            capture_loaded=True,
            capture_path="/foo/bar.rdc",
            capture_state="loaded",
        )
        assert result is True
        conn = conn_manager.get_connection(conn_id)
        assert conn.gui_state_revision == 5
        assert conn.capture_loaded is True
        assert conn.capture_path == "/foo/bar.rdc"
        assert conn.capture_state == "loaded"

    def test_update_with_same_revision_returns_false(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_manager.update_gui_state(
            connection_id=conn_id,
            revision=5,
            capture_loaded=True,
            capture_path="/foo.rdc",
            capture_state="loaded",
        )
        result = conn_manager.update_gui_state(
            connection_id=conn_id,
            revision=5,
            capture_loaded=False,
            capture_path=None,
            capture_state="unloaded",
        )
        assert result is False
        # State unchanged
        conn = conn_manager.get_connection(conn_id)
        assert conn.capture_loaded is True

    def test_update_with_lower_revision_returns_false(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_manager.update_gui_state(
            connection_id=conn_id,
            revision=10,
            capture_loaded=True,
            capture_path="/bar.rdc",
            capture_state="loaded",
        )
        result = conn_manager.update_gui_state(
            connection_id=conn_id,
            revision=3,
            capture_loaded=False,
            capture_path=None,
            capture_state="unloaded",
        )
        assert result is False

    def test_update_unknown_connection_returns_false(self, conn_manager):
        result = conn_manager.update_gui_state(
            connection_id="nonexistent",
            revision=1,
            capture_loaded=True,
            capture_path="/foo.rdc",
            capture_state="loaded",
        )
        assert result is False

    def test_session_manager_notified_on_state_change(self, auth_manager, tmp_path):
        session_mgr = MagicMock()
        manager = ExtensionConnectionManager(
            auth_manager=auth_manager,
            session_manager=session_mgr,
        )
        conn_id, _ = manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        manager.update_gui_state(
            connection_id=conn_id,
            revision=1,
            capture_loaded=True,
            capture_path="/foo.rdc",
            capture_state="loaded",
        )
        session_mgr.on_gui_state_changed.assert_called_once_with(
            connection_id=conn_id,
            capture_path="/foo.rdc",
            capture_loaded=True,
        )


class TestDisconnectConnection:
    def test_disconnect_marks_not_connected(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_manager.disconnect_connection(conn_id)
        conn = conn_manager.get_connection(conn_id)
        assert conn.connected is False

    def test_disconnect_nonexistent_no_error(self, conn_manager):
        conn_manager.disconnect_connection("nonexistent")  # Should not raise

    def test_session_manager_notified_on_disconnect(self, auth_manager, tmp_path):
        session_mgr = MagicMock()
        manager = ExtensionConnectionManager(
            auth_manager=auth_manager,
            session_manager=session_mgr,
        )
        conn_id, _ = manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        manager.disconnect_connection(conn_id)
        session_mgr.on_extension_disconnected.assert_called_once_with(conn_id)


class TestListAndCount:
    def test_list_connections_returns_all(self, conn_manager, auth_manager):
        for i in range(3):
            conn_manager.register_connection(
                instance_id="inst-{}".format(i),
                process_id=i + 1,
                extension_version="0.1.0",
                renderdoc_version="unknown",
                auth_token=auth_manager.token,
            )
        conns = conn_manager.list_connections()
        assert len(conns) == 3

    def test_active_count_counts_only_connected(self, conn_manager, auth_manager):
        conn_id1, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_id2, _ = conn_manager.register_connection(
            instance_id="inst-2",
            process_id=2,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        assert conn_manager.active_count() == 2
        conn_manager.disconnect_connection(conn_id1)
        assert conn_manager.active_count() == 1

    def test_multiple_connections_tracked_independently(self, conn_manager, auth_manager):
        conn_id1, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_id2, _ = conn_manager.register_connection(
            instance_id="inst-2",
            process_id=2,
            extension_version="0.2.0",
            renderdoc_version="1.0.0",
            auth_token=auth_manager.token,
        )
        c1 = conn_manager.get_connection(conn_id1)
        c2 = conn_manager.get_connection(conn_id2)
        assert c1.instance_id == "inst-1"
        assert c2.instance_id == "inst-2"
        assert c1.extension_version == "0.1.0"
        assert c2.extension_version == "0.2.0"


class TestGetConnectionForInstance:
    def test_returns_connected_connection(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn = conn_manager.get_connection_for_instance("inst-1")
        assert conn is not None
        assert conn.connection_id == conn_id

    def test_returns_none_after_disconnect(self, conn_manager, auth_manager):
        conn_id, _ = conn_manager.register_connection(
            instance_id="inst-1",
            process_id=1,
            extension_version="0.1.0",
            renderdoc_version="unknown",
            auth_token=auth_manager.token,
        )
        conn_manager.disconnect_connection(conn_id)
        conn = conn_manager.get_connection_for_instance("inst-1")
        assert conn is None

    def test_returns_none_for_unknown_instance(self, conn_manager):
        conn = conn_manager.get_connection_for_instance("nonexistent")
        assert conn is None
