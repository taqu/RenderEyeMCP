# Session Management

## Overview

Phase 2 of RenderEyeMCP introduces session management: the ability to track RenderDoc
instances (running processes), enumerate their windows, launch new instances, and maintain
persistent session records that survive server restarts.

## Session IDs

Session IDs use the format `session-NNNNNN` (e.g. `session-000001`). They are assigned
sequentially and stored in the `registry_meta` SQLite table alongside the capture counter.
The counter persists across server restarts.

## Session Lifecycle

```
CREATING  →  ACTIVE  →  CLOSING  →  CLOSED
                ↓
          DISCONNECTED  →  RECOVERING  →  ACTIVE
```

- **CREATING**: Session has been requested; RenderDoc is launching.
- **ACTIVE**: Session is running normally.
- **DISCONNECTED**: The process appears to have exited but the session record is kept.
- **RECOVERING**: Server is attempting to reconnect to a process.
- **CLOSING**: WM_CLOSE has been sent; waiting for window to disappear.
- **CLOSED**: Session ended gracefully.

## Managed vs External Sessions

| Property | Managed | External |
|----------|---------|----------|
| Launched by RenderEyeMCP | Yes | No |
| Can be closed via `session_close` | Yes (if unprotected) | No |
| Ownership | `managed` | `external` |

External sessions are discovered during `instance_list` or reconciliation — they represent
RenderDoc instances the user launched manually.

## Protected Sessions

Any session can be marked `protected=True` via `session_protect`. Protected sessions:

- Cannot be closed by `session_close` (returns `error: session_protected`).
- Cannot be implicitly replaced.
- Must be explicitly unprotected first.

## Window Association

When a session is created, window association is initially `UNKNOWN`. RenderDoc may reuse
an existing window rather than opening a new one when already running. To resolve windows:

1. Call `instance_list` to trigger a refresh of running processes and their windows.
2. `focus_session` will attempt to find a window for the session's instance.

Association statuses:
- **CONFIRMED**: We launched it and correlated the window.
- **INFERRED**: Correlated by timing or title heuristics.
- **UNKNOWN**: No window found yet.
- **LOST**: Previously associated window is no longer present.

## Focus and Close Behavior

### session_focus

Calls `ShowWindow(SW_RESTORE)` + `SetForegroundWindow()` on the session's window.
Windows may deny foreground activation (returns `denied_by_windows`). The window
must be in the running instance manager — call `instance_list` first if needed.

### session_close

Sends `WM_CLOSE` via `PostMessage` and polls for window disappearance (3 second
timeout). Never calls `TerminateProcess`. Returns `confirmed: true` if the window
disappears within the timeout.

## Startup Recovery (Reconciliation)

On startup, `SessionManager.reconcile()` checks each ACTIVE/DISCONNECTED session:

1. If `process_id` no longer exists → status becomes `DISCONNECTED`, `association_status` becomes `LOST`.
2. If process is running again (different create_time) → stays `DISCONNECTED`.
3. If window_id is no longer valid → `association_status` becomes `LOST`.

This recovers from crashes and allows sessions to be resumed if the process is still
running.

## SQLite Schema

Sessions are stored in the same database file as captures (`captures.db`):

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    capture_path TEXT NOT NULL,
    instance_id TEXT,
    window_id TEXT,
    process_id INTEGER,
    status TEXT NOT NULL,
    managed INTEGER NOT NULL DEFAULT 1,
    protected INTEGER NOT NULL DEFAULT 0,
    association_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);
```

The session counter is stored in `registry_meta` as `next_session_id`.

## Extension Connection States (Phase 3)

Sessions gain additional extension connectivity information from Phase 3:

### ExtensionConnection

Each authenticated IPC connection creates an `ExtensionConnection` record in the `ExtensionConnectionManager`:

| Field | Description |
|-------|-------------|
| `connection_id` | Server-assigned UUID (stable for session lifetime) |
| `instance_id` | RenderDoc instance the extension reports |
| `authenticated` | Whether auth token was validated |
| `connected` | Whether TCP connection is currently active |
| `gui_state_revision` | Monotonically increasing revision of GUI state |
| `capture_loaded` | Whether a capture is currently loaded |
| `capture_path` | Path to the loaded capture (or null) |
| `capture_state` | `"loaded"` \| `"unloaded"` \| `"loading"` \| `"error"` \| `"unknown"` |

### Session Association Freshness

When `instance_gui_state` is queried:
- `freshness: "fresh"` — extension is currently connected
- `freshness: "stale"` — extension was previously connected but has since disconnected
- `freshness: "unavailable"` — no extension connection found for this instance

### Callbacks

`SessionManager` receives two callbacks from `ExtensionConnectionManager`:

- `on_gui_state_changed(connection_id, capture_path, capture_loaded)` — called when extension pushes a GUI state update
- `on_extension_disconnected(connection_id)` — called when the extension TCP connection closes
