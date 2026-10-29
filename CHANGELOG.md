# Changelog

All notable changes to RenderEyeMCP are documented in this file.

## [1.0.0] — Unreleased (Phase 12: release preparation)

No tag or release has been published yet; earlier 1.0.0 entries below describe work
merged before Phase 12. Draft notes: [docs/release_notes_v1.0.md](docs/release_notes_v1.0.md).

### Added

- Bilingual documentation: `README.md` / `README.ja.md`, `docs/en/` and `docs/ja/`
  (installation, configuration, quick start, tool reference, troubleshooting,
  architecture, prompt examples, six debugging scenarios).
- `CONTRIBUTING.md`, `SECURITY.md`, GitHub issue templates.
- `scripts/check_docs.py` (links, anchors, EN/JA parity) — run in CI and in `tests/test_docs.py`.
- Package metadata: MIT license expression, license file, project URLs.
- Release bundle includes `README.ja.md`, `LICENSE` and the `docs/` tree.

### Fixed

- RenderDoc 1.46: render/depth targets read from `Descriptor.resource`; `TextureSave`
  slice/sample mapping; six-argument `GetHistogram`.
- IPC message limit raised to 16 MiB with matching stream limits; oversized replies
  return `result_too_large` instead of hanging until timeout.
- `get_pixel_value` exposes `coords` through MCP.
- `image_too_large` no longer suggests a mip that does not fit.
- `RENDEREYE_CAPTURE_DIRS` split on `os.pathsep`.
- `setup-agent` prefers the invoked executable / running environment over `PATH`.
- CLI tolerates non-UTF-8 consoles; `service status` detects stale ready files and
  `service stop` removes them.
- Ruff findings (106) resolved; real-client Claude Code test made locale- and
  approval-independent.

### Changed

- Removed superseded docs: `docs/installation.md`, `docs/installation-manual.md`,
  `docs/mcp_api.md`, `docs/troubleshooting.md`, `docs/architecture.md`, `docs/agents/`.
- `.mcp.json` (development) no longer contains a machine-specific path.

## [1.0.0] — 2026-10-24 (Phase 5 + Phase 5.1 + Phase 5.2)

### Added (Phase 5.2 — GitHub Actions CI/CD & Automated GitHub Releases)

- `.github/workflows/ci.yml` — CI workflow: lint, test matrix (Windows + Linux, Python 3.11/3.12), package build check, and clean-install verification without `uv`.
- `.github/workflows/release.yml` — Release workflow: version validation, full test matrix, artifact build, verification, and GitHub Release publishing triggered by version tags (`v*.*.*`). Supports dry-run via `workflow_dispatch` with `publish: false`.
- `scripts/validate_release.py` — validates version consistency (`__init__.py`, `pyproject.toml`, `extension.json`), validates git tag against package version, and checks release artifact contents and structure.
- `scripts/build_release.py` — creates distributable ZIP archives from the assembled release package (`RenderEyeMCP-v{version}.zip` and `RenderEyeMCP-Extension-v{version}.zip`).
- `scripts/generate_checksums.py` — generates `SHA256SUMS.txt` for all release artifacts.
- `docs/releasing.md` — complete release guide covering versioning policy, dry-run instructions, publication procedure, artifact verification, rollback/recovery, and CI security.

---

## [1.0.0] — 2026-10-24 (Phase 5 + Phase 5.1)

### Added

- **Phase 5 reliability hardening** across all subsystems.
- 14 new regression tests covering Phase 5 fixes (`tests/test_phase5_reliability.py`).
- IPC transport connection limit (64 maximum concurrent connections) to prevent unbounded resource growth.
- `docs/release_readiness.md` — baseline audit, gap classification, and remediation status.
- `docs/release_testing.md` — acceptance test matrix and real-RenderDoc validation record.
- `docs/troubleshooting.md` — diagnostic guide for common operational failures.
- `docs/release_notes_v1.0.md` — v1.0.0 release notes.
- `docs/mcp_api.md` — complete MCP tool reference.
- `CHANGELOG.md` — this file.
- **Phase 5.1 — Manual Installation Support:**
  - `docs/installation-manual.md` — comprehensive manual installation guide (Windows + Linux, pip/venv, no uv required).
  - `examples/` — agent configuration examples for Claude Code, Cursor, VS Code, OpenAI Codex CLI, Gemini CLI.
  - `scripts/create_release_package.py` — assembles the manual-installation-friendly release package.
  - `dist/packages/RenderEyeMCP-v1.0.0/` — release package with wheel, extension, and examples.
  - 32 new packaging tests (`tests/test_phase5_1_packaging.py`).
  - Updated `README.md` to document all three installation methods.
  - Updated `docs/development.md` to clarify developer vs. end-user setup.
  - Fixed RenderDoc discovery to probe `C:\Program Files\RenderDoc\` before developer-specific paths.

### Fixed

- **Race condition in `CaptureRegistry._schedule_from_thread`** — snapshot the event-loop reference before the `is_running()` check to prevent a TOCTOU race between the watcher thread and asyncio shutdown. `RuntimeError` from a concurrently closed loop is now caught and logged.
- **`_poll_for_window` does not detect process death** — the polling loop now checks `InstanceStatus.EXITED` on each iteration and returns `None` immediately when the target process has exited, rather than waiting for the full timeout.
- **`_resolve_capture` accepts non-ready captures** — the method now enforces `CaptureStatus.READY`. Captures in `DISCOVERED`, `PENDING`, `MISSING`, `INACCESSIBLE`, or `INVALID` states are refused with a log warning, preventing RenderDoc from attempting to open incomplete or invalid files.
- **Missing transaction rollback in `CaptureStorage.upsert_capture`** — wrapped the execute/commit pair in try/except/rollback so that any exception during the commit phase is properly rolled back and re-raised.
- **Missing transaction rollback in `SessionStorage.upsert_session`** — same fix applied to session persistence.
- **4 ruff import-ordering violations** in test files — auto-corrected with `ruff --fix`.
- **Test mock `mock_capture.status.value = "ready"`** — corrected to `mock_capture.status = CaptureStatus.READY` so that the enum identity comparison in `_resolve_capture` works correctly.

### Changed

- Version bumped from `0.1.0` to `1.0.0`.
- Extension `extension.json` version updated to `1.0.0`.

---

## [0.1.0] — initial development

Phase 0–4 implementation: MCP server foundation, Capture Registry, Instance and Session Manager, RenderDoc Extension, IPC connection management, and async operation tracking.
