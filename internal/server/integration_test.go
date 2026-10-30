package server

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/ipc"
)

// startTestServer spins up a real server on an OS-assigned port and returns
// a cancel function plus the listening address.
func startTestServer(t *testing.T) (addr string, cancel context.CancelFunc, auth *Auth) {
	t.Helper()
	cfg := &config.Config{
		IPCHost:  "127.0.0.1",
		IPCPort:  0, // OS assigns a free port
		LogLevel: "warn",
	}

	authInst := NewAuth()
	svcInstanceID := generateInstanceID()
	router := NewRouter(svcInstanceID, authInst)

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	_ = cfg

	ctx, cancelFn := context.WithCancel(context.Background())

	svc := &Server{
		cfg:    cfg,
		router: router,
		auth:   authInst,
	}
	svc.listener = ln

	go svc.acceptLoop(ctx, ln)

	t.Cleanup(func() {
		cancelFn()
		ln.Close()
		svc.connWG.Wait()
		router.Close()
	})

	return ln.Addr().String(), cancelFn, authInst
}

// dialConn opens a TCP connection to addr and returns a reader/writer pair.
func dialConn(t *testing.T, addr string) (net.Conn, *bufio.Reader) {
	t.Helper()
	conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
	if err != nil {
		t.Fatalf("dial %s: %v", addr, err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn, bufio.NewReaderSize(conn, ipc.MaxMessageBytes+64)
}

// sendJSON marshals msg and writes it as an NDJSON frame.
func sendJSON(t *testing.T, conn net.Conn, msg interface{}) {
	t.Helper()
	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := ipc.WriteMessage(conn, data); err != nil {
		t.Fatalf("write: %v", err)
	}
}

// recvMsg reads one newline-delimited JSON message and deserialises into out.
func recvMsg(t *testing.T, r *bufio.Reader, out interface{}) {
	t.Helper()
	line, err := ipc.ReadMessage(r)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	if err := json.Unmarshal(trimNewline(line), out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
}

// ---------------------------------------------------------------------------

func TestServiceInfoRequest(t *testing.T) {
	addr, _, _ := startTestServer(t)
	conn, r := dialConn(t, addr)

	sendJSON(t, conn, ipc.ServiceInfoRequestMessage{
		RequestID:  "req-svc-1",
		ClientType: "bridge",
		Type:       "service_info_request",
	})

	var resp ipc.ServiceInfoResponseMessage
	recvMsg(t, r, &resp)

	if resp.Type != "service_info_response" {
		t.Errorf("type got %q want service_info_response", resp.Type)
	}
	if resp.ServiceName != config.ServiceName {
		t.Errorf("service_name got %q want %q", resp.ServiceName, config.ServiceName)
	}
	if resp.RequestID != "req-svc-1" {
		t.Errorf("request_id echo got %q want req-svc-1", resp.RequestID)
	}
}

func TestHelloAndRegisterExtension(t *testing.T) {
	addr, _, authInst := startTestServer(t)
	conn, r := dialConn(t, addr)

	// Step 1: hello
	sendJSON(t, conn, ipc.HelloMessage{
		RequestID:        "req-hello-1",
		InstanceID:       "inst-test",
		ProcessID:        9999,
		ExtensionVersion: "1.0.0",
		Type:             "hello",
		ProtocolVersion:  ipc.ProtocolVersion,
	})
	var ack ipc.HelloAckMessage
	recvMsg(t, r, &ack)
	if ack.Type != "hello_ack" {
		t.Fatalf("expected hello_ack, got %q", ack.Type)
	}

	// Step 2: register_instance
	sendJSON(t, conn, ipc.RegisterInstanceMessage{
		RequestID:        "req-reg-1",
		InstanceID:       "inst-test",
		ProcessID:        9999,
		ExtensionVersion: "1.0.0",
		RenderdocVersion: "1.34",
		AuthToken:        authInst.token,
		Type:             "register_instance",
		ProtocolVersion:  ipc.ProtocolVersion,
	})
	var regAck ipc.RegisterAckMessage
	recvMsg(t, r, &regAck)
	if regAck.Type != "register_ack" {
		t.Fatalf("expected register_ack, got %q", regAck.Type)
	}
	if regAck.ConnectionID == "" {
		t.Error("connection_id should be non-empty")
	}
}

func TestExtensionAuthFailed(t *testing.T) {
	addr, _, _ := startTestServer(t)
	conn, r := dialConn(t, addr)

	sendJSON(t, conn, ipc.RegisterInstanceMessage{
		RequestID: "req-bad-auth",
		AuthToken: "wrong-token",
		Type:      "register_instance",
	})
	var errMsg ipc.ErrorMessage
	recvMsg(t, r, &errMsg)
	if errMsg.Code != "auth_failed" {
		t.Errorf("expected auth_failed, got %q", errMsg.Code)
	}
}

func TestBridgeRegistration(t *testing.T) {
	addr, _, authInst := startTestServer(t)
	conn, r := dialConn(t, addr)

	sendJSON(t, conn, ipc.BridgeRegisterMessage{
		RequestID:     "req-bridge-1",
		BridgeID:      "bridge-test",
		ProcessID:     1234,
		BridgeVersion: "1.0.0",
		AuthToken:     authInst.token,
		Type:          "bridge_register",
		ProtocolVersion: ipc.ProtocolVersion,
	})
	var ack ipc.BridgeRegisterAckMessage
	recvMsg(t, r, &ack)
	if ack.Type != "bridge_register_ack" {
		t.Fatalf("expected bridge_register_ack, got %q", ack.Type)
	}
	if ack.BridgeConnectionID == "" {
		t.Error("bridge_connection_id should be non-empty")
	}
}

func TestHeartbeat(t *testing.T) {
	addr, _, authInst := startTestServer(t)
	conn, r := dialConn(t, addr)

	// Register as extension first.
	sendJSON(t, conn, ipc.HelloMessage{RequestID: "h", InstanceID: "i", ProcessID: 1, ExtensionVersion: "1.0", Type: "hello", ProtocolVersion: 1})
	var hAck ipc.HelloAckMessage
	recvMsg(t, r, &hAck)

	sendJSON(t, conn, ipc.RegisterInstanceMessage{RequestID: "r", InstanceID: "i", ProcessID: 1, ExtensionVersion: "1.0", AuthToken: authInst.token, Type: "register_instance", ProtocolVersion: 1})
	var rAck ipc.RegisterAckMessage
	recvMsg(t, r, &rAck)

	// Send heartbeat.
	sendJSON(t, conn, ipc.HeartbeatMessage{RequestID: "hb-1", Type: "heartbeat"})
	var hbAck ipc.HeartbeatAckMessage
	recvMsg(t, r, &hbAck)
	if hbAck.Type != "heartbeat_ack" {
		t.Errorf("expected heartbeat_ack, got %q", hbAck.Type)
	}
	if hbAck.RequestID != "hb-1" {
		t.Errorf("request_id echo got %q want hb-1", hbAck.RequestID)
	}
}

func TestToolCallRoutingEndToEnd(t *testing.T) {
	addr, _, authInst := startTestServer(t)

	// Connect extension.
	extConn, extReader := dialConn(t, addr)
	sendJSON(t, extConn, ipc.HelloMessage{RequestID: "h", InstanceID: "inst-e2e", ProcessID: 1, ExtensionVersion: "1.0", Type: "hello", ProtocolVersion: 1})
	var hAck ipc.HelloAckMessage
	recvMsg(t, extReader, &hAck)
	sendJSON(t, extConn, ipc.RegisterInstanceMessage{RequestID: "r", InstanceID: "inst-e2e", ProcessID: 1, ExtensionVersion: "1.0", AuthToken: authInst.token, Type: "register_instance", ProtocolVersion: 1})
	var rAck ipc.RegisterAckMessage
	recvMsg(t, extReader, &rAck)

	// Connect bridge.
	bridgeConn, bridgeReader := dialConn(t, addr)
	sendJSON(t, bridgeConn, ipc.BridgeRegisterMessage{RequestID: "br", BridgeID: "bridge-e2e", ProcessID: 2, BridgeVersion: "1.0", AuthToken: authInst.token, Type: "bridge_register", ProtocolVersion: 1})
	var brAck ipc.BridgeRegisterAckMessage
	recvMsg(t, bridgeReader, &brAck)

	// Bridge sends tool_call.
	sendJSON(t, bridgeConn, ipc.ToolCallMessage{
		RequestID:          "tc-1",
		BridgeConnectionID: brAck.BridgeConnectionID,
		ToolName:           "list_capture_events",
		Arguments:          map[string]interface{}{"limit": 10},
		Type:               "tool_call",
	})

	// Extension should receive inspect_capture.
	extConn.SetReadDeadline(time.Now().Add(3 * time.Second))
	var inspectReq ipc.InspectCaptureRequestMessage
	recvMsg(t, extReader, &inspectReq)
	if inspectReq.Type != "inspect_capture" {
		t.Fatalf("expected inspect_capture, got %q", inspectReq.Type)
	}
	if inspectReq.Operation != "list_events" {
		t.Errorf("operation got %q want list_events", inspectReq.Operation)
	}
	if inspectReq.RequestID != "tc-1" {
		t.Errorf("request_id propagated incorrectly")
	}

	// Extension sends inspect_capture_result back.
	sendJSON(t, extConn, ipc.InspectCaptureResultMessage{
		RequestID: inspectReq.RequestID,
		Operation: inspectReq.Operation,
		Result:    map[string]interface{}{"events": []interface{}{}},
		Error:     "",
		Type:      "inspect_capture_result",
	})

	// Bridge receives tool_result.
	bridgeConn.SetReadDeadline(time.Now().Add(3 * time.Second))
	var toolResult ipc.ToolResultMessage
	recvMsg(t, bridgeReader, &toolResult)
	if toolResult.Type != "tool_result" {
		t.Fatalf("expected tool_result, got %q", toolResult.Type)
	}
	if toolResult.RequestID != "tc-1" {
		t.Errorf("request_id echo got %q want tc-1", toolResult.RequestID)
	}
	if toolResult.ToolName != "list_capture_events" {
		t.Errorf("tool_name got %q", toolResult.ToolName)
	}
	if toolResult.Error != "" {
		t.Errorf("unexpected error: %s", toolResult.Error)
	}
}

func TestServerStatusTool(t *testing.T) {
	addr, _, authInst := startTestServer(t)
	bridgeConn, bridgeReader := dialConn(t, addr)

	sendJSON(t, bridgeConn, ipc.BridgeRegisterMessage{RequestID: "br", BridgeID: "b", ProcessID: 1, AuthToken: authInst.token, Type: "bridge_register", ProtocolVersion: 1})
	var brAck ipc.BridgeRegisterAckMessage
	recvMsg(t, bridgeReader, &brAck)

	sendJSON(t, bridgeConn, ipc.ToolCallMessage{
		RequestID: "ss-1",
		ToolName:  "server_status",
		Arguments: map[string]interface{}{},
		Type:      "tool_call",
	})

	bridgeConn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var result ipc.ToolResultMessage
	recvMsg(t, bridgeReader, &result)
	if result.Error != "" {
		t.Errorf("server_status returned error: %s", result.Error)
	}
	m, _ := result.Result.(map[string]interface{})
	if m == nil {
		t.Fatal("expected result map")
	}
	if m["server_name"] != config.ServiceName {
		t.Errorf("server_name got %v", m["server_name"])
	}
}

func TestTwoBridgesConcurrent(t *testing.T) {
	addr, _, authInst := startTestServer(t)

	// One extension.
	extConn, extReader := dialConn(t, addr)
	sendJSON(t, extConn, ipc.HelloMessage{RequestID: "h", InstanceID: "inst-mc", ProcessID: 1, ExtensionVersion: "1.0", Type: "hello", ProtocolVersion: 1})
	var hAck ipc.HelloAckMessage
	recvMsg(t, extReader, &hAck)
	sendJSON(t, extConn, ipc.RegisterInstanceMessage{RequestID: "r", InstanceID: "inst-mc", ProcessID: 1, ExtensionVersion: "1.0", AuthToken: authInst.token, Type: "register_instance", ProtocolVersion: 1})
	var rAck ipc.RegisterAckMessage
	recvMsg(t, extReader, &rAck)

	// Bridge A.
	connA, readerA := dialConn(t, addr)
	sendJSON(t, connA, ipc.BridgeRegisterMessage{RequestID: "bra", BridgeID: "bridge-A", ProcessID: 2, AuthToken: authInst.token, Type: "bridge_register", ProtocolVersion: 1})
	var ackA ipc.BridgeRegisterAckMessage
	recvMsg(t, readerA, &ackA)

	// Bridge B.
	connB, readerB := dialConn(t, addr)
	sendJSON(t, connB, ipc.BridgeRegisterMessage{RequestID: "brb", BridgeID: "bridge-B", ProcessID: 3, AuthToken: authInst.token, Type: "bridge_register", ProtocolVersion: 1})
	var ackB ipc.BridgeRegisterAckMessage
	recvMsg(t, readerB, &ackB)

	// Both send one tool call.
	sendJSON(t, connA, ipc.ToolCallMessage{RequestID: "tc-A", ToolName: "get_selected_event", Arguments: map[string]interface{}{}, Type: "tool_call"})
	sendJSON(t, connB, ipc.ToolCallMessage{RequestID: "tc-B", ToolName: "get_selected_event", Arguments: map[string]interface{}{}, Type: "tool_call"})

	// Extension receives two inspect_capture messages; respond to both.
	extConn.SetReadDeadline(time.Now().Add(3 * time.Second))
	responses := map[string]string{}
	for i := 0; i < 2; i++ {
		var req ipc.InspectCaptureRequestMessage
		recvMsg(t, extReader, &req)
		// Record which bridge ID this requestID belongs to.
		if strings.HasSuffix(req.RequestID, "A") {
			responses[req.RequestID] = "A"
		} else {
			responses[req.RequestID] = "B"
		}
		sendJSON(t, extConn, ipc.InspectCaptureResultMessage{
			RequestID: req.RequestID,
			Operation: req.Operation,
			Result:    map[string]interface{}{"from": responses[req.RequestID]},
			Type:      "inspect_capture_result",
		})
	}

	// Each bridge receives only its own result.
	var mu sync.Mutex
	got := map[string]ipc.ToolResultMessage{}
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		connA.SetReadDeadline(time.Now().Add(3 * time.Second))
		var r ipc.ToolResultMessage
		recvMsg(t, readerA, &r)
		mu.Lock()
		got["A"] = r
		mu.Unlock()
	}()
	go func() {
		defer wg.Done()
		connB.SetReadDeadline(time.Now().Add(3 * time.Second))
		var r ipc.ToolResultMessage
		recvMsg(t, readerB, &r)
		mu.Lock()
		got["B"] = r
		mu.Unlock()
	}()
	wg.Wait()

	if got["A"].RequestID != "tc-A" {
		t.Errorf("bridge A got request_id %q want tc-A", got["A"].RequestID)
	}
	if got["B"].RequestID != "tc-B" {
		t.Errorf("bridge B got request_id %q want tc-B", got["B"].RequestID)
	}
}

func TestUnknownMessageType(t *testing.T) {
	addr, _, _ := startTestServer(t)
	conn, r := dialConn(t, addr)

	// Send an entirely unknown message type.
	raw := fmt.Sprintf(`{"type":"unknown_type_xyz","request_id":"uq-1"}`)
	conn.Write(append([]byte(raw), '\n'))

	conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var errMsg ipc.ErrorMessage
	recvMsg(t, r, &errMsg)
	if errMsg.Type != "error" {
		t.Errorf("expected error message, got %q", errMsg.Type)
	}
	if errMsg.Code != "unexpected_message" {
		t.Errorf("expected unexpected_message code, got %q", errMsg.Code)
	}
}

func TestMalformedJSON(t *testing.T) {
	addr, _, _ := startTestServer(t)
	conn, r := dialConn(t, addr)

	conn.Write([]byte("not valid json\n"))

	conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var errMsg ipc.ErrorMessage
	recvMsg(t, r, &errMsg)
	if errMsg.Code != "parse_error" {
		t.Errorf("expected parse_error, got %q", errMsg.Code)
	}
}
