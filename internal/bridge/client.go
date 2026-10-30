// Package bridge implements the MCP bridge client that connects to the
// rendereye-ipc Shared IPC Service and forwards tool calls.
package bridge

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/ipc"
)

const (
	heartbeatInterval = 15 * time.Second
	toolCallTimeout   = 60 * time.Second
)

// ServiceClient manages a TCP connection to the rendereye-ipc service and
// multiplexes concurrent tool calls over it.
type ServiceClient struct {
	host string
	port int

	conn   net.Conn
	reader *bufio.Reader
	mu     sync.Mutex // guards conn writes

	bridgeConnectionID string

	// pending maps request_id → channel for tool_result messages.
	pendingMu sync.Mutex
	pending   map[string]chan *ipc.ToolResultMessage

	// done is closed when the reader loop exits (connection dropped or Close called).
	done chan struct{}

	closeOnce sync.Once
}

// NewServiceClient creates a ServiceClient that will connect to host:port.
func NewServiceClient(host string, port int) *ServiceClient {
	return &ServiceClient{
		host:    host,
		port:    port,
		pending: make(map[string]chan *ipc.ToolResultMessage),
		done:    make(chan struct{}),
	}
}

// Connect performs the full IPC handshake:
//  1. TCP dial
//  2. service_info_request / service_info_response
//  3. bridge_register / bridge_register_ack
//
// It must be called before CallTool.
func (c *ServiceClient) Connect(ctx context.Context) error {
	addr := net.JoinHostPort(c.host, strconv.Itoa(c.port))
	conn, err := net.DialTimeout("tcp", addr, 5*time.Second)
	if err != nil {
		return fmt.Errorf("dial %s: %w", addr, err)
	}
	c.conn = conn
	c.reader = bufio.NewReader(conn)

	// ---- service_info_request ----
	infoReq := ipc.ServiceInfoRequestMessage{
		RequestID:  newRequestID(),
		ClientType: "mcp_bridge",
		Type:       "service_info_request",
	}
	if err := c.writeMessage(infoReq); err != nil {
		conn.Close()
		return fmt.Errorf("send service_info_request: %w", err)
	}
	data, err := ipc.ReadMessage(c.reader)
	if err != nil {
		conn.Close()
		return fmt.Errorf("read service_info_response: %w", err)
	}
	var infoResp ipc.ServiceInfoResponseMessage
	if err := json.Unmarshal(data, &infoResp); err != nil {
		conn.Close()
		return fmt.Errorf("decode service_info_response: %w", err)
	}
	if infoResp.ServiceName != config.ServiceName {
		conn.Close()
		return fmt.Errorf("unexpected service name %q (want %q)", infoResp.ServiceName, config.ServiceName)
	}
	slog.Debug("service_info received",
		"service", infoResp.ServiceName,
		"version", infoResp.ServiceVersion,
		"pid", infoResp.ServicePID,
	)

	// ---- read auth token ----
	tokenData, err := os.ReadFile(config.TokenPath())
	if err != nil {
		conn.Close()
		return fmt.Errorf("read auth token from %s: %w", config.TokenPath(), err)
	}
	authToken := strings.TrimSpace(string(tokenData))

	// ---- bridge_register ----
	regReq := ipc.BridgeRegisterMessage{
		RequestID:       newRequestID(),
		BridgeID:        newRequestID(), // reuse UUID generator for bridge ID
		ProcessID:       os.Getpid(),
		BridgeVersion:   config.GoServiceVersion,
		AuthToken:       authToken,
		Type:            "bridge_register",
		ProtocolVersion: ipc.ProtocolVersion,
	}
	if err := c.writeMessage(regReq); err != nil {
		conn.Close()
		return fmt.Errorf("send bridge_register: %w", err)
	}
	data, err = ipc.ReadMessage(c.reader)
	if err != nil {
		conn.Close()
		return fmt.Errorf("read bridge_register_ack: %w", err)
	}
	var ack ipc.BridgeRegisterAckMessage
	if err := json.Unmarshal(data, &ack); err != nil {
		conn.Close()
		return fmt.Errorf("decode bridge_register_ack: %w", err)
	}
	c.bridgeConnectionID = ack.BridgeConnectionID
	slog.Info("bridge registered",
		"bridge_connection_id", c.bridgeConnectionID,
		"service_version", ack.ServiceVersion,
	)

	// Start background goroutines.
	go c.readLoop()
	go c.heartbeatLoop()

	return nil
}

// CallTool sends a tool_call message and waits for the matching tool_result.
// If the result contains an error field, it is returned as a structured map
// (not a Go error), matching Python bridge behaviour.
func (c *ServiceClient) CallTool(ctx context.Context, toolName string, arguments map[string]interface{}) (interface{}, error) {
	reqID := newRequestID()

	ch := make(chan *ipc.ToolResultMessage, 1)
	c.pendingMu.Lock()
	c.pending[reqID] = ch
	c.pendingMu.Unlock()

	defer func() {
		c.pendingMu.Lock()
		delete(c.pending, reqID)
		c.pendingMu.Unlock()
	}()

	msg := ipc.ToolCallMessage{
		RequestID:          reqID,
		BridgeConnectionID: c.bridgeConnectionID,
		ToolName:           toolName,
		Arguments:          arguments,
		Type:               "tool_call",
	}
	if err := c.writeMessage(msg); err != nil {
		return nil, fmt.Errorf("send tool_call: %w", err)
	}

	timeout := time.NewTimer(toolCallTimeout)
	defer timeout.Stop()

	select {
	case result := <-ch:
		if result.Error != "" {
			return map[string]interface{}{"error": result.Error}, nil
		}
		return result.Result, nil
	case <-timeout.C:
		return nil, fmt.Errorf("tool_call %q timed out after %s", toolName, toolCallTimeout)
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-c.done:
		return nil, fmt.Errorf("IPC connection closed while waiting for tool_call %q", toolName)
	}
}

// Close sends a goodbye message, stops background goroutines, and closes the
// TCP connection.
func (c *ServiceClient) Close() {
	c.closeOnce.Do(func() {
		// Send goodbye (best-effort).
		bye := ipc.GoodbyeMessage{
			Reason: "bridge_shutdown",
			Type:   "goodbye",
		}
		_ = c.writeMessage(bye)

		if c.conn != nil {
			c.conn.Close()
		}
		// readLoop will exit and close done when conn is closed.
	})
}

// writeMessage serialises v as JSON and writes it via ipc.WriteMessage (NDJSON).
// It is goroutine-safe.
func (c *ServiceClient) writeMessage(v interface{}) error {
	data, err := json.Marshal(v)
	if err != nil {
		return err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return ipc.WriteMessage(c.conn, data)
}

// readLoop reads incoming messages from the TCP connection and dispatches
// tool_result messages to waiting CallTool callers.
func (c *ServiceClient) readLoop() {
	defer close(c.done)
	for {
		data, err := ipc.ReadMessage(c.reader)
		if err != nil {
			slog.Debug("readLoop exiting", "err", err)
			return
		}
		var env ipc.MessageEnvelope
		if err := json.Unmarshal(data, &env); err != nil {
			slog.Warn("failed to decode message envelope", "err", err)
			continue
		}
		switch env.Type {
		case "tool_result":
			var result ipc.ToolResultMessage
			if err := json.Unmarshal(data, &result); err != nil {
				slog.Warn("failed to decode tool_result", "err", err)
				continue
			}
			c.pendingMu.Lock()
			ch, ok := c.pending[result.RequestID]
			c.pendingMu.Unlock()
			if ok {
				ch <- &result
			} else {
				slog.Warn("received tool_result for unknown request_id", "request_id", result.RequestID)
			}
		case "heartbeat_ack":
			// Expected — no action needed.
		default:
			slog.Debug("ignoring message", "type", env.Type)
		}
	}
}

// heartbeatLoop sends a heartbeat every heartbeatInterval until the connection
// closes.
func (c *ServiceClient) heartbeatLoop() {
	ticker := time.NewTicker(heartbeatInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			msg := ipc.HeartbeatMessage{
				RequestID: newRequestID(),
				Type:      "heartbeat",
			}
			if err := c.writeMessage(msg); err != nil {
				slog.Debug("heartbeat send failed", "err", err)
				return
			}
		case <-c.done:
			return
		}
	}
}
