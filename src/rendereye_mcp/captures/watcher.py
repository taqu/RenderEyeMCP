"""Watchdog-based filesystem monitor for .rdc capture files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

if TYPE_CHECKING:
    from rendereye_mcp.captures.registry import CaptureRegistry

logger = logging.getLogger(__name__)


class RDCEventHandler(FileSystemEventHandler):
    """Handles watchdog events for .rdc files only."""

    def __init__(self, registry: "CaptureRegistry") -> None:
        super().__init__()
        self._registry = registry

    def _is_rdc(self, path: str) -> bool:
        return Path(path).suffix.lower() == ".rdc"

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and self._is_rdc(event.src_path):
            logger.debug("Watchdog: created %s", event.src_path)
            self._registry.on_file_created(Path(event.src_path))

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and self._is_rdc(event.src_path):
            logger.debug("Watchdog: modified %s", event.src_path)
            self._registry.on_file_modified(Path(event.src_path))

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not event.is_directory and self._is_rdc(event.src_path):
            logger.debug("Watchdog: deleted %s", event.src_path)
            self._registry.on_file_deleted(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            src_rdc = self._is_rdc(event.src_path)
            dest_rdc = self._is_rdc(event.dest_path)
            if src_rdc or dest_rdc:
                logger.debug("Watchdog: moved %s -> %s", event.src_path, event.dest_path)
                self._registry.on_file_moved(
                    Path(event.src_path), Path(event.dest_path)
                )


class CaptureWatcher:
    def __init__(self, registry: "CaptureRegistry") -> None:
        self._registry = registry
        self._observer: Optional[Observer] = None
        self._handler = RDCEventHandler(registry)

    def start(self, directories: list[tuple[Path, bool]]) -> None:
        """Start watching directories. directories = [(path, recursive), ...]"""
        self._observer = Observer()
        for path, recursive in directories:
            if path.is_dir():
                self._observer.schedule(self._handler, str(path), recursive=recursive)
                logger.info("Watching directory: %s (recursive=%s)", path, recursive)
            else:
                logger.warning("Watch directory not found, skipping: %s", path)
        self._observer.start()
        logger.info("CaptureWatcher started")

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        logger.info("CaptureWatcher stopped")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
