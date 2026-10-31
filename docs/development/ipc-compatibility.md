# IPC Protocol Compatibility

## Golden Fixture Structure

Fixtures live in `tests/protocol/fixtures/` and are organised by category:

```
tests/protocol/fixtures/
  connection/      # handshake and error messages
  requests/        # client-to-server request messages
  responses/       # server-to-client response messages
  notifications/   # fire-and-forget push messages
  binary/          # messages containing base64-encoded binary data
```

Each fixture file is a JSON object:

```json
{
  "category": "<category>",
  "description": "<human-readable description>",
  "wire": "<exact UTF-8 JSON line including trailing \\n>",
  "fields": { "<field>": <value>, ... }
}
```

- `wire` is the exact output of `json.dumps(asdict(msg), separators=(",",":")) + "\n"`.
- `fields` contains every field of the dataclass, including `type` and `protocol_version`.
- Values use deterministic placeholder UUIDs and numbers; no random data.

## Regenerating Fixtures

If a message dataclass is changed (field added, renamed, or reordered), regenerate affected fixtures by running Python with the dataclass directly:

```python
import json
from dataclasses import asdict
from rendereye_mcp.ipc.protocol import HelloMessage

msg = HelloMessage(
    request_id="aaaaaaaa-0000-0000-0000-000000000001",
    instance_id="bbbbbbbb-0000-0000-0000-000000000001",
    process_id=12345,
    extension_version="1.0.0",
)
wire = json.dumps(asdict(msg), separators=(",", ":")) + "\n"
print(repr(wire))
```

Paste the output into the fixture's `wire` field, and update `fields` to match.

The three fixture tests in `test_fixtures.py` will catch any mismatch between `wire` and `fields`:

- `test_fixture_wire_deserializes_correctly` — deserialize wire, compare all fields
- `test_fixture_wire_roundtrip` — serialize ↔ deserialize stability
- `test_fixture_wire_exact_bytes` — `serialize(msg)` must equal `wire` exactly

## Test Categories

| File | What it tests |
|------|---------------|
| `test_fixtures.py` | Golden fixture conformance: all 29 fixtures |
| `test_framing.py` | TCP framing edge cases: partial writes, max size, unicode, null values |
| `test_binary_payloads.py` | Binary and large payload handling in ToolResultMessage |
| `test_failure_injection.py` | Error paths: malformed JSON, unknown types, goodbye, timeout constants |

The full suite runs with:

```
uv run pytest tests/protocol/ -v
```

## Cross-Language Compatibility Approach

The Go probe (`tools/ipc-probe/`) verifies that:

1. `go build ./tools/ipc-probe/...` succeeds (compilation check).
2. `-mock` mode parses hard-coded mock responses using Go's `encoding/json` (type compatibility check).
3. `-fixtures tests/protocol/fixtures` loads every fixture file and decodes the wire field using the corresponding Go struct (structural compatibility check).

The Go structs in `internal/ipc/protocol.go` mirror the Python dataclass field names exactly via `json` struct tags.

## Backward Compatibility Expectations

Protocol version 1 is the baseline.  The following rules apply:

1. **No field removal:** Removing a field from a message type is a breaking change.
2. **No field rename:** Renaming a field (JSON key) breaks all existing clients.
3. **Field addition:** Adding optional fields to a message type is safe provided the receiver ignores unknown JSON keys (Python's `deserialize()` filters by `_READONLY_FIELDS` then passes remaining keys as `**kwargs` — unknown keys cause a `TypeError` and must not be added without updating the constructor).
4. **Type change:** Changing a field's JSON type (e.g., `int` → `string`) is a breaking change.

In practice, any change to the wire format requires:
- Updating the Python dataclass
- Regenerating affected fixtures
- Updating the Go structs
- Bumping a documented protocol version once version negotiation is implemented

## Versioning Policy

`protocol_version` is always `1`.  There is no negotiation logic currently.  A future protocol version bump will require:

1. Incrementing `PROTOCOL_VERSION` in `protocol.py`
2. Adding server-side negotiation in `ClientConnection._handle_hello` / `_handle_bridge_register`
3. Maintaining backward-compatible handling for version 1 connections during the transition window
