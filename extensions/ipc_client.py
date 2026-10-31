"""IPC client for the RenderDoc extension — stdlib only, Python 3.6 compatible.

This module implements a non-blocking, reconnecting TCP client that runs in a
background thread so it never blocks RenderDoc's main thread.

Usage::

    client = IPCClient(host="127.0.0.1", port=37020, instance_id="abc",
                       extension_version="0.1.0")
    client.start()          # starts background thread
    # ... RenderDoc runs normally ...
    client.stop()           # graceful shutdown
"""

from __future__ import absolute_import

import json
import logging
import os
import queue
import socket
import tempfile
import threading
import time
import uuid

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = 1
_HEARTBEAT_INTERVAL = 5.0  # seconds between heartbeats
_CONNECT_TIMEOUT = 1.0  # max seconds to wait for connect
_SEND_TIMEOUT = 1.0  # max seconds to wait for a send
_RECV_TIMEOUT = 2.0  # max seconds to wait for a recv
_RETRY_DELAY_BASE = 2.0  # base delay for exponential backoff (seconds)
_MAX_MESSAGE_BYTES = 16 * 1024 * 1024  # must match server MAX_MESSAGE_BYTES


def _make_request_id():
    """Return a unique request ID string."""
    return str(uuid.uuid4())


def _read_auth_token():
    """Read auth token from the server's token file."""
    token_path = os.environ.get("RENDEREYE_TOKEN_PATH") or os.path.join(
        tempfile.gettempdir(), "rendereye_mcp_token.txt"
    )
    try:
        with open(token_path, "r") as f:
            return f.read().strip()
    except (IOError, OSError):
        return ""  # empty token — server may reject but won't crash


class IPCClient(object):
    """Background-thread IPC client connecting to the RenderEyeMCP server."""

    def __init__(
        self,
        host="127.0.0.1",
        port=37020,
        instance_id=None,
        extension_version="0.1.0",
        renderdoc_version="unknown",
    ):
        self._host = host
        self._port = port
        self._instance_id = instance_id or str(uuid.uuid4())
        self._extension_version = extension_version
        self._renderdoc_version = renderdoc_version
        self._process_id = os.getpid()

        self._sock = None
        self._buf = b""
        self._connected = False
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._outgoing = queue.Queue(maxsize=256)
        self.command_handler = None
        self.inspect_handler = None
        self._capture_loading = False

        # Capture path from RenderDoc API (may be updated externally)
        self._capture_path = None
        self._capture_loaded = False
        self._state_revision = 0

        # Connection ID assigned by the server after register_ack
        self._connection_id = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self):
        return self._connected

    def start(self):
        """Start the background IPC thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="rendereye-ipc",
            daemon=True,
        )
        try:
            self._thread.start()
        except Exception:
            self._running = False
            self._thread = None
            raise
        logger.info("IPCClient started (pid=%d instance=%s)", self._process_id, self._instance_id)

    def stop(self):
        """Signal the background thread to stop and wait for it."""
        self._running = False
        self._stop_event.set()
        self._disconnect()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                raise RuntimeError("IPC worker did not stop")
            self._thread = None
        logger.info("IPCClient stopped.")

    def set_capture_path(self, path):
        """Update the capture path reported in status responses."""
        with self._lock:
            self._capture_path = path

    def send_gui_state_changed(self, capture_path, capture_loaded, revision, loading=False):
        """Cache every snapshot, including while offline; never send on the GUI thread."""
        with self._lock:
            self._capture_path = capture_path
            self._capture_loaded = capture_loaded
            self._capture_loading = loading
            self._state_revision = revision
        if self._connected:
            self._queue_message(self._state_message("gui_state_changed"))

    def _state_message(self, message_type, request_id=None):
        with self._lock:
            msg = {
                "type": message_type,
                "instance_id": self._instance_id,
                "revision": self._state_revision,
                "capture_loaded": self._capture_loaded,
                "capture_path": self._capture_path,
                "capture_state": "loading"
                if self._capture_loading
                else ("loaded" if self._capture_loaded else "unloaded"),
            }
        if request_id is not None:
            msg["request_id"] = request_id
        return msg

    def _queue_message(self, msg):
        try:
            self._outgoing.put_nowait(msg)
        except queue.Full:
            logger.warning("Outgoing queue full; state remains available via get_gui_state")

    def _drain_outgoing(self):
        while not self._outgoing.empty():
            self._send_message(self._outgoing.get_nowait())

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run_loop(self):
        retries = 0
        while self._running:
            try:
                self._connect()
                self._send_hello()
                self._recv_hello_ack()
                self._send_register_instance()
                self._recv_register_ack()
                retries = 0  # reset on successful connection
                self._send_message(self._state_message("gui_state_changed"))
                self._heartbeat_loop()
                self._disconnect()
            except Exception as exc:
                logger.warning("IPC error (attempt %d): %s", retries + 1, exc)
                self._disconnect()
                if not self._running:
                    break
                retries += 1
                delay = min(30.0, _RETRY_DELAY_BASE * (2 ** min(retries - 1, 4)))
                if self._stop_event.wait(delay):
                    break
        self._disconnect()

    def _heartbeat_loop(self):
        """Send heartbeats and read incoming messages until disconnected."""
        last_hb = time.time()
        while self._running and self._connected:
            self._drain_outgoing()
            now = time.time()
            if now - last_hb >= _HEARTBEAT_INTERVAL:
                self._send_heartbeat()
                last_hb = now

            # Non-blocking peek for incoming server messages
            try:
                self._sock.settimeout(0.1)
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise IOError("Server closed connection.")
                self._buf += chunk
                if len(self._buf) > _MAX_MESSAGE_BYTES:
                    raise IOError("Incoming IPC message exceeds size limit")
                self._process_buf()
            except socket.timeout:
                pass
            except IOError:
                raise

    def _process_buf(self):
        """Process all complete newline-delimited messages in the buffer."""
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if line:
                self._dispatch(line)

    def _dispatch(self, line):
        """Dispatch a single received message line."""
        try:
            msg = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning("Failed to parse server message: %s", exc)
            return

        msg_type = msg.get("type")
        if msg_type == "get_status":
            self._send_status_response(msg.get("request_id", ""))
        elif msg_type == "heartbeat_ack":
            logger.debug("Heartbeat ack received.")
        elif msg_type == "get_gui_state":
            self._handle_get_gui_state(msg)
        elif msg_type == "execute_gui_command":
            self._handle_execute_gui_command(msg)
        elif msg_type == "inspect_capture":
            self._handle_inspect_capture(msg)
        elif msg_type == "goodbye":
            logger.info("Server sent goodbye: %s", msg.get("reason", ""))
            raise IOError("Server restarting/disconnecting")
        elif msg_type == "error":
            logger.warning("Server error: [%s] %s", msg.get("code"), msg.get("message"))
        else:
            logger.debug("Unhandled server message type: %s", msg_type)

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(_CONNECT_TIMEOUT)
        with self._lock:
            self._sock = sock
        try:
            sock.connect((self._host, self._port))
        except Exception:
            sock.close()
            raise
        if not self._running:
            sock.close()
            raise IOError("Extension stopped")
        sock.settimeout(_RECV_TIMEOUT)
        with self._lock:
            self._sock = sock
            self._connected = True
            self._buf = b""
            self._connection_id = None
        logger.info("Connected to %s:%d", self._host, self._port)

    def _disconnect(self):
        with self._lock:
            self._connected = False
            if self._sock is not None:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

    def _send_raw(self, data):
        """Send bytes to the server (must hold no lock)."""
        with self._lock:
            sock = self._sock
        if sock is None:
            raise IOError("Not connected.")
        sock.settimeout(_SEND_TIMEOUT)
        sock.sendall(data)

    def _send_message(self, obj):
        """Serialize and send a message dict."""
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")
        if len(encoded) > _MAX_MESSAGE_BYTES:
            logger.error("Message too large (%d bytes) -- not sent.", len(encoded))
            if obj.get("type") == "inspect_capture_result":
                # Tell the server instead of letting the request time out.
                self._send_message(dict(
                    obj,
                    result=None,
                    error="result_too_large: %d bytes exceeds %d" % (len(encoded), _MAX_MESSAGE_BYTES),
                ))
            return
        self._send_raw(encoded)

    # ------------------------------------------------------------------
    # Protocol messages
    # ------------------------------------------------------------------

    def _send_hello(self):
        self._send_message(
            {
                "type": "hello",
                "protocol_version": _PROTOCOL_VERSION,
                "request_id": _make_request_id(),
                "instance_id": self._instance_id,
                "process_id": self._process_id,
                "extension_version": self._extension_version,
            }
        )

    def _recv_hello_ack(self):
        """Wait for hello_ack from the server."""
        deadline = time.time() + _CONNECT_TIMEOUT * 10
        while self._running and time.time() < deadline:
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise IOError("Server closed connection before hello_ack.")
                self._buf += chunk
                if len(self._buf) > _MAX_MESSAGE_BYTES:
                    raise IOError("Incoming IPC message exceeds size limit")
                if b"\n" in self._buf:
                    line, self._buf = self._buf.split(b"\n", 1)
                    msg = json.loads(line.decode("utf-8"))
                    if msg.get("type") == "hello_ack":
                        if msg.get("protocol_version") != _PROTOCOL_VERSION:
                            raise IOError("Unsupported IPC protocol version")
                        logger.info("Hello ack from server version: %s", msg.get("server_version"))
                        return
                    else:
                        raise IOError("Expected hello_ack, got: %s" % msg.get("type"))
            except socket.timeout:
                continue
        raise IOError("Timed out waiting for hello_ack.")

    def _send_register_instance(self):
        token = _read_auth_token()
        self._send_message(
            {
                "type": "register_instance",
                "protocol_version": _PROTOCOL_VERSION,
                "request_id": _make_request_id(),
                "instance_id": self._instance_id,
                "process_id": self._process_id,
                "extension_version": self._extension_version,
                "renderdoc_version": self._renderdoc_version,
                "auth_token": token,
            }
        )

    def _recv_register_ack(self):
        """Wait for register_ack from the server."""
        deadline = time.time() + _CONNECT_TIMEOUT * 10
        while self._running and time.time() < deadline:
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise IOError("Server closed connection before register_ack.")
                self._buf += chunk
                if len(self._buf) > _MAX_MESSAGE_BYTES:
                    raise IOError("Incoming IPC message exceeds size limit")
                if b"\n" in self._buf:
                    line, self._buf = self._buf.split(b"\n", 1)
                    msg = json.loads(line.decode("utf-8"))
                    if msg.get("type") == "register_ack":
                        self._connection_id = msg.get("connection_id")
                        logger.info(
                            "Register ack: connection_id=%s",
                            self._connection_id,
                        )
                        return
                    elif msg.get("type") == "error":
                        raise IOError(
                            "Registration failed: [{}] {}".format(
                                msg.get("code"), msg.get("message")
                            )
                        )
                    else:
                        raise IOError("Expected register_ack, got: %s" % msg.get("type"))
            except socket.timeout:
                continue
        raise IOError("Timed out waiting for register_ack.")

    def _send_heartbeat(self):
        self._send_message(
            {
                "type": "heartbeat",
                "request_id": _make_request_id(),
            }
        )

    def _send_goodbye(self):
        try:
            self._send_message(
                {
                    "type": "goodbye",
                    "reason": "extension_unregistered",
                }
            )
        except Exception:
            pass

    def _send_status_response(self, request_id):
        with self._lock:
            capture_path = self._capture_path
        self._send_message(
            {
                "type": "status_response",
                "request_id": request_id,
                "process_id": self._process_id,
                "instance_id": self._instance_id,
                "extension_version": self._extension_version,
                "capture_path": capture_path,
                "connected": self._connected,
            }
        )

    def _handle_get_gui_state(self, msg):
        """Handle get_gui_state request from server."""
        self._send_message(self._state_message("gui_state_response", msg.get("request_id", "")))

    def _handle_execute_gui_command(self, msg):
        command = msg.get("command", "")
        request_id = msg.get("request_id", "")

        def complete(success, outcome, error):
            self._queue_message(
                {
                    "type": "gui_command_result",
                    "request_id": request_id,
                    "command": command,
                    "success": success,
                    "outcome": outcome,
                    "error": error,
                }
            )

        if self.command_handler is None:
            complete(False, "unsupported", "GUI dispatcher unavailable")
            return
        try:
            self.command_handler(command, msg.get("params", {}), complete)
        except Exception as exc:
            complete(False, "failed", str(exc))

    def _handle_inspect_capture(self, msg):
        operation = msg.get("operation", "")
        params = msg.get("params", {})
        request_id = msg.get("request_id", "")

        def complete(result, error):
            self._queue_message({
                "type": "inspect_capture_result",
                "request_id": request_id,
                "operation": operation,
                "result": result,
                "error": error or "",
            })

        if self.inspect_handler is None:
            complete(None, "inspect_handler_unavailable")
            return
        try:
            self.inspect_handler(operation, params, complete)
        except Exception as exc:
            complete(None, str(exc))
