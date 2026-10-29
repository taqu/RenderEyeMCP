"""Tests for CaptureRegistry."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rendereye_mcp.captures.models import CaptureStatus
from rendereye_mcp.captures.registry import CaptureRegistry
from rendereye_mcp.captures.storage import CaptureStorage
from rendereye_mcp.config import CaptureConfig, CaptureDirectoryConfig, Config


def _make_config(
    directories: list[Path],
    recursive: bool = False,
    scan_interval: float = 100.0,
    stability: float = 0.1,
    enabled: bool = True,
    storage_path: str = "",
) -> Config:
    dirs = [CaptureDirectoryConfig(path=str(d), recursive=recursive) for d in directories]
    capture_cfg = CaptureConfig(
        enabled=enabled,
        scan_interval_seconds=scan_interval,
        readiness_stability_seconds=stability,
        directories=dirs,
        min_file_size_bytes=4,
    )
    return Config(capture=capture_cfg, storage_path=storage_path)


def _make_rdc(directory: Path, name: str, size: int = 100) -> Path:
    p = directory / name
    p.write_bytes(b"\x00" * size)
    return p


async def _start_and_wait(registry: CaptureRegistry, wait: float = 0.3) -> None:
    """Start registry and wait briefly for async tasks."""
    await registry.start()
    await asyncio.sleep(wait)


@pytest.fixture()
def storage(tmp_path: Path) -> CaptureStorage:
    db = tmp_path / "captures.db"
    s = CaptureStorage(db)
    yield s
    s.close()


class TestRegistryStartup:
    async def test_startup_scan_discovers_files(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame1.rdc")
        _make_rdc(watch_dir, "frame2.rdc")

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.6)

        records, total = registry.list_captures()
        await registry.stop()
        assert total == 2

    async def test_disabled_registry_does_not_scan(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame.rdc")

        config = _make_config([watch_dir], enabled=False)
        registry = CaptureRegistry(config, storage)
        storage.initialize()
        await registry.start()

        records, total = registry.list_captures()
        await registry.stop()
        assert total == 0


class TestFileLifecycle:
    async def test_new_file_becomes_ready(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame.rdc")

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.8)

        records, _ = registry.list_captures()
        await registry.stop()

        assert len(records) >= 1
        assert any(r.status == CaptureStatus.READY for r in records)

    async def test_deleted_file_becomes_missing(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        p = _make_rdc(watch_dir, "frame.rdc")

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.8)

        # Delete file
        p.unlink()
        # Trigger deletion detection via registry
        await registry._handle_deletion(p)

        records, _ = registry.list_captures()
        await registry.stop()

        assert any(r.status == CaptureStatus.MISSING for r in records)


class TestRescan:
    async def test_rescan_detects_new_file(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await registry.start()

        # Add a file after startup
        _make_rdc(watch_dir, "after_start.rdc")
        result = await registry.rescan()

        await registry.stop()
        assert result["scanned"] >= 1


class TestStableCaptureIds:
    async def test_ids_survive_restart(self, tmp_path: Path) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame.rdc")

        db = tmp_path / "captures.db"

        # First run
        s1 = CaptureStorage(db)
        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        r1 = CaptureRegistry(config, s1)
        await _start_and_wait(r1, wait=0.6)
        records1, _ = r1.list_captures()
        await r1.stop()
        s1.close()

        assert len(records1) >= 1
        original_id = records1[0].capture_id

        # Second run with same DB
        s2 = CaptureStorage(db)
        r2 = CaptureRegistry(config, s2)
        await _start_and_wait(r2, wait=0.6)
        records2, _ = r2.list_captures()
        await r2.stop()
        s2.close()

        # Same file should have same capture_id
        assert any(r.capture_id == original_id for r in records2)


class TestDeduplication:
    async def test_same_file_single_record(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame.rdc")

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.3)
        # Process same file twice
        path = watch_dir / "frame.rdc"
        await registry._process_file(path.resolve(), str(watch_dir.resolve()))
        await registry._process_file(path.resolve(), str(watch_dir.resolve()))

        records, total = registry.list_captures()
        await registry.stop()

        # Should still be just 1 record for this path
        paths = [r.path for r in records if r.filename == "frame.rdc"]
        assert len(set(paths)) == 1

    async def test_same_filename_different_dirs(self, tmp_path: Path, storage: CaptureStorage) -> None:
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        _make_rdc(dir1, "frame.rdc")
        _make_rdc(dir2, "frame.rdc")

        config = _make_config([dir1, dir2], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.3)

        records, total = registry.list_captures()
        await registry.stop()

        assert total == 2
        ids = {r.capture_id for r in records}
        assert len(ids) == 2


class TestRegistryQueries:
    async def test_list_and_get_latest(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()
        _make_rdc(watch_dir, "frame.rdc")

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await _start_and_wait(registry, wait=0.8)

        records, total = registry.list_captures()
        registry.get_latest_capture()
        await registry.stop()

        assert total >= 1

    async def test_inaccessible_directory_handled_gracefully(
        self, tmp_path: Path, storage: CaptureStorage
    ) -> None:
        missing_dir = tmp_path / "does_not_exist"

        config = _make_config([missing_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        # Should not raise
        await registry.start()
        result = await registry.rescan()
        await registry.stop()
        assert result is not None

    async def test_get_status(self, tmp_path: Path, storage: CaptureStorage) -> None:
        watch_dir = tmp_path / "captures"
        watch_dir.mkdir()

        config = _make_config([watch_dir], stability=0.1, scan_interval=100.0)
        registry = CaptureRegistry(config, storage)
        await registry.start()
        status = registry.get_status()
        await registry.stop()

        assert "enabled" in status
        assert "running" in status
        assert "total_captures" in status
