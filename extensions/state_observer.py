"""Poll actual capture state through MiniQt, never directly from a worker."""

from __future__ import absolute_import

import logging
import threading

logger = logging.getLogger(__name__)


class StateObserver(object):
    def __init__(self, gui, dispatcher, on_state_changed, poll_interval=0.25):
        self._gui = gui
        self._dispatcher = dispatcher
        self._on_state_changed = on_state_changed
        self._interval = poll_interval
        self._stop = threading.Event()
        self._pending = threading.Event()
        self._thread = None
        self._state = None
        self._revision = 0

    def start(self):
        self._pending.set()
        self._dispatcher.submit(self._sample)
        self._thread = threading.Thread(
            target=self._run, name="rendereye-state-observer", daemon=True
        )
        try:
            self._thread.start()
        except Exception:
            self._stop.set()
            self._thread = None
            raise

    def _sample(self):
        try:
            if self._stop.is_set():
                return
            state = self._gui.snapshot()
            if state != self._state:
                self._state = state
                self._revision += 1
                self._on_state_changed(state[0], state[1], self._revision, state[2])
        except Exception:
            logger.exception("Could not read GUI state")
        finally:
            self._pending.clear()

    def _run(self):
        while not self._stop.wait(self._interval):
            if not self._pending.is_set():
                self._pending.set()
                try:
                    self._dispatcher.submit(self._sample)
                except Exception:
                    self._pending.clear()
                    logger.exception("Could not dispatch GUI state query")

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                raise RuntimeError("State observer did not stop")
            self._thread = None
