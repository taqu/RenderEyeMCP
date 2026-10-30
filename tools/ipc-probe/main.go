// ipc-probe is a minimal Go client that verifies Go can speak the RenderEyeMCP
// IPC protocol.  It supports three modes:
//
//   - Normal mode: connects to a running service and performs the bridge handshake.
//   - Mock mode (-mock): parses mock responses without a real service.
//   - Fixture mode (-fixtures <dir>): verifies all JSON fixtures can be decoded.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	ipc "github.com/taqu/rendereye-mcp/internal/ipc"
)

// serviceReadyFile returns the path to the service ready JSON file.
func serviceReadyFile() string {
	return filepath.Join(os.TempDir(), "rendereye_mcp_service.json")
}

// tokenFile returns the path to the auth token file.
func tokenFile() string {
	return filepath.Join(os.TempDir(), "rendereye_mcp_token.txt")
}

// serviceInfo is the schema of the service ready file.
type serviceInfo struct {
	PID        int    `json:"pid"`
	InstanceID string `json:"instance_id"`
	Port       int    `json:"port"`
	Host       string `json:"host"`
}

func readServiceInfo() (*serviceInfo, error) {
	data, err := os.ReadFile(serviceReadyFile())
	if err != nil {
		return nil, fmt.Errorf("read service ready file %s: %w", serviceReadyFile(), err)
	}
	var info serviceInfo
	if err := json.Unmarshal(data, &info); err != nil {
		return nil, fmt.Errorf("parse service ready file: %w", err)
	}
	return &info, nil
}

func readToken() (string, error) {
	data, err := os.ReadFile(tokenFile())
	if err != nil {
		return "", fmt.Errorf("read token file %s: %w", tokenFile(), err)
	}
	return strings.TrimSpace(string(data)), nil
}

func runProbe(host string, port int, token string) error {
	client, err := ipc.NewClient(host, port)
	if err != nil {
		return fmt.Errorf("connect to %s:%d: %w", host, port, err)
	}
	defer client.Close()
	fmt.Printf("\u2713 Connected to %s:%d\n", host, port)

	// Step 1: service_info_request
	reqID1 := "go-probe-0000-0000-0000-000000000001"
	if err := client.Send(map[string]interface{}{
		"request_id":  reqID1,
		"client_type": "go_probe",
		"type":        "service_info_request",
	}); err != nil {
		return fmt.Errorf("send service_info_request: %w", err)
	}

	var infoResp ipc.ServiceInfoResponseMessage
	if err := client.ReceiveAs(&infoResp); err != nil {
		return fmt.Errorf("receive service_info_response: %w", err)
	}
	if infoResp.Type != "service_info_response" {
		return fmt.Errorf("expected service_info_response, got %q", infoResp.Type)
	}
	fmt.Printf("\u2713 Service: %s v%s (pid %d)\n", infoResp.ServiceName, infoResp.ServiceVersion, infoResp.ServicePID)

	// Step 2: bridge_register
	reqID2 := "go-probe-0000-0000-0000-000000000002"
	if err := client.Send(map[string]interface{}{
		"request_id":    reqID2,
		"bridge_id":     "go-probe-bridge-id",
		"process_id":    os.Getpid(),
		"bridge_version": "0.0.1",
		"auth_token":    token,
		"type":          "bridge_register",
		"protocol_version": ipc.ProtocolVersion,
	}); err != nil {
		return fmt.Errorf("send bridge_register: %w", err)
	}

	var ack ipc.BridgeRegisterAckMessage
	if err := client.ReceiveAs(&ack); err != nil {
		return fmt.Errorf("receive bridge_register_ack: %w", err)
	}
	if ack.Type == "error" {
		var errMsg ipc.ErrorMessage
		// Re-read raw for cleaner error
		return fmt.Errorf("bridge registration rejected (code=%s)", errMsg.Code)
	}
	if ack.Type != "bridge_register_ack" {
		return fmt.Errorf("expected bridge_register_ack, got %q", ack.Type)
	}
	fmt.Printf("\u2713 Registered as bridge: connection_id=%s\n", ack.BridgeConnectionID)

	// Step 3: goodbye
	reqID3 := "go-probe-0000-0000-0000-000000000003"
	_ = reqID3
	if err := client.Send(map[string]interface{}{
		"reason": "probe_complete",
		"type":   "goodbye",
	}); err != nil {
		return fmt.Errorf("send goodbye: %w", err)
	}
	fmt.Println("\u2713 Goodbye sent")

	return nil
}

func runMock() error {
	fmt.Println("Running in mock mode \u2014 no real service required")

	// Verify we can build and parse mock responses.
	mockServiceInfoResp := []byte(`{"request_id":"r1","service_name":"RenderEyeMCP","service_version":"1.0.0","service_pid":12345,"service_instance_id":"mock-inst","type":"service_info_response","protocol_version":1}` + "\n")

	var infoResp ipc.ServiceInfoResponseMessage
	if err := json.Unmarshal(mockServiceInfoResp, &infoResp); err != nil {
		return fmt.Errorf("parse mock service_info_response: %w", err)
	}
	fmt.Printf("  Parsed service_info_response: name=%s version=%s pid=%d\n",
		infoResp.ServiceName, infoResp.ServiceVersion, infoResp.ServicePID)

	mockAck := []byte(`{"request_id":"r2","bridge_connection_id":"mock-conn-123","service_version":"1.0.0","type":"bridge_register_ack","protocol_version":1}` + "\n")
	var ack ipc.BridgeRegisterAckMessage
	if err := json.Unmarshal(mockAck, &ack); err != nil {
		return fmt.Errorf("parse mock bridge_register_ack: %w", err)
	}
	fmt.Printf("  Parsed bridge_register_ack: bridge_connection_id=%s\n", ack.BridgeConnectionID)

	fmt.Println("\u2713 Mock mode: all types parse correctly")
	return nil
}

func main() {
	mockMode := flag.Bool("mock", false, "Run in mock mode without a real service")
	fixturesDir := flag.String("fixtures", "", "Path to fixtures directory to verify")
	flag.Parse()

	if *mockMode {
		if err := runMock(); err != nil {
			fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
			os.Exit(1)
		}
		return
	}

	if *fixturesDir != "" {
		if err := runFixtureCheck(*fixturesDir); err != nil {
			fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
			os.Exit(1)
		}
		return
	}

	// Normal mode: connect to the running service.
	info, err := readServiceInfo()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		fmt.Fprintln(os.Stderr, "Is the RenderEyeMCP service running?")
		os.Exit(1)
	}

	token, err := readToken()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}

	if err := runProbe(info.Host, info.Port, token); err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}
}
