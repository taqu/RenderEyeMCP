"""Setup and uninstall commands for RenderEyeMCP.

Implements: rendereye-mcp setup / rendereye-mcp uninstall-setup

Reuses logic from scripts/setup_env.py and scripts/install_extension.py
but works from the installed package (no source checkout required).
"""

from __future__ import annotations

import os
import platform
import shutil
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Package resource access
# ---------------------------------------------------------------------------

_PKG_DIR = Path(__file__).parent
_EXT_DATA = _PKG_DIR / "_extension_data"
_ENV_EXAMPLE = _PKG_DIR / "env.example"


# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------


def get_default_install_dir() -> Path:
    """Return the platform-default configuration directory."""
    if platform.system() == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return Path(local_appdata) / "RenderEyeMCP"
        return Path.home() / "AppData" / "Local" / "RenderEyeMCP"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg) / "rendereye_mcp"
    return Path.home() / ".config" / "rendereye_mcp"


def get_extension_install_dir() -> Path:
    """Return the RenderDoc user extension directory."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "qrenderdoc" / "extensions" / "rendereye"
        return Path.home() / "AppData" / "Roaming" / "qrenderdoc" / "extensions" / "rendereye"
    xdg_data = os.environ.get("XDG_DATA_HOME", "")
    if xdg_data:
        return Path(xdg_data) / "qrenderdoc" / "extensions" / "rendereye"
    return Path.home() / ".local" / "share" / "qrenderdoc" / "extensions" / "rendereye"


# ---------------------------------------------------------------------------
# RenderDoc detection
# ---------------------------------------------------------------------------


def detect_renderdoc() -> str | None:
    """Return path to qrenderdoc.exe / qrenderdoc, or None if not found."""
    if platform.system() == "Windows":
        prog = os.environ.get("ProgramFiles", "C:\\Program Files")
        prog_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        candidates = [
            Path(prog) / "RenderDoc" / "qrenderdoc.exe",
            Path(prog_x86) / "RenderDoc" / "qrenderdoc.exe",
            Path("D:/Programs/RenderDoc/qrenderdoc.exe"),
        ]
    else:
        candidates = [
            Path("/usr/bin/qrenderdoc"),
            Path("/usr/local/bin/qrenderdoc"),
            Path.home() / ".local" / "bin" / "qrenderdoc",
        ]
    for c in candidates:
        try:
            if c.is_file():
                return str(c.resolve())
        except (OSError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# .env management
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        shutil.move(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_env_values(path: Path) -> dict[str, str]:
    try:
        from dotenv import dotenv_values
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
    try:
        from dotenv import set_key
        set_key(str(path), key, value, quote_mode="auto")
        return
    except Exception:
        pass
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


def _create_env(env_file: Path) -> bool:
    """Create .env from bundled template. Returns True if created, False if already existed."""
    if env_file.exists():
        return False
    if _ENV_EXAMPLE.exists():
        shutil.copy2(_ENV_EXAMPLE, env_file)
    else:
        _atomic_write(
            env_file,
            "# RenderEyeMCP configuration\nRENDEREYE_RENDERDOC_EXE=\n",
        )
    return True


# ---------------------------------------------------------------------------
# Windows registry
# ---------------------------------------------------------------------------


def _register_env_var_windows(env_file: Path) -> bool:
    try:
        import winreg
    except ImportError:
        return False
    env_file_str = str(env_file)
    try:
        try:
            rkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ)
            try:
                existing, _ = winreg.QueryValueEx(rkey, "RENDEREYE_ENV_FILE")
                if existing and existing != env_file_str:
                    print(f"  Warning: RENDEREYE_ENV_FILE currently points to:\n    {existing}")
                    print(f"  Updating to:\n    {env_file_str}")
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

        os.environ["RENDEREYE_ENV_FILE"] = env_file_str

        try:
            import ctypes
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
    try:
        import winreg
    except ImportError:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        )
        try:
            try:
                existing, _ = winreg.QueryValueEx(key, "RENDEREYE_ENV_FILE")
            except FileNotFoundError:
                print("  RENDEREYE_ENV_FILE is not registered — nothing to remove.")
                return True
            try:
                Path(existing).relative_to(install_dir)
                belongs = True
            except ValueError:
                belongs = False
            if not belongs:
                print(f"  RENDEREYE_ENV_FILE ({existing}) does not belong to {install_dir}.")
                print("  Leaving it unchanged.")
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
# Extension installation
# ---------------------------------------------------------------------------


def install_extension(dst: Path | None = None) -> bool:
    """Install the bundled RenderDoc extension. Returns True on success."""
    if dst is None:
        dst = get_extension_install_dir()

    if not _EXT_DATA.exists():
        print(f"  Error: bundled extension data not found at {_EXT_DATA}")
        return False

    dst.mkdir(parents=True, exist_ok=True)
    installed = []
    for src_file in _EXT_DATA.iterdir():
        if src_file.name.startswith("__pycache__"):
            continue
        if not src_file.is_file():
            continue
        if src_file.name == "rendereye_init.py":
            dst_name = "__init__.py"
        else:
            dst_name = src_file.name
        shutil.copy2(src_file, dst / dst_name)
        installed.append(dst_name)
    print(f"  Extension installed to: {dst}")
    print(f"  Files: {', '.join(sorted(installed))}")
    return True


def uninstall_extension(dst: Path | None = None) -> bool:
    """Remove the installed RenderDoc extension. Returns True if removed."""
    if dst is None:
        dst = get_extension_install_dir()
    if not dst.exists():
        print("  Extension not installed.")
        return True
    shutil.rmtree(dst)
    print(f"  Extension removed from: {dst}")
    return True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_setup(install_dir: Path) -> list[tuple[str, str, str]]:
    """Return list of (status, component, detail) tuples."""
    results = []
    env_file = install_dir / ".env"

    # Config directory
    if install_dir.exists():
        results.append(("PASS", "Config directory", str(install_dir)))
    else:
        results.append(("FAIL", "Config directory", f"Missing: {install_dir}"))

    # .env file
    if env_file.exists():
        results.append(("PASS", ".env file", str(env_file)))
    else:
        results.append(("FAIL", ".env file", f"Missing: {env_file}"))

    # RENDEREYE_ENV_FILE
    registered = os.environ.get("RENDEREYE_ENV_FILE", "")
    if registered:
        if Path(registered) == env_file:
            results.append(("PASS", "RENDEREYE_ENV_FILE", registered))
        else:
            results.append(("WARNING", "RENDEREYE_ENV_FILE", f"Points elsewhere: {registered}"))
    else:
        results.append(("WARNING", "RENDEREYE_ENV_FILE", "Not set in current process"))

    # RenderDoc exe
    if env_file.exists():
        vals = _read_env_values(env_file)
        rdoc = vals.get("RENDEREYE_RENDERDOC_EXE", "")
        if rdoc and Path(rdoc).is_file():
            results.append(("PASS", "RenderDoc executable", rdoc))
        elif rdoc:
            results.append(("WARNING", "RenderDoc executable", f"Configured but not found: {rdoc}"))
        else:
            results.append(("WARNING", "RenderDoc executable", "Not configured"))

    # Extension
    ext_dir = get_extension_install_dir()
    if ext_dir.exists() and (ext_dir / "__init__.py").exists():
        results.append(("PASS", "RenderDoc extension", str(ext_dir)))
    else:
        results.append(("FAIL", "RenderDoc extension", f"Not installed: {ext_dir}"))

    return results


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------


def run_setup(install_dir: Path | None = None, interactive: bool = True) -> None:
    """Run the setup command."""
    if install_dir is None:
        install_dir = get_default_install_dir()

    print("RenderEyeMCP — setup")
    print(f"  Configuration directory: {install_dir}")

    # Create directories
    for subdir in ("", "data", "logs"):
        d = install_dir / subdir if subdir else install_dir
        d.mkdir(parents=True, exist_ok=True)

    env_file = install_dir / ".env"
    created = _create_env(env_file)
    if created:
        print(f"  Created: {env_file}")
    else:
        print(f"  Existing .env preserved: {env_file}")

    # RenderDoc detection
    existing = _read_env_values(env_file)
    existing_rdoc = existing.get("RENDEREYE_RENDERDOC_EXE", "")

    if not existing_rdoc:
        rdoc_path = detect_renderdoc()
        if rdoc_path:
            _set_env_key(env_file, "RENDEREYE_RENDERDOC_EXE", rdoc_path)
            print(f"  RenderDoc detected: {rdoc_path}")
        else:
            print(f"  Warning: RenderDoc not found — set RENDEREYE_RENDERDOC_EXE in {env_file}")
    elif not Path(existing_rdoc).is_file():
        print(f"  Warning: RenderDoc path not found: {existing_rdoc}")
    else:
        print(f"  RenderDoc: {existing_rdoc}")

    # Install extension
    print()
    print("Installing RenderDoc extension...")
    install_extension()

    # Register environment variable
    print()
    if platform.system() == "Windows":
        print("Registering RENDEREYE_ENV_FILE...")
        if _register_env_var_windows(env_file):
            print(f"  Registered: RENDEREYE_ENV_FILE={env_file}")
            print(
                "  Note: Restart running coding agents and IDEs to inherit the updated variable."
            )
        else:
            print("  Could not register via registry. Set manually in PowerShell:")
            print(
                f"  [Environment]::SetEnvironmentVariable('RENDEREYE_ENV_FILE', '{env_file}', 'User')"
            )
    else:
        print("Add to your shell profile (~/.profile or ~/.bashrc):")
        print(f'  export RENDEREYE_ENV_FILE="{env_file}"')
        print("  Then restart your terminal and coding agent.")

    # Validation summary
    print()
    print("Setup summary:")
    for status, component, detail in validate_setup(install_dir):
        mark = "✓" if status == "PASS" else ("!" if status == "WARNING" else "✗")
        print(f"  [{mark}] {component}: {detail}")

    print()
    print("Setup complete. Run 'rendereye-mcp doctor' to verify.")


def run_uninstall(install_dir: Path | None = None) -> None:
    """Run the uninstall-setup command."""
    if install_dir is None:
        install_dir = get_default_install_dir()

    print("RenderEyeMCP — uninstall-setup")
    print(f"  Configuration directory: {install_dir}")

    # Remove extension
    print()
    print("Removing RenderDoc extension...")
    uninstall_extension()

    # Remove environment variable registration
    print()
    if platform.system() == "Windows":
        print("Removing RENDEREYE_ENV_FILE registration...")
        _unregister_env_var_windows(install_dir)
    else:
        print(
            "Linux/macOS: Remove the RENDEREYE_ENV_FILE export from your shell profile manually."
        )

    print()
    print(
        "Note: .env and application data have been preserved.\n"
        "Delete them manually to remove all RenderEyeMCP data:\n"
        f"  {install_dir}"
    )
    print()
    print(
        "To remove the application:\n"
        "  uv tool uninstall rendereye-mcp   (if installed with uv)\n"
        "  or delete the venv directory      (if installed with pip)"
    )
