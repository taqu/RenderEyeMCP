"""Contract tests use a strict supplied context, never invented module APIs."""

import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from extensions.rendereye.gui_context import GUIContext


class Context:
    def __init__(self):
        self.loaded = False
        self.loading = False
        self.path = ""
        self.window = SimpleNamespace(PromptCloseCapture=Mock(return_value=True))

    def IsCaptureLoaded(self):
        return self.loaded

    def IsCaptureLoading(self):
        return self.loading

    def GetCaptureFilename(self):
        return self.path

    def Extensions(self):
        return None

    def GetMainWindow(self):
        return self.window

    def LoadCapture(self, path, opts, original, temporary, local):
        assert original == path and temporary is False and local is True
        self.loaded, self.path = True, path


@pytest.fixture
def ctx():
    return Context()


def test_supplied_context_and_state(ctx):
    gui = GUIContext(ctx, "1.46")
    assert gui.context is ctx
    assert gui.snapshot() == (None, False, False)
    ctx.loaded, ctx.path = True, "A.rdc"
    assert gui.snapshot() == ("A.rdc", True, False)
    ctx.loading = True
    assert gui.snapshot()[2] is True


def test_capabilities_required():
    with pytest.raises(RuntimeError, match="IsCaptureLoaded"):
        GUIContext(object(), "1.46")


def test_wrong_thread_rejected(ctx):
    gui = GUIContext(ctx, "1.46")
    gui.snapshot()  # bind from the dispatched GUI callback before checking another thread
    errors = []

    def run():
        try:
            gui.snapshot()
        except RuntimeError as exc:
            errors.append(str(exc))

    t = threading.Thread(target=run)
    t.start()
    t.join()
    assert errors


def test_open_capture_full_signature(ctx, tmp_path, monkeypatch):
    capture = tmp_path / "test.rdc"
    capture.write_bytes(b"fixture")
    monkeypatch.setitem(sys.modules, "renderdoc", SimpleNamespace(ReplayOptions=object))
    assert GUIContext(ctx, "1.46").execute("open_capture", {"path": str(capture)}) == (
        True,
        "success",
        "",
    )


def test_cancel_preserves_capture(ctx, tmp_path):
    ctx.loaded, ctx.path = True, "user.rdc"
    ctx.window.PromptCloseCapture.return_value = False
    assert GUIContext(ctx, "1.46").execute("close_capture", {})[0] is False
    assert ctx.path == "user.rdc"


def test_context_cleared(ctx):
    gui = GUIContext(ctx, "1.46")
    gui.close()
    with pytest.raises(RuntimeError, match="unregistered"):
        gui.snapshot()


def test_unknown_command(ctx):
    assert GUIContext(ctx, "1.46").execute("focus_window", {})[1] == "unsupported"
