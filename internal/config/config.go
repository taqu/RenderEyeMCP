// Package config loads runtime configuration for the rendereye-ipc service.
package config

import (
	"os"
	"path/filepath"
	"strconv"
)

const (
	DefaultHost = "127.0.0.1"
	DefaultPort = 37020
	ServiceName = "RenderEyeMCP"
	// GoServiceVersion is reported in service_info_response and hello_ack.
	GoServiceVersion = "1.0.0-go"
)

// Config holds resolved runtime settings.
type Config struct {
	IPCHost  string
	IPCPort  int
	LogLevel string
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
		IPCHost:  host,
		IPCPort:  port,
		LogLevel: getEnv("RENDEREYE_LOG_LEVEL", "info"),
	}
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
