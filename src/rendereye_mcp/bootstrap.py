from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def initialize_environment(env_file: Path | None = None) -> Path | None:
    """Load .env variables into os.environ before configuration initialization.

    Precedence:
    1. Explicit *env_file* argument (programmatic override / testing).
    2. RENDEREYE_ENV_FILE environment variable (installer-managed).
    3. CWD/.env fallback (development convenience — silent if absent).

    Returns the Path that was loaded, or None when no file was loaded.
    Raises ValueError when an explicitly specified path is not absolute.
    Raises FileNotFoundError when an explicitly specified file does not exist.
    """
    if env_file is not None:
        return _load_explicit(Path(env_file))

    env_path_str = os.environ.get("RENDEREYE_ENV_FILE")
    if env_path_str:
        return _load_explicit(Path(env_path_str).expanduser())

    # Dev fallback: load CWD/.env when present, silently skip when absent.
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        load_dotenv(dotenv_path=cwd_env, override=False)
        return cwd_env

    return None


def _load_explicit(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError(
            f"RENDEREYE_ENV_FILE must be an absolute path, got: {path}"
        )
    if not path.is_file():
        raise FileNotFoundError(f"Environment file not found: {path}")
    load_dotenv(dotenv_path=path, override=False)
    return path
