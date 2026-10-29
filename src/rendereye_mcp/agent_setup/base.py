"""Shared fail-closed configuration editing and transactional writes."""

from __future__ import annotations

import copy
import difflib
import json
import math
import os
import stat
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from . import json_edit


def same_values(left, right):
    """Compare values with their types, including valid TOML NaNs and dates."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same_values(left[k], right[k]) for k in left)
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(same_values(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and math.isnan(left) and math.isnan(right):
        return True
    return left == right


class Config(dict):
    """Parsed configuration with the exact source snapshot used for conflict checks."""

    def __init__(self, data, path, raw, jsonc=False):
        super().__init__(data)
        self.path = path.absolute()
        self.raw = raw
        self.original = copy.deepcopy(data)
        self.jsonc = jsonc


def read_bytes(path):
    if path.is_symlink():
        raise ValueError(f"Refusing symbolic-link configuration: {path}")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def atomic_write(path: Path, content: bytes, expected: bytes | None) -> None:
    """Keep an exclusive recovery backup and detect changes before replacement.

    The sidecar lock serializes our own writers. External editors do not honor it;
    the final snapshot check detects their edits up to the replacement boundary.
    """
    if read_bytes(path) != expected:
        raise ValueError(f"Configuration changed concurrently: {path}; retry")
    if content == expected:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".rendereye.lock")
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    tmp = None
    try:
        mode = stat.S_IMODE(path.stat().st_mode) if expected is not None else 0o600
        if not mode & stat.S_IWUSR:
            raise PermissionError(f"Configuration is read-only: {path}")
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        if read_bytes(path) != expected:
            raise ValueError(f"Configuration changed concurrently: {path}; retry")
        if expected is not None:
            # Never replace an earlier recovery snapshot.
            backup = path.with_suffix(path.suffix + ".bak")
            index = 0
            while True:
                try:
                    backup_fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    break
                except FileExistsError:
                    index += 1
                    backup = path.with_name(path.name + f".bak.{index}")
            with os.fdopen(backup_fd, "wb") as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
        if read_bytes(path) != expected:
            raise ValueError(f"Configuration changed concurrently: {path}; retry")
        os.replace(tmp, path)
        tmp = None
        if read_bytes(path) != content:
            # Never overwrite a possible subsequent external edit during rollback.
            raise OSError(f"Post-write verification failed: {path}; original is in its backup")
    finally:
        if tmp is not None:
            os.unlink(tmp)
        os.close(lock_fd)
        lock.unlink()


def read_json(path: Path, *, jsonc=False) -> dict:
    raw = read_bytes(path)
    data = {} if raw is None else json_edit.parse(raw.decode("utf-8-sig"), jsonc)
    return Config(data, path, raw, jsonc)


def write_json(path: Path, config: dict) -> None:
    """Compatibility helper with the same targeted mcpServers editing contract."""

    class JsonAdapter(AgentAdapter):
        def config_path(self, scope, project_path=None):
            return path

    JsonAdapter().write_config(path, config)


class AgentAdapter(ABC):
    NAME = ""
    SUPPORTS_USER_SCOPE = True
    SUPPORTS_PROJECT_SCOPE = True
    JSONC = False

    @abstractmethod
    def config_path(self, scope: str, project_path: Path | None = None) -> Path: ...

    def read_config(self, path: Path) -> dict:
        config = read_json(path, jsonc=self.JSONC)
        self._servers(config)
        return config

    def write_config(self, path: Path, config: dict) -> None:
        if (
            isinstance(config, Config)
            and same_values(config, config.original)
            and config.raw is None
        ):
            if read_bytes(path) is not None:
                raise ValueError(f"Configuration changed concurrently: {path}; retry")
            return
        content, expected = self.render(path, config)
        atomic_write(path, content, expected)

    def get_servers_key(self) -> list[str]:
        return ["mcpServers"]

    def build_server_entry(self, executable: Path) -> dict:
        entry = {"command": str(executable), "args": ["serve"]}
        if os.environ.get("RENDEREYE_ENV_FILE"):
            entry["env"] = {"RENDEREYE_ENV_FILE": os.environ["RENDEREYE_ENV_FILE"]}
        return entry

    def _servers(self, config, create=False):
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object/table")
        node = config
        for key in self.get_servers_key():
            if key not in node:
                if not create:
                    return {}
                node[key] = {}
            node = node[key]
            if not isinstance(node, dict):
                raise ValueError(f"{key} must be an object/table; configuration left intact")
        return node

    def apply(self, config, executable, force=False):
        result = copy.deepcopy(config)
        node = self._servers(result, create=True)
        desired = self.build_server_entry(executable)
        if "rendereye" in node:
            if node["rendereye"] == desired:
                return result, "unchanged"
            if not force:
                # Do not print existing env values or other potentially secret fields.
                current = node["rendereye"]
                command = (
                    current.get("command", "<non-stdio>")
                    if isinstance(current, dict)
                    else "<invalid>"
                )
                raise ValueError(
                    f"Rendereye entry conflict: current command {command!r}; "
                    f"proposed command {str(executable)!r}. Review with --force --dry-run; "
                    "use --force to replace only this entry."
                )
            node["rendereye"] = desired
            return result, "updated"
        node["rendereye"] = desired
        return result, "added"

    def remove(self, config, *, force=False):
        result = copy.deepcopy(config)
        node = self._servers(result)
        if "rendereye" not in node:
            return result, False
        entry = node["rendereye"]
        # Only recognize the generated stdio launch shape. Custom namesakes require force.
        command = entry.get("command", "") if isinstance(entry, dict) else ""
        recognized = (
            isinstance(command, str)
            and Path(command).name.lower() in ("rendereye-mcp", "rendereye-mcp.exe")
            and entry.get("args") == ["serve"]
            and entry.get("type", "stdio") == "stdio"
            and set(entry) <= {"command", "args", "type", "env"}
            and isinstance(entry.get("env", {}), dict)
            and set(entry.get("env", {})) <= {"RENDEREYE_ENV_FILE"}
        )
        if not recognized:
            if not force:
                raise ValueError(
                    "Unrecognized rendereye entry; review it before removal with --force"
                )
        del node["rendereye"]
        return result, True

    def render(self, path, config):
        if not isinstance(config, Config):
            # Direct callers still undergo the same preservation check.
            snapshot = self.read_config(path)
        else:
            snapshot = config
        if snapshot.path != path.absolute():
            raise ValueError("Configuration snapshot belongs to a different path")
        key = self.get_servers_key()[0]
        before = copy.deepcopy(snapshot.original)
        after = copy.deepcopy(dict(config))
        for value in (before, after):
            if key in value:
                if not isinstance(value[key], dict):
                    raise ValueError(f"{key} must be an object/table")
                value[key].pop("rendereye", None)
                if not value[key]:
                    del value[key]
        if not same_values(before, after):
            raise ValueError("Refusing changes outside the rendereye MCP entry")
        if same_values(config, snapshot.original) and snapshot.raw is not None:
            return snapshot.raw, snapshot.raw
        content = self.serialize(snapshot, config)
        if not same_values(self.parse(content.decode("utf-8-sig")), dict(config)):
            raise ValueError("Generated configuration failed semantic validation")
        return content, snapshot.raw

    def parse(self, text):
        return json_edit.parse(text, self.JSONC)

    def serialize(self, snapshot, config):
        if snapshot.raw is None:
            return (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode()
        text = snapshot.raw.decode("utf-8-sig")
        key = self.get_servers_key()[0]
        content = json_edit.edit(text, key, config.get(key, {}), self.JSONC).encode()
        if snapshot.raw.startswith(b"\xef\xbb\xbf"):
            content = b"\xef\xbb\xbf" + content
        return content

    def preview(self, path, config):
        content, expected = self.render(path, config)

        def focused(data):
            entry = self._servers(data).get("rendereye")
            if entry is None:
                return []
            if not isinstance(entry, dict):
                return ["<non-object entry>"]
            safe = {
                key: value if key in ("command", "args", "type") else "<redacted>"
                for key, value in entry.items()
            }
            return json.dumps({"rendereye": safe}, indent=2, ensure_ascii=False).splitlines()

        diff = difflib.unified_diff(
            focused(self.parse(expected.decode("utf-8-sig")) if expected is not None else {}),
            focused(self.parse(content.decode("utf-8-sig"))),
            fromfile=str(path),
            tofile=str(path) + " (proposed)",
            n=0,
        )
        print("\n".join(diff))
        print("Unrelated settings preserved: yes (validated)")

    def print_restart_instructions(self):
        print(f"  Restart {self.NAME} to apply the MCP configuration.")
