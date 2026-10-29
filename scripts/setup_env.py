"""Setup the RenderEyeMCP environment configuration file.

Creates or updates the .env file in the installation directory,
auto-detects RenderDoc, and registers the RENDEREYE_ENV_FILE
user-level environment variable.

Usage:
    python scripts/setup_env.py [--install-dir <path>] [--uninstall]

This script is idempotent: re-running it preserves existing .env settings
and only updates unset or invalid values.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"


# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------


def get_default_install_dir() -> Path:
    """Return the platform default installation directory."""
    if platform.system() == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return Path(local_appdata) / "RenderEyeMCP"
        return Path.home() / "AppData" / "Local" / "RenderEyeMCP"
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg_config:
        return Path(xdg_config) / "rendereye_mcp"
    return Path.home() / ".config" / "rendereye_mcp"


# ---------------------------------------------------------------------------
# RenderDoc detection
# ---------------------------------------------------------------------------


def detect_renderdoc() -> str | None:
    """Return the absolute path to the RenderDoc GUI executable, or None."""
    if platform.system() == "Windows":
        prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        candidates = [
            Path(prog_files) / "RenderDoc" / "qrenderdoc.exe",
            Path(prog_files_x86) / "RenderDoc" / "qrenderdoc.exe",
            Path("D:/Programs/RenderDoc/qrenderdoc.exe"),
        ]
    else:
        candidates = [
            Path("/usr/bin/qrenderdoc"),
            Path("/usr/local/bin/qrenderdoc"),
            Path.home() / ".local" / "bin" / "qrenderdoc",
        ]

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except (OSError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# .env file management
# ---------------------------------------------------------------------------


def _read_env_values(path: Path) -> dict[str, str]:
    """Read key→value pairs from a .env file."""
    try:
        from dotenv import dotenv_values  # type: ignore[import]
        return {k: (v or "") for k, v in dotenv_values(path).items()}
    except Exception:
        pass
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _set_env_key(path: Path, key: str, value: str) -> None:
    """Set one key in a .env file, preserving all comments and other keys."""
    try:
        from dotenv import set_key  # type: ignore[import]
        set_key(str(path), key, value, quote_mode="auto")
        return
    except Exception:
        pass
    # Fallback: line-by-line replacement
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f'{key}="{value}"\n')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'{key}="{value}"\n')
    _atomic_write(path, "".join(new_lines))


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path via a temp file for crash safety."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        shutil.move(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Environment variable registration
# ---------------------------------------------------------------------------


def _register_env_var_windows(env_file: Path) -> bool:
    """Register RENDEREYE_ENV_FILE in the Windows User environment registry."""
    try:
        import winreg  # type: ignore[import]
    except ImportError:
        return False

    env_file_str = str(env_file)
    try:
        # Check for existing value
        try:
            rkey = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ
            )
            try:
                existing, _ = winreg.QueryValueEx(rkey, "RENDEREYE_ENV_FILE")
                if existing and existing != env_file_str:
                    print(
                        f"  Warning: RENDEREYE_ENV_FILE currently points to:\n"
                        f"    {existing}\n"
                        f"  Updating to:\n"
                        f"    {env_file_str}"
                    )
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(rkey)
        except OSError:
            pass

        wkey = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.SetValueEx(wkey, "RENDEREYE_ENV_FILE", 0, winreg.REG_SZ, env_file_str)
        finally:
            winreg.CloseKey(wkey)

        # Apply to current process immediately
        os.environ["RENDEREYE_ENV_FILE"] = env_file_str

        # Notify running applications of the environment change
        try:
            import ctypes  # type: ignore[import]
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                SMTO_ABORTIFHUNG, 5000, ctypes.byref(result),
            )
        except Exception:
            pass

        return True

    except Exception as exc:
        print(f"  Warning: registry write failed: {exc}")
        return False


def _unregister_env_var_windows(install_dir: Path) -> bool:
    """Remove RENDEREYE_ENV_FILE from the Windows User environment registry
    only when it points to this installation."""
    try:
        import winreg  # type: ignore[import]
    except ImportError:
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        )
        try:
            try:
                existing, _ = winreg.QueryValueEx(key, "RENDEREYE_ENV_FILE")
            except FileNotFoundError:
                print("  RENDEREYE_ENV_FILE is not registered — nothing to remove.")
                return True

            # Safety check: only remove if it belongs to this install
            try:
                Path(existing).relative_to(install_dir)
                belongs = True
            except ValueError:
                belongs = False

            if not belongs:
                print(
                    f"  RENDEREYE_ENV_FILE ({existing}) does not belong to {install_dir}.\n"
                    f"  Leaving it unchanged."
                )
                return False

            winreg.DeleteValue(key, "RENDEREYE_ENV_FILE")
            os.environ.pop("RENDEREYE_ENV_FILE", None)
            print(f"  Removed RENDEREYE_ENV_FILE (was: {existing})")
            return True
        finally:
            winreg.CloseKey(key)
    except Exception as exc:
        print(f"  Warning: registry operation failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main operations
# ---------------------------------------------------------------------------


def setup(install_dir: Path) -> None:
    """Create or update .env and register RENDEREYE_ENV_FILE."""
    print("RenderEyeMCP — environment setup")
    print(f"  Install directory: {install_dir}")

    install_dir.mkdir(parents=True, exist_ok=True)
    env_file = install_dir / ".env"

    is_first_install = not env_file.exists()

    if is_first_install:
        if _ENV_EXAMPLE.exists():
            shutil.copy2(_ENV_EXAMPLE, env_file)
        else:
            _atomic_write(
                env_file,
                "# RenderEyeMCP configuration\nRENDEREYE_RENDERDOC_EXE=\n",
            )
        print(f"  Created .env")
    else:
        print(f"  Existing .env found — preserving user settings")

    # Auto-detect RenderDoc when the path is unset or invalid
    existing = _read_env_values(env_file)
    existing_rdoc = existing.get("RENDEREYE_RENDERDOC_EXE", "")

    if not existing_rdoc:
        rdoc_path = detect_renderdoc()
        if rdoc_path:
            _set_env_key(env_file, "RENDEREYE_RENDERDOC_EXE", rdoc_path)
            print(f"  RenderDoc detected: {rdoc_path}")
        else:
            print(
                "  Warning: RenderDoc executable not found.\n"
                "  Set RENDEREYE_RENDERDOC_EXE manually in:"
            )
            print(f"    {env_file}")
    elif not Path(existing_rdoc).is_file():
        print(
            f"  Warning: Configured RenderDoc path does not exist:\n"
            f"    {existing_rdoc}\n"
            f"  Update RENDEREYE_RENDERDOC_EXE in {env_file}"
        )
    else:
        print(f"  RenderDoc: {existing_rdoc}")

    # Register RENDEREYE_ENV_FILE
    print()
    if platform.system() == "Windows":
        print("Registering RENDEREYE_ENV_FILE...")
        if _register_env_var_windows(env_file):
            print(f"  Registered: RENDEREYE_ENV_FILE={env_file}")
            print(
                "  Note: Already-running coding agents and IDEs must be restarted\n"
                "  to inherit the updated environment variable."
            )
        else:
            print("  Could not register via registry. Set it manually in PowerShell:")
            print(
                f"  [Environment]::SetEnvironmentVariable("
                f"'RENDEREYE_ENV_FILE', '{env_file}', 'User')"
            )
    else:
        print("Linux / macOS: Add to your shell profile (~/.profile or ~/.bashrc):")
        print(f'  export RENDEREYE_ENV_FILE="{env_file}"')
        print("  Then restart your terminal and coding agent.")

    print(f"\nConfiguration file: {env_file}")
    print("Setup complete.")


def uninstall(install_dir: Path) -> None:
    """Remove the RENDEREYE_ENV_FILE registration for this installation."""
    print("RenderEyeMCP — environment uninstall")
    print(f"  Install directory: {install_dir}")

    if platform.system() == "Windows":
        _unregister_env_var_windows(install_dir)
    else:
        print(
            "  Linux / macOS: Remove the RENDEREYE_ENV_FILE export from\n"
            "  your shell profile (~/.profile or ~/.bashrc) manually."
        )

    print(
        "\nNote: The .env file and application data have been preserved.\n"
        "Delete them manually if you want to remove all RenderEyeMCP data."
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Setup RenderEyeMCP environment configuration",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help=(
            "Installation directory where .env will be created "
            "(default: platform user-local directory)"
        ),
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the RENDEREYE_ENV_FILE registration for this installation",
    )
    args = parser.parse_args()

    install_dir = args.install_dir or get_default_install_dir()

    if args.uninstall:
        uninstall(install_dir)
    else:
        setup(install_dir)


if __name__ == "__main__":
    main()
