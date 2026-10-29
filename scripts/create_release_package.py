"""Create a manual-installation-friendly release package.

Usage:
    python scripts/create_release_package.py
    python scripts/create_release_package.py --output-dir dist/packages

Produces:
    dist/packages/RenderEyeMCP-v<version>/
        python/
            rendereye_mcp-<version>-py3-none-any.whl
        renderdoc-extension/
            rendereye/
                __init__.py
                extension.json
                ipc_client.py
                gui_context.py
                state_observer.py
        examples/
            claude-code/
            cursor/
            vscode/
            codex/
            gemini/
        docs/                (user documentation: en/, ja/ and reference pages)
        INSTALL-MANUAL.md    (points to docs/en/installation.md and docs/ja/installation.md)
        README.md
        README.ja.md
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXTENSION_SRC = REPO_ROOT / "extensions" / "rendereye"
EXAMPLES_SRC = REPO_ROOT / "examples"
DOCS_SRC = REPO_ROOT / "docs"
DIST_SRC = REPO_ROOT / "dist"


_INSTALL_POINTER = """# RenderEyeMCP {version} — Installation

[English](docs/en/installation.md) | [日本語](docs/ja/installation.md)

The wheel is in `python/`. Install it with either:

    uv tool install python/rendereye_mcp-{version}-py3-none-any.whl
    python -m pip install python/rendereye_mcp-{version}-py3-none-any.whl   (inside a venv)

then run `rendereye-mcp setup` and follow docs/en/installation.md
(日本語: docs/ja/installation.md).
"""


def get_version() -> str:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from rendereye_mcp import __version__

    return __version__


def find_wheel(version: str) -> Path:
    wheel = DIST_SRC / f"rendereye_mcp-{version}-py3-none-any.whl"
    if not wheel.exists():
        raise FileNotFoundError(
            f"Wheel not found: {wheel}\nRun 'python -m build --wheel' first."
        )
    return wheel


def create_package(output_dir: Path) -> Path:
    version = get_version()
    wheel = find_wheel(version)

    pkg_dir = output_dir / f"RenderEyeMCP-v{version}"
    if pkg_dir.resolve().parent != output_dir.resolve():
        raise ValueError("Package target must remain directly inside the output directory")
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True)

    # python/
    py_dir = pkg_dir / "python"
    py_dir.mkdir()
    shutil.copy2(wheel, py_dir / wheel.name)
    print(f"  [python] {wheel.name}")

    # renderdoc-extension/rendereye/
    ext_dst = pkg_dir / "renderdoc-extension" / "rendereye"
    ext_dst.mkdir(parents=True)
    for f in EXTENSION_SRC.iterdir():
        if f.name.startswith("__pycache__") or f.suffix == ".pyc":
            continue
        if f.is_file():
            shutil.copy2(f, ext_dst / f.name)
            print(f"  [extension] {f.name}")

    # examples/
    if EXAMPLES_SRC.exists():
        shutil.copytree(EXAMPLES_SRC, pkg_dir / "examples")
        print(f"  [examples] {len(list(EXAMPLES_SRC.rglob('*')))} files")

    # docs/ (README links resolve inside the package; phase work notes are excluded)
    shutil.copytree(DOCS_SRC, pkg_dir / "docs", ignore=shutil.ignore_patterns("work"))
    print(f"  [docs] {len(list((pkg_dir / 'docs').rglob('*.md')))} pages")

    # INSTALL-MANUAL.md: stable entry point for the release ZIP
    (pkg_dir / "INSTALL-MANUAL.md").write_text(_INSTALL_POINTER.format(version=version), encoding="utf-8")
    print("  [docs] INSTALL-MANUAL.md")

    for name in ("README.md", "README.ja.md", "LICENSE"):
        source = REPO_ROOT / name
        if source.exists():
            shutil.copy2(source, pkg_dir / name)
            print(f"  [docs] {name}")

    print(f"\nRelease package created: {pkg_dir}")
    return pkg_dir


def verify_package(pkg_dir: Path) -> bool:
    errors: list[str] = []

    required = [
        "python",
        "renderdoc-extension/rendereye/__init__.py",
        "renderdoc-extension/rendereye/extension.json",
        "renderdoc-extension/rendereye/ipc_client.py",
        "renderdoc-extension/rendereye/gui_context.py",
        "renderdoc-extension/rendereye/gui_dispatcher.py",
        "renderdoc-extension/rendereye/state_observer.py",
        "examples/claude-code/mcp-config.json",
        "examples/cursor/mcp.json",
        "examples/vscode/mcp.json",
        "examples/codex/config.toml",
        "examples/gemini/settings.json",
        "INSTALL-MANUAL.md",
        "README.md",
        "README.ja.md",
        "LICENSE",
        "docs/en/installation.md",
        "docs/ja/installation.md",
    ]

    for rel in required:
        path = pkg_dir / rel
        if not path.exists():
            errors.append(f"MISSING: {rel}")

    # Check no wheel for wrong version
    wheels = list((pkg_dir / "python").glob("*.whl"))
    if not wheels:
        errors.append("MISSING: python/*.whl")

    # Check no developer-specific paths in config examples
    dev_paths = ["D:/Programs", "D:\\Programs", "/home/taqu", "taqu_"]
    for example_file in (pkg_dir / "examples").rglob("*"):
        if example_file.is_file() and example_file.suffix in (".json", ".toml"):
            text = example_file.read_text(encoding="utf-8")
            for pat in dev_paths:
                if pat in text:
                    errors.append(f"DEV PATH in {example_file.relative_to(pkg_dir)}: {pat!r}")

    if errors:
        print("\nPackage verification FAILED:")
        for e in errors:
            print(f"  {e}")
        return False

    print("\nPackage verification PASSED.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Create RenderEyeMCP release package")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DIST_SRC / "packages",
        help="Output directory for the release package",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        pkg_dir = create_package(output_dir)
        ok = verify_package(pkg_dir)
        return 0 if ok else 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
