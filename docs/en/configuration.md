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

Every agent starts the `rendereye-mcp` executable over stdio. No subcommand is needed;
the default mode is the MCP Bridge:

```text
<path to rendereye-mcp executable>
```

Add this to your agent's MCP server configuration and restart the agent.

## Connect Claude Code

Add to `~/.claude.json` (user scope) or `.mcp.json` in your project (project scope):

```json
{
  "mcpServers": {
    "rendereye": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
    }
  }
}
```

Replace the path with the actual location of `rendereye-mcp.exe` — the installer places
it at `%LOCALAPPDATA%\RenderEyeMCP\rendereye-mcp.exe` by default. On Linux or macOS use
the path from `which rendereye-mcp`.

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

Add to `~/.codex/config.toml` (user scope) or `<project>/.codex/config.toml` (project
scope):

```toml
[mcp_servers.rendereye]
command = "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
```

Confirm:

```powershell
codex mcp list
```

`rendereye` should be listed.

- Project-scope configuration is only read for projects you have marked as trusted.

## Other MCP clients

Any MCP client that can start a stdio server works. Use the `rendereye-mcp` executable
path as the command with no arguments. Please report results for clients other than Claude
Code and Codex.

## Verify the connection

Check each layer separately:

| Check | Command or prompt | Expected |
|-------|-------------------|----------|
| Binary works | `rendereye-mcp version` | Version line |
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
`rendereye-mcp` process (MCP Bridge); all of them connect to the same service, and the
service is the only process that talks to RenderDoc.

```text
Claude Code ──stdio── rendereye-mcp ─┐
                                     ├─ TCP 127.0.0.1:37020 ─ rendereye-mcp service ─ RenderDoc extension(s)
Codex ───────stdio── rendereye-mcp ─┘
```

No extra configuration is needed: configure both agents as above and start them in any
order. Example:

1. Open a capture in RenderDoc and select a draw call.
2. In Claude Code ask: *"Summarize the pipeline state of the selected draw call."*
3. At the same time, in Codex ask: *"List the textures bound to the selected pixel shader."*

Both answers come from the same RenderDoc session. All inspection tools are read-only,
so concurrent use does not interfere. Do not allocate separate ports per agent.

The service keeps running until you stop it or restart your machine. To stop it, kill the
`rendereye-mcp service` process; it will be started again automatically the next time an
agent launches.

## Environment settings (.env)

Settings are read from a `.env` file. The bridge looks for the file at
`RENDEREYE_ENV_FILE` (if that environment variable is set), otherwise falls back to
`.env` in the current working directory. Precedence:

1. Environment variables already set in the process (highest)
2. Values in the `.env` file
3. Built-in defaults

The default configuration (host `127.0.0.1`, port `37020`) works without editing `.env`.
Most users never need to edit it.

| Variable | Default | Meaning |
|----------|---------|---------|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | Service address. Loopback only; `0.0.0.0` is refused |
| `RENDEREYE_IPC_PORT` | `37020` | Service port |
| `RENDEREYE_LOG_LEVEL` | `info` | `debug`, `info`, `warn`, `error` |

Notes:

- **Changes take effect when the service restarts.** Kill the `rendereye-mcp service`
  process and restart your agent to pick up the new port.
- **Changing the port:** the RenderDoc extension does not read `.env`; it reads
  `RENDEREYE_IPC_PORT` from RenderDoc's own environment. If you change the port, set it
  as a user environment variable as well so RenderDoc inherits it, then restart RenderDoc.
