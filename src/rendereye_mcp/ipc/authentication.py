"""Per-server authentication token for local IPC security."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional

_TOKEN_LENGTH = 32  # bytes -> 64 hex chars


class AuthManager:
    """Manages the server-side auth token.

    Token is generated once per server run and stored in a temp file.
    Extensions read the token from the file to include in register_instance.
    """

    def __init__(self, token_path: Optional[Path] = None):
        self._token: Optional[str] = None
        self._token_path = token_path or self._default_token_path()

    @staticmethod
    def _default_token_path() -> Path:
        base = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))
        return base / "rendereye_mcp_token.txt"

    def generate(self) -> str:
        """Generate a new token, write to file, return it."""
        self._token = secrets.token_hex(_TOKEN_LENGTH)
        try:
            self._token_path.write_text(self._token, encoding="utf-8")
        except OSError:
            pass  # token path write failure is non-fatal
        return self._token

    def validate(self, token: str) -> bool:
        """Return True if token matches the generated token (constant-time compare)."""
        if self._token is None:
            return False
        return secrets.compare_digest(self._token, token)

    def get_token_path(self) -> Path:
        return self._token_path

    def cleanup(self) -> None:
        try:
            if self._token_path.exists():
                self._token_path.unlink()
        except OSError:
            pass

    @property
    def token(self) -> Optional[str]:
        return self._token
