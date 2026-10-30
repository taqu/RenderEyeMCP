package bridge

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/exec"
	"strconv"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
)

// EnsureServiceRunning checks whether the IPC service is already listening on
// cfg.IPCHost:cfg.IPCPort. If not, it launches the current executable in
// "service" mode as a detached process.
//
// If startup times out, an error is returned but the caller should log a
// warning and continue — the service may be started manually.
func EnsureServiceRunning(ctx context.Context, cfg *config.Config) error {
	if portOpen(cfg.IPCHost, cfg.IPCPort) {
		slog.Debug("IPC service already running", "host", cfg.IPCHost, "port", cfg.IPCPort)
		return nil
	}

	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("could not determine executable path: %w", err)
	}

	slog.Info("starting IPC service", "exe", exe, "mode", "service")

	// Use exec.Command (no context) so the service process is not killed when
	// the parent bridge's context is cancelled.
	cmd := exec.Command(exe, "service")
	cmd.Stdin = nil
	cmd.Stdout = nil
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = detachedSysProcAttr()

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start service process: %w", err)
	}

	slog.Debug("service process started", "pid", cmd.Process.Pid)

	// Wait up to 10 seconds for the ready file to appear.
	readyPath := config.ReadyFilePath()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(readyPath); err == nil {
			slog.Info("IPC service is ready", "ready_file", readyPath)
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(200 * time.Millisecond):
		}
	}

	return fmt.Errorf("IPC service did not become ready within 10 seconds (ready file: %s)", readyPath)
}

// portOpen returns true if a TCP connection can be established to host:port
// within a short timeout.
func portOpen(host string, port int) bool {
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}
