"""Verify dispatched state sampling and cancellation without a RenderDoc import."""

import threading
import time
from types import SimpleNamespace

from extensions.rendereye.gui_context import GUIContext
from extensions.rendereye.gui_dispatcher import GUIDispatcher
from extensions.rendereye.state_observer import StateObserver
from tests.extensions.test_gui_context import Context


class Helper:
    def __init__(self):
        self.pending = []
        self.owner = threading.get_ident()

    def InvokeOntoUIThread(self, cb):
        if threading.get_ident() == self.owner:
            cb()
        else:
            self.pending.append(cb)

    def pump(self):
        queued, self.pending = self.pending, []
        for cb in queued:
            cb()


def test_state_sampling_runs_only_when_gui_pumps():
    ctx, helper, events = Context(), Helper(), []
    ctx.Extensions = lambda: SimpleNamespace(GetMiniQtHelper=lambda: helper)
    dispatcher = GUIDispatcher(ctx)
    observer = StateObserver(
        GUIContext(ctx, "1.46"), dispatcher, lambda *args: events.append(args), 0.01
    )
    observer.start()
    try:
        assert events == [(None, False, 1, False)]
        ctx.loaded, ctx.path = True, "A.rdc"
        time.sleep(0.05)
        assert len(helper.pending) == 1 and len(events) == 1
        helper.pump()
        assert events[-1] == ("A.rdc", True, 2, False)
        ctx.path = "B.rdc"
        observer._sample()
        ctx.loaded, ctx.path = False, ""
        observer._sample()
        assert [e[0] for e in events] == [None, "A.rdc", "B.rdc", None]
        observer._sample()
        assert len(events) == 4
    finally:
        dispatcher.close()
        observer.stop()
    assert observer._thread is None
    before = len(events)
    helper.pump()
    assert len(events) == before


def test_dispatcher_cancels_queued_commands():
    helper = Helper()
    ctx = SimpleNamespace(Extensions=lambda: SimpleNamespace(GetMiniQtHelper=lambda: helper))
    dispatcher = GUIDispatcher(ctx)
    called = []
    worker = threading.Thread(target=lambda: dispatcher.submit(lambda: called.append(True)))
    worker.start()
    worker.join()
    dispatcher.close()
    helper.pump()
    assert not called
