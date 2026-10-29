# Capture Registry — Design Reference

## Registry Data Model

The capture registry manages `.rdc` (RenderDoc capture) files discovered on the filesystem. Each file is represented by a `CaptureRecord` stored in a SQLite database.

### CaptureRecord Fields

| Field | Type | Description |
|---|---|---|
| `capture_id` | `str` | Stable identifier in `cap-NNNNNN` format |
| `path` | `str` | Canonical absolute path (resolved via `Path.resolve()`) |
| `filename` | `str` | Basename of the file |
| `file_size` | `int` | File size in bytes at last observation |
| `fs_created_at` | `datetime?` | Filesystem ctime (unreliable on Windows) |
| `fs_modified_at` | `datetime?` | Filesystem mtime |
| `discovered_at` | `datetime` | When the registry first observed the file |
| `last_seen_at` | `datetime` | Most recent timestamp when file was confirmed present |
| `readiness_confirmed_at` | `datetime?` | When the readiness check passed |
| `status` | `CaptureStatus` | Current lifecycle state |
| `selection_basis` | `str` | How the file is ranked (always `filesystem_modification_time`) |
| `ordering_confidence` | `str` | Confidence in ordering (always `heuristic`) |
| `source_directory` | `str` | Configured watch directory that owns this record |
| `error_message` | `str` | Last error reason if any |

## State Machine

```
         [file appears on disk]
                  |
                  v
           DISCOVERED
                  |
       [readiness check starts]
                  |
                  v
            PENDING
           /        \
    [stable]      [growing / not yet stable]
        |                    |
        v                  (retry)
      READY <-----------+
        |
   [file deleted]
        |
        v
     MISSING
        |
   [file reappears]
        |
        v
    DISCOVERED (again)

DISCOVERED -> INACCESSIBLE  (if file can't be opened)
DISCOVERED -> INVALID       (reserved for future format validation)
READY      -> STALE         (reserved for future age-based expiry)
```

## Ordering Policy

`get_latest_capture()` returns the READY capture with the highest priority according to:

1. `fs_modified_at DESC NULLS LAST` — most recently modified first
2. `fs_created_at DESC NULLS LAST` — tiebreaker by creation time
3. `discovered_at DESC` — tiebreaker by when we saw it
4. `capture_id DESC` — final tiebreaker (higher ID = seen later)

`ordering_confidence = "heuristic"` because on Windows, filesystem timestamps can be unreliable (FAT32 has 2-second resolution; some drivers reset ctime on copy).

## Timestamp Semantics

All timestamps are stored as ISO 8601 strings with UTC timezone (`+00:00` suffix). The registry uses `datetime.now(timezone.utc)` throughout.

- `fs_created_at` (`ctime`) — On Windows this is the file creation time; on Linux it is the inode change time. Treat as unreliable for ordering.
- `fs_modified_at` (`mtime`) — More reliable indicator of when the GPU capture occurred.
- `discovered_at` — Registry-assigned; monotonically increasing with capture_id.

## Duplicate Handling

Paths are canonicalized via `Path.resolve()` before storage. The `path` column has a `UNIQUE` constraint; an `ON CONFLICT DO UPDATE` upsert merges metadata without creating a new record.

Two files with the same basename in different directories get different `capture_id`s because their resolved paths differ.

## Rename / Deletion Behavior

| Event | Action |
|---|---|
| File deleted | Status → `MISSING`, `last_seen_at` updated |
| File renamed (src .rdc) | Old record → `MISSING` |
| File renamed (dest .rdc) | New record created via `_process_file` |
| File reappears | Status → `DISCOVERED`, readiness re-checked |

## Storage Schema

```sql
CREATE TABLE captures (
    capture_id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    fs_created_at TEXT,
    fs_modified_at TEXT,
    discovered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    readiness_confirmed_at TEXT,
    status TEXT NOT NULL,
    selection_basis TEXT NOT NULL DEFAULT 'filesystem_modification_time',
    ordering_confidence TEXT NOT NULL DEFAULT 'heuristic',
    source_directory TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE registry_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

`registry_meta` stores:
- `next_capture_id` — integer counter for ID generation (auto-incremented atomically)
- `schema_version` — current schema version (1)

## Concurrency Model

The registry uses a two-layer concurrency model:

1. **Asyncio layer** (`asyncio.Lock`) — protects async operations (scan, readiness checks) within the event loop
2. **Threading layer** (`threading.Lock` in `CaptureStorage`) — protects SQLite access from multiple threads

Watchdog callbacks fire on a background thread. The registry bridges them to the asyncio loop via `asyncio.run_coroutine_threadsafe(coro, loop)`. The event loop reference is captured at `registry.start()` time.

SQLite is opened with `check_same_thread=False` and WAL journal mode for improved concurrent read performance.

## Readiness Check Algorithm

A file is considered "ready" (stable, not actively being written) when:

1. File exists and is readable
2. `file_size >= min_size` (default 4 bytes)
3. Size and mtime are identical across two checks separated by `stability_seconds / 2`
4. A third check after another `stability_seconds / 2` confirms no change

If the file is still growing after checks, the status remains `PENDING` and the check is retried after another stability window.
