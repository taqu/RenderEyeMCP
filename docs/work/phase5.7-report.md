# Phase 5.7 implementation and verification report

Date: 2026-10-28. Environment: Windows, Python 3.11.6, tomlkit 0.15.2.
Status: **implementation complete; real-client compatibility partially verified**.
No GitHub Release was published. No real user agent configuration was modified by
the new safety, client or wheel verification tests.

## Root cause and reproduction

The original `agent_setup/codex.py` parsed TOML to dictionaries, then rebuilt the
whole file using a handwritten shallow writer. `_format_toml_value()` fell through
to `str(v)` for dictionaries. The outer writer emitted nested project keys without
TOML quoting, yielding unquoted Windows paths and Python dictionary representations.
It also discarded comments and could move settings into incorrect table contexts.
`_read_toml()` swallowed parsing errors and returned `{}`, enabling later writes to
replace malformed files with a minimal server configuration. The shared JSON
reader did the same on parse or read errors, exposing all JSON adapters to data loss.

The launcher resolver trusted any absolute existing `sys.argv[0]`, so module
invocation could write `__main__.py` as the executable. Existing entries were replaced
without enforcing a conflict policy. VS Code user scope incorrectly targeted a
project `.mcp.json`, and new workspace files could receive `mcpServers` instead of
`servers`. Direct writers lacked concurrent modification detection.

Reproduction used the original writer from `git show HEAD:src/rendereye_mcp/agent_setup/codex.py`
on the synthetic `tests/fixtures/agents/codex.toml`. Observed: dictionary repr present,
unquoted Windows project key present, and `tomllib` failed with:
`Expected '=' after a key in a key/value pair (at line 6, column 17)`.
This exercised the old implementation, not a speculative reimplementation.

## Components and files changed

- `src/rendereye_mcp/agent_setup/base.py`: snapshots, semantic preservation checks,
  targeted JSON edits, conflict/removal policy, previews, backups and atomic writes.
- `src/rendereye_mcp/agent_setup/json_edit.py`: JSON/JSONC parsing and member offsets;
  duplicate keys and invalid constants are refused; surrounding text is retained.
- `src/rendereye_mcp/agent_setup/codex.py`: lossless TOML editing with tomlkit and
  independent tomllib validation; user home override and trusted-project scope.
- `claude_code.py`, `cursor.py`, `gemini.py`, `vscode.py`: shared safety implementation,
  corrected schema/paths, and format-specific comment handling.
- `agent_setup/__init__.py`, `cli.py`, `doctor.py`: launcher restrictions, aliases,
  one workflow for single/all/interactive setup, error exit status and diagnostics.
- `pyproject.toml`, `uv.lock`: runtime tomlkit dependency. End users do not need uv.
- `tests/test_phase5_7_agent_safety.py`, `tests/fixtures/agents/*`: safety and integration
  regressions for all five adapters. Legacy adapter expectations were corrected in
  `test_phase5_4_agent_setup.py`. Older server startup tests in
  `test_phase5_1_packaging.py` now isolate .env, storage, token location and IPC port.
- `scripts/verify_agent_config_wheel.py`: reproducible built-wheel adapter verification.
- README, installation, troubleshooting, all five agent guides, and
  `docs/agent_configuration_safety.md`: corrected setup contract and recovery guidance.

`docs/work/phase5.7.md` was an existing untracked instruction file and was left intact.

## Adapter audit matrix

| Adapter | Scope / schema verified against official sources | Automated preservation | Actual client loading |
|---|---|---|---|
| Claude Code | User `~/.claude.json`, project `.mcp.json`; `mcpServers` | Passed, including permissions/hooks/projects | Claude Code 2.1.113: isolated project entry loaded; MCP get reported Connected |
| Codex CLI / IDE | User `$CODEX_HOME/config.toml` (default `~/.codex`), project `.codex/config.toml`; `mcp_servers` | Passed, including trusted Windows projects, profiles, providers, policies and unknown types | Codex CLI 0.164.0: isolated `mcp list --json` listed both RenderEye and the existing synthetic server; trust settings preserved |
| Cursor | User/project `.cursor/mcp.json`; `mcpServers` | Passed, including environment and unknown properties | Unverified: client not found on PATH |
| VS Code / Copilot Local harness | Default stable user-profile `mcp.json`, workspace `.vscode/mcp.json`; `servers` | Passed, including comments, trailing commas, inputs and Windows paths | Unverified: client not found on PATH |
| Gemini CLI | User/project `.gemini/settings.json`; `mcpServers`; comments permitted | Passed, including general/security/tools preferences and comments | Unverified: client not found on PATH |

A successful server subprocess handshake is separate from client acceptance.
Codex MCP list validates client configuration loading but does not itself prove that
Codex invoked the server. All five generated launcher shapes were separately
verified through real MCP initialize and tools/list requests using the MCP SDK.
Claude's MCP get additionally performed its native connection health check.

## Editing contract and lifecycle

Only the `rendereye` member may change. Adapters compare all other values with
recursive type-aware equality, including TOML dates, arrays of tables and NaNs.
Source snapshots retain original bytes and parsed values; modifications happen
on copies. Generated output is parsed again and checked before any file operation.
Codex preserves the document via tomlkit. JSON and JSONC replace or insert only the
owned member rather than serializing the entire configuration. Unrelated text,
comments, quoting and line endings are preserved outside the edited region.

Existing different entries require `--force` for writing. Dry-run can display a
conflict replacement without authorizing it, and redacts environment/unknown entry
fields. `--force` never bypasses syntax or preservation checks. Removal recognizes
the generated stdio launch shape; customized namesakes require explicit force.
Only the RenderEye entry is removed; empty containers remain. Absent removal and
identical setup do not rewrite files. Removal does not require a working launcher.

The `code` alias explicitly selects Codex; `copilot` selects the VS Code adapter;
`gemini-cli` selects Gemini. Single, interactive and --all setup share the same
safety workflow. --all continues after per-agent errors and returns failure if any
adapter failed; it does not provide cross-file rollback.

Repository searches found no automatic agent registration, upgrade/migration writer
or agent cleanup in `setup`, package upgrade scripts or `uninstall-setup`. These
operations remain separate. Agent removal is explicit via `setup-agent --remove`.

## Transactional safety and recovery

The writer creates a temporary file in the destination directory, flushes/fsyncs it,
preserves mode bits, validates the original snapshot before replacement, and uses
`os.replace`. Existing originals are backed up with exclusive creation as `.bak`,
`.bak.1`, etc.; earlier snapshots are never overwritten. An exclusive sidecar lock
coordinates RenderEye writers. Failed temp writes, permissions, rename errors and
handled interruption preserve the original and remove the writer's temp/lock files.
After replacement, exact bytes are re-read and compared with validated output.

Changes by external editors are detected with snapshot checks. A post-replacement
external edit is reported without blindly overwriting it during rollback; recovery
uses the retained original backup. Lock-ignoring editors can race between the last
check and replacement. This is documented optimistic conflict detection, not an
OS-level compare-and-swap guarantee. Forced process death can leave a stale lock;
manual recovery instructions require first checking that no writer is active.

Malformed configuration is never repaired automatically. Troubleshooting documents
how to save the corrupted file, restore a known-valid backup, validate it with
tomllib, then rerun dry-run. Deleting the entire Codex configuration is not the
normal recovery path. Secrets are not dumped into preview diffs or copied from .env.

## Test commands and observed outcomes

Commands used the existing project virtual environment:

```powershell
uv sync
.venv/Scripts/python.exe -m pytest tests/test_phase5_7_agent_safety.py -k 'not installed_client and not generated_command' -q
.venv/Scripts/python.exe -m pytest tests/test_phase5_7_agent_safety.py -k 'generated_command or installed_client' -q
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check src/rendereye_mcp/agent_setup src/rendereye_mcp/cli.py src/rendereye_mcp/doctor.py tests/test_phase5_7_agent_safety.py
uv build --out-dir dist/phase5.7
.venv/Scripts/python.exe scripts/verify_agent_config_wheel.py dist/phase5.7/rendereye_mcp-1.0.0-py3-none-any.whl
```

Observed outcomes:

- Final complete regression suite: **616 passed in 33.09s**.
- Client/MCP subset: **7 passed** (five SDK handshakes and two installed clients).
  The final suite also ran handshakes from copied console launchers in paths with
  spaces and Japanese characters.
- Ruff on changed production modules and the new safety tests: passed.
- Wheel and source distribution: built successfully. uv emitted its existing
  build-backend/current-uv-version advisory; build completed successfully.
- Wheel verification: dependency metadata includes tomlkit; json_edit is included;
  all five adapters loaded from extracted wheel code outside the checkout and passed
  preview/add/idempotency/remove/preservation checks through the console launcher.
  Dependencies came from the current environment; this was not an offline clean-room
  dependency installation test.

The first full run had 604 passes and one older startup test failure because that
test inherited local configuration. After isolating its runtime environment,
the test passed, followed by the final full-suite pass. Early handshake test
assertions used the wrong SDK attribute spelling; correcting the test to the SDK's
`server_info` field resolved those assertions without changing server behavior.

Failure injection covers temp-file creation, fsync, replacement, read-only mode,
handled interruption and edits during temp-file writes. Additional cases cover
missing/empty/malformed files, bad container types, duplicate keys, Unicode, spaces,
Windows literal path keys, comments, trailing commas, custom conflicts, backup
versioning, lock contention, --all continuation, absent removal and source-file
launcher rejection. No real user config fixtures or secrets were added.

## Official references reviewed

- [Codex MCP](https://developers.openai.com/codex/mcp) and
  [configuration layers](https://developers.openai.com/codex/config-basic).
- [Claude MCP scopes, add/remove and health checks](https://code.claude.com/docs/en/mcp).
- [Cursor MCP configuration](https://prod.cursor.com/docs/mcp).
- [VS Code MCP schema, user profile, workspace and CLI registration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).
- [Gemini MCP commands and scopes](https://geminicli.com/docs/tools/mcp-server/),
  [configuration](https://geminicli.com/docs/reference/configuration/), and its
  [maintained settings loader](https://github.com/google-gemini/gemini-cli/blob/main/packages/cli/src/config/settings.ts).

Claude and Gemini native management commands were evaluated. Direct targeted edits
were retained to provide consistent dry-run, conflict checks, recoverable backups
and semantic verification without requiring the client binary to be installed.

## Remaining limits and release readiness

No unresolved configuration corruption was observed in the tested workflows.
The safety corrections are ready for review and Windows distribution with the
listed scope. Phase 5.7 remains **partially verified** as a client compatibility
claim: Cursor, VS Code and Gemini runtime acceptance is unverified, as are other
OS/client versions. No broad client-version support is inferred from these tests.

VS Code support targets its default stable profile and Local harness; portable
Copilot/harness config, custom profiles, Insiders and remote layouts require native
client registration. Existing portable files are not migrated or deleted. Claude
local scope and custom client location overrides beyond CODEX_HOME are not added.
Cursor/Claude commented files are refused rather than guessed as JSONC. Native
schema validation for unknown future client options relies on the client; the tool
validates syntax, required server container and generated stdio entry shape.

Custom Windows ACL retention, lock-ignoring editor races, network filesystem rename
behavior and power loss remain outside verified guarantees. End users do not need
uv, a checkout or development Python source paths. No release was published.
