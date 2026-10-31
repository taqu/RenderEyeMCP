"""The actual RenderDoc two-argument registration contract and IPC cleanup."""

import inspect
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import extensions.rendereye as extension
from extensions.rendereye.ipc_client import IPCClient
from tests.extensions.test_gui_context import Context
from tests.extensions.test_state_observer import Helper


@pytest.fixture
def context():
    ctx, helper = Context(), Helper()
    ctx.Extensions = lambda: SimpleNamespace(GetMiniQtHelper=lambda: helper)
    yield ctx
    extension.unregister()


@pytest.fixture
def fake_ipc(monkeypatch):
    cls = Mock()
    monkeypatch.setattr(extension, "IPCClient", cls)
    return cls


def test_signatures():
    assert list(inspect.signature(extension.register).parameters) == ["version", "pyrenderdoc"]
    assert not inspect.signature(extension.unregister).parameters


def test_register_repeat_unregister_register(context, fake_ipc):
    extension.register("1.46", context)
    first = extension._runtime
    assert first.gui.context is context
    extension.register("1.46", context)
    assert first.gui.context is None and first.observer._thread is None
    extension.unregister()
    extension.unregister()
    assert extension._runtime is None
    extension.register("1.46", context)
    assert extension._runtime.gui.context is context


def test_registration_failure(context, fake_ipc):
    fake_ipc.return_value.start.side_effect = RuntimeError("startup failed")
    with pytest.raises(RuntimeError, match="startup failed"):
        extension.register("1.46", context)
    assert extension._runtime is None
    fake_ipc.return_value.stop.assert_called_once()
    assert not any(t.name == "rendereye-state-observer" for t in threading.enumerate())


def test_missing_context():
    with pytest.raises(RuntimeError):
        extension.register("1.46", None)
    assert extension._runtime is None


def test_missing_dispatcher(context):
    context.Extensions = lambda: SimpleNamespace(GetMiniQtHelper=lambda: object())
    with pytest.raises(RuntimeError, match="InvokeOntoUIThread"):
        extension.register("1.46", context)
    assert extension._runtime is None


def test_constructor_failure(context, fake_ipc):
    fake_ipc.side_effect = RuntimeError("cannot construct")
    with pytest.raises(RuntimeError):
        extension.register("1.46", context)
    assert extension._runtime is None


def test_ipc_offline_state_is_retained():
    client = IPCClient()
    client.send_gui_state_changed("A.rdc", True, 7)
    assert client._state_message("gui_state_changed")["capture_path"] == "A.rdc"
    assert client._state_message("gui_state_changed")["revision"] == 7


def test_gui_updates_never_write_socket():
    client = IPCClient()
    client._connected = True
    client._send_message = Mock(side_effect=AssertionError("GUI socket write"))
    client.send_gui_state_changed("A.rdc", True, 1)
    assert client._outgoing.get_nowait()["capture_loaded"]


def test_worker_shutdown_during_reconnect():
    client = IPCClient(port=0)
    client.start()
    worker = client._thread
    client.stop()
    assert not worker.is_alive()


def test_registration_from_non_gui_thread(context, fake_ipc):
    errors = []

    def register():
        try:
            extension.register("1.46", context)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=register)
    worker.start()
    worker.join()
    assert not errors
    runtime = extension._runtime
    assert runtime.gui.thread_id is None
    helper = runtime.dispatcher._helper
    helper.pump()
    assert runtime.gui.thread_id == threading.get_ident()
    fake_ipc.return_value.send_gui_state_changed.assert_called_once_with(None, False, 1, False)


def test_python36_syntax():
    import ast

    root = Path(__file__).resolve().parents[2]
    for source in (root / "extensions/rendereye").glob("*.py"):
        ast.parse(source.read_text(encoding="utf-8"), feature_version=(3, 6))
