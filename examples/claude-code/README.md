# Claude Code MCP Configuration

Copy `mcp-config.json` to one of these locations:

- **Project-level** (affects only this project): `.mcp.json` in your project root
- **User-level** (affects all projects): `%USERPROFILE%\.claude\mcp.json`

Replace `<USERNAME>` with your Windows username.

## Minimal configuration (no env overrides)

```json
{
  "mcpServers": {
    "rendereye": {
      "command": "C:\\Users\\<USERNAME>\\AppData\\Local\\RenderEyeMCP\\venv\\Scripts\\python.exe",
      "args": ["-m", "rendereye_mcp"]
    }
  }
}
```

## Verification

In Claude Code, type:
```
What MCP tools do you have available?
```

Claude should list `server_status`, `capture_list`, `capture_open`, etc.

Then call `server_status` to confirm connectivity.
