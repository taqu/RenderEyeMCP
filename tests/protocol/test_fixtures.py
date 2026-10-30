"""Protocol conformance tests using golden fixtures.

Each fixture JSON file in tests/protocol/fixtures/**/*.json describes a
canonical wire message along with the expected decoded field values.  These
tests verify that ``deserialize()`` produces the correct dataclass for every
fixture, and that the deserialized object's fields match the expected values.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from rendereye_mcp.ipc.protocol import deserialize

# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _collect_fixtures():
    """Return a list of (fixture_path, fixture_data) for all fixture files."""
    fixtures = []
    for path in sorted(FIXTURES_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        # Use relative path as the test ID
        rel = path.relative_to(FIXTURES_DIR)
        fixtures.append(pytest.param(data, id=str(rel).replace("\\", "/")))
    return fixtures


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _collect_fixtures())
def test_fixture_wire_deserializes_correctly(fixture):
    """Deserializing the wire field must produce the fields listed in the fixture."""
    wire: str = fixture["wire"]
    expected_fields: dict = fixture["fields"]

    # Deserialize the wire representation
    msg = deserialize(wire.encode("utf-8"))

    # Convert the deserialized dataclass to a plain dict for comparison
    actual = asdict(msg)

    # Verify every expected field matches the actual field
    for key, expected_value in expected_fields.items():
        assert key in actual, f"Field {key!r} missing from deserialized {type(msg).__name__}"
        assert actual[key] == expected_value, (
            f"Field {key!r}: expected {expected_value!r}, got {actual[key]!r}"
        )


@pytest.mark.parametrize("fixture", _collect_fixtures())
def test_fixture_wire_roundtrip(fixture):
    """Serializing and re-deserializing must reproduce the same fields."""
    from rendereye_mcp.ipc.protocol import serialize

    wire: str = fixture["wire"]
    msg = deserialize(wire.encode("utf-8"))

    # Re-serialize and re-deserialize
    roundtripped_wire = serialize(msg)
    msg2 = deserialize(roundtripped_wire)

    assert asdict(msg) == asdict(msg2)


@pytest.mark.parametrize("fixture", _collect_fixtures())
def test_fixture_wire_exact_bytes(fixture):
    """The wire field must exactly match what serialize() produces."""
    from rendereye_mcp.ipc.protocol import serialize

    wire: str = fixture["wire"]
    msg = deserialize(wire.encode("utf-8"))

    produced = serialize(msg).decode("utf-8")
    assert produced == wire, (
        f"Wire mismatch for {type(msg).__name__}:\n"
        f"  expected: {wire!r}\n"
        f"  produced: {produced!r}"
    )
