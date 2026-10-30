// Package ipc defines the wire protocol types for RenderEyeMCP IPC.
//
// Messages are newline-delimited JSON objects (NDJSON).  Each message has a
// "type" field that identifies its kind, and most have a "request_id" field
// for correlating requests with responses.
package ipc

// ProtocolVersion is the current IPC protocol version.
const ProtocolVersion = 1

// MaxMessageBytes is the maximum permitted serialised message size.
const MaxMessageBytes = 16 * 1024 * 1024

// MessageEnvelope is used for first-pass type detection before full decoding.
type MessageEnvelope struct {
	Type string `json:"type"`
}

// ---------------------------------------------------------------------------
// Connection / handshake messages
// ---------------------------------------------------------------------------

// HelloMessage is sent by the RenderDoc extension immediately after connecting.
type HelloMessage struct {
	RequestID        string `json:"request_id"`
	InstanceID       string `json:"instance_id"`
	ProcessID        int    `json:"process_id"`
	ExtensionVersion string `json:"extension_version"`
	Type             string `json:"type"`
	ProtocolVersion  int    `json:"protocol_version"`
}

// HelloAckMessage is the server acknowledgement of a HelloMessage.
type HelloAckMessage struct {
	RequestID       string `json:"request_id"`
	ServerVersion   string `json:"server_version"`
	Type            string `json:"type"`
	ProtocolVersion int    `json:"protocol_version"`
}

// HeartbeatMessage is a periodic keep-alive sent by the extension.
type HeartbeatMessage struct {
	RequestID string `json:"request_id"`
	Type      string `json:"type"`
}

// HeartbeatAckMessage is the server acknowledgement of a HeartbeatMessage.
type HeartbeatAckMessage struct {
	RequestID string `json:"request_id"`
	Type      string `json:"type"`
}

// GetStatusMessage requests current extension/capture status.
type GetStatusMessage struct {
	RequestID string `json:"request_id"`
	Type      string `json:"type"`
}

// StatusResponseMessage is the extension response to a GetStatusMessage.
type StatusResponseMessage struct {
	RequestID        string  `json:"request_id"`
	ProcessID        int     `json:"process_id"`
	InstanceID       string  `json:"instance_id"`
	ExtensionVersion string  `json:"extension_version"`
	CapturePath      *string `json:"capture_path"`
	Connected        bool    `json:"connected"`
	Type             string  `json:"type"`
}

// ErrorMessage is a generic error response.
type ErrorMessage struct {
	RequestID string `json:"request_id"`
	Code      string `json:"code"`
	Message   string `json:"message"`
	Type      string `json:"type"`
}

// RegisterInstanceMessage is sent by the extension to register with the server after hello.
type RegisterInstanceMessage struct {
	RequestID        string `json:"request_id"`
	InstanceID       string `json:"instance_id"`
	ProcessID        int    `json:"process_id"`
	ExtensionVersion string `json:"extension_version"`
	RenderdocVersion string `json:"renderdoc_version"`
	AuthToken        string `json:"auth_token"`
	Type             string `json:"type"`
	ProtocolVersion  int    `json:"protocol_version"`
}

// RegisterAckMessage is the server acknowledgement of a RegisterInstanceMessage.
type RegisterAckMessage struct {
	RequestID       string `json:"request_id"`
	ConnectionID    string `json:"connection_id"`
	ServerVersion   string `json:"server_version"`
	Type            string `json:"type"`
	ProtocolVersion int    `json:"protocol_version"`
}

// GoodbyeMessage is sent by either side before intentional disconnection.
type GoodbyeMessage struct {
	Reason string `json:"reason"`
	Type   string `json:"type"`
}

// ---------------------------------------------------------------------------
// GUI state messages
// ---------------------------------------------------------------------------

// GuiStateChangedMessage is pushed by the extension when GUI state changes.
type GuiStateChangedMessage struct {
	InstanceID   string  `json:"instance_id"`
	Revision     int     `json:"revision"`
	CaptureLoaded bool   `json:"capture_loaded"`
	CapturePath  *string `json:"capture_path"`
	CaptureState string  `json:"capture_state"`
	Type         string  `json:"type"`
}

// GetGuiStateMessage is sent by the server to request a GUI state snapshot.
type GetGuiStateMessage struct {
	RequestID string `json:"request_id"`
	Type      string `json:"type"`
}

// GuiStateResponseMessage is the extension response to GetGuiStateMessage.
type GuiStateResponseMessage struct {
	RequestID     string  `json:"request_id"`
	InstanceID    string  `json:"instance_id"`
	Revision      int     `json:"revision"`
	CaptureLoaded bool    `json:"capture_loaded"`
	CapturePath   *string `json:"capture_path"`
	CaptureState  string  `json:"capture_state"`
	Type          string  `json:"type"`
}

// ExecuteGuiCommandMessage requests the extension to execute a GUI command.
type ExecuteGuiCommandMessage struct {
	RequestID string                 `json:"request_id"`
	Command   string                 `json:"command"`
	Params    map[string]interface{} `json:"params"`
	Type      string                 `json:"type"`
}

// GuiCommandResultMessage reports the result of a GUI command.
type GuiCommandResultMessage struct {
	RequestID     string `json:"request_id"`
	Command       string `json:"command"`
	Success       bool   `json:"success"`
	Outcome       string `json:"outcome"`
	Error         string `json:"error"`
	StateRevision int    `json:"state_revision"`
	Type          string `json:"type"`
}

// ---------------------------------------------------------------------------
// Bridge / service messages (Phase 6)
// ---------------------------------------------------------------------------

// ServiceInfoRequestMessage is sent by a bridge client before registration.
type ServiceInfoRequestMessage struct {
	RequestID  string `json:"request_id"`
	ClientType string `json:"client_type"`
	Type       string `json:"type"`
}

// ServiceInfoResponseMessage is the service response with identity information.
type ServiceInfoResponseMessage struct {
	RequestID         string `json:"request_id"`
	ServiceName       string `json:"service_name"`
	ServiceVersion    string `json:"service_version"`
	ServicePID        int    `json:"service_pid"`
	ServiceInstanceID string `json:"service_instance_id"`
	Type              string `json:"type"`
	ProtocolVersion   int    `json:"protocol_version"`
}

// BridgeRegisterMessage is sent by the MCP bridge to register with the service.
type BridgeRegisterMessage struct {
	RequestID       string `json:"request_id"`
	BridgeID        string `json:"bridge_id"`
	ProcessID       int    `json:"process_id"`
	BridgeVersion   string `json:"bridge_version"`
	AuthToken       string `json:"auth_token"`
	Type            string `json:"type"`
	ProtocolVersion int    `json:"protocol_version"`
}

// BridgeRegisterAckMessage is the service acknowledgement of bridge registration.
type BridgeRegisterAckMessage struct {
	RequestID          string `json:"request_id"`
	BridgeConnectionID string `json:"bridge_connection_id"`
	ServiceVersion     string `json:"service_version"`
	Type               string `json:"type"`
	ProtocolVersion    int    `json:"protocol_version"`
}

// ToolCallMessage is sent by the bridge to forward an MCP tool call.
type ToolCallMessage struct {
	RequestID          string                 `json:"request_id"`
	BridgeConnectionID string                 `json:"bridge_connection_id"`
	ToolName           string                 `json:"tool_name"`
	Arguments          map[string]interface{} `json:"arguments"`
	Type               string                 `json:"type"`
}

// ToolResultMessage carries the result of a tool call back to the bridge.
type ToolResultMessage struct {
	RequestID string      `json:"request_id"`
	ToolName  string      `json:"tool_name"`
	Result    interface{} `json:"result"`
	Error     string      `json:"error"`
	Type      string      `json:"type"`
}

// ---------------------------------------------------------------------------
// Capture inspection messages (Phase 8)
// ---------------------------------------------------------------------------

// InspectCaptureRequestMessage requests capture inspection from the extension.
type InspectCaptureRequestMessage struct {
	RequestID string                 `json:"request_id"`
	Operation string                 `json:"operation"`
	Params    map[string]interface{} `json:"params"`
	Type      string                 `json:"type"`
}

// InspectCaptureResultMessage carries the inspection result from the extension.
type InspectCaptureResultMessage struct {
	RequestID string      `json:"request_id"`
	Operation string      `json:"operation"`
	Result    interface{} `json:"result"`
	Error     string      `json:"error"`
	Type      string      `json:"type"`
}
