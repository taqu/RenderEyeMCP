"""Install the RenderEye extension to the RenderDoc extension directory.

Usage: uv run python scripts/install_extension.py [--uninstall]
"""

import argparse
import os
import platform
import shutil
from pathlib import Path

EXTENSION_NAME = "rendereye"
EXTENSION_SRC = Path(__file__).parent.parent / "extensions" / "rendereye"


def get_extension_dir() -> Path:
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA not set")
        return Path(appdata) / "qrenderdoc" / "extensions" / EXTENSION_NAME
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "qrenderdoc" / "extensions" / EXTENSION_NAME


def install():
    dst = get_extension_dir()
    print(f"Installing to: {dst}")
    dst.mkdir(parents=True, exist_ok=True)

    for src_file in EXTENSION_SRC.iterdir():
        if src_file.name.startswith("__pycache__"):
            continue
        dst_file = dst / src_file.name
        shutil.copy2(src_file, dst_file)
        print(f"  Copied: {src_file.name}")
    print("Installation complete.")
    print("Enable via: RenderDoc -> Tools -> Manage Extensions -> RenderEyeMCP -> Enable")


def uninstall():
    dst = get_extension_dir()
    if not dst.exists():
        print("Extension not installed.")
        return
    shutil.rmtree(dst)
    print(f"Uninstalled from: {dst}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install/uninstall RenderEye extension")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if args.uninstall:
        uninstall()
    else:
        install()
