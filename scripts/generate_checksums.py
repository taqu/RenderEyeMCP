"""Generate SHA-256 checksums for release artifacts.

Usage:
    python scripts/generate_checksums.py file1.whl file2.tar.gz --output SHA256SUMS.txt
    python scripts/generate_checksums.py --dir dist/packages/ --output SHA256SUMS.txt
    python scripts/generate_checksums.py dist/*.whl dist/*.tar.gz --output checksums.txt
"""

import argparse
import hashlib
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_checksums(files: list[Path], output: Path) -> int:
    if not files:
        print("No files to checksum.", file=sys.stderr)
        return 1

    lines: list[str] = []
    errors: list[str] = []

    for path in sorted(files):
        if not path.exists():
            errors.append(f"File not found: {path}")
            continue
        if not path.is_file():
            continue
        digest = sha256_file(path)
        lines.append(f"{digest}  {path.name}")
        print(f"  {digest}  {path.name}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nChecksums written to: {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SHA-256 checksums")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to checksum",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        metavar="DIR",
        help="Directory of files to checksum (*.whl, *.tar.gz, *.zip)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("SHA256SUMS.txt"),
        metavar="FILE",
        help="Output checksum file (default: SHA256SUMS.txt)",
    )
    args = parser.parse_args()

    files: list[Path] = list(args.files)

    if args.dir:
        if not args.dir.exists():
            print(f"ERROR: Directory not found: {args.dir}", file=sys.stderr)
            return 1
        for pattern in ("*.whl", "*.tar.gz", "*.zip"):
            files.extend(args.dir.glob(pattern))

    if not files:
        parser.error("Provide files as arguments or use --dir")

    return generate_checksums(files, args.output)


if __name__ == "__main__":
    sys.exit(main())
