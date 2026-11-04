package toolspec

import (
	"os"
	"path/filepath"
	"regexp"
	"testing"
)

func TestCatalogEntriesAreWellFormed(t *testing.T) {
	for _, s := range All() {
		switch s.Route {
		case RouteService:
			if s.Operation != "" {
				t.Errorf("%s: service tools must not name an extension operation", s.Name)
			}
		case RouteExtension:
			if s.Operation == "" {
				t.Errorf("%s: extension tools need an operation", s.Name)
			}
		default:
			t.Errorf("%s: invalid route %v", s.Name, s.Route)
		}
		if s.Timeout <= 0 {
			t.Errorf("%s: timeout must be positive", s.Name)
		}
	}
}

// TestExtensionImplementsOperations checks every inspect_capture operation the
// Go service can send against the RenderDoc extension's dispatcher, so a
// forwarded tool can never reach an unsupported_operation branch.
func TestExtensionImplementsOperations(t *testing.T) {
	src, err := os.ReadFile(filepath.Join("..", "..", "extensions", "rendereye", "gui_context.py"))
	if err != nil {
		t.Fatalf("read extension source: %v", err)
	}
	implemented := map[string]bool{}
	for _, m := range regexp.MustCompile(`operation == "([a-z_]+)"`).FindAllStringSubmatch(string(src), -1) {
		implemented[m[1]] = true
	}
	if len(implemented) == 0 {
		t.Fatal("no operations found in gui_context.py; has the dispatcher changed shape?")
	}
	for _, op := range ExtensionOperations() {
		if !implemented[op] {
			t.Errorf("extension does not implement operation %q", op)
		}
	}
}
