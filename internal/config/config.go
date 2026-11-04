// Package config loads runtime configuration for the rendereye-ipc service.
package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	DefaultHost = "127.0.0.1"
	DefaultPort = 37020
	ServiceName = "RenderEyeMCP"
	// GoServiceVersion is reported in service_info_response and hello_ack.
	GoServiceVersion = "1.0.0-go"
)

// CaptureDirectory is one watched capture folder.
type CaptureDirectory struct {
	Path      string
	Recursive bool
}

// CaptureConfig configures the capture-file registry.
type CaptureConfig struct {
	Enabled           bool
	ScanInterval      time.Duration
	StabilityDuration time.Duration
	MinFileSize       int64
	Directories       []CaptureDirectory
}

// Config holds resolved runtime settings.
type Config struct {
	IPCHost  string
	IPCPort  int
	LogLevel string

	// RenderdocExe is the explicit qrenderdoc executable; empty probes the
	// standard install locations.
	RenderdocExe string
	// StoragePath is the SQLite database holding capture and session records.
	StoragePath string
	// Capture configures the capture-file registry.
	Capture CaptureConfig
}

// FromEnv builds a Config from environment variables, falling back to defaults.
func FromEnv() *Config {
	host := getEnv("RENDEREYE_IPC_HOST", DefaultHost)
	if host == "0.0.0.0" {
		// Safety: never expose IPC publicly.
		host = DefaultHost
	}
	portStr := getEnv("RENDEREYE_IPC_PORT", strconv.Itoa(DefaultPort))
	port, err := strconv.Atoi(portStr)
	if err != nil || port <= 0 || port > 65535 {
		port = DefaultPort
	}
	return &Config{
		IPCHost:      host,
		IPCPort:      port,
		LogLevel:     getEnv("RENDEREYE_LOG_LEVEL", "info"),
		RenderdocExe: os.Getenv("RENDEREYE_RENDERDOC_EXE"),
		StoragePath:  getEnv("RENDEREYE_STORAGE_PATH", DefaultStoragePath()),
		Capture:      captureFromEnv(),
	}
}

// DefaultCaptureConfig returns the registry defaults (no watched folders).
func DefaultCaptureConfig() CaptureConfig {
	return CaptureConfig{
		Enabled:           true,
		ScanInterval:      10 * time.Second,
		StabilityDuration: 2 * time.Second,
		MinFileSize:       4,
	}
}

func captureFromEnv() CaptureConfig {
	c := DefaultCaptureConfig()
	if v := os.Getenv("RENDEREYE_CAPTURE_ENABLED"); v != "" {
		switch strings.ToLower(strings.TrimSpace(v)) {
		case "0", "false", "no", "off":
			c.Enabled = false
		}
	}
	if d, ok := envSeconds("RENDEREYE_CAPTURE_SCAN_INTERVAL"); ok && d > 0 {
		c.ScanInterval = d
	}
	if d, ok := envSeconds("RENDEREYE_CAPTURE_STABILITY_SECONDS"); ok && d >= 0 {
		c.StabilityDuration = d
	}
	recursive := false
	if v := strings.ToLower(strings.TrimSpace(os.Getenv("RENDEREYE_CAPTURE_RECURSIVE"))); v == "1" || v == "true" || v == "yes" {
		recursive = true
	}
	// os.PathListSeparator: ';' on Windows (drive letters contain ':'), ':' elsewhere.
	for _, p := range strings.Split(os.Getenv("RENDEREYE_CAPTURE_DIRS"), string(os.PathListSeparator)) {
		if p = strings.TrimSpace(p); p != "" {
			c.Directories = append(c.Directories, CaptureDirectory{Path: p, Recursive: recursive})
		}
	}
	return c
}

func envSeconds(key string) (time.Duration, bool) {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return 0, false
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return 0, false
	}
	return time.Duration(f * float64(time.Second)), true
}

// DefaultStoragePath is %APPDATA%/rendereye_mcp/captures.db on Windows (the
// same file the former Python service used) and the user config dir elsewhere.
func DefaultStoragePath() string {
	base := os.Getenv("APPDATA")
	if base == "" {
		if d, err := os.UserConfigDir(); err == nil {
			base = d
		} else if h, err := os.UserHomeDir(); err == nil {
			base = h
		} else {
			base = tempDir()
		}
	}
	return filepath.Join(base, "rendereye_mcp", "captures.db")
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// tempDir returns the platform temp directory, honouring TEMP / TMP on Windows.
func tempDir() string {
	if d := os.Getenv("TEMP"); d != "" {
		return d
	}
	if d := os.Getenv("TMP"); d != "" {
		return d
	}
	return os.TempDir()
}

// TokenPath is the file where the auth token is stored for clients to read.
func TokenPath() string {
	return filepath.Join(tempDir(), "rendereye_mcp_token.txt")
}

// ReadyFilePath is the file written once the service is ready to accept connections.
func ReadyFilePath() string {
	return filepath.Join(tempDir(), "rendereye_mcp_service.json")
}

// LockFilePath is used for the Unix flock startup-coordination lock.
func LockFilePath() string {
	return filepath.Join(tempDir(), "rendereye_mcp_startup.lock")
}
