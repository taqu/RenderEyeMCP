# RenderEyeMCP — Phase 5.7 Implementation Instructions

## Coding Agent MCP Configuration Safety Audit & Fixes

## Objective

Perform a comprehensive safety audit and correction of the RenderEyeMCP coding agent configuration system.

The command:

```powershell
rendereye-mcp setup-agent code
```

has produced a corrupted OpenAI Codex `config.toml` file.

The generated configuration contains invalid TOML syntax, including Windows paths serialized as unquoted keys and Python dictionary representations written directly into TOML.

Example of the observed corruption:

```toml
[projects]
d:\projects\cpp\pathtrace = {'trust_level': 'trusted'}
```

The correct representation requires valid TOML syntax, such as:

```toml
[projects.'d:\projects\cpp\pathtrace']
trust_level = "trusted"
```

The MCP entry also incorrectly references a Python source file as an executable rather than using a verified installed launcher.

These problems suggest that the current configuration-writing implementation may be unsafe.

**The objective is to verify and correct the configuration handling for every supported coding agent, not just Codex.**

No RenderEyeMCP setup command may corrupt, discard, unexpectedly rewrite, or silently overwrite unrelated user configuration.

---

## 1. Scope

Audit and fix MCP configuration management for:

1. Claude Code
2. OpenAI Codex CLI / IDE
3. Cursor
4. Visual Studio Code / GitHub Copilot
5. Gemini CLI

Include all supported aliases, such as `code` and `codex`, after verifying their intended mapping.

### Operations to Audit

Audit every operation that modifies coding agent configuration:

- `setup-agent`
- `setup-agent --remove`
- `setup-agent --force`
- `setup-agent --scope user`
- `setup-agent --scope project`
- `setup-agent --dry-run`
- `setup-agent --all`
- Automatic setup integration
- Uninstallation cleanup
- Upgrade and migration operations

Audit actual supported commands and flags. Do not assume all listed options are already implemented.

Also search for any other code paths that modify the same configuration files.

### Out of Scope

Do not implement unrelated MCP functionality, GPU analysis, or RenderDoc GUI features.

---

## 2. Task A — Root Cause Analysis

Investigate the actual Codex configuration corruption.

### Known Failure

The Codex configuration was transformed into invalid TOML.

Example:

```toml
[projects]
d:\projects\cpp\pathtrace = {'trust_level': 'trusted'}
```

Another affected configuration value resembles:

```toml
model_availability_nux = {'gpt-6-astra': 4, 'gpt-6.1-sol': 4}
```

These are Python dictionary representations, not valid TOML values.

### Investigation

Locate the exact code responsible for:

1. Reading the existing configuration.
2. Parsing its contents.
3. Representing nested configuration values.
4. Inserting the RenderEye MCP server.
5. Serializing the configuration.
6. Writing the resulting file.

Check whether the implementation:

- Uses `str()` or `repr()` on dictionaries.
- Uses generic JSON serialization for TOML.
- Flattens nested TOML tables incorrectly.
- Mishandles Windows path keys.
- Rebuilds the entire configuration from an incomplete schema.
- Discards unknown settings.
- Changes existing values or types.
- Performs unsafe regular-expression replacements.

### MCP Command

Inspect how the MCP executable is determined.

The following is not an appropriate general-purpose CLI launcher:

```toml
command = "D:\\Projects\\python\\RenderEyeMCP\\src\\rendereye_mcp\\__main__.py"
args = ["serve"]
```

Use the verified installed RenderEyeMCP console executable instead, or a real Python executable with correctly constructed `-m rendereye_mcp serve` arguments.

### Deliverable

Document the actual root cause and affected code paths.

Do not assume that correcting one TOML serialization function fixes all agent adapters.

---

## 3. Task B — Audit Every Coding Agent Adapter

Inspect the implementation of all supported coding agent configuration adapters.

For each agent, identify:

- Configuration file location
- Supported user and project scopes
- Actual file format
- File parsing method
- File serialization method
- Configuration update method
- Existing configuration preservation behavior
- Backup mechanism
- Error handling
- Removal behavior

### Audit Questions

Determine whether each adapter can:

1. Read a valid existing configuration.
2. Preserve unrelated settings.
3. Preserve unrelated MCP servers.
4. Preserve unknown configuration fields.
5. Insert RenderEye without replacing the entire file.
6. Update an existing RenderEye entry.
7. Remove only the RenderEye entry.
8. Handle invalid configuration safely.
9. Handle read-only files safely.
10. Handle concurrent modifications safely.

### Official Specifications

Verify the current official MCP configuration format for each coding agent.

Use official documentation and maintained configuration schemas where available.

Do not assume that JSON, JSONC, and TOML have interchangeable parsing rules.

Do not assume that all agents store user and project configuration in equivalent locations.

### Deliverable

A configuration adapter audit covering all five agent integrations.

---

## 4. Task C — Establish a Non-Destructive Editing Contract

Create a shared safety contract that every coding agent adapter must follow.

### Fundamental Rule

**Modify only the RenderEyeMCP-owned MCP configuration entry.**

Never replace the complete configuration with a generated template when an existing configuration is present.

### Required Invariants

After adding or updating RenderEye:

- All unrelated configuration values remain unchanged.
- All unrelated MCP entries remain present.
- Existing user preferences remain unchanged.
- Existing project trust settings remain unchanged.
- Existing approval and sandbox policies remain unchanged.
- Unknown settings remain unchanged.
- Configuration files remain valid for their respective clients.

### Value Preservation

The non-RenderEye portion of the parsed configuration must remain semantically identical.

For adapters supporting lossless editing, preserve comments, ordering, quoting, and whitespace as well.

If exact textual preservation cannot be guaranteed by a particular format or client tool, document the limitations and require a safe editing strategy.

### Fail Closed

If an adapter cannot safely interpret or modify a configuration:

- Do not overwrite it.
- Do not replace it with defaults.
- Do not discard unknown fields.
- Report an actionable error.
- Leave the original file intact.

### No Automatic Repair

Do not automatically rewrite an already-corrupted configuration using speculative transformations.

Offer a separately invoked, reviewable recovery procedure when appropriate.

### Deliverable

A shared configuration editing safety contract enforced by automated tests.

---

## 5. Task D — Fix Codex TOML Handling

Correct the Codex configuration adapter.

### Configuration Format

Codex uses TOML.

Ensure valid TOML serialization.

### Required Behavior

Preserve existing sections such as:

- Model configuration
- Reasoning settings
- Approval policy
- Sandbox configuration
- Trusted projects
- Profiles
- Model providers
- UI settings
- Existing MCP servers
- Unknown future settings

### Recommended Library

Use `tomlkit` or another suitable lossless TOML editing library.

Do not serialize nested dictionaries using Python string representations.

Do not implement a general-purpose TOML writer using string concatenation.

### Desired Modification

Add or update only the required MCP entry:

```toml
[mcp_servers.rendereye]
command = "C:\\Path\\To\\rendereye-mcp.exe"
args = ["serve"]
```

The executable path is illustrative.

Resolve the real installed launcher path.

### Windows Path Keys

Test TOML keys such as:

```toml
[projects.'d:\projects\cpp\pathtrace']
trust_level = "trusted"
```

Ensure they remain valid and unchanged after adding RenderEye.

### Validation

Use Python `tomllib` or an equivalent standards-compliant parser to verify the generated TOML.

Compare the parsed configuration before and after modification, excluding only the intended RenderEye entry.

### Deliverable

A corrected Codex adapter that never emits Python dictionary syntax into TOML.

---

## 6. Task E — Audit Claude Code Configuration

Review the Claude Code integration.

### Requirements

Verify supported official mechanisms for:

- User-scope registration
- Project-scope registration
- Local-scope registration where applicable
- Existing MCP server updates
- Server removal

### Preferred Approach

Where Claude Code provides an official CLI mechanism for MCP registration, evaluate using it instead of directly rewriting complex settings files.

The selected approach must still preserve unrelated user configuration.

### Configuration Safety

Test preservation of:

- Existing MCP servers
- User settings
- Permissions
- Hooks
- Project-specific configuration
- Unknown fields

Do not assume that all Claude Code settings belong in one JSON file.

### Verification

After installation:

- Confirm the RenderEye MCP entry exists.
- Confirm unrelated settings are unchanged.
- Confirm the launch command is valid.
- Confirm the resulting configuration can be read by Claude Code.

### Deliverable

A safe Claude Code configuration adapter.

---

## 7. Task F — Audit Cursor Configuration

Inspect the Cursor MCP configuration adapter.

### Required Checks

Verify the supported paths and schemas for:

- User-level configuration
- Project-level configuration

The expected project-level configuration commonly uses:

```text
.cursor/mcp.json
```

Verify against current official documentation.

### Safety Requirements

Preserve:

- Existing `mcpServers` entries
- Existing server environment settings
- Unknown properties
- Existing file contents unrelated to RenderEye

Do not replace the entire `mcpServers` object.

### JSON Handling

Use a proper parser and serializer.

If a supported configuration format permits comments or trailing commas, do not silently corrupt or strip them using a strict JSON parser.

Verify the actual supported file format.

### Deliverable

A safe Cursor configuration adapter.

---

## 8. Task G — Audit VS Code / GitHub Copilot Configuration

Verify the VS Code MCP configuration adapter.

### Important Distinction

Different MCP integration surfaces may use different configuration structures.

For example, VS Code workspace MCP configuration commonly uses:

```text
.vscode/mcp.json
```

with a top-level `servers` object.

Other MCP configurations may use `mcpServers`.

Do not assume these formats are interchangeable.

### Required Checks

Verify:

- User-level configuration mechanism
- Workspace-level configuration
- Correct MCP server schema
- Supported stdio command format
- Environment variable handling
- Existing configuration preservation

### JSONC Safety

VS Code configuration files may use JSON with comments depending on the specific file and supported schema.

Determine whether the target configuration uses JSON or JSONC.

Do not use a strict JSON serializer to rewrite a JSONC file containing comments if doing so would destroy valid user-authored content.

Use an appropriate structure-preserving editor or the official VS Code registration mechanism where available.

### Preservation Tests

Include fixtures with:

- Existing servers
- Comments
- Trailing commas where supported
- Windows executable paths
- Unrelated settings

### Deliverable

A safe VS Code / GitHub Copilot configuration adapter.

---

## 9. Task H — Audit Gemini CLI Configuration

Inspect Gemini CLI configuration handling.

### Configuration

Gemini CLI uses `settings.json`, with MCP server definitions under `mcpServers`.

Verify supported user and project scopes.

### Requirements

Preserve existing settings such as:

- General preferences
- Security settings
- Tool configuration
- Model configuration
- Existing MCP servers
- Unknown settings

### Preferred Approach

Evaluate Gemini CLI's official MCP management commands before directly rewriting its settings file.

If native registration provides reliable non-destructive updates, prefer that mechanism.

Otherwise, use safe structured configuration editing.

### Validation

Ensure resulting settings are valid according to the relevant Gemini CLI configuration schema.

Do not remove unrelated settings.

### Deliverable

A safe Gemini CLI configuration adapter.

---

## 10. Task I — Shared Configuration Editing Infrastructure

Implement common transactional file-editing utilities where appropriate.

### Design

Keep format-specific parsing and serialization separate.

Suggested architecture:

```text
Agent Setup
    |
    v
Agent Adapter
    |
    +-- Claude Code
    +-- Codex
    +-- Cursor
    +-- VS Code
    +-- Gemini CLI
    |
    v
Safe Configuration Update
    |
    +-- Read existing file
    +-- Parse using correct format
    +-- Validate structure
    +-- Apply targeted modification
    +-- Validate preserved settings
    +-- Serialize
    +-- Parse generated content again
    +-- Write safely
    +-- Verify final contents
```

### Do Not Over-Generalize

Do not force every agent through one serializer.

Use:

- TOML-aware editing for Codex
- JSON-aware editing where appropriate
- JSONC-aware editing where supported and required
- Official client CLI operations where safer

### Backups

Before modifying an existing file:

1. Preserve the original bytes.
2. Keep a recoverable backup where justified.
3. Ensure failures do not remove the original.
4. Avoid writing sensitive configuration contents into logs.

### Atomic File Replacement

For direct file editing:

1. Read the original file.
2. Record its state.
3. Parse and validate it.
4. Apply the targeted change in memory.
5. Validate the new content.
6. Write a temporary file in the same directory.
7. Flush and close it.
8. Confirm the source has not changed since it was read.
9. Atomically replace the target where supported.
10. Reopen and validate the resulting file.

Preserve file permissions where appropriate.

### Concurrent Modification

Avoid blindly overwriting edits made by another process after the file was read.

Use suitable file locking or conflict detection.

If concurrent changes are detected, abort or safely retry using a fresh read.

### Rollback

If validation or writing fails, preserve or restore the original content.

Report any rollback failure explicitly.

### Deliverable

Reusable safe-editing infrastructure without unnecessary abstraction.

---

## 11. Task J — Dry-Run and Confirmation Behavior

Implement or correct:

```powershell
rendereye-mcp setup-agent codex --dry-run
```

### Dry Run

A dry run must:

- Locate the intended configuration.
- Read and parse the existing content.
- Compute the proposed change.
- Validate the result.
- Display the target path.
- Display a focused diff.
- Report whether existing settings are preserved.
- Perform no writes.

### Existing Configuration Conflicts

If an MCP entry named `rendereye` already exists but points to a different executable:

- Show the current entry.
- Show the proposed replacement.
- Explain the change.
- Follow a documented conflict policy.

Do not silently overwrite an unrelated or user-customized entry merely because its name matches.

### Force Mode

`--force` may authorize replacing the RenderEye-owned entry.

It must never authorize deleting unrelated settings or bypassing syntax validation.

### Deliverable

A trustworthy preview and conflict-resolution workflow.

---

## 12. Task K — Safe Removal and Uninstallation

Audit:

```powershell
rendereye-mcp setup-agent codex --remove
```

and the equivalent operations for every supported agent.

### Requirements

Remove only RenderEye-owned configuration.

Preserve:

- Other MCP servers
- Model settings
- Trusted projects
- Permissions
- UI settings
- Unknown fields
- Comments wherever safely supported

### Empty Containers

If an `mcpServers` or equivalent container becomes empty, preserve or remove it according to the agent's supported configuration format and documented policy.

Do not delete parent configuration files containing unrelated data.

### Idempotency

Removing an already-absent RenderEye entry must not corrupt or rewrite the configuration unnecessarily.

### Deliverable

Safe MCP entry removal for all supported agents.

---

## 13. Task L — Regression Test Fixtures

Create representative existing configuration fixtures for every supported coding agent.

### Codex Fixtures

Include:

- Trusted Windows projects
- Multiple profiles
- Model settings
- Model provider settings
- Existing MCP servers
- Inline tables
- Comments
- Unicode strings
- Unknown future fields

Include a regression case derived from the reported corruption:

```toml
model = "example-model"

[projects.'d:\projects\cpp\pathtrace']
trust_level = "trusted"

[projects.'d:\projects\go\agentcap']
trust_level = "trusted"

[windows]
sandbox = "elevated"

[tui]
screen_reader_detection_done = true

[mcp_servers.other]
command = "other-server"
```

After adding RenderEye, all original values must remain unchanged.

### Claude Code Fixtures

Include:

- Multiple MCP servers
- Existing permissions
- Hooks
- Custom settings
- Different supported scopes

### Cursor Fixtures

Include:

- Existing `mcpServers`
- Multiple servers
- Custom environment variables
- Unknown fields

### VS Code Fixtures

Include:

- Existing `servers`
- Comments where supported
- Trailing commas where supported
- Workspace-specific settings
- Multiple MCP servers

### Gemini CLI Fixtures

Include:

- Existing `mcpServers`
- General preferences
- Tool settings
- Security settings
- Unknown fields

### Common Edge Cases

All applicable adapters must be tested with:

- Missing file
- Empty file
- Already configured RenderEye
- Malformed file
- Read-only file
- Unicode paths
- Paths containing spaces
- Windows backslashes
- Concurrent modification
- Failed write
- Interrupted replacement
- Repeated installation
- Repeated removal

### Deliverable

Version-controlled, synthetic configuration fixtures with no real user secrets.

---

## 14. Task M — Configuration Preservation Tests

Implement automated preservation tests for every agent.

### Add Operation

Given a valid existing configuration:

1. Parse the original content.
2. Add RenderEye.
3. Parse the new content.
4. Remove the RenderEye entry from the parsed result.
5. Compare the remaining configuration with the original.

They must be semantically identical.

### Update Operation

Given an existing RenderEye entry:

1. Update only the explicitly permitted RenderEye fields.
2. Verify unrelated settings remain unchanged.
3. Verify unrelated MCP servers remain unchanged.

### Remove Operation

Given a valid existing configuration:

1. Remove RenderEye.
2. Verify the remaining configuration matches the expected result.
3. Verify unrelated settings remain unchanged.

### Idempotency

Running setup twice must not create duplicate entries.

If no change is necessary, prefer leaving the configuration file byte-for-byte unchanged.

### Invalid Input

If parsing fails:

- Do not modify the file.
- Report the parse error.
- Preserve the original bytes.

### Failure Injection

Simulate:

- Permission errors
- Disk write failures
- Rename failures
- Interrupted operations
- Concurrent edits

Verify that the original remains recoverable and no partial configuration is left behind.

### Deliverable

Automated evidence that all supported adapters preserve unrelated settings.

---

## 15. Task N — Verify MCP Startup Commands

Correct the generation of MCP server launch configurations.

### Requirements

Use the actual installed RenderEyeMCP executable.

For example:

```text
<absolute-path-to-rendereye-mcp> serve
```

Alternatively, use a real Python interpreter with:

```text
-m rendereye_mcp serve
```

Do not generate a configuration that directly executes a Python source file unless that file is independently executable in the target environment and the approach is explicitly supported.

### Windows

Handle:

- Executable paths containing spaces
- `.exe` launchers
- Python virtual environments
- `uv tool install` environments

Do not add shell quoting characters into a configuration value that expects an executable path rather than a shell command line.

### Environment

If required, pass only:

```text
RENDEREYE_ENV_FILE
```

through an agent's environment configuration.

Do not duplicate the contents of `.env`.

### Verification

Test the generated command using a real subprocess and verify MCP initialization where possible.

### Deliverable

Correct MCP startup configurations across all agents.

---

## 16. Task O — Actual Client Verification

Where the relevant coding agents are installed, verify real configuration loading.

### Codex

Confirm:

- `config.toml` parses successfully.
- Codex starts without TOML syntax errors.
- Existing project trust settings remain intact.
- RenderEye appears in the MCP server list.
- The MCP server launches successfully.

### Claude Code

Confirm:

- Existing settings remain usable.
- Existing MCP servers remain registered.
- RenderEye is available.

### Cursor

Confirm:

- MCP configuration is accepted.
- Existing MCP servers remain available.
- RenderEye launches.

### VS Code / GitHub Copilot

Confirm:

- MCP configuration loads.
- Existing servers remain registered.
- RenderEye launches.

### Gemini CLI

Confirm:

- Settings are accepted.
- Existing preferences remain intact.
- Existing MCP servers remain registered.
- RenderEye launches.

### Safety

Do not modify real user agent configuration files while conducting automated tests.

Use isolated test profiles or temporary configurations.

If a real client cannot be tested, record it as unverified rather than claiming success.

### Deliverable

An evidence-based MCP configuration compatibility report.

---

## 17. Task P — Documentation and Recovery

Update:

- `README.md`
- `docs/installation.md`
- `docs/troubleshooting.md`
- `docs/agents/claude-code.md`
- `docs/agents/codex.md`
- `docs/agents/cursor.md`
- `docs/agents/vscode-copilot.md`
- `docs/agents/gemini-cli.md`

### Document

Explain:

- How configuration files are modified
- How unrelated settings are preserved
- How to preview changes
- How to remove RenderEye
- How backups work
- How to recover from failed modifications
- What to do when existing configuration is malformed

### Codex Recovery

Include a troubleshooting entry for:

```text
missing assignment between key-value pairs, expected `=`
```

Explain how to:

1. Stop further setup attempts.
2. Back up the corrupted configuration.
3. Restore a valid configuration from a trusted backup or version history.
4. Validate TOML syntax.
5. Re-run the corrected setup procedure.

Do not suggest deleting the entire Codex configuration as the normal recovery method.

### Deliverable

Accurate setup and recovery documentation.

---

## 18. Definition of Done

Phase 5.7 is complete when:

- [ ] Root cause of the Codex TOML corruption is identified.
- [ ] Codex TOML serialization is corrected.
- [ ] Existing Codex project trust settings are preserved.
- [ ] Existing Codex model and approval settings are preserved.
- [ ] Claude Code adapter has been audited and corrected.
- [ ] Cursor adapter has been audited and corrected.
- [ ] VS Code / GitHub Copilot adapter has been audited and corrected.
- [ ] Gemini CLI adapter has been audited and corrected.
- [ ] Official configuration specifications have been reviewed.
- [ ] Agent-specific parsing and serialization are correct.
- [ ] Existing unrelated MCP servers are preserved.
- [ ] Unknown settings are preserved.
- [ ] Invalid configurations are never silently overwritten.
- [ ] Configuration updates are safe and recoverable.
- [ ] Dry-run correctly previews changes.
- [ ] Repeated setup is idempotent.
- [ ] Removal affects only RenderEye-owned entries.
- [ ] MCP startup commands reference valid executables.
- [ ] Windows paths with spaces and backslashes work.
- [ ] Regression fixtures exist for every agent.
- [ ] Configuration preservation tests pass for every agent.
- [ ] Failure-injection tests pass.
- [ ] Existing RenderEyeMCP tests remain passing.
- [ ] Real client integration has been verified where possible.
- [ ] Documentation and troubleshooting guides are updated.

### Mandatory Safety Gate

**Phase 5.7 must not be considered complete if any supported coding agent adapter can overwrite unrelated configuration, generate invalid configuration syntax, or corrupt an existing file during a failed operation.**

An adapter that cannot safely modify a configuration must refuse the operation without writing.

---

## 19. Execution Instructions

Execute the work in this order:

1. Inspect the current repository.
2. Reproduce the Codex configuration corruption using synthetic fixtures.
3. Identify the root cause.
4. Audit every supported agent adapter.
5. Review the official configuration formats.
6. Define common configuration safety invariants.
7. Fix Codex TOML handling.
8. Fix Claude Code configuration handling.
9. Fix Cursor configuration handling.
10. Fix VS Code / GitHub Copilot configuration handling.
11. Fix Gemini CLI configuration handling.
12. Implement safe file updates and conflict detection.
13. Implement or correct dry-run behavior.
14. Implement safe removal.
15. Correct MCP executable resolution.
16. Create regression fixtures.
17. Implement preservation tests.
18. Implement failure-injection tests.
19. Execute automated tests.
20. Execute real client tests where practical.
21. Update documentation.
22. Review all acceptance criteria.
23. Produce the final report.

Work autonomously using the available repository and development tools.

Do not stop after fixing only Codex.

Do not replace entire configuration files with generated templates.

Do not repair malformed user settings speculatively.

Do not implement unrelated features.

Do not modify the production engine.

Do not publish a GitHub Release without explicit authorization.

---

## 20. Final Report

After implementation, report:

1. **Root Cause Analysis** — Exact cause of Codex configuration corruption.
2. **Affected Components** — All configuration adapters and shared code.
3. **Files Changed** — Implementations, tests, and documentation.
4. **Agent Audit Matrix** — Results for Claude Code, Codex, Cursor, VS Code, and Gemini CLI.
5. **Configuration Preservation** — How unrelated settings are protected.
6. **Transactional Safety** — Backup, validation, atomic writes, and recovery.
7. **Regression Tests** — Exact commands and outcomes.
8. **MCP Startup Verification** — Installed executable resolution and connection results.
9. **Real Client Tests** — Verified integrations and untested cases.
10. **Documentation Changes** — Setup and recovery instructions.
11. **Known Limitations** — Any remaining constraints.
12. **Phase 5.7 Status** — Complete, partially verified, or blocked.
13. **Release Readiness** — Whether `setup-agent` is safe to distribute.

Do not claim an integration is verified unless corresponding tests were actually executed.

**Primary Goal: Make every RenderEyeMCP coding agent configuration operation safe, targeted, idempotent, format-correct, and non-destructive, so users can register or remove the MCP server without risking their existing agent configuration.**
