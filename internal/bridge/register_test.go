package bridge

import (
	"context"
	"sort"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/taqu/rendereye-mcp/internal/toolspec"
)

// registeredTools lists the tools the MCP server actually exposes, via an
// in-memory MCP client session.
func registeredTools(t *testing.T) []*mcp.Tool {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	server := NewMCPServer(NewServiceClient("127.0.0.1", 1))
	st, ct := mcp.NewInMemoryTransports()
	ss, err := server.Connect(ctx, st, nil)
	if err != nil {
		t.Fatalf("server connect: %v", err)
	}
	defer ss.Close()
	cs, err := mcp.NewClient(&mcp.Implementation{Name: "test", Version: "0"}, nil).Connect(ctx, ct, nil)
	if err != nil {
		t.Fatalf("client connect: %v", err)
	}
	defer cs.Close()

	var tools []*mcp.Tool
	for tool, err := range cs.Tools(ctx, nil) {
		if err != nil {
			t.Fatalf("list tools: %v", err)
		}
		tools = append(tools, tool)
	}
	return tools
}

// TestRegisteredToolsMatchCatalog guarantees that every MCP tool the bridge
// registers has an execution path in the service catalog, and that the
// catalog lists no tool the bridge does not expose.
func TestRegisteredToolsMatchCatalog(t *testing.T) {
	tools := registeredTools(t)
	registered := make([]string, 0, len(tools))
	seen := map[string]bool{}
	for _, tool := range tools {
		if seen[tool.Name] {
			t.Errorf("tool %q registered twice", tool.Name)
		}
		seen[tool.Name] = true
		registered = append(registered, tool.Name)
		if _, ok := toolspec.Lookup(tool.Name); !ok {
			t.Errorf("tool %q is registered but has no execution path in toolspec", tool.Name)
		}
	}
	for _, name := range toolspec.Names() {
		if !seen[name] {
			t.Errorf("toolspec lists %q but the bridge does not register it", name)
		}
	}
	sort.Strings(registered)
	if len(registered) != len(toolspec.Names()) {
		t.Errorf("registered %d tools, catalog has %d", len(registered), len(toolspec.Names()))
	}
}

// TestBridgeTimeoutExceedsServiceBudget ensures the bridge never gives up
// before the service has returned its own structured timeout result.
func TestBridgeTimeoutExceedsServiceBudget(t *testing.T) {
	for _, s := range toolspec.All() {
		if bt := toolspec.BridgeTimeout(s.Name); bt <= s.Timeout {
			t.Errorf("%s: bridge timeout %s must exceed service timeout %s", s.Name, bt, s.Timeout)
		}
	}
	if got := toolspec.BridgeTimeout("collect_gpu_counters"); got < toolspec.MaxCounterRepeats*toolspec.ReplayTimeout {
		t.Errorf("collect_gpu_counters bridge timeout %s cannot cover %d replay runs", got, toolspec.MaxCounterRepeats)
	}
}
