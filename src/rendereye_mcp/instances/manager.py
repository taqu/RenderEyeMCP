"""InstanceManager: tracks known RenderDoc instances and their windows."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from .discovery import discover_all_windows, discover_renderdoc_instances
from .models import InstanceOwnership, InstanceRecord, InstanceStatus, WindowRecord

logger = logging.getLogger(__name__)


class InstanceManager:
    """Tracks known RenderDoc instances and their windows. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: dict[str, InstanceRecord] = {}  # instance_id -> record
        self._managed_pids: set[int] = set()  # PIDs we launched
        self._next_instance_id: int = 1
        self._next_window_id: int = 1

    def refresh(self) -> None:
        """Re-enumerate running processes and windows. Updates internal state."""
        discovered = discover_renderdoc_instances(known_managed_pids=self._managed_pids)

        with self._lock:
            now = datetime.now(timezone.utc)

            # Build a lookup of known instances by (pid, create_time)
            known_by_key: dict[tuple[int, float], InstanceRecord] = {}
            for inst in self._instances.values():
                key = (inst.process_id, round(inst.process_create_time, 1))
                known_by_key[key] = inst

            # Mark all existing as potentially exited
            for inst in self._instances.values():
                inst.status = InstanceStatus.EXITED
                inst.windows = []

            new_instances: dict[str, InstanceRecord] = {}

            for disc in discovered:
                key = (disc.process_id, round(disc.process_create_time, 1))
                if key in known_by_key:
                    # Update existing
                    existing = known_by_key[key]
                    existing.status = InstanceStatus.RUNNING
                    existing.last_seen_at = now
                    # Update ownership if we now know it's managed
                    if disc.process_id in self._managed_pids:
                        existing.ownership = InstanceOwnership.MANAGED
                    new_instances[existing.instance_id] = existing
                else:
                    # New process
                    iid = self._next_iid()
                    disc.instance_id = iid
                    disc.last_seen_at = now
                    new_instances[iid] = disc

            # Keep exited instances for a bit (callers may still query them)
            for iid, inst in self._instances.items():
                if iid not in new_instances:
                    inst.status = InstanceStatus.EXITED
                    new_instances[iid] = inst

            self._instances = new_instances

            # Enumerate windows for running instances
            running = [i for i in self._instances.values() if i.status == InstanceStatus.RUNNING]
            windows = discover_all_windows(running, id_counter_start=self._next_window_id)

            # Assign windows to instances
            inst_windows: dict[str, list[WindowRecord]] = {i.instance_id: [] for i in running}
            for w in windows:
                if w.instance_id in inst_windows:
                    inst_windows[w.instance_id].append(w)

            for inst in running:
                inst.windows = inst_windows.get(inst.instance_id, [])

            if windows:
                self._next_window_id = (
                    max(int(w.window_id.split("-")[1]) for w in windows) + 1
                )

    def register_launched(
        self, pid: int, create_time: float, exe_path: str
    ) -> InstanceRecord:
        """Register a process we just launched as MANAGED."""
        with self._lock:
            self._managed_pids.add(pid)
            iid = self._next_iid()
            now = datetime.now(timezone.utc)
            record = InstanceRecord(
                instance_id=iid,
                process_id=pid,
                process_create_time=create_time,
                exe_path=exe_path,
                ownership=InstanceOwnership.MANAGED,
                status=InstanceStatus.RUNNING,
                last_seen_at=now,
            )
            self._instances[iid] = record
            return record

    def get_instance(self, instance_id: str) -> Optional[InstanceRecord]:
        with self._lock:
            return self._instances.get(instance_id)

    def get_instance_by_pid(self, pid: int) -> Optional[InstanceRecord]:
        with self._lock:
            for inst in self._instances.values():
                if inst.process_id == pid:
                    return inst
            return None

    def list_instances(self) -> list[InstanceRecord]:
        with self._lock:
            return list(self._instances.values())

    def list_windows(self) -> list[WindowRecord]:
        with self._lock:
            result: list[WindowRecord] = []
            for inst in self._instances.values():
                result.extend(inst.windows)
            return result

    def get_window(self, window_id: str) -> Optional[WindowRecord]:
        with self._lock:
            for inst in self._instances.values():
                for w in inst.windows:
                    if w.window_id == window_id:
                        return w
            return None

    def find_windows_for_instance(self, instance_id: str) -> list[WindowRecord]:
        with self._lock:
            inst = self._instances.get(instance_id)
            if inst is None:
                return []
            return list(inst.windows)

    def _next_iid(self) -> str:
        iid = f"instance-{self._next_instance_id:06d}"
        self._next_instance_id += 1
        return iid

    def _next_wid(self) -> str:
        wid = f"window-{self._next_window_id:06d}"
        self._next_window_id += 1
        return wid
