[English](configuration.md) | [日本語](../ja/configuration.md)

# Configure coding agents and RenderEyeMCP

- [How an agent talks to RenderEyeMCP](#how-an-agent-talks-to-rendereyemcp)
- [Connect Claude Code](#connect-claude-code)
- [Connect Codex](#connect-codex)
- [Other MCP clients](#other-mcp-clients)
- [Verify the connection](#verify-the-connection)
- [Use several agents at once](#use-several-agents-at-once)
- [Environment settings (.env)](#environment-settings-env)

## How an agent talks to RenderEyeMCP

Every agent starts the same command over stdio:

```text
<path to rendereye-mcp executable> serve
```

`rendereye-mcp setup-agent <agent>` writes this entry for you. It:

- uses the absolute path of the `rendereye-mcp` executable you ran it with,
- adds `RENDEREYE_ENV_FILE` to the entry when that variable is set in your terminal,
- edits only the `rendereye` entry, keeps every other setting, refuses malformed files,
  and saves the previous file as `.bak` (then `.bak.1`, …) before writing.

Useful options: `--dry-run` (preview only), `--scope project --project-path <dir>`,
`--force` (replace a different existing `rendereye` entry), `--remove`.
Details: [configuration safety](../agent_configuration_safety.md).

> Run `setup-agent` from a **new terminal opened after `rendereye-mcp setup`** so the
> entry includes `RENDEREYE_ENV_FILE`. Without it the agent still works, as long as the
> agent process itself was started after setup.

## Connect Claude Code

**Prerequisites:** Claude Code installed; `rendereye-mcp setup` completed.

```powershell
rendereye-mcp setup-agent claude-code                 # user scope: ~/.claude.json
rendereye-mcp setup-agent claude-code --scope project # project scope: .mcp.json in the current directory
```

Manual equivalent (user scope, `~/.claude.json` → `mcpServers`). Replace the paths with
your own; `where.exe rendereye-mcp` prints the executable path.

```json
{
  "mcpServers": {
    "rendereye": {
      "type": "stdio",
      "command": "C:\\Users\\<you>\\.local\\bin\\rendereye-mcp.exe",
      "args": ["serve"],
      "env": {
        "RENDEREYE_ENV_FILE": "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\.env"
      }
    }
  }
}
```

Restart Claude Code, then confirm:

```powershell
claude mcp get rendereye
```

Expected: `Status: ✓ Connected`. Inside a session, `/mcp` lists `rendereye` and its tools.

Claude Code-specific notes:

- Project-scope servers from `.mcp.json` must be approved the first time Claude Code
  starts in that folder. Until then `claude mcp get` shows *Pending approval*.
- If the server shows *Failed*, run `claude --debug` to see the server's stderr log.

## Connect Codex

**Prerequisites:** Codex CLI installed; `rendereye-mcp setup` completed.

```powershell
rendereye-mcp setup-agent codex                  # user scope: ~/.codex/config.toml (honors CODEX_HOME)
rendereye-mcp setup-agent codex --scope project  # <project>/.codex/config.toml
```

Manual equivalent (TOML — escape backslashes):

```toml
[mcp_servers.rendereye]
command = "C:\\Users\\<you>\\.local\\bin\\rendereye-mcp.exe"
args = ["serve"]

[mcp_servers.rendereye.env]
RENDEREYE_ENV_FILE = "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\.env"
```

Confirm:

```powershell
codex mcp list
```

`rendereye` should be listed. Codex-specific notes:

- Project-scope configuration is only read for projects you have marked as trusted.
- `setup-agent code` is an alias for Codex, not for VS Code (use `vscode`).

## Other MCP clients

`setup-agent` also writes configuration for `cursor`, `vscode` (GitHub Copilot) and
`gemini`. Those files are produced and validated by the automated tests, but the real
clients were **not** exercised for this release. Any MCP client that can start a stdio
server with the command above should work; please report results.

## Verify the connection

Check each layer separately:

| Check | Command or prompt | Expected |
|-------|-------------------|----------|
| Agent config is valid | `rendereye-mcp doctor --agent claude-code` (or `codex`) | No `✗` lines |
| Agent can start the server | `claude mcp get rendereye` / `codex mcp list` | Connected / listed |
| Tools are discovered | Ask: *"Call server_status."* | `server_name: RenderEyeMCP`, `server_version` |
| RenderDoc is reachable | Ask: *"List the RenderDoc sessions."* | A session with `connection_state: connected` |
| A capture is visible | Ask: *"What capture is currently loaded in RenderDoc?"* | `status: loaded` and the `.rdc` path |

The prompts are ordinary requests in natural language. The agent decides which MCP tools
to call (`server_status`, `list_renderdoc_sessions`, `get_current_capture`, …); you never
have to type tool names. If an agent picks the wrong tool, naming the tool in the prompt
is a useful hint.

## Use several agents at once

RenderEyeMCP runs one **shared IPC service** per user session. Each agent starts its own
small `rendereye-mcp serve` process; all of them connect to the same service, and the
service is the only process that talks to RenderDoc.

```text
Claude Code ──stdio── rendereye-mcp serve ─┐
                                            ├─ TCP 127.0.0.1:37020 ─ shared service ─ RenderDoc extension(s)
Codex ───────stdio── rendereye-mcp serve ─┘
```

No extra configuration is needed: configure both agents as above and start them in any
order. Example:

1. Open a capture in RenderDoc and select a draw call.
2. In Claude Code ask: *"Summarize the pipeline state of the selected draw call."*
3. At the same time, in Codex ask: *"List the textures bound to the selected pixel shader."*

Both answers come from the same RenderDoc session. All inspection tools are read-only,
so concurrent use does not interfere. Do not allocate separate ports per agent.

The service keeps running after the agents exit. Stop it with
`rendereye-mcp service stop`; it is started again on demand.

## Environment settings (.env)

Settings are read from the `.env` file that `RENDEREYE_ENV_FILE` points to. Precedence:

1. Environment variables already set in the process (highest)
2. Values in the `.env` file
3. Built-in defaults

If `RENDEREYE_ENV_FILE` is not set, a `.env` in the current working directory is used
when present (development convenience). Most users never need to edit `.env`.

| Variable | Default | Meaning |
|----------|---------|---------|
| `RENDEREYE_RENDERDOC_EXE` | detected by setup | Full path to `qrenderdoc.exe` (status checks and `capture_open`) |
| `RENDEREYE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | Service address. Loopback only; `0.0.0.0` is refused |
| `RENDEREYE_IPC_PORT` | `37020` | Service port (see note below) |
| `RENDEREYE_CONNECTION_TIMEOUT` | `10.0` | IPC connection timeout in seconds |
| `RENDEREYE_STORAGE_PATH` | `%APPDATA%\rendereye_mcp\captures.db` | SQLite database for the capture registry and sessions |
| `RENDEREYE_CAPTURE_ENABLED` | `true` | Enable `.rdc` file discovery |
| `RENDEREYE_CAPTURE_DIRS` | empty | Folders to watch for `.rdc` files, separated by `;` on Windows and `:` on Linux |
| `RENDEREYE_CAPTURE_SCAN_INTERVAL` | `10.0` | Background rescan interval (seconds) |
| `RENDEREYE_CAPTURE_STABILITY_SECONDS` | `2.0` | How long a new file must stay unchanged before it is "ready" |

Notes:

- **Changes take effect when the shared service restarts.** Run
  `rendereye-mcp service stop`, then restart your agent.
- **Changing the port:** the RenderDoc extension does not read `.env`; it reads
  `RENDEREYE_IPC_PORT` from RenderDoc's own environment. If you change the port, set it
  as a user environment variable as well so RenderDoc inherits it, then restart RenderDoc.
- `RENDEREYE_CAPTURE_DIRS` is only needed for the capture-registry tools
  (`capture_list`, `capture_latest`, …). Inspecting the capture open in RenderDoc does not
  use it.
