"""Validate version consistency and release artifacts.

Usage:
    # Check that pyproject.toml, __init__.py, and extension.json versions match
    python scripts/validate_release.py --check-versions

    # Validate that a git tag matches the package version
    python scripts/validate_release.py --tag v1.0.0

    # Validate contents of built release artifacts
    python scripts/validate_release.py --artifacts-dir dist/packages/ --version 1.0.0

    # All checks (for release workflow)
    python scripts/validate_release.py --check-versions --tag v1.0.0 --artifacts-dir dist/packages/ --version 1.0.0
"""

import argparse
import json
import sys
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SENSITIVE_PATTERNS = [
    ".env",
    "*.key",
    "*.pem",
    "*.p12",
    ".git/",
    "__pycache__",
    "*.pyc",
    ".venv/",
    "venv/",
    "node_modules/",
    "*.rdc",
    "*.db",
]

SENSITIVE_CONTENT_PATTERNS = [
    "password",
    "secret",
    "private_key",
    "api_key",
    "access_token",
]


def get_package_version() -> str:
    init_py = REPO_ROOT / "src" / "rendereye_mcp" / "__init__.py"
    for line in init_py.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip('"').strip("'")
    raise RuntimeError(f"__version__ not found in {init_py}")


def get_pyproject_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_extension_version() -> str:
    ext_json = REPO_ROOT / "extensions" / "rendereye" / "extension.json"
    data = json.loads(ext_json.read_text(encoding="utf-8"))
    return data["version"]


def check_versions() -> list[str]:
    errors: list[str] = []
    pkg_ver = get_package_version()
    pyproject_ver = get_pyproject_version()
    ext_ver = get_extension_version()

    print(f"  __init__.py:      {pkg_ver}")
    print(f"  pyproject.toml:   {pyproject_ver}")
    print(f"  extension.json:   {ext_ver}")

    if pkg_ver != pyproject_ver:
        errors.append(
            f"Version mismatch: __init__.py={pkg_ver!r} vs pyproject.toml={pyproject_ver!r}"
        )
    if pkg_ver != ext_ver:
        errors.append(
            f"Version mismatch: __init__.py={pkg_ver!r} vs extension.json={ext_ver!r}"
        )
    return errors


def check_tag(tag: str) -> list[str]:
    errors: list[str] = []
    if not tag.startswith("v"):
        errors.append(f"Tag {tag!r} does not start with 'v'")
        return errors

    tag_version = tag[1:]
    pkg_version = get_package_version()

    if tag_version != pkg_version:
        errors.append(
            f"Tag version {tag_version!r} does not match package version {pkg_version!r}"
        )
    else:
        print(f"  Tag {tag!r} matches package version {pkg_version!r}")
    return errors


def check_zip_safety(zip_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if ".." in name or name.startswith("/"):
                    errors.append(f"Unsafe path in {zip_path.name}: {name!r}")
    except zipfile.BadZipFile as e:
        errors.append(f"Invalid ZIP {zip_path.name}: {e}")
    return errors


def find_artifact(artifacts_dir: Path, name: str) -> Path | None:
    """Search for an artifact by name anywhere under artifacts_dir."""
    matches = list(artifacts_dir.rglob(name))
    return matches[0] if matches else None


def check_artifacts(artifacts_dir: Path, version: str) -> list[str]:
    errors: list[str] = []

    expected_files = [
        f"rendereye_mcp-{version}-py3-none-any.whl",
        f"rendereye_mcp-{version}.tar.gz",
        f"RenderEyeMCP-v{version}.zip",
        f"RenderEyeMCP-Extension-v{version}.zip",
        "SHA256SUMS.txt",
    ]

    found_paths: dict[str, Path] = {}
    for fname in expected_files:
        path = find_artifact(artifacts_dir, fname)
        if path is None:
            errors.append(f"MISSING artifact: {fname}")
        elif path.stat().st_size == 0:
            errors.append(f"EMPTY artifact: {fname}")
        else:
            found_paths[fname] = path
            print(f"  OK: {fname} ({path.stat().st_size:,} bytes)")

    # Validate ZIP archives
    for zip_name in [
        f"RenderEyeMCP-v{version}.zip",
        f"RenderEyeMCP-Extension-v{version}.zip",
    ]:
        zip_path = found_paths.get(zip_name)
        if zip_path:
            errors.extend(check_zip_safety(zip_path))

    # Validate extension ZIP contains required files
    ext_zip = found_paths.get(f"RenderEyeMCP-Extension-v{version}.zip")
    if ext_zip:
        with zipfile.ZipFile(ext_zip) as zf:
            names = set(zf.namelist())
            required_in_ext = [
                "__init__.py",
                "extension.json",
                "ipc_client.py",
                "gui_context.py",
                "state_observer.py",
            ]
            for fname in required_in_ext:
                matches = [n for n in names if n.endswith(fname)]
                if not matches:
                    errors.append(f"Extension ZIP missing: {fname}")

    # Validate bundle ZIP contains required structure
    bundle_zip = found_paths.get(f"RenderEyeMCP-v{version}.zip")
    if bundle_zip:
        with zipfile.ZipFile(bundle_zip) as zf:
            names = set(zf.namelist())
            required_in_bundle = [
                "python/",
                "renderdoc-extension/rendereye/__init__.py",
                "renderdoc-extension/rendereye/extension.json",
                "INSTALL-MANUAL.md",
                "README.md",
            ]
            for pattern in required_in_bundle:
                matches = [n for n in names if n.endswith(pattern.rstrip("/"))]
                if not matches and not any(n.startswith(pattern) for n in names):
                    errors.append(f"Bundle ZIP missing: {pattern}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RenderEyeMCP release")
    parser.add_argument(
        "--check-versions",
        action="store_true",
        help="Validate version consistency across source files",
    )
    parser.add_argument(
        "--tag",
        metavar="TAG",
        help="Validate that a git tag matches the package version (e.g. v1.0.0)",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        metavar="DIR",
        help="Directory containing release artifacts to validate",
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        help="Expected version string (required with --artifacts-dir)",
    )
    args = parser.parse_args()

    if not any([args.check_versions, args.tag, args.artifacts_dir]):
        parser.error("Specify at least one of: --check-versions, --tag, --artifacts-dir")

    errors: list[str] = []

    if args.check_versions:
        print("Checking version consistency...")
        errs = check_versions()
        errors.extend(errs)
        if not errs:
            print("  Version consistency: PASS")

    if args.tag:
        print(f"Checking tag {args.tag!r}...")
        errs = check_tag(args.tag)
        errors.extend(errs)
        if not errs:
            print("  Tag validation: PASS")

    if args.artifacts_dir:
        if not args.version:
            errors.append("--version is required when --artifacts-dir is specified")
        else:
            print(f"Checking artifacts in {args.artifacts_dir}...")
            if not args.artifacts_dir.exists():
                errors.append(f"Artifacts directory not found: {args.artifacts_dir}")
            else:
                errs = check_artifacts(args.artifacts_dir, args.version)
                errors.extend(errs)
                if not errs:
                    print("  Artifact validation: PASS")

    if errors:
        print("\nValidation FAILED:")
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        return 1

    print("\nAll validation checks PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
