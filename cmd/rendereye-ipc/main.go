// rendereye-ipc is the standalone Go Shared IPC Service for RenderEyeMCP.
//
// It accepts TCP connections from Go MCP Bridges and RenderDoc Extensions,
// routes tool calls from bridges to extensions via the inspect_capture protocol,
// and returns results to the originating bridges.
//
// Usage:
//
//	rendereye-ipc [flags]
//
// Flags:
//
//	-host string   TCP bind address (default: RENDEREYE_IPC_HOST or 127.0.0.1)
//	-port int      TCP port (default: RENDEREYE_IPC_PORT or 37020)
//	-log  string   Log level: debug|info|warn|error (default: info)
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/lifecycle"
	"github.com/taqu/rendereye-mcp/internal/server"
)

func main() {
	var (
		flagHost = flag.String("host", "", "TCP bind host (overrides RENDEREYE_IPC_HOST)")
		flagPort = flag.Int("port", 0, "TCP port (overrides RENDEREYE_IPC_PORT)")
		flagLog  = flag.String("log", "", "Log level: debug|info|warn|error")
	)
	flag.Parse()

	cfg := config.FromEnv()
	if *flagHost != "" {
		cfg.IPCHost = *flagHost
	}
	if *flagPort != 0 {
		cfg.IPCPort = *flagPort
	}
	if *flagLog != "" {
		cfg.LogLevel = *flagLog
	}

	configureLogging(cfg.LogLevel)

	slog.Info("rendereye-ipc starting",
		"host", cfg.IPCHost,
		"port", cfg.IPCPort,
		"pid", os.Getpid(),
	)

	// Fast path: if the port is already occupied we assume another service is
	// running and exit cleanly rather than failing noisily.
	if portOpen(cfg.IPCHost, cfg.IPCPort) {
		slog.Info("port already in use — another service instance appears to be running; exiting",
			"addr", fmt.Sprintf("%s:%d", cfg.IPCHost, cfg.IPCPort),
		)
		os.Exit(0)
	}

	// Acquire the cross-process startup coordination lock so that concurrent
	// bridge processes don't each try to bind the port simultaneously.
	lock := lifecycle.NewServiceStartupLock(30 * time.Second)
	if err := lock.Acquire(); err != nil {
		slog.Error("failed to acquire startup lock", "err", err)
		os.Exit(1)
	}

	// Re-check after acquiring the lock — another process may have started
	// the service while we were waiting.
	if portOpen(cfg.IPCHost, cfg.IPCPort) {
		slog.Info("port now in use after lock acquisition — another service started; exiting")
		lock.Release()
		os.Exit(0)
	}

	svc, serviceInstanceID := server.New(cfg)
	slog.Info("service initialised",
		"instance_id", serviceInstanceID,
		"pid", os.Getpid(),
	)

	// Release the startup lock once we are about to bind.
	// We hold it just long enough to prevent races between concurrent starters.
	lock.Release()

	// OS signal handling.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		slog.Info("received signal", "signal", sig)
		cancel()
	}()

	// Start the server (blocks until ctx is cancelled or a fatal error occurs).
	if err := svc.Start(ctx); err != nil {
		if ctx.Err() == nil {
			// Unexpected error (e.g. port already bound by an unrecognised process).
			slog.Error("server start failed", "err", err)
			svc.Stop()
			os.Exit(1)
		}
	}

	svc.Stop()
	slog.Info("rendereye-ipc exited cleanly")
}

// portOpen returns true if a TCP connection can be established to host:port
// within a short timeout.  Used for fast pre-check before binding.
func portOpen(host string, port int) bool {
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

// configureLogging sets the global slog handler based on the log level string.
func configureLogging(level string) {
	var lvl slog.Level
	switch level {
	case "debug":
		lvl = slog.LevelDebug
	case "warn", "warning":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}
	handler := slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: lvl})
	slog.SetDefault(slog.New(handler))
}
