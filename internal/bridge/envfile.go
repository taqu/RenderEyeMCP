package bridge

import (
	"bufio"
	"log/slog"
	"os"
	"strings"
)

// LoadEnvFile loads environment variables from a .env-style file.
// It checks RENDEREYE_ENV_FILE first; if not set, it tries "./env".
// Lines starting with '#' are comments. Existing env vars are NOT overridden.
func LoadEnvFile() {
	path := os.Getenv("RENDEREYE_ENV_FILE")
	if path == "" {
		path = ".env"
	}

	f, err := os.Open(path)
	if err != nil {
		// File not found is expected; log at debug level.
		slog.Debug("env file not loaded", "path", path, "reason", err)
		return
	}
	defer f.Close()

	slog.Debug("loading env file", "path", path)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])
		if key == "" {
			continue
		}
		// Only set if not already present.
		if os.Getenv(key) == "" {
			if err := os.Setenv(key, value); err != nil {
				slog.Warn("failed to set env var from file", "key", key, "err", err)
			}
		}
	}
}
