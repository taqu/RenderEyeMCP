# OpenAI Codex CLI MCP Configuration

The Codex CLI reads MCP configuration from `~/.codex/config.toml`.

Copy the contents of `config.toml` into `~/.codex/config.toml`, replacing `<USERNAME>` with your Windows username.

> **Note:** Verify the current Codex CLI configuration schema in the official documentation, as formats may change between versions.

## Verification

Run:
```
codex mcp list
```

`rendereye` should appear in the list. Then test connectivity:
```
codex "Call the rendereye server_status tool"
```
