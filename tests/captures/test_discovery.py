"""Tests for capture discovery (scan_directory)."""

from __future__ import annotations

from pathlib import Path

from rendereye_mcp.captures.discovery import scan_directory


def _make_rdc(directory: Path, name: str, size: int = 100) -> Path:
    p = directory / name
    p.write_bytes(b"\x00" * size)
    return p


class TestScanDirectory:
    def test_empty_directory(self, tmp_path: Path) -> None:
        results = list(scan_directory(tmp_path, recursive=False))
        assert results == []

    def test_single_rdc(self, tmp_path: Path) -> None:
        _make_rdc(tmp_path, "capture.rdc")
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 1
        assert results[0].name == "capture.rdc"

    def test_multiple_rdc_files(self, tmp_path: Path) -> None:
        _make_rdc(tmp_path, "a.rdc")
        _make_rdc(tmp_path, "b.rdc")
        _make_rdc(tmp_path, "c.rdc")
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 3

    def test_uppercase_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "capture.RDC"
        p.write_bytes(b"\x00" * 100)
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 1

    def test_nested_not_found_when_not_recursive(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        _make_rdc(subdir, "nested.rdc")
        results = list(scan_directory(tmp_path, recursive=False))
        assert results == []

    def test_nested_found_when_recursive(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        _make_rdc(subdir, "nested.rdc")
        results = list(scan_directory(tmp_path, recursive=True))
        assert len(results) == 1
        assert results[0].name == "nested.rdc"

    def test_non_rdc_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("hello")
        (tmp_path / "file.png").write_bytes(b"\x00" * 100)
        results = list(scan_directory(tmp_path, recursive=False))
        assert results == []

    def test_missing_directory_no_exception(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        results = list(scan_directory(missing, recursive=False))
        assert results == []

    def test_unicode_filename(self, tmp_path: Path) -> None:
        _make_rdc(tmp_path, "ファイル.rdc")
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 1

    def test_file_smaller_than_min_size_excluded(self, tmp_path: Path) -> None:
        p = tmp_path / "tiny.rdc"
        p.write_bytes(b"\x00" * 2)  # 2 bytes < default min_size=4
        results = list(scan_directory(tmp_path, recursive=False, min_size=4))
        assert results == []

    def test_file_exactly_min_size_included(self, tmp_path: Path) -> None:
        p = tmp_path / "exact.rdc"
        p.write_bytes(b"\x00" * 4)
        results = list(scan_directory(tmp_path, recursive=False, min_size=4))
        assert len(results) == 1

    def test_mixed_extensions(self, tmp_path: Path) -> None:
        _make_rdc(tmp_path, "good.rdc")
        (tmp_path / "bad.rdc.bak").write_bytes(b"\x00" * 100)
        (tmp_path / "also.rdc2").write_bytes(b"\x00" * 100)
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 1
        assert results[0].name == "good.rdc"

    def test_deeply_nested_recursive(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        _make_rdc(deep, "deep.rdc")
        results = list(scan_directory(tmp_path, recursive=True))
        assert len(results) == 1

    def test_deduplication(self, tmp_path: Path) -> None:
        """Each resolved path is yielded at most once."""
        _make_rdc(tmp_path, "dup.rdc")
        results = list(scan_directory(tmp_path, recursive=False))
        assert len(results) == 1
