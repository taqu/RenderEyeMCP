package ipc

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fixture is the schema of files in tests/protocol/fixtures/**/*.json.
type fixture struct {
	Category    string                 `json:"category"`
	Description string                 `json:"description"`
	Wire        string                 `json:"wire"`
	Fields      map[string]interface{} `json:"fields"`
}

// fixtureDir returns the path to the golden fixtures relative to this test file.
// We walk up from the package directory (internal/ipc) to the repo root.
func fixtureDir(t *testing.T) string {
	t.Helper()
	// __file__ analogue: find the module root by locating go.mod
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			break
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("could not find go.mod")
		}
		dir = parent
	}
	return filepath.Join(dir, "tests", "protocol", "fixtures")
}

// loadFixtures returns all fixture files found under base.
func loadFixtures(t *testing.T, base string) []fixture {
	t.Helper()
	var fixtures []fixture
	err := filepath.Walk(base, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() || !strings.HasSuffix(path, ".json") {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var f fixture
		if err := json.Unmarshal(data, &f); err != nil {
			t.Logf("skipping invalid fixture %s: %v", path, err)
			return nil
		}
		if f.Wire != "" {
			fixtures = append(fixtures, f)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return fixtures
}

// TestFixtureWireDeserialization verifies that every golden wire string can be
// parsed by the Go framing layer and that the "type" field survives the round-trip.
func TestFixtureWireDeserialization(t *testing.T) {
	base := fixtureDir(t)
	fixtures := loadFixtures(t, base)
	if len(fixtures) == 0 {
		t.Skip("no fixture files found")
	}

	for _, f := range fixtures {
		f := f
		t.Run(f.Description, func(t *testing.T) {
			wire := f.Wire
			// Verify the wire string is valid JSON followed by newline.
			if len(wire) == 0 || wire[len(wire)-1] != '\n' {
				t.Fatalf("wire does not end with newline: %q", wire)
			}
			jsonPart := wire[:len(wire)-1]
			var env MessageEnvelope
			if err := json.Unmarshal([]byte(jsonPart), &env); err != nil {
				t.Fatalf("cannot parse wire as JSON: %v\nwire=%q", err, wire)
			}
			if env.Type == "" {
				t.Fatalf("wire has no 'type' field: %q", wire)
			}
			// Cross-check type against fields.
			if want, ok := f.Fields["type"].(string); ok {
				if env.Type != want {
					t.Fatalf("type mismatch: got %q want %q", env.Type, want)
				}
			}
		})
	}
}

// TestFixtureFieldPresence verifies that every field listed in a fixture's
// "fields" map is present in the decoded wire bytes.
func TestFixtureFieldPresence(t *testing.T) {
	base := fixtureDir(t)
	fixtures := loadFixtures(t, base)
	if len(fixtures) == 0 {
		t.Skip("no fixture files found")
	}

	for _, f := range fixtures {
		f := f
		t.Run(f.Description, func(t *testing.T) {
			wire := f.Wire
			jsonPart := wire
			if len(jsonPart) > 0 && jsonPart[len(jsonPart)-1] == '\n' {
				jsonPart = jsonPart[:len(jsonPart)-1]
			}

			var decoded map[string]interface{}
			if err := json.Unmarshal([]byte(jsonPart), &decoded); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}

			for key := range f.Fields {
				if _, exists := decoded[key]; !exists {
					t.Errorf("field %q missing from decoded wire", key)
				}
			}
		})
	}
}

// TestProtocolVersion ensures the ProtocolVersion constant matches fixtures.
func TestProtocolVersion(t *testing.T) {
	if ProtocolVersion != 1 {
		t.Fatalf("unexpected ProtocolVersion %d (expected 1)", ProtocolVersion)
	}
}

// TestMessageEnvelopeType verifies type-routing for every known message type.
func TestMessageEnvelopeType(t *testing.T) {
	cases := []struct {
		wire    string
		wantType string
	}{
		{`{"type":"hello","request_id":"x"}`, "hello"},
		{`{"type":"hello_ack","request_id":"x"}`, "hello_ack"},
		{`{"type":"register_instance","request_id":"x"}`, "register_instance"},
		{`{"type":"register_ack","request_id":"x"}`, "register_ack"},
		{`{"type":"heartbeat","request_id":"x"}`, "heartbeat"},
		{`{"type":"heartbeat_ack","request_id":"x"}`, "heartbeat_ack"},
		{`{"type":"service_info_request","request_id":"x"}`, "service_info_request"},
		{`{"type":"service_info_response","request_id":"x"}`, "service_info_response"},
		{`{"type":"bridge_register","request_id":"x"}`, "bridge_register"},
		{`{"type":"bridge_register_ack","request_id":"x"}`, "bridge_register_ack"},
		{`{"type":"tool_call","request_id":"x"}`, "tool_call"},
		{`{"type":"tool_result","request_id":"x"}`, "tool_result"},
		{`{"type":"inspect_capture","request_id":"x"}`, "inspect_capture"},
		{`{"type":"inspect_capture_result","request_id":"x"}`, "inspect_capture_result"},
		{`{"type":"gui_state_changed"}`, "gui_state_changed"},
		{`{"type":"error","request_id":"x"}`, "error"},
		{`{"type":"goodbye"}`, "goodbye"},
	}

	for _, c := range cases {
		var env MessageEnvelope
		if err := json.Unmarshal([]byte(c.wire), &env); err != nil {
			t.Errorf("unmarshal %q: %v", c.wire, err)
			continue
		}
		if env.Type != c.wantType {
			t.Errorf("got type %q want %q for %q", env.Type, c.wantType, c.wire)
		}
	}
}
