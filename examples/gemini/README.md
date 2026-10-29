# Gemini CLI MCP Configuration

The Gemini CLI reads MCP configuration from `~/.gemini/settings.json` (user-level) or `.gemini/settings.json` in your project directory.

Copy `settings.json` to the appropriate location. Replace `<USERNAME>` with your Windows username.

> **Note:** Verify the current Gemini CLI configuration schema in the official Google documentation, as formats may change between versions.

## Verification

Run:
```
gemini mcp list
```

Then test connectivity by asking Gemini to call `server_status`.
