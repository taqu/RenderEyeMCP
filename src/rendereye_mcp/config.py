"""Configuration dataclass with defaults and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_IPC_TRANSPORTS = {"tcp"}


@dataclass
class CaptureDirectoryConfig:
    """Configuration for a single capture watch directory."""

    path: str
    recursive: bool = False


@dataclass
class CaptureConfig:
    """Configuration for capture discovery and registry."""

    enabled: bool = True
    recursive: bool = False
    scan_interval_seconds: float = 10.0
    readiness_stability_seconds: float = 2.0
    directories: list[CaptureDirectoryConfig] = field(default_factory=list)
    max_file_size_bytes: int = 0  # 0 = no limit
    min_file_size_bytes: int = 4  # minimum .rdc size


@dataclass
class Config:
    """RenderEyeMCP configuration.

    All fields can be overridden via environment variables with the
    ``RENDEREYE_`` prefix (e.g. ``RENDEREYE_IPC_PORT=37021``).
    """

    renderdoc_exe: str = "C:/Program Files/RenderDoc/qrenderdoc.exe"
    ipc_transport: str = "tcp"
    ipc_host: str = "127.0.0.1"
    ipc_port: int = 37020
    connection_timeout: float = 10.0
    log_level: str = "INFO"
    extension_path: str = ""
    storage_path: str = ""
    capture: CaptureConfig = field(default_factory=CaptureConfig)

    # Internal mutable state — not a constructor parameter
    _active_connections: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.log_level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log_level {self.log_level!r}. "
                f"Must be one of {sorted(_VALID_LOG_LEVELS)}."
            )
        if self.ipc_transport not in _VALID_IPC_TRANSPORTS:
            raise ValueError(
                f"Invalid ipc_transport {self.ipc_transport!r}. "
                f"Must be one of {sorted(_VALID_IPC_TRANSPORTS)}."
            )
        if not (1 <= self.ipc_port <= 65535):
            raise ValueError(
                f"Invalid ipc_port {self.ipc_port}. Must be between 1 and 65535."
            )
        if self.connection_timeout <= 0:
            raise ValueError(
                f"Invalid connection_timeout {self.connection_timeout}. Must be > 0."
            )

    @classmethod
    def from_env(cls) -> "Config":
        """Create a Config, overriding defaults from RENDEREYE_* environment variables."""
        kwargs: dict = {}

        _str_keys = ["renderdoc_exe", "ipc_transport", "ipc_host", "log_level", "extension_path", "storage_path"]
        _int_keys = ["ipc_port"]
        _float_keys = ["connection_timeout"]

        for key in _str_keys:
            env_key = f"RENDEREYE_{key.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                kwargs[key] = val

        for key in _int_keys:
            env_key = f"RENDEREYE_{key.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                try:
                    kwargs[key] = int(val)
                except ValueError:
                    raise ValueError(
                        f"Environment variable {env_key}={val!r} is not a valid integer."
                    )

        for key in _float_keys:
            env_key = f"RENDEREYE_{key.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                try:
                    kwargs[key] = float(val)
                except ValueError:
                    raise ValueError(
                        f"Environment variable {env_key}={val!r} is not a valid float."
                    )

        # Build CaptureConfig from RENDEREYE_CAPTURE_* env vars
        capture_kwargs: dict = {}

        _capture_enabled = os.environ.get("RENDEREYE_CAPTURE_ENABLED")
        if _capture_enabled is not None:
            capture_kwargs["enabled"] = _capture_enabled.lower() not in ("0", "false", "no")

        _capture_scan = os.environ.get("RENDEREYE_CAPTURE_SCAN_INTERVAL")
        if _capture_scan is not None:
            try:
                capture_kwargs["scan_interval_seconds"] = float(_capture_scan)
            except ValueError:
                raise ValueError(
                    f"Environment variable RENDEREYE_CAPTURE_SCAN_INTERVAL={_capture_scan!r} "
                    f"is not a valid float."
                )

        _capture_stability = os.environ.get("RENDEREYE_CAPTURE_STABILITY_SECONDS")
        if _capture_stability is not None:
            try:
                capture_kwargs["readiness_stability_seconds"] = float(_capture_stability)
            except ValueError:
                raise ValueError(
                    f"Environment variable RENDEREYE_CAPTURE_STABILITY_SECONDS={_capture_stability!r} "
                    f"is not a valid float."
                )

        _capture_dirs = os.environ.get("RENDEREYE_CAPTURE_DIRS")
        if _capture_dirs:
            dirs = []
            # os.pathsep: ";" on Windows (drive letters contain ":"), ":" elsewhere.
            for p in _capture_dirs.split(os.pathsep):
                p = p.strip()
                if p:
                    dirs.append(CaptureDirectoryConfig(path=p))
            capture_kwargs["directories"] = dirs

        if capture_kwargs:
            kwargs["capture"] = CaptureConfig(**capture_kwargs)

        return cls(**kwargs)
