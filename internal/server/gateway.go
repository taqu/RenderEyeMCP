package server

import (
	"context"
	"encoding/json"
	"log/slog"
	"time"

	"github.com/taqu/rendereye-mcp/internal/ipc"
	"github.com/taqu/rendereye-mcp/internal/sessions"
)

// Router implements sessions.Gateway.
var _ sessions.Gateway = (*Router)(nil)

// ExtensionForProcess returns the connected extension whose RenderDoc process
// is pid.  Managed sessions are correlated with extensions by process ID: the
// session's instance ID ("instance-NNNNNN") and the extension's instance_id
// (a UUID) are different namespaces.
func (r *Router) ExtensionForProcess(pid int) (sessions.Extension, bool) {
	if pid <= 0 {
		return sessions.Extension{}, false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, e := range r.extensions {
		if e.connected && e.processID == pid {
			return sessions.Extension{
				ConnID: e.connID, InstanceID: e.instanceID, ProcessID: e.processID,
				CaptureLoaded: e.capLoaded, CapturePath: e.capPath,
			}, true
		}
	}
	return sessions.Extension{}, false
}

// ExecuteGuiCommand sends execute_gui_command to the extension connID and
// waits for its gui_command_result.
func (r *Router) ExecuteGuiCommand(ctx context.Context, connID, command string, params map[string]interface{}, timeout time.Duration) (sessions.GuiCommandResult, string) {
	r.mu.Lock()
	ext := r.extensions[connID]
	r.mu.Unlock()
	if ext == nil {
		return sessions.GuiCommandResult{}, "no_connection"
	}
	if params == nil {
		params = map[string]interface{}{}
	}
	rep := r.request(ctx, ext, "", "execute_gui_command:"+command, timeout, func(id string) []byte {
		data, err := json.Marshal(ipc.ExecuteGuiCommandMessage{RequestID: id, Command: command, Params: params, Type: "execute_gui_command"})
		if err != nil {
			slog.Error("failed to marshal execute_gui_command", "err", err)
			return nil
		}
		return append(data, '\n')
	})
	if rep.failure != "" {
		return sessions.GuiCommandResult{}, rep.failure
	}
	if rep.gui == nil {
		return sessions.GuiCommandResult{}, failInvalidReply
	}
	return sessions.GuiCommandResult{Success: rep.gui.Success, Outcome: rep.gui.Outcome, Error: rep.gui.Error}, ""
}

// inspect issues one inspect_capture request on behalf of a composite tool
// and normalises the outcome: on success it returns the result map; otherwise
// it returns nil and the structured error to report.
func (r *Router) inspect(ctx context.Context, ext *extState, operation string, params map[string]interface{}, timeout time.Duration) (map[string]interface{}, map[string]interface{}) {
	rep := r.callExtension(ctx, ext, "", operation, params, timeout)
	if rep.failure != "" {
		return nil, map[string]interface{}{"error": rep.failure, "message": failureMessage(rep.failure, operation, r.timeout(timeout))}
	}
	if rep.errStr != "" {
		return nil, map[string]interface{}{"error": "extension_error", "message": rep.errStr, "operation": operation}
	}
	m, ok := rep.result.(map[string]interface{})
	if !ok {
		return nil, map[string]interface{}{"error": failInvalidReply, "message": "extension returned a non-object result", "operation": operation}
	}
	if _, isErr := m["error"]; isErr {
		return nil, m
	}
	return m, nil
}
