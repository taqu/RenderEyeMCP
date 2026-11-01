[English](configuration.md) | [日本語](../ja/configuration.md)

# Configure coding agents and RenderEyeMCP

- [How an agent talks to RenderEyeMCP](#how-an-agent-talks-to-rendereyemcp)
- [Connect Claude Code](#connect-claude-code)
- [Connect Codex](#connect-codex)
- [Other MCP clients](#other-mcp-clients)
- [Verify the connection](#verify-the-connection)
- [Use several agents at once](#use-several-agents-at-once)
- [Environment settings](#environment-settings)

## How an agent talks to RenderEyeMCP

Every agent starts the same command over stdio:

```text
<full path to rendereye-mcp executable>
```

No subcommand is needed. The binary starts the MCP Bridge automatically.
It also auto-starts the Shared IPC Service on `127.0.0.1:37020` if it is not already running.

Add the entry manually to your agent's MCP configuration, or copy the snippet printed by
`install.ps1` / `install.sh` when you ran the installer.

## Connect Claude Code

Add a `rendereye` entry to `~/.claude.json` (user scope) or `.mcp.json` in your project
directory (project scope). Replace the path with the actual location of `rendereye-mcp.exe`:

```json
{
  "mcpServers": {
    "rendereye": {
      "type": "stdio",
      "command": "C:\\Tools\\RenderEyeMCP\\rendereye-mcp.exe"
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

Add a `rendereye` entry to `~/.codex/config.toml` (user scope) or
`<project>/.codex/config.toml` (project scope):

```toml
[mcp_servers.rendereye]
command = "C:\\Tools\\RenderEyeMCP\\rendereye-mcp.exe"
```

Confirm:

```powershell
codex mcp list
```

`rendereye` should be listed.

## Other MCP clients

Any MCP client that can start a stdio server with the command above should work.
The [examples](../examples/) directory contains configuration snippets for Cursor,
VS Code (GitHub Copilot), and Gemini.

## Verify the connection

Check each layer separately:

| Check | How | Expected |
|-------|-----|----------|
| Binary works | `rendereye-mcp.exe version` | Prints version and build date |
| Agent can start the server | `claude mcp get rendereye` / `codex mcp list` | Connected / listed |
| Tools are discovered | Ask: *"List the MCP tools available from rendereye."* | Lists tools like `get_current_capture` |
| RenderDoc is reachable | Ask: *"List the RenderDoc sessions RenderEyeMCP can see."* | A session with `connection_state: connected` |
| A capture is visible | Ask: *"What capture is currently loaded in RenderDoc?"* | `status: loaded` and the `.rdc` path |

## Use several agents at once

RenderEyeMCP runs one **shared IPC service** per machine. Each agent starts its own
MCP Bridge process; all bridges connect to the same service, and the service is the
only process that talks to the RenderDoc extension.

```text
Claude Code ──stdio── rendereye-mcp ─┐
                                     ├─ TCP 127.0.0.1:37020 ─ shared service ─ RenderDoc extension(s)
Codex ───────stdio── rendereye-mcp ─┘
```

No extra configuration is needed. Configure both agents as above and start them in any
order. All inspection tools are read-only, so concurrent use does not interfere.

To stop the shared service manually:

```powershell
# Windows: kill the service process
taskkill /F /IM rendereye-mcp.exe
```

The service starts again automatically the next time an agent invokes the bridge.

## Environment settings

Configuration is read from environment variables, optionally sourced from a `.env` file.
Point `RENDEREYE_ENV_FILE` to a `.env` file if you want to set these persistently.

| Variable | Default | Meaning |
|----------|---------|---------|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | Service bind address. Loopback only; `0.0.0.0` is refused. |
| `RENDEREYE_IPC_PORT` | `37020` | Service TCP port. |
| `RENDEREYE_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error`. |
| `RENDEREYE_ENV_FILE` | (none) | Path to a `.env` file loaded at startup. |

**Changing the port:** the RenderDoc extension reads `RENDEREYE_IPC_PORT` from RenderDoc's
own environment. If you change the port, set it as a user environment variable before
starting RenderDoc, then restart RenderDoc so the extension picks it up.
