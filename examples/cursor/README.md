# Cursor MCP Configuration

Cursor reads MCP server configuration from:

- **Project-level**: `.cursor/mcp.json` in your project root
- **User-level**: `%USERPROFILE%\.cursor\mcp.json`

Copy `mcp.json` to the appropriate location. Replace `<USERNAME>` with your Windows username.

## Verification

Open Cursor → Settings → MCP. RenderEyeMCP should appear in the server list with status "running".

Use the Cursor AI chat to call `server_status` to confirm connectivity.
