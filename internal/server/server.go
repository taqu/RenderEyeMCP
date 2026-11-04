// Package server implements the TCP server for the rendereye-ipc daemon.
package server

import (
	"context"
	"crypto/rand"
	"database/sql"
	"fmt"
	"log/slog"
	"net"
	"os"
	"sync"
	"sync/atomic"

	"github.com/taqu/rendereye-mcp/internal/captures"
	"github.com/taqu/rendereye-mcp/internal/config"
	"github.com/taqu/rendereye-mcp/internal/instances"
	"github.com/taqu/rendereye-mcp/internal/operations"
	"github.com/taqu/rendereye-mcp/internal/sessions"
	"github.com/taqu/rendereye-mcp/internal/store"
)

// maxConnections is the maximum number of concurrent client connections.
const maxConnections = 64

// Server manages the TCP listener and connection lifecycle.
type Server struct {
	cfg    *config.Config
	router *Router
	auth   *Auth

	db       *sql.DB
	registry *captures.Registry
	sessions *sessions.Manager

	lnMu     sync.Mutex
	listener net.Listener
	connWG   sync.WaitGroup
	// connCount tracks active connections for limit enforcement.
	connCount atomic.Int32
}

// New creates a Server with a freshly generated auth token and service ID.
//
// It opens the capture/session database and builds the capture registry,
// instance manager and session manager.  If the database cannot be opened the
// service still starts; registry and session tools then report themselves
// unavailable instead of failing every call.
func New(cfg *config.Config) (*Server, string) {
	auth := NewAuth()
	serviceInstanceID := generateInstanceID()
	s := &Server{cfg: cfg, auth: auth}

	svc := &Services{RenderdocExe: cfg.RenderdocExe, Instances: instances.NewManager()}
	if db, err := store.Open(cfg.StoragePath); err != nil {
		slog.Error("capture/session storage unavailable; registry and session tools disabled",
			"path", cfg.StoragePath, "err", err)
	} else {
		s.db = db
		s.registry = captures.NewRegistry(cfg.Capture, captures.NewStorage(db))
		s.sessions = sessions.NewManager(sessions.NewStorage(db), svc.Instances, s.registry,
			operations.NewTracker(), cfg.RenderdocExe)
		svc.Captures = s.registry
		svc.Sessions = s.sessions
	}
	s.router = NewRouterWithServices(serviceInstanceID, auth, svc)
	return s, serviceInstanceID
}

// Start binds the TCP listener, writes the ready file, and begins accepting
// connections.  It blocks until ctx is cancelled.
func (s *Server) Start(ctx context.Context) error {
	addr := fmt.Sprintf("%s:%d", s.cfg.IPCHost, s.cfg.IPCPort)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("listen %s: %w", addr, err)
	}
	s.lnMu.Lock()
	s.listener = ln
	s.lnMu.Unlock()
	slog.Info("IPC listener ready", "addr", addr)

	if s.registry != nil {
		s.registry.Start()
	}
	if s.sessions != nil {
		rec, recov, lost := s.sessions.Reconcile()
		slog.Info("sessions reconciled", "reconciled", rec, "recovered", recov, "lost", lost)
	}

	WriteReadyFile(s.router.serviceInstanceID, s.cfg.IPCHost, s.cfg.IPCPort, os.Getpid())

	go s.acceptLoop(ctx, ln)

	<-ctx.Done()
	return nil
}

// Stop closes the listener, waits for all connections to finish, and stops
// Router background goroutines.
func (s *Server) Stop() {
	slog.Info("server stopping")
	RemoveReadyFile()
	s.auth.Cleanup()
	if s.listener != nil {
		s.listener.Close()
	}
	s.router.Close()
	s.connWG.Wait()
	if s.registry != nil {
		s.registry.Stop()
	}
	if s.db != nil {
		s.db.Close()
	}
	slog.Info("server stopped")
}

// listenerAddr returns the bound address once Start is listening ("" before).
func (s *Server) listenerAddr() string {
	s.lnMu.Lock()
	defer s.lnMu.Unlock()
	if s.listener == nil {
		return ""
	}
	return s.listener.Addr().String()
}

// acceptLoop accepts new TCP connections and spawns a handler goroutine for each.
func (s *Server) acceptLoop(ctx context.Context, ln net.Listener) {
	for {
		conn, err := ln.Accept()
		if err != nil {
			select {
			case <-ctx.Done():
				return
			default:
				if !isClosedConn(err) {
					slog.Warn("accept error", "err", err)
				}
				return
			}
		}

		if int(s.connCount.Load()) >= maxConnections {
			slog.Warn("connection limit reached; rejecting client", "limit", maxConnections)
			conn.Close()
			continue
		}

		s.connCount.Add(1)
		s.connWG.Add(1)
		go func(c net.Conn) {
			defer s.connCount.Add(-1)
			defer s.connWG.Done()
			h := newConnHandler(c, s.router, s.auth)
			h.Run(ctx)
		}(conn)
	}
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

func generateInstanceID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "00000000-0000-0000-0000-000000000000"
	}
	// Format as UUID v4.
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

func newUUID() string {
	return generateInstanceID()
}

func currentPID() int {
	return os.Getpid()
}
