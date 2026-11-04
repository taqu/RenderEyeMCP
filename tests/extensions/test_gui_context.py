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


def _action(eid, flags, name="", children=()):
    return SimpleNamespace(eventId=eid, flags=flags, customName=name, children=list(children))


def test_event_tree_returns_marker_hierarchy(ctx):
    ctx.loaded, ctx.path = True, "tree.rdc"
    draw, dispatch, marker = 2, 4, 64
    ctx.CurRootActions = lambda: [
        _action(1, marker, "Shadow", [_action(2, draw, "Draw A"), _action(3, dispatch)]),
        _action(4, draw, "Draw B"),
    ]
    result = GUIContext(ctx, "1.46").inspect("event_tree", {})
    assert result["_capture_path"] == "tree.rdc"
    assert result["total_nodes"] == 4 and result["truncated"] is False
    shadow, draw_b = result["events"]
    assert shadow["action_type"] == "marker_begin" and shadow["name"] == "Shadow"
    assert [c["event_id"] for c in shadow["children"]] == [2, 3]
    assert shadow["children"][1]["action_type"] == "dispatch"
    assert shadow["children"][1]["name"] == "Event 3"
    assert draw_b["children"] == []


def test_event_tree_truncates(ctx):
    ctx.loaded, ctx.path = True, "tree.rdc"
    ctx.CurRootActions = lambda: [_action(i, 2) for i in range(1, 6)]
    result = GUIContext(ctx, "1.46").inspect("event_tree", {"max_nodes": 3})
    assert len(result["events"]) == 3 and result["truncated"] is True
