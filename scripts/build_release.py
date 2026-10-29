"""Orchestrate the full release build: archives and packaging.

This script is called after 'uv build' and 'create_release_package.py' have run.
It creates the final distributable ZIP archives for GitHub Releases.

Usage:
    python scripts/build_release.py --create-archives --version 1.0.0
    python scripts/build_release.py --create-archives --version 1.0.0 --output-dir dist/packages
"""

import argparse
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DIST_DIR = REPO_ROOT / "dist"
PACKAGES_DIR = DIST_DIR / "packages"


def create_bundle_archive(version: str, packages_dir: Path) -> Path:
    bundle_dir = packages_dir / f"RenderEyeMCP-v{version}"
    if not bundle_dir.exists():
        raise FileNotFoundError(
            f"Bundle directory not found: {bundle_dir}\n"
            "Run 'python scripts/create_release_package.py' first."
        )

    archive_path = packages_dir / f"RenderEyeMCP-v{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(bundle_dir.rglob("*")):
            if file_path.is_file():
                arc_name = file_path.relative_to(bundle_dir)
                zf.write(file_path, arc_name)
    print(f"  Created: {archive_path.name} ({archive_path.stat().st_size:,} bytes)")
    return archive_path


def create_extension_archive(version: str, packages_dir: Path) -> Path:
    bundle_dir = packages_dir / f"RenderEyeMCP-v{version}"
    ext_src = bundle_dir / "renderdoc-extension"
    if not ext_src.exists():
        raise FileNotFoundError(
            f"Extension directory not found: {ext_src}\n"
            "Run 'python scripts/create_release_package.py' first."
        )

    archive_path = packages_dir / f"RenderEyeMCP-Extension-v{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ext_src.rglob("*")):
            if file_path.is_file():
                arc_name = file_path.relative_to(ext_src)
                zf.write(file_path, arc_name)
    print(f"  Created: {archive_path.name} ({archive_path.stat().st_size:,} bytes)")
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RenderEyeMCP release archives")
    parser.add_argument(
        "--create-archives",
        action="store_true",
        help="Create ZIP archives from the assembled release package",
    )
    parser.add_argument(
        "--version",
        required=True,
        metavar="VERSION",
        help="Release version (e.g. 1.0.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PACKAGES_DIR,
        metavar="DIR",
        help="Output directory for archives",
    )
    args = parser.parse_args()

    if not args.create_archives:
        parser.error("Specify --create-archives")

    packages_dir = args.output_dir
    packages_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building release archives for v{args.version}...")

    try:
        bundle_archive = create_bundle_archive(args.version, packages_dir)
        ext_archive = create_extension_archive(args.version, packages_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("\nRelease archives ready:")
    print(f"  {bundle_archive}")
    print(f"  {ext_archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
