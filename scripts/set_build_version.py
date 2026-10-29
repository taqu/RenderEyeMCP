"""Inject a build version into source files without committing.

Updates pyproject.toml [project].version and src/rendereye_mcp/__init__.py
__version__ to the supplied version string. Intended for CI test builds where
the package version must differ from the static version stored in the repository.

Does NOT modify extensions/rendereye/extension.json — that file is not included
in the Python wheel or source distribution.
Does NOT commit changes.

Usage:
    python scripts/set_build_version.py 1.0.0.dev1
    python scripts/set_build_version.py 1.0.0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tomlkit

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT_PY = REPO_ROOT / "src" / "rendereye_mcp" / "__init__.py"


def _validate_version(version: str) -> None:
    """Raise ValueError if version is not a plausible PEP 440 string."""
    try:
        from packaging.version import Version, InvalidVersion
        Version(version)
    except ImportError:
        # packaging not available — accept any non-empty string
        if not version or not version[0].isdigit():
            raise ValueError(f"Version {version!r} does not look like a PEP 440 version")
    except Exception:
        raise ValueError(f"Version {version!r} is not a valid PEP 440 version")


def set_pyproject_version(version: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    doc = tomlkit.loads(text)
    old = doc["project"]["version"]
    doc["project"]["version"] = version
    PYPROJECT.write_text(tomlkit.dumps(doc), encoding="utf-8")
    print(f"  pyproject.toml: {old!r} -> {version!r}")


def set_init_version(version: str) -> None:
    lines = INIT_PY.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    changed = False
    for line in lines:
        if line.startswith("__version__"):
            old = line.strip()
            line = f'__version__ = "{version}"\n'
            print(f"  __init__.py: {old!r} -> {line.strip()!r}")
            changed = True
        new_lines.append(line)
    if not changed:
        raise RuntimeError(f"__version__ not found in {INIT_PY}")
    INIT_PY.write_text("".join(new_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set the build version in pyproject.toml and __init__.py (no commit)."
    )
    parser.add_argument("version", help="PEP 440 version string (e.g. 1.0.0.dev1)")
    args = parser.parse_args()

    try:
        _validate_version(args.version)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Setting build version to {args.version!r}:")
    set_pyproject_version(args.version)
    set_init_version(args.version)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
