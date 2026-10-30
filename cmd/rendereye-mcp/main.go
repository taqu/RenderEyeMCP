// rendereye-mcp is the unified Go executable for RenderEyeMCP.
//
// Operating modes:
//
//	rendereye-mcp              — MCP Bridge (default; used by coding agents)
//	rendereye-mcp service      — Shared IPC Service
//	rendereye-mcp version      — Print version information
//	rendereye-mcp help         — Print usage
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

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/taqu/rendereye-mcp/internal/bridge"
	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/lifecycle"
	"github.com/taqu/rendereye-mcp/internal/server"
	"github.com/taqu/rendereye-mcp/internal/version"
)

func main() {
	subcommand := ""
	remaining := os.Args[1:]
	if len(remaining) > 0 {
		subcommand = remaining[0]
		remaining = remaining[1:]
	}

	switch subcommand {
	case "service":
		runService(remaining)
	case "version":
		runVersion()
	case "help", "--help", "-help", "-h":
		runHelp()
	default:
		// Unknown flag passed as first arg: treat as bridge (MCP SDK handles --help etc.)
		runBridge()
	}
}

// runBridge starts the MCP stdio server. All diagnostics go to stderr so that
// stdout remains protocol-clean for the MCP client.
func runBridge() {
	bridge.LoadEnvFile()

	cfg := config.FromEnv()
	configureLogging(cfg.LogLevel)

	slog.Info("rendereye-mcp starting (bridge mode)", "pid", os.Getpid())

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		slog.Info("received signal", "signal", sig)
		cancel()
	}()

	if err := bridge.EnsureServiceRunning(ctx, cfg); err != nil {
		slog.Warn("auto-start of IPC service failed — continuing; ensure it is started manually",
			"err", err,
		)
	}

	client := bridge.NewServiceClient(cfg.IPCHost, cfg.IPCPort)

	const maxAttempts = 3
	var connectErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		connectErr = client.Connect(ctx)
		if connectErr == nil {
			break
		}
		slog.Warn("failed to connect to IPC service",
			"attempt", attempt,
			"max", maxAttempts,
			"err", connectErr,
		)
		if attempt < maxAttempts {
			select {
			case <-ctx.Done():
				slog.Error("context cancelled during connect retry")
				os.Exit(1)
			case <-time.After(time.Second):
			}
		}
	}
	if connectErr != nil {
		slog.Error("could not connect to IPC service after retries", "err", connectErr)
		os.Exit(1)
	}

	defer func() {
		slog.Info("closing IPC client")
		client.Close()
	}()

	mcpServer := bridge.NewMCPServer(client)

	slog.Info("rendereye-mcp ready, running stdio transport")

	if err := mcpServer.Run(ctx, &mcp.StdioTransport{}); err != nil {
		if ctx.Err() == nil {
			slog.Error("MCP server exited with error", "err", err)
			os.Exit(1)
		}
	}

	slog.Info("rendereye-mcp exited cleanly")
}

// runService starts the Shared IPC Service. This is the same logic as the
// standalone rendereye-ipc binary, preserved here so a single executable
// covers both roles.
func runService(args []string) {
	fs := flag.NewFlagSet("rendereye-mcp service", flag.ExitOnError)
	flagHost := fs.String("host", "", "TCP bind host (overrides RENDEREYE_IPC_HOST)")
	flagPort := fs.Int("port", 0, "TCP port (overrides RENDEREYE_IPC_PORT)")
	flagLog := fs.String("log", "", "Log level: debug|info|warn|error")
	_ = fs.Parse(args)

	bridge.LoadEnvFile()

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

	slog.Info("rendereye-mcp starting (service mode)",
		"host", cfg.IPCHost,
		"port", cfg.IPCPort,
		"pid", os.Getpid(),
	)

	// Fast path: exit cleanly if the port is already occupied.
	if servicePortOpen(cfg.IPCHost, cfg.IPCPort) {
		slog.Info("port already in use — another service instance appears to be running; exiting",
			"addr", net.JoinHostPort(cfg.IPCHost, strconv.Itoa(cfg.IPCPort)),
		)
		os.Exit(0)
	}

	// Acquire the cross-process startup coordination lock.
	lock := lifecycle.NewServiceStartupLock(30 * time.Second)
	if err := lock.Acquire(); err != nil {
		slog.Error("failed to acquire startup lock", "err", err)
		os.Exit(1)
	}

	// Re-check after acquiring the lock.
	if servicePortOpen(cfg.IPCHost, cfg.IPCPort) {
		slog.Info("port now in use after lock acquisition — another service started; exiting")
		lock.Release()
		os.Exit(0)
	}

	svc, serviceInstanceID := server.New(cfg)
	slog.Info("service initialised",
		"instance_id", serviceInstanceID,
		"pid", os.Getpid(),
	)

	lock.Release()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		slog.Info("received signal", "signal", sig)
		cancel()
	}()

	if err := svc.Start(ctx); err != nil {
		if ctx.Err() == nil {
			slog.Error("server start failed", "err", err)
			svc.Stop()
			os.Exit(1)
		}
	}

	svc.Stop()
	slog.Info("rendereye-mcp service exited cleanly")
}

// runVersion prints version metadata to stdout and exits. This must not start
// MCP mode or produce MCP protocol output.
func runVersion() {
	fmt.Printf("rendereye-mcp %s\n", version.Version)
	fmt.Printf("  git commit : %s\n", version.GitCommit)
	fmt.Printf("  build date : %s\n", version.BuildDate)
	fmt.Printf("  ipc proto  : %s\n", "1")
}

// runHelp prints usage to stdout.
func runHelp() {
	fmt.Print(`rendereye-mcp — RenderEyeMCP unified executable

Usage:
  rendereye-mcp                Start MCP Bridge (stdio, for coding agents)
  rendereye-mcp service        Start Shared IPC Service
  rendereye-mcp version        Print version information
  rendereye-mcp help           Print this help

Environment variables:
  RENDEREYE_IPC_HOST     IPC service host (default: 127.0.0.1)
  RENDEREYE_IPC_PORT     IPC service port (default: 37020)
  RENDEREYE_LOG_LEVEL    Log level: debug|info|warn|error (default: info)
  RENDEREYE_ENV_FILE     Path to .env file (default: .env)

Service flags (rendereye-mcp service [flags]):
  -host string   TCP bind host
  -port int      TCP port
  -log  string   Log level

All log output goes to stderr. stdout is reserved for MCP protocol traffic.
`)
}

// servicePortOpen returns true if a TCP connection can be established to
// host:port within a short timeout.
func servicePortOpen(host string, port int) bool {
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

// configureLogging sets the global slog handler writing to stderr.
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
