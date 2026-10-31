"""Asynchronous MiniQt dispatch with cancellation on shutdown."""

from __future__ import absolute_import


class GUIDispatcher(object):
    def __init__(self, context):
        self._helper = context.Extensions().GetMiniQtHelper()
        if not callable(getattr(self._helper, "InvokeOntoUIThread", None)):
            raise RuntimeError("MiniQtHelper.InvokeOntoUIThread unavailable")
        self._active = True

    def submit(self, callback):
        def invoke():
            if self._active:
                callback()

        if self._active:
            self._helper.InvokeOntoUIThread(invoke)

    def close(self):
        self._active = False
