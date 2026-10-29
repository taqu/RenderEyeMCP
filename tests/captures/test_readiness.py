"""Tests for readiness checking."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rendereye_mcp.captures.readiness import check_readiness


class TestCheckReadiness:
    async def test_stable_file(self, tmp_path: Path) -> None:
        p = tmp_path / "stable.rdc"
        p.write_bytes(b"\x00" * 100)
        result = await check_readiness(p, stability_seconds=0.1, min_size=4, poll_interval=0.05)
        assert result.passed is True
        assert result.reason == "stable"
        assert result.file_size == 100

    async def test_growing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "growing.rdc"
        p.write_bytes(b"\x00" * 100)

        async def _grow():
            await asyncio.sleep(0.05)
            p.write_bytes(b"\x00" * 200)

        # Run growth and readiness concurrently
        _, result = await asyncio.gather(
            _grow(),
            check_readiness(p, stability_seconds=0.2, min_size=4, poll_interval=0.05),
        )
        assert result.passed is False
        assert result.reason == "growing"

    async def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.rdc"
        result = await check_readiness(p, stability_seconds=0.1, min_size=4)
        assert result.passed is False
        assert result.reason == "missing"
        assert result.file_size == 0

    async def test_too_small_file(self, tmp_path: Path) -> None:
        p = tmp_path / "small.rdc"
        p.write_bytes(b"\x00" * 2)
        result = await check_readiness(p, stability_seconds=0.1, min_size=4)
        assert result.passed is False
        assert result.reason == "too_small"
        assert result.file_size == 2

    async def test_file_not_readable(self, tmp_path: Path) -> None:
        """Test file that exists but can't be opened."""
        p = tmp_path / "locked.rdc"
        p.write_bytes(b"\x00" * 100)
        # On Windows we can't easily make a file unreadable without special tools,
        # so we patch the open call instead
        import unittest.mock as mock

        original_open = open

        def mock_open(path, *args, **kwargs):
            if str(path) == str(p):
                raise PermissionError("Access denied")
            return original_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=mock_open):
            result = await check_readiness(p, stability_seconds=0.1, min_size=4)

        assert result.passed is False
        assert result.reason == "inaccessible"

    async def test_file_disappears_mid_check(self, tmp_path: Path) -> None:
        """File exists at start but disappears during stability wait."""
        p = tmp_path / "disappears.rdc"
        p.write_bytes(b"\x00" * 100)

        async def _delete():
            await asyncio.sleep(0.06)
            p.unlink()

        _, result = await asyncio.gather(
            _delete(),
            check_readiness(p, stability_seconds=0.2, min_size=4, poll_interval=0.05),
        )
        assert result.passed is False
        assert result.reason == "missing"

    async def test_returns_correct_path(self, tmp_path: Path) -> None:
        p = tmp_path / "check.rdc"
        p.write_bytes(b"\x00" * 100)
        result = await check_readiness(p, stability_seconds=0.1, min_size=4)
        assert result.path == p
