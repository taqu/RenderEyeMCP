package server

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/ipc"
)

const (
	readTimeoutUnauthenticated = 10 * time.Second
	readTimeoutAuthenticated   = 60 * time.Second
)

// connHandler manages a single TCP connection's read/write lifecycle.
// One reader goroutine and one writer goroutine are launched per connection.
type connHandler struct {
	conn   net.Conn
	peer   string
	reader *bufio.Reader
	send   chan []byte // bounded outbound queue
	router *Router
	auth   *Auth
	logger *slog.Logger

	// Role flags — set during handshake.
	isExt   bool
	isBridge bool

	// Per-connection identifiers assigned by the router.
	extConnID    string
	bridgeConnID string

	// greeted is true after a successful hello or service_info_request.
	greeted bool
}

// newConnHandler allocates a handler for the given TCP connection.
func newConnHandler(conn net.Conn, router *Router, auth *Auth) *connHandler {
	return &connHandler{
		conn:   conn,
		peer:   conn.RemoteAddr().String(),
		reader: bufio.NewReaderSize(conn, ipc.MaxMessageBytes+64),
		send:   make(chan []byte, sendQueueSize),
		router: router,
		auth:   auth,
		logger: slog.Default(),
	}
}

// Run starts the read/write goroutines and blocks until both complete.
func (h *connHandler) Run(ctx context.Context) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	defer h.cleanup()

	h.logger.Info("client connected", "peer", h.peer)

	writerDone := make(chan struct{})
	go func() {
		defer close(writerDone)
		h.writeLoop(ctx)
	}()

	h.readLoop(ctx)

	// Signal writer to stop and wait.
	cancel()
	close(h.send)
	<-writerDone
}

// cleanup unregisters the connection from the router on any exit path.
func (h *connHandler) cleanup() {
	if h.isExt {
		h.router.DisconnectExtension(h.extConnID)
	} else if h.isBridge {
		h.router.DisconnectBridge(h.bridgeConnID)
	}
	h.conn.Close()
	h.logger.Info("client disconnected", "peer", h.peer)
}

// ---------------------------------------------------------------------------
// Read loop
// ---------------------------------------------------------------------------

func (h *connHandler) readLoop(ctx context.Context) {
	for {
		// Dynamic read deadline based on authentication state.
		timeout := readTimeoutUnauthenticated
		if h.greeted || h.isBridge {
			timeout = readTimeoutAuthenticated
		}
		h.conn.SetReadDeadline(time.Now().Add(timeout))

		line, err := ipc.ReadMessage(h.reader)
		if err != nil {
			if isTimeout(err) {
				h.logger.Warn("read timeout", "peer", h.peer)
			} else if !isClosedConn(err) {
				h.logger.Debug("read error", "peer", h.peer, "err", err)
			}
			return
		}

		if err := h.dispatch(line); err != nil {
			h.logger.Warn("dispatch error", "peer", h.peer, "err", err)
		}
	}
}

// dispatch routes one raw JSON message to the correct handler.
func (h *connHandler) dispatch(line []byte) error {
	var env ipc.MessageEnvelope
	if err := json.Unmarshal(line, &env); err != nil {
		h.sendError("", "parse_error", fmt.Sprintf("invalid JSON: %v", err))
		return nil
	}

	switch env.Type {
	// Pre-auth bridge messages
	case "service_info_request":
		return h.handleServiceInfoRequest(line)
	case "bridge_register":
		return h.handleBridgeRegister(line)

	// Extension handshake
	case "hello":
		return h.handleHello(line)
	case "register_instance":
		return h.handleRegisterInstance(line)

	// Bridge active
	case "tool_call":
		if h.isBridge {
			return h.handleToolCall(line)
		}
		h.sendError(requestIDFrom(line), "not_a_bridge", "tool_call requires bridge registration first")

	// Extension active
	case "heartbeat":
		return h.handleHeartbeat(line)
	case "gui_state_changed":
		return h.handleGuiStateChanged(line)
	case "gui_state_response":
		return h.handleGuiStateResponse(line)
	case "gui_command_result":
		return h.handleGuiCommandResult(line)
	case "inspect_capture_result":
		return h.handleInspectCaptureResult(line)
	case "goodbye":
		return h.handleGoodbye(line)

	default:
		reqID := requestIDFrom(line)
		h.logger.Warn("unexpected message type", "type", env.Type, "peer", h.peer)
		h.sendError(reqID, "unexpected_message", fmt.Sprintf("server does not expect %q from clients", env.Type))
	}
	return nil
}

// ---------------------------------------------------------------------------
// Pre-auth handlers
// ---------------------------------------------------------------------------

func (h *connHandler) handleServiceInfoRequest(line []byte) error {
	var msg ipc.ServiceInfoRequestMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.sendError("", "parse_error", err.Error())
		return nil
	}
	h.logger.Debug("service_info_request", "peer", h.peer, "client_type", msg.ClientType)
	h.sendMsg(ipc.ServiceInfoResponseMessage{
		RequestID:         msg.RequestID,
		ServiceName:       config.ServiceName,
		ServiceVersion:    config.GoServiceVersion,
		ServicePID:        currentPID(),
		ServiceInstanceID: h.router.serviceInstanceID,
		Type:              "service_info_response",
		ProtocolVersion:   ipc.ProtocolVersion,
	})
	return nil
}

func (h *connHandler) handleBridgeRegister(line []byte) error {
	var msg ipc.BridgeRegisterMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.sendError("", "parse_error", err.Error())
		return nil
	}
	if !h.auth.Validate(msg.AuthToken) {
		h.logger.Warn("bridge auth failed", "peer", h.peer, "bridge_id", msg.BridgeID)
		h.sendError(msg.RequestID, "auth_failed", "bridge authentication failed")
		return nil
	}
	connID := newUUID()
	h.isBridge = true
	h.bridgeConnID = connID
	h.router.RegisterBridge(connID, msg.BridgeID, h.send)
	h.sendMsg(ipc.BridgeRegisterAckMessage{
		RequestID:          msg.RequestID,
		BridgeConnectionID: connID,
		ServiceVersion:     config.GoServiceVersion,
		Type:               "bridge_register_ack",
		ProtocolVersion:    ipc.ProtocolVersion,
	})
	return nil
}

// ---------------------------------------------------------------------------
// Extension handshake handlers
// ---------------------------------------------------------------------------

func (h *connHandler) handleHello(line []byte) error {
	var msg ipc.HelloMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.sendError("", "parse_error", err.Error())
		return nil
	}
	h.greeted = true
	h.logger.Info("hello", "peer", h.peer, "instance_id", msg.InstanceID, "pid", msg.ProcessID)
	h.sendMsg(ipc.HelloAckMessage{
		RequestID:       msg.RequestID,
		ServerVersion:   config.GoServiceVersion,
		Type:            "hello_ack",
		ProtocolVersion: ipc.ProtocolVersion,
	})
	return nil
}

func (h *connHandler) handleRegisterInstance(line []byte) error {
	var msg ipc.RegisterInstanceMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.sendError("", "parse_error", err.Error())
		return nil
	}
	if !h.auth.Validate(msg.AuthToken) {
		h.logger.Warn("extension auth failed", "peer", h.peer, "instance_id", msg.InstanceID)
		h.sendError(msg.RequestID, "auth_failed", "extension authentication failed")
		return nil
	}
	connID := newUUID()
	h.isExt = true
	h.extConnID = connID
	h.router.RegisterExtension(connID, msg.InstanceID, msg.ProcessID, msg.ExtensionVersion, msg.RenderdocVersion, h.send)
	h.sendMsg(ipc.RegisterAckMessage{
		RequestID:       msg.RequestID,
		ConnectionID:    connID,
		ServerVersion:   config.GoServiceVersion,
		Type:            "register_ack",
		ProtocolVersion: ipc.ProtocolVersion,
	})
	return nil
}

// ---------------------------------------------------------------------------
// Extension active handlers
// ---------------------------------------------------------------------------

func (h *connHandler) handleHeartbeat(line []byte) error {
	var msg ipc.HeartbeatMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.logger.Warn("malformed heartbeat message", "peer", h.peer, "err", err)
		return nil
	}
	h.sendMsg(ipc.HeartbeatAckMessage{
		RequestID: msg.RequestID,
		Type:      "heartbeat_ack",
	})
	return nil
}

func (h *connHandler) handleGuiStateChanged(line []byte) error {
	var msg ipc.GuiStateChangedMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.logger.Warn("malformed gui_state_changed message", "peer", h.peer, "err", err)
		return nil
	}
	if h.isExt {
		h.router.UpdateGuiState(h.extConnID, msg.Revision, msg.CaptureLoaded, msg.CapturePath, msg.CaptureState)
	}
	return nil
}

func (h *connHandler) handleGuiStateResponse(line []byte) error {
	var msg ipc.GuiStateResponseMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.logger.Warn("malformed gui_state_response message", "peer", h.peer, "err", err)
		return nil
	}
	if h.isExt {
		h.router.UpdateGuiState(h.extConnID, msg.Revision, msg.CaptureLoaded, msg.CapturePath, msg.CaptureState)
	}
	return nil
}

func (h *connHandler) handleGuiCommandResult(line []byte) error {
	// Not used by Phase 17 tool routing; logged for completeness.
	h.logger.Debug("gui_command_result received", "peer", h.peer)
	return nil
}

func (h *connHandler) handleInspectCaptureResult(line []byte) error {
	var msg ipc.InspectCaptureResultMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.logger.Warn("failed to parse inspect_capture_result", "peer", h.peer, "err", err)
		return nil
	}
	h.router.RouteInspectCaptureResult(&msg)
	return nil
}

func (h *connHandler) handleGoodbye(line []byte) error {
	var msg ipc.GoodbyeMessage
	if err := json.Unmarshal(line, &msg); err == nil {
		h.logger.Info("goodbye", "peer", h.peer, "reason", msg.Reason)
	}
	return fmt.Errorf("goodbye received") // causes readLoop to exit
}

// ---------------------------------------------------------------------------
// Bridge active handlers
// ---------------------------------------------------------------------------

func (h *connHandler) handleToolCall(line []byte) error {
	var msg ipc.ToolCallMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		h.sendError("", "parse_error", err.Error())
		return nil
	}
	h.logger.Debug("tool_call", "tool", msg.ToolName, "request_id", msg.RequestID, "bridge", h.bridgeConnID)
	go h.router.RouteToolCall(&msg, h.bridgeConnID)
	return nil
}

// ---------------------------------------------------------------------------
// Write loop
// ---------------------------------------------------------------------------

func (h *connHandler) writeLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case data, ok := <-h.send:
			if !ok {
				return
			}
			h.conn.SetWriteDeadline(time.Now().Add(30 * time.Second))
			if _, err := h.conn.Write(data); err != nil {
				if !isClosedConn(err) {
					h.logger.Debug("write error", "peer", h.peer, "err", err)
				}
				return
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// sendMsg serialises msg to compact JSON + newline and queues it for writing.
func (h *connHandler) sendMsg(msg interface{}) {
	data, err := json.Marshal(msg)
	if err != nil {
		h.logger.Error("marshal failed", "err", err)
		return
	}
	safeSend(h.send, append(data, '\n'))
}

// sendError sends an ErrorMessage to the client.
func (h *connHandler) sendError(requestID, code, message string) {
	h.sendMsg(ipc.ErrorMessage{
		RequestID: requestID,
		Code:      code,
		Message:   message,
		Type:      "error",
	})
}

// requestIDFrom extracts the request_id field without full unmarshal.
func requestIDFrom(line []byte) string {
	var env struct {
		RequestID string `json:"request_id"`
	}
	json.Unmarshal(line, &env) //nolint:errcheck
	return env.RequestID
}

func isTimeout(err error) bool {
	if ne, ok := err.(net.Error); ok {
		return ne.Timeout()
	}
	return false
}

func isClosedConn(err error) bool {
	if err == nil {
		return false
	}
	s := err.Error()
	return contains(s, "use of closed network connection") ||
		contains(s, "connection reset by peer") ||
		contains(s, "broken pipe") ||
		contains(s, "EOF")
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(s) > 0 && findSub(s, sub))
}

func findSub(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
