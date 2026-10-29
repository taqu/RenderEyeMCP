# VS Code / GitHub Copilot MCP Configuration

VS Code with GitHub Copilot reads MCP configuration from:

- **Project-level**: `.vscode/mcp.json` in your workspace root
- **User-level**: Open VS Code settings (JSON) and add `"mcp"` key

Copy `mcp.json` to `.vscode/mcp.json` in your workspace. Replace `<USERNAME>` with your Windows username.

## Requirements

- VS Code 1.99 or later
- GitHub Copilot extension with agent mode enabled

## Verification

Open GitHub Copilot Chat → Agent mode. Type `@rendereye server_status` or ask Copilot to call `server_status`.

The server list is visible in VS Code Settings → MCP Servers.
