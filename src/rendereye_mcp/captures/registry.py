"""Central coordinator for capture discovery and registry management."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rendereye_mcp.captures.discovery import scan_directory
from rendereye_mcp.captures.models import CaptureRecord, CaptureStatus
from rendereye_mcp.captures.readiness import check_readiness
from rendereye_mcp.captures.storage import CaptureStorage

if TYPE_CHECKING:
    from rendereye_mcp.config import Config

logger = logging.getLogger(__name__)


class CaptureRegistry:
    def __init__(self, config: "Config", storage: CaptureStorage) -> None:
        self._config = config
        self._storage = storage
        self._watcher: Optional["CaptureWatcher"] = None  # noqa: F821
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._reconcile_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()
        self._stats = {
            "scanned": 0,
            "new": 0,
            "updated": 0,
        }

    async def start(self) -> None:
        """Initialize storage, scan directories, start watcher, start background reconciler."""
        self._loop = asyncio.get_event_loop()
        self._storage.initialize()
        self._running = True

        capture_cfg = self._config.capture
        if capture_cfg.enabled:
            await self.scan_all()
            await self._start_watcher()
            self._reconcile_task = asyncio.ensure_future(self._reconcile_loop())
            logger.info("CaptureRegistry started")
        else:
            logger.info("CaptureRegistry disabled by config")

    async def stop(self) -> None:
        """Stop watcher and background tasks cleanly."""
        self._running = False
        if self._reconcile_task is not None:
            self._reconcile_task.cancel()
            try:
                await self._reconcile_task
            except asyncio.CancelledError:
                pass
            self._reconcile_task = None

        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

        logger.info("CaptureRegistry stopped")

    async def _start_watcher(self) -> None:
        from rendereye_mcp.captures.watcher import CaptureWatcher

        dirs = [
            (Path(d.path), d.recursive)
            for d in self._config.capture.directories
        ]
        if dirs:
            self._watcher = CaptureWatcher(self)
            self._watcher.start(dirs)

    async def scan_all(self) -> int:
        """Scan all configured directories. Returns count of new/updated records."""
        total = 0
        for dir_cfg in self._config.capture.directories:
            total += await self.scan_directory(
                Path(dir_cfg.path), dir_cfg.recursive
            )
        return total

    async def scan_directory(self, directory: Path, recursive: bool) -> int:
        """Scan one directory, upsert or update records."""
        count = 0
        source_dir = str(directory.resolve())
        min_size = self._config.capture.min_file_size_bytes

        try:
            paths = list(
                scan_directory(directory, recursive, min_size=min_size)
            )
        except Exception as exc:
            logger.warning("Error scanning directory %s: %s", directory, exc)
            return 0

        for path in paths:
            try:
                await self._process_file(path, source_dir)
                count += 1
            except Exception as exc:
                logger.warning("Error processing file %s: %s", path, exc)

        return count

    async def _process_file(self, path: Path, source_dir: str) -> None:
        """Discover or update a single file. Schedule readiness check if needed."""
        canonical = str(path.resolve())
        now = datetime.now(timezone.utc)

        existing = self._storage.get_capture_by_path(canonical)

        try:
            stat = path.stat()
            file_size = stat.st_size
            fs_created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
            fs_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            if existing is not None:
                existing.status = CaptureStatus.MISSING
                existing.last_seen_at = now
                self._storage.upsert_capture(existing)
            return

        if existing is None:
            capture_id = self._storage.get_next_capture_id()
            record = CaptureRecord(
                capture_id=capture_id,
                path=canonical,
                filename=path.name,
                file_size=file_size,
                fs_created_at=fs_created_at,
                fs_modified_at=fs_modified_at,
                discovered_at=now,
                last_seen_at=now,
                readiness_confirmed_at=None,
                status=CaptureStatus.DISCOVERED,
                source_directory=source_dir,
            )
            self._storage.upsert_capture(record)
            asyncio.ensure_future(
                self._run_readiness_check(capture_id, path)
            )
        else:
            existing.last_seen_at = now
            existing.file_size = file_size
            existing.fs_modified_at = fs_modified_at
            if existing.status == CaptureStatus.MISSING:
                existing.status = CaptureStatus.DISCOVERED
                existing.readiness_confirmed_at = None
                asyncio.ensure_future(
                    self._run_readiness_check(existing.capture_id, path)
                )
            self._storage.upsert_capture(existing)

    async def _run_readiness_check(self, capture_id: str, path: Path) -> None:
        """Run readiness check and update record status."""
        record = self._storage.get_capture(capture_id)
        if record is None:
            return

        record.status = CaptureStatus.PENDING
        self._storage.upsert_capture(record)

        stability = self._config.capture.readiness_stability_seconds
        min_size = self._config.capture.min_file_size_bytes

        result = await check_readiness(
            path,
            stability_seconds=stability,
            min_size=min_size,
        )

        record = self._storage.get_capture(capture_id)
        if record is None:
            return

        now = datetime.now(timezone.utc)
        if result.passed:
            record.status = CaptureStatus.READY
            record.readiness_confirmed_at = now
            record.file_size = result.file_size
            record.error_message = ""
        else:
            if result.reason == "missing":
                record.status = CaptureStatus.MISSING
            elif result.reason in ("too_small", "inaccessible"):
                record.status = CaptureStatus.INACCESSIBLE
            else:
                # growing — reschedule later
                record.status = CaptureStatus.PENDING
            record.error_message = result.reason

        record.last_seen_at = now
        self._storage.upsert_capture(record)

        # If still pending (growing), retry after stability window
        if record.status == CaptureStatus.PENDING:
            await asyncio.sleep(stability)
            await self._run_readiness_check(capture_id, path)

    async def _reconcile_loop(self) -> None:
        """Periodic background reconciliation task."""
        interval = self._config.capture.scan_interval_seconds
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self.scan_all()
                # Check for missing files
                records, _ = self._storage.list_captures(
                    status=CaptureStatus.READY, limit=1000
                )
                now = datetime.now(timezone.utc)
                for record in records:
                    p = Path(record.path)
                    if not p.exists():
                        record.status = CaptureStatus.MISSING
                        record.last_seen_at = now
                        self._storage.upsert_capture(record)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Reconcile loop error: %s", exc)

    def get_capture(self, capture_id: str) -> Optional[CaptureRecord]:
        return self._storage.get_capture(capture_id)

    def list_captures(
        self,
        status: Optional[CaptureStatus] = None,
        directory: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CaptureRecord], int]:
        return self._storage.list_captures(
            status=status, directory=directory, limit=limit, offset=offset
        )

    def get_latest_capture(
        self, directory: Optional[str] = None
    ) -> Optional[CaptureRecord]:
        return self._storage.get_latest_capture(directory=directory)

    async def rescan(self) -> dict:
        """Trigger immediate rescan. Returns {'scanned': N, 'new': N, 'updated': N}."""
        before_records, before_total = self._storage.list_captures(limit=10000)
        before_ids = {r.capture_id for r in before_records}

        scanned = await self.scan_all()

        after_records, after_total = self._storage.list_captures(limit=10000)
        after_ids = {r.capture_id for r in after_records}

        new_count = len(after_ids - before_ids)
        updated_count = scanned - new_count if scanned > new_count else 0

        return {
            "scanned": scanned,
            "new": new_count,
            "updated": updated_count,
        }

    def get_status(self) -> dict:
        """Return registry status dict for MCP."""
        enabled = self._config.capture.enabled
        dirs = [d.path for d in self._config.capture.directories]

        records, total = self._storage.list_captures(limit=0) if enabled else ([], 0)

        # Count by status
        status_counts: dict[str, int] = {}
        if enabled:
            for s in CaptureStatus:
                _, count = self._storage.list_captures(status=s, limit=0)
                status_counts[s.value] = count

        return {
            "enabled": enabled,
            "running": self._running,
            "watcher_active": self._watcher.is_running if self._watcher else False,
            "watched_directories": dirs,
            "total_captures": total,
            "captures_by_status": status_counts,
            "scan_interval_seconds": self._config.capture.scan_interval_seconds,
            "readiness_stability_seconds": self._config.capture.readiness_stability_seconds,
        }

    # Called from watchdog thread (must be thread-safe, not async):
    def on_file_created(self, path: Path) -> None:
        self._schedule_from_thread(self._process_file(path, self._source_dir_for(path)))

    def on_file_modified(self, path: Path) -> None:
        self._schedule_from_thread(self._process_file(path, self._source_dir_for(path)))

    def on_file_deleted(self, path: Path) -> None:
        self._schedule_from_thread(self._handle_deletion(path))

    def on_file_moved(self, src: Path, dest: Path) -> None:
        self._schedule_from_thread(self._handle_move(src, dest))

    def _source_dir_for(self, path: Path) -> str:
        """Find the configured source directory for a given path."""
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path

        for dir_cfg in self._config.capture.directories:
            try:
                d = Path(dir_cfg.path).resolve()
                resolved.relative_to(d)
                return str(d)
            except ValueError:
                continue
        # Fallback: parent directory
        return str(resolved.parent)

    def _schedule_from_thread(self, coro) -> None:
        """Schedule a coroutine on the asyncio event loop from a non-async thread."""
        loop = self._loop  # snapshot to avoid TOCTOU race with stop()
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coro, loop)
            except RuntimeError:
                logger.warning("Cannot schedule coroutine: event loop closed")
        else:
            logger.warning("Cannot schedule coroutine: event loop not running")

    async def _handle_deletion(self, path: Path) -> None:
        canonical = str(path.resolve())
        record = self._storage.get_capture_by_path(canonical)
        if record is not None:
            now = datetime.now(timezone.utc)
            record.status = CaptureStatus.MISSING
            record.last_seen_at = now
            self._storage.upsert_capture(record)

    async def _handle_move(self, src: Path, dest: Path) -> None:
        """Handle a file rename/move event."""
        now = datetime.now(timezone.utc)

        # Mark old path as missing
        src_canonical = str(src.resolve() if src.exists() else src)
        old_record = self._storage.get_capture_by_path(src_canonical)
        if old_record is not None:
            old_record.status = CaptureStatus.MISSING
            old_record.last_seen_at = now
            self._storage.upsert_capture(old_record)

        # Process new path if it's an .rdc
        if dest.suffix.lower() == ".rdc":
            source_dir = self._source_dir_for(dest)
            await self._process_file(dest, source_dir)
