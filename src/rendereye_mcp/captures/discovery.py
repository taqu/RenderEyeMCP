"""Filesystem discovery of .rdc capture files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


def scan_directory(
    directory: Path,
    recursive: bool,
    min_size: int = 4,
) -> Iterator[Path]:
    """Yield .rdc file paths (case-insensitive on Windows) from directory.

    Skips inaccessible files/dirs silently. Does not follow symlink cycles.
    Deduplicates by resolved path.
    """
    if not directory.is_dir():
        return

    seen: set[Path] = set()

    def _iter(d: Path) -> Iterator[Path]:
        try:
            entries = list(d.iterdir())
        except OSError:
            return

        for entry in entries:
            # Use os.stat with follow_symlinks=False to detect symlinks
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue

            is_link = os.path.islink(entry)

            if st.st_mode & 0o170000 == 0o040000:  # S_ISDIR
                # It's a directory (or symlink to dir if we dereference)
                if is_link:
                    # For symlinks pointing to dirs, resolve and check for cycles
                    try:
                        resolved = entry.resolve()
                    except OSError:
                        continue
                    if recursive and resolved not in seen:
                        seen.add(resolved)
                        yield from _iter(entry)
                else:
                    if recursive:
                        try:
                            resolved = entry.resolve()
                        except OSError:
                            resolved = entry
                        if resolved not in seen:
                            seen.add(resolved)
                            yield from _iter(entry)
            elif st.st_mode & 0o170000 == 0o100000:  # S_ISREG
                if entry.suffix.lower() != ".rdc":
                    continue
                try:
                    resolved = entry.resolve()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                # Check size
                try:
                    if entry.stat().st_size < min_size:
                        continue
                except OSError:
                    continue
                yield resolved
            # else: symlink to file, or other special file — check dereferenced
            elif is_link:
                # Symlink to a regular file
                if entry.suffix.lower() != ".rdc":
                    continue
                try:
                    resolved = entry.resolve()
                    real_st = resolved.stat()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                if real_st.st_size < min_size:
                    continue
                yield resolved

    yield from _iter(directory)
