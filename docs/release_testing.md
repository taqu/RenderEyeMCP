# Release testing record — v1.0.0 (Phase 12)

Date: 2026-10-29. Supersedes the Phase 5 record (still in git history).

## Environment

| Item | Value |
|------|-------|
| OS | Windows 11 Pro 10.0.26300 (development machine, not a clean VM) |
| Console code page | cp932 (Japanese) |
| Python | 3.11 (project venv), 3.12.6 (clean-venv install test) |
| uv | 0.12.6 |
| RenderDoc | 1.46 (installed outside `Program Files`), embedded Python 3.8 |
| Capture | Proprietary D3D12 game capture, 2,370 events / 533 draws / 17 dispatches, NVIDIA |
| Agents | Claude Code (`claude` CLI), Codex CLI |

## Automated checks

| Check | Command | Result |
|-------|---------|--------|
| Unit/integration tests | `uv run pytest tests` | **938 passed, 67 skipped** with a built release bundle in `dist/` (932 passed / 73 skipped without it). Remaining skips need RenderDoc's `renderdoc` module |
| Lint | `uv run ruff check src/ tests/` | Clean (was 106 findings) |
| Documentation | `uv run python scripts/check_docs.py` | Pass: links, anchors, 14 EN/JA page pairs |
| Build | `uv build` | wheel + sdist |
| Distribution metadata | `uvx twine check dist/*` | Pass |
| Version consistency | `scripts/validate_release.py --check-versions` | Pass (1.0.0 everywhere) |
| Release bundle | `create_release_package.py`, `build_release.py --create-archives`, `generate_checksums.py` | Pass |
| Artifact validation | `validate_release.py --artifacts-dir ... --version 1.0.0` | Pass (5 artifacts) |
| GitHub Actions CI | — | **Not run** (changes not pushed) |

## Installation

| Scenario | Result |
|----------|--------|
| `uv tool install .` into isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` | Pass |
| `uv tool install <wheel>` (isolated) | Pass |
| Fresh `py -3.12 -m venv` + `pip install <wheel>` (no uv) | Pass; `--version`, `--help` |
| `setup` with redirected `%LOCALAPPDATA%`/`%APPDATA%`, registry write stubbed, run twice | Pass: `.env` created, then preserved; RenderDoc detected; 6 extension files |
| `setup-agent claude-code/codex --scope project` from the clean venv | Pass after fix (previously wrote the dev checkout's executable) |
| `doctor` | 9 PASS, 1 WARNING (no service running) |
| RenderDoc in standard / custom / missing location | Custom location detected; **standard and missing locations not tested on a real machine** (covered by unit tests) |
| Clean Windows VM | **Not performed** |

## Agent configuration

| Agent | Evidence | Result |
|-------|----------|--------|
| Claude Code | `tests/test_phase5_7_agent_safety.py::test_installed_client_loads_isolated_config[claude]` — real `claude mcp get rendereye` against a generated `.mcp.json` | `Connected` |
| Codex | Same test, `[codex]` — real `codex mcp list --json` | Listed, other servers preserved |
| MCP stdio | Python MCP client → `rendereye-mcp serve` | 38 tools; tool calls return data and image content |
| Cursor / VS Code / Gemini | Fixture tests only | Not verified with real clients |

## Live inspection scenarios

Selection for B–F was set with a `qrenderdoc --python` startup script
(`SetEventID`), not by clicking.

| # | Scenario | Event | Result |
|---|----------|-------|--------|
| 1 | Active capture discovery (sessions, current capture, capture info) | — | Pass |
| 2 | Selected event inspection | GUI-click selection | **Fail/unresolved:** extension reported the post-load event (see readiness blocker 1) |
| 2b | Selected event inspection | Draw EID 1039 (API selection) | Pass |
| 3 | Pipeline state, all sections | Draw EID 7467 | Pass after Descriptor fix |
| 4 | Shader/resource inspection (reflection, bindings, disassembly, source) | Draw EID 7467, Dispatch EID 888 | Pass |
| 5 | Render target, pixel values, statistics, histogram, PNG | Draw EID 7467 | Pass after fixes |
| 6 | Compute dispatch: dimensions, CS bindings, cbuffer decode | Dispatch EID 888 | Pass |
| 7 | Error paths: bad resource, bad section, bad instance, oversize buffer read, oversize image | — | Pass |
| 8 | RenderDoc closed and restarted while the service runs | — | Pass: old session listed `disconnected` with `last_known_capture`, new window registered as a new connected session |

Not run live: two agents simultaneously, managed-window tools (`capture_open`,
`session_*`), service restart while RenderDoc stays open, Linux, non-D3D12 APIs.
