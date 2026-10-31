"""RenderDoc UI extension; stdlib only, compatible with Python 3.6."""

from __future__ import absolute_import

import logging
import os

from .gui_context import GUIContext
from .gui_dispatcher import GUIDispatcher
from .ipc_client import IPCClient
from .state_observer import StateObserver

logger = logging.getLogger(__name__)
_EXTENSION_VERSION = "1.0.0"
_runtime = None


class Runtime(object):
    def __init__(self, version, context):
        self.gui = GUIContext(context, version)
        self.dispatcher = GUIDispatcher(context)
        self.client = IPCClient(
            host=os.environ.get("RENDEREYE_IPC_HOST", "127.0.0.1"),
            port=int(os.environ.get("RENDEREYE_IPC_PORT", "37020")),
            extension_version=_EXTENSION_VERSION,
            renderdoc_version=version,
        )
        self.client.command_handler = self.execute
        self.client.inspect_handler = self.inspect
        self.observer = StateObserver(self.gui, self.dispatcher, self.client.send_gui_state_changed)

    def start(self):
        self.observer.start()
        self.client.start()

    def execute(self, command, params, complete):
        def invoke():
            try:
                result = self.gui.execute(command, params)
            except AttributeError as exc:
                result = False, "unsupported", str(exc)
            except Exception as exc:
                result = False, "failed", str(exc)
            self.observer._sample()
            complete(*result)

        self.dispatcher.submit(invoke)

    def inspect(self, operation, params, complete):
        def invoke():
            try:
                result = self.gui.inspect(operation, params)
                complete(result, "")
            except Exception as exc:
                complete(None, str(exc))

        self.dispatcher.submit(invoke)

    def close(self):
        self.dispatcher.close()
        try:
            self.observer.stop()
        finally:
            try:
                self.client.stop()
            finally:
                self.gui.close()


def register(version, pyrenderdoc):
    """Receive RenderDoc's version and existing CaptureContext on the GUI thread."""
    global _runtime
    unregister()
    runtime = Runtime(version, pyrenderdoc)
    _runtime = runtime
    try:
        runtime.start()
    except Exception:
        unregister()
        raise
    logger.info("RenderEyeMCP %s registered with RenderDoc %s", _EXTENSION_VERSION, version)


def unregister():
    """Called without arguments by RenderDoc before reload."""
    global _runtime
    runtime = _runtime
    _runtime = None
    if runtime is not None:
        runtime.close()
