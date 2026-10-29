# Coding agent configuration safety

Only the `rendereye` entry inside the client's server container may change.
The adapter checks the parsed configuration before and after editing, validates
serialized output, and refuses unknown structures it cannot safely edit. It does
not repair malformed files. Unknown settings and other servers remain unchanged.

| Agent | User scope | Project scope | Format / container |
|---|---|---|---|
| Claude Code | `~/.claude.json` | `.mcp.json` | JSON / `mcpServers` |
| Codex CLI / IDE | `$CODEX_HOME/config.toml`, default `~/.codex/config.toml` | `.codex/config.toml` (trusted projects) | TOML / `mcp_servers` |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` | JSON / `mcpServers` |
| VS Code Local harness / Copilot | default stable `Code/User/mcp.json` in OS config directory | `.vscode/mcp.json` | JSONC / `servers` |
| Gemini CLI | `~/.gemini/settings.json` | `.gemini/settings.json` | JSON with comments / `mcpServers` |

`code` means Codex, `copilot` means the VS Code adapter, and `gemini-cli` means
Gemini. Claude local scope is available through `claude mcp` but is not a
RenderEye setup scope. Use `--scope user` or `--scope project` explicitly.

Codex uses `tomlkit` for lossless edits and `tomllib` for independent syntax and
value validation. JSON/JSONC uses standard JSON parsing after position-preserving
comment masking where allowed. Targeted member edits preserve other text.
VS Code accepts comments and trailing commas. Gemini accepts comments but rejects
trailing commas, matching its `JSON.parse(stripJsonComments(...))` loader. Cursor
and Claude use strict JSON here; commented/nonstandard files are refused without
writing rather than normalized speculatively. Empty TOML is valid; empty JSON
files are refused and must be deliberately initialized to `{}` by the user.
Duplicate JSON keys and nonstandard numeric constants are refused.

## Preview, conflicts and removal

```powershell
rendereye-mcp setup-agent codex --dry-run
rendereye-mcp setup-agent codex --force --dry-run
rendereye-mcp setup-agent codex --force
rendereye-mcp setup-agent codex --remove
```

Dry-run reads/parses, computes and validates a proposed change, prints the target
and a focused entry diff, and writes nothing (including no directories or locks).
Environment values and unknown entry fields are redacted; command and arguments
are visible for review. Existing entries must match exactly or setup refuses
unless `--force` is supplied. Force only permits replacing that one entry; it
never bypasses parsing or preservation checks.

Removal recognizes the generated stdio command/arguments and optional environment
path. A customized namesake needs `--remove --force`. Removal does not resolve a
launcher and works after package removal. Empty server containers are retained.
Repeated identical setup/removal leaves the file byte-for-byte unchanged.
`--all` applies the same checks per adapter, continues past errors, then reports
a failure if any adapter failed; it is not one transaction across all files.
User-scope detection is based on the configuration directory existing.

The launcher resolver accepts the installed `rendereye-mcp` / `rendereye-mcp.exe`
console script from the invocation, PATH or the current Python's scripts directory.
It rejects arbitrary `sys.argv[0]` source files. Paths contain no embedded shell
quotes. Only `RENDEREYE_ENV_FILE`, when set, is forwarded; setup never copies
`.env` contents or other environment variables into agent configuration.

## Transactions and recovery

Before replacement, the writer validates all content in memory, writes a temporary
file beside the target, flushes/fsyncs it, preserves file mode bits, and checks the
original byte snapshot again. Existing bytes are saved to an exclusively created
`.bak`, then `.bak.1`, `.bak.2`, etc. Backups never overwrite earlier snapshots.
The temporary file is atomically replaced with `os.replace`, then reopened and
compared to the already validated bytes. Failed writes/replacements leave the
original in place; temporary files and the writer's lock are removed on normal
errors or handled interruption. Backup contents may contain secrets: protect
backups as carefully as the configuration itself. POSIX backups use mode 0600;
Windows files inherit directory ACLs.

An exclusive `.rendereye.lock` sidecar serializes RenderEye writers. Snapshot
checks reject detected external edits. Editors that ignore this lock can still
race the tiny interval between the last check and atomic replacement; avoid
editing the same file while setup runs. An external edit detected after the
replacement is reported, never overwritten by an automatic rollback. Recover
from the saved original only after reviewing the new external contents.
Atomic rename is not a multi-process compare-and-swap or a power-loss guarantee.
Custom Windows ACL preservation and network filesystem atomicity are unverified.
Symbolic-link targets are refused. Parent-directory symlinks are not resolved or
locked against independent filesystem changes.

If setup reports an error, inspect the original and its backups. The latest valid
backup can be restored manually after saving the current file and stopping other
writers. Do not blindly pick the newest snapshot: it may reflect another version
of your settings. Validate restored syntax before retrying with `--dry-run`.
A process forcibly killed while writing can leave a temporary file or stale lock.
After verifying that no setup process is active, remove that specific stale lock
and retry; do not remove another active writer's lock.

Automatic environment setup, package upgrades and `uninstall-setup` do not modify
coding agent files. Explicit `setup-agent --remove` is required for cleanup.
There is no implicit configuration migration or speculative corruption repair.

## Official references and verification

Reviewed 2026-10-28:

- [Claude MCP scopes and CLI management](https://code.claude.com/docs/en/mcp).
- [Codex MCP](https://developers.openai.com/codex/mcp) and [configuration layers](https://developers.openai.com/codex/config-basic).
- [Cursor MCP paths and schema](https://prod.cursor.com/docs/mcp).
- [VS Code schemas, destinations and CLI registration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).
- [Gemini MCP commands and scopes](https://geminicli.com/docs/tools/mcp-server/) and [settings loader](https://github.com/google-gemini/gemini-cli/blob/main/packages/cli/src/config/settings.ts).

Claude and Gemini official CLI registration was evaluated. RenderEye retains
direct targeted editing so dry-run, conflict policy, preservation validation and
versioned backups behave consistently without requiring a client installation.
Native CLI registration does not provide these shared guarantees. Custom client
profiles or configuration location overrides outside the listed contract should
use the client's native registration workflow.

See the [Phase 5.7 implementation report](work/phase5.7-report.md) for executed
tests and real client results. Windows is the tested environment. Other client
versions, operating systems, custom VS Code profiles and Copilot's separate
portable/harness config are unverified.
