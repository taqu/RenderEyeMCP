package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	ipc "github.com/taqu/rendereye-mcp/internal/ipc"
)

// fixtureFile is the schema of a golden fixture JSON file.
type fixtureFile struct {
	Category    string                 `json:"category"`
	Description string                 `json:"description"`
	Wire        string                 `json:"wire"`
	Fields      map[string]interface{} `json:"fields"`
}

// decodeByType attempts to unmarshal wire bytes into the correct Go struct based
// on the message type field.  Returns the decoded struct as interface{} and a
// string representation of the type field found.
func decodeByType(wire []byte) (interface{}, string, error) {
	// First pass: detect type
	var env ipc.MessageEnvelope
	if err := json.Unmarshal(wire, &env); err != nil {
		return nil, "", fmt.Errorf("unmarshal envelope: %w", err)
	}

	var target interface{}
	switch env.Type {
	case "hello":
		target = new(ipc.HelloMessage)
	case "hello_ack":
		target = new(ipc.HelloAckMessage)
	case "heartbeat":
		target = new(ipc.HeartbeatMessage)
	case "heartbeat_ack":
		target = new(ipc.HeartbeatAckMessage)
	case "get_status":
		target = new(ipc.GetStatusMessage)
	case "status_response":
		target = new(ipc.StatusResponseMessage)
	case "error":
		target = new(ipc.ErrorMessage)
	case "register_instance":
		target = new(ipc.RegisterInstanceMessage)
	case "register_ack":
		target = new(ipc.RegisterAckMessage)
	case "gui_state_changed":
		target = new(ipc.GuiStateChangedMessage)
	case "get_gui_state":
		target = new(ipc.GetGuiStateMessage)
	case "gui_state_response":
		target = new(ipc.GuiStateResponseMessage)
	case "execute_gui_command":
		target = new(ipc.ExecuteGuiCommandMessage)
	case "gui_command_result":
		target = new(ipc.GuiCommandResultMessage)
	case "goodbye":
		target = new(ipc.GoodbyeMessage)
	case "service_info_request":
		target = new(ipc.ServiceInfoRequestMessage)
	case "service_info_response":
		target = new(ipc.ServiceInfoResponseMessage)
	case "bridge_register":
		target = new(ipc.BridgeRegisterMessage)
	case "bridge_register_ack":
		target = new(ipc.BridgeRegisterAckMessage)
	case "tool_call":
		target = new(ipc.ToolCallMessage)
	case "tool_result":
		target = new(ipc.ToolResultMessage)
	case "inspect_capture":
		target = new(ipc.InspectCaptureRequestMessage)
	case "inspect_capture_result":
		target = new(ipc.InspectCaptureResultMessage)
	default:
		return nil, env.Type, fmt.Errorf("unknown message type: %q", env.Type)
	}

	if err := json.Unmarshal(wire, target); err != nil {
		return nil, env.Type, fmt.Errorf("unmarshal %q: %w", env.Type, err)
	}
	return target, env.Type, nil
}

// runFixtureCheck walks dir recursively, loading every .json file as a fixture
// and verifying its wire field can be decoded by Go's json package.
func runFixtureCheck(dir string) error {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return fmt.Errorf("resolve fixtures dir %s: %w", dir, err)
	}

	fmt.Printf("Checking fixtures in %s\n", abs)

	var total, passed, failed int

	err = filepath.WalkDir(abs, func(path string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() || !strings.HasSuffix(path, ".json") {
			return nil
		}

		total++
		rel, _ := filepath.Rel(abs, path)

		data, readErr := os.ReadFile(path)
		if readErr != nil {
			fmt.Printf("  FAIL %s: read error: %v\n", rel, readErr)
			failed++
			return nil
		}

		var fx fixtureFile
		if jsonErr := json.Unmarshal(data, &fx); jsonErr != nil {
			fmt.Printf("  FAIL %s: parse fixture: %v\n", rel, jsonErr)
			failed++
			return nil
		}

		// Remove trailing newline from wire for json.Unmarshal
		wire := strings.TrimRight(fx.Wire, "\n")

		_, msgType, decErr := decodeByType([]byte(wire))
		if decErr != nil {
			fmt.Printf("  FAIL %s: decode wire (type=%s): %v\n", rel, msgType, decErr)
			failed++
			return nil
		}

		fmt.Printf("  OK   %s (type=%s)\n", rel, msgType)
		passed++
		return nil
	})

	if err != nil {
		return fmt.Errorf("walk fixtures: %w", err)
	}

	fmt.Printf("\nResults: %d/%d passed", passed, total)
	if failed > 0 {
		fmt.Printf(", %d FAILED", failed)
	}
	fmt.Println()

	if failed > 0 {
		return fmt.Errorf("%d fixture(s) failed", failed)
	}
	fmt.Println("\u2713 All fixtures verified")
	return nil
}
