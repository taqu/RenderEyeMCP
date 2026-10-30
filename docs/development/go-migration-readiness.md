# Go Migration Readiness (Phase 17)

## Phase 17 Migration Plan Summary

Phase 17 will rewrite the Shared IPC Service from Python/asyncio to Go.  The MCP Bridge and RenderDoc Extension (C++) are out of scope for Phase 17.  The Go service must be wire-compatible with the existing Python clients: zero changes to extensions or bridges.

## Protocol Components Ready for Go Implementation

All message types defined in `internal/ipc/protocol.go` are verified against the golden fixtures.  The following components have Go implementations ready:

| Component | Go file | Status |
|-----------|---------|--------|
| All 23 message structs | `internal/ipc/protocol.go` | Done |
| NDJSON framing (read/write) | `internal/ipc/framing.go` | Done |
| TCP client (probe/test use) | `internal/ipc/client.go` | Done |
| IPC probe (integration test) | `tools/ipc-probe/main.go` | Done |
| Fixture verification | `tools/ipc-probe/fixture_check.go` | Done |

Remaining work for Phase 17:

- TCP server (accept, dispatch, concurrency limit of 64)
- `ClientConnection` state machine in Go
- `ExtensionConnectionManager` equivalent (registry of authenticated extensions)
- Auth token generation and validation (`crypto/rand` + `crypto/subtle.ConstantTimeCompare`)
- Ready file and token file writing
- Single-service ownership (named mutex on Windows via `golang.org/x/sys/windows`; `flock` on Unix)
- Tool executor interface and dispatch
- Graceful shutdown (context cancellation, draining connections)

## Python-Specific Dependencies to Avoid in Go

| Python construct | Go alternative |
|-----------------|----------------|
| `asyncio.StreamReader.readline()` | `bufio.Reader.ReadBytes('\n')` |
| `asyncio.wait_for` | `context.WithTimeout` + channel select |
| `asyncio.Future` for pending requests | `chan` or `sync.Map` of response channels |
| `dataclasses.asdict` | `encoding/json.Marshal` with struct tags |
| `secrets.compare_digest` | `crypto/subtle.ConstantTimeCompare` |
| `asyncio.create_task` | `go func()` goroutine |
| `asyncio.Lock` | `sync.Mutex` |

## OS-Specific Dependencies

### Windows

- Named mutex for single-service ownership: `CreateMutexW` via `golang.org/x/sys/windows` or `syscall.NewLazyDLL`.
- Token and ready files in `os.Getenv("TEMP")` or `os.TempDir()`.

### Unix/macOS

- File lock for single-service ownership: `syscall.Flock` with `LOCK_EX | LOCK_NB` on the ready file.
- Token and ready files in `/tmp/` (or `os.TempDir()`).

## Identified Go Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Named mutex on Windows requires CGo or syscall | Medium | Use `golang.org/x/sys/windows` (pure Go) |
| `gui_state_changed` stale revision suppression must be race-free | Medium | Use `sync.Mutex` on per-connection state |
| `send_request` future pattern requires request ID → channel map | Low | `sync.Map[string, chan any]` |
| Tool executor dispatch requires calling Python extension code | High | Phase 17 scope: Go service proxies to Go-native tool implementations |
| Max 64 connections enforcement | Low | Semaphore (`make(chan struct{}, 64)`) |
| `asyncio.wait_for` shield prevents timeout from cancelling the inner task | Low | Go context cancel propagates; use `context.WithTimeout` carefully |

## Phase 17 Acceptance Criteria

1. `go build ./...` succeeds with no CGo required on Windows and Linux.
2. `go run ./tools/ipc-probe/... -mock` exits 0.
3. `go run ./tools/ipc-probe/... -fixtures tests/protocol/fixtures` exits 0 (all 29 fixtures pass).
4. When the Go service is running, the existing Python extension (`tests/ipc/`) and bridge tests pass unchanged.
5. The Go service writes the ready file and token file in the correct locations.
6. Only one Go service instance can hold the single-service lock at a time.
7. The Go service accepts up to 64 simultaneous connections and rejects the 65th.

## Test Matrix

| Scenario | Tools required | Phase 16 | Phase 17 |
|----------|---------------|----------|----------|
| Fixture structure conformance (Python) | pytest | Done | Maintained |
| Fixture decode (Go) | go run -fixtures | Done | Maintained |
| Framing edge cases | pytest | Done | Go equivalent needed |
| Go probe mock mode | go run -mock | Done | Maintained |
| Go probe real service | Running Python service | Manual | Automated |
| Go service + Python extension | Python extension | N/A | Phase 17 target |
| Go service + Python bridge | Python bridge | N/A | Phase 17 target |
| Multi-bridge routing | Running service | Manual | Phase 17 target |
| Single-service lock (Windows) | Windows runner | N/A | Phase 17 CI |
