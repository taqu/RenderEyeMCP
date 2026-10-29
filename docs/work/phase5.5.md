# RenderEyeMCP — Phase 5.5 Implementation Instructions

## Documentation Overhaul, Installation Guide & User Experience

## Objective

Implement **Phase 5.5: Documentation Overhaul & User Experience** for RenderEyeMCP.

Previous development phases implemented the MCP server, RenderDoc extension, Capture Registry, Session Manager, installation mechanisms, coding agent integrations, and GitHub Actions release infrastructure.

However, the repository's documentation, particularly `README.md`, has not been properly updated to reflect these changes.

Phase 5.5 must comprehensively review, correct, reorganize, and improve the documentation so that new users can successfully install and use RenderEyeMCP without understanding its internal implementation.

**This is a documentation-focused implementation phase. The primary deliverable is a substantially rewritten, accurate, complete, and user-friendly README.md.**

Do not stop after producing a documentation plan.

Actually modify the repository documentation files.

Do not consider this phase complete unless `README.md` has been meaningfully updated and the documented procedures have been validated.

---

## 1. Documentation Principles

Follow these principles throughout the work.

### Accuracy First

Documentation must describe the application as it actually exists.

- Inspect the implementation before documenting commands.
- Verify CLI arguments and subcommands.
- Verify installation procedures.
- Verify package and executable names.
- Verify configuration file locations.
- Verify RenderDoc extension installation paths.
- Verify supported MCP clients.
- Verify release artifact names.
- Verify actual platform compatibility.

Do not document proposed features as already implemented.

If an expected feature is missing, report the discrepancy.

Do not invent commands, configuration schemas, installation paths, release URLs, or unsupported capabilities.

### User-Oriented Writing

Write documentation for users who have never seen the project before.

Assume they understand basic development tools but may be unfamiliar with:

- MCP servers
- RenderDoc Python extensions
- `uv`
- Python virtual environments
- `.env` configuration
- Coding agent MCP configuration files

Explain unfamiliar concepts briefly when necessary.

Avoid excessive internal architecture explanations in the README.

### Documentation Language

Write all project documentation in clear, natural English.

Prefer concise sentences and practical examples.

Use consistent terminology throughout the repository.

### Copy-and-Paste Reliability

Commands should be directly usable whenever possible.

Clearly distinguish:

- PowerShell
- Bash
- JSON
- TOML
- Environment configuration
- Example output

Do not mix Windows and Linux syntax in the same command block.

Do not include commands that depend on an unspecified working directory.

### Progressive Disclosure

The README should provide a straightforward path from installation to first use.

Detailed explanations belong in dedicated documentation pages.

A user should not need to read the complete architecture documentation to install RenderEyeMCP.

---

## 2. Task A — Repository and Documentation Audit

Before editing documentation:

1. Inspect the complete repository.
2. Read the existing `README.md`.
3. Read all files under `docs/`.
4. Inspect `pyproject.toml`.
5. Inspect installed console entry points.
6. Inspect the CLI implementation.
7. Inspect RenderDoc extension packaging.
8. Inspect installation and uninstallation scripts.
9. Inspect `.env` configuration handling.
10. Inspect coding agent configuration generators.
11. Inspect GitHub Actions workflows.
12. Inspect release packaging scripts.
13. Inspect the MCP tool implementations.
14. Run relevant commands and tests where possible.

### Documentation Inventory

Identify:

- Missing documentation
- Outdated information
- Incorrect commands
- Duplicated explanations
- Broken relative links
- Inconsistent file paths
- Inconsistent executable names
- Missing installation steps
- Missing prerequisites
- Unsupported claims
- Incorrect MCP configuration examples
- Missing troubleshooting instructions

### Implementation Verification

Check whether these commands actually exist:

```text
rendereye-mcp --help
rendereye-mcp --version
rendereye-mcp serve
rendereye-mcp setup
rendereye-mcp setup-agent
rendereye-mcp doctor
rendereye-mcp uninstall-setup
```

These are expected interfaces from the previous development plan, not assumptions about the current implementation.

Use the actual implementation as the source of truth.

If some commands are missing, do not silently document them as available.

Record missing functionality separately.

### Deliverable

Create a documentation audit summary identifying incorrect and missing information.

---

## 3. Task B — Completely Review and Rewrite README.md

**This is the highest-priority task in Phase 5.5.**

The existing `README.md` must be substantially revised where necessary.

Do not simply append a new paragraph to the existing README.

Reorganize and replace outdated sections.

Preserve accurate and useful existing content.

### Recommended README Structure

```text
README.md

1. Project Title and Introduction
2. Key Features
3. How It Works
4. Requirements
5. Installation
   5.1 Quick Installation with uv
   5.2 Installation Without uv
   5.3 Manual Installation
6. Initial Setup
7. Coding Agent Integration
8. Quick Start
9. Configuration
10. MCP Tools
11. Updating
12. Uninstallation
13. Troubleshooting
14. Supported Platforms
15. Development
16. Contributing
17. License
```

Adapt the structure if the actual repository requires a different organization.

Avoid unnecessary sections that contain no useful information.

### README Quality Requirements

The README must:

- Explain what RenderEyeMCP does.
- Explain why it is useful.
- Explain how it works at a high level.
- Present the simplest installation method first.
- Provide working installation commands.
- Explain how to configure RenderDoc.
- Explain how to configure coding agents.
- Provide a minimal first-use example.
- Link to detailed documentation.
- Explain where to find help.
- Clearly distinguish user installation from development setup.

### First-Time User Experience

A new visitor should be able to answer these questions immediately:

1. What is RenderEyeMCP?
2. Why would I use it?
3. What software do I need?
4. How do I install it?
5. How do I connect RenderDoc?
6. How do I connect Claude Code or another coding agent?
7. How do I verify that everything works?
8. How do I open my first capture?
9. What should I do if installation fails?

### Deliverable

A substantially improved `README.md` that serves as the primary entry point for the project.

---

## 4. Task C — Project Overview and Feature Explanation

Rewrite the introductory documentation to clearly explain RenderEyeMCP.

### Project Description

RenderEyeMCP is an MCP server and RenderDoc Python extension that enables coding agents to discover and manage RenderDoc capture files (`.rdc`) and control debugging sessions.

Its primary focus is reliable capture lifecycle management and RenderDoc GUI orchestration.

### Core Features

Document verified implementations of:

- Automatic `.rdc` discovery
- Latest capture identification
- Capture Registry
- Persistent Capture IDs
- RenderDoc process discovery
- Multiple RenderDoc GUI sessions
- Session IDs
- Window focusing
- Safe session closure
- Protected sessions
- RenderDoc Python extension integration
- GUI state synchronization
- MCP integration with coding agents

Only describe features as available when they have actually been implemented.

### Project Scope

Explain that RenderEyeMCP focuses on capture and session management.

Do not imply that it currently provides:

- Shader debugging
- Texture analysis
- Pipeline state inspection
- Automatic GPU bug diagnosis
- GPU frame difference analysis

Unless such capabilities have been separately implemented and verified, keep them out of the main feature list.

### How It Works

Include a simple architectural overview.

Example:

```text
Coding Agent
    |
    | MCP
    v
RenderEyeMCP Server
    |
    +-- Capture Registry
    +-- Session Manager
    +-- RenderDoc Connection Manager
                    |
                    | Local IPC
                    v
             RenderDoc Extension
                    |
                    v
               RenderDoc GUI
```

Use this only if it accurately reflects the implementation.

### Deliverable

A clear and approachable project introduction.

---

## 5. Task D — Quick Installation with uv

Make `uv tool install` the recommended end-user installation method.

### Important Distinction

Do not use `uv sync` as an end-user installation procedure.

`uv sync` is intended for the development checkout.

`uv tool install` is the preferred method for installing RenderEyeMCP as a persistent application.

### Recommended Workflow

Document the verified equivalent of:

```powershell
uv tool install .\rendereye_mcp-1.0.0-py3-none-any.whl
rendereye-mcp setup
rendereye-mcp setup-agent claude-code
rendereye-mcp doctor
```

The wheel filename and commands are illustrative.

Use actual filenames, entry points, and arguments from the repository.

### Installation Source

Explain how to obtain the package.

If RenderEyeMCP is distributed through GitHub Releases:

1. Link to the actual release page.
2. Explain which asset to download.
3. Explain where the downloaded wheel should be located when running the command.
4. Provide the exact installation command.

Do not invent a GitHub repository URL.

If the package is published to a supported package index, document index-based installation only after verifying availability.

### uv Prerequisite

Explain how to install `uv` using its official documentation.

Do not require Git.

Explain that `uv` can manage a compatible Python interpreter when supported.

### PATH Handling

Explain what to do if `rendereye-mcp` is not found after installation.

Document `uv tool update-shell` where appropriate.

Explain when the terminal or coding agent must be restarted.

### Verification

Show users how to check:

```powershell
rendereye-mcp --version
rendereye-mcp doctor
```

Only include commands confirmed to exist.

### Deliverable

A concise, correct, copy-and-paste-ready Quick Installation section.

---

## 6. Task E — Installation Without uv

Provide a complete alternative for users who do not want to install `uv`.

### Requirements

- Use standard Python.
- Use `venv`.
- Use `pip`.
- Install from a released wheel.
- Do not require Git.
- Do not require the source repository.
- Do not require administrator privileges by default.

### Windows

Provide verified PowerShell commands for:

1. Creating the application directory.
2. Creating the virtual environment.
3. Installing the wheel.
4. Running the setup command.
5. Configuring a coding agent.
6. Running diagnostics.

Recommended installation location:

```text
%LOCALAPPDATA%\RenderEyeMCP\
```

### Linux

Provide equivalent Bash instructions using an appropriate user-local directory.

Do not reuse Windows paths.

### Important Requirements

Explain:

- How to find the Python interpreter.
- How to install a supported Python version.
- How to select the downloaded wheel.
- How to run the installed CLI.
- How to avoid modifying global Python packages.

### Deliverable

Accurate installation instructions without `uv`.

---

## 7. Task F — Manual Installation

Provide clear manual installation instructions.

Manual installation must remain officially supported.

### Documentation

Create or update:

`docs/installation-manual.md`

### Required Instructions

Explain how to:

1. Install the RenderEyeMCP Python package.
2. Copy the RenderDoc extension manually.
3. Create `.env` from `.env.example`.
4. Configure the RenderDoc executable path.
5. Register `RENDEREYE_ENV_FILE`.
6. Configure a coding agent manually.
7. Verify MCP connectivity.
8. Update the installation.
9. Uninstall safely.

### RenderDoc Extension

Verify the correct extension directory.

On Windows, an expected candidate is:

```text
%APPDATA%\qrenderdoc\extensions\rendereye\
```

Do not assume that this path is correct without checking the supported RenderDoc extension discovery mechanism.

Explain how to enable the extension in RenderDoc.

### Important Packaging Detail

Do not reference:

```text
scripts/setup_env.py
scripts/install_extension.py
```

unless those files are actually included in the downloaded distribution and the documented command works from that distribution.

Prefer installed CLI commands for shared setup functionality.

### Deliverable

A complete manual installation guide independent of source checkout scripts.

---

## 8. Task G — Configuration Documentation

Document the centralized `.env` configuration system.

### Default Windows Configuration Location

```text
%LOCALAPPDATA%\RenderEyeMCP\.env
```

### Environment Variable

```text
RENDEREYE_ENV_FILE
```

Explain that the installer registers this variable at Windows User scope.

Do not describe it as a Machine-level environment variable.

### Startup Sequence

Document the actual behavior:

```text
Start MCP Server
    |
    v
Read RENDEREYE_ENV_FILE
    |
    v
Load .env into os.environ
    |
    v
Construct Config
    |
    v
Start Services
```

### Configuration Precedence

Document:

1. Existing process environment variables
2. Values loaded from `.env`
3. Application defaults

### RenderDoc Executable

Explain automatic discovery.

Preferred Windows candidate:

```text
C:\Program Files\RenderDoc\qrenderdoc.exe
```

Document the actual configuration key for overriding this path.

Do not assume the preferred path exists on every machine.

### Existing Configuration

Explain that setup and upgrade procedures preserve existing user settings.

### Configuration Changes

Explain when restarting the MCP server or coding agent is necessary.

### Security

Do not recommend committing actual `.env` files containing credentials or machine-specific settings.

### Deliverable

A concise README configuration section and a detailed configuration reference.

---

## 9. Task H — Coding Agent Setup Documentation

Document setup for the supported coding agents.

### Required Targets

- Claude Code
- OpenAI Codex CLI / IDE
- Cursor
- Visual Studio Code / GitHub Copilot
- Gemini CLI

### README

Provide a concise overview of supported agents.

Show verified commands for configuring them.

For example:

```powershell
rendereye-mcp setup-agent claude-code
rendereye-mcp setup-agent codex
rendereye-mcp setup-agent cursor
rendereye-mcp setup-agent vscode
rendereye-mcp setup-agent gemini
```

Only document supported names and commands confirmed by the implementation.

### Detailed Guides

Create or update:

```text
docs/agents/
├── claude-code.md
├── codex.md
├── cursor.md
├── vscode-copilot.md
└── gemini-cli.md
```

### Every Agent Guide Must Include

1. Prerequisites
2. Automatic setup
3. Manual setup
4. User-level configuration
5. Project-level configuration where supported
6. Complete configuration example
7. MCP server startup command
8. Connection verification
9. Example user prompts
10. Troubleshooting
11. Configuration removal

### Configuration Format

Verify the current documented MCP configuration format for every agent.

Do not assume that all agents use the same JSON structure.

In particular, distinguish VS Code MCP configuration from portable Copilot MCP configuration where applicable.

### Executable Path

Explain that generated MCP settings should reference the verified installed executable.

Do not use the development virtual environment in user documentation.

### Shared Configuration

Explain that RenderEyeMCP application settings are centralized in `.env`.

Do not instruct users to duplicate RenderDoc executable paths across every coding agent.

### Verification

Document how to verify that the agent can actually invoke `server_status` or another read-only MCP tool.

Do not confuse successful configuration-file generation with successful MCP connectivity.

### Deliverable

Complete, accurate coding agent setup documentation.

---

## 10. Task I — Quick Start Tutorial

Add a practical first-use walkthrough.

The README should include a short Quick Start section.

### Example Workflow

After installation:

1. Start RenderDoc.
2. Verify the RenderEye extension is loaded.
3. Generate or locate a valid `.rdc` capture.
4. Confirm that RenderEyeMCP discovers it.
5. Start a configured coding agent.
6. Ask the agent to list available RenderDoc captures.
7. Ask the agent to open the latest capture.
8. Verify that the correct RenderDoc window opens.

### Example Prompts

Provide examples such as:

> List the available RenderDoc captures.

> Open the latest RenderDoc capture.

> Open the latest capture in a new window and keep the previous one.

> Show the currently active RenderDoc sessions.

> Focus the window associated with the previous capture.

Only use prompts supported by actual implemented MCP functionality.

### Error Cases

Explain what the user should expect if:

- No captures are available.
- RenderDoc is not installed.
- The extension is disconnected.
- A session is protected.
- The requested capture is missing.
- A GUI operation cannot be verified.

### Deliverable

A short, practical Quick Start guide that demonstrates RenderEyeMCP's primary value.

---

## 11. Task J — MCP Tool Reference

Document all publicly exposed MCP tools.

### Requirements

Inspect the actual MCP server tool registration.

Do not generate the tool list solely from previous roadmap documents.

### README

Provide a compact overview of the most important tools.

### Detailed Reference

Create or update:

`docs/mcp_api.md`

For each implemented tool, document:

- Tool name
- Purpose
- Parameters
- Default values
- Example request
- Example response
- Side effects
- Error behavior
- Safety restrictions

### Categories

Organize tools into:

- Capture Management
- Session Management
- Instance Management
- Diagnostics

Only include categories with actual implemented tools.

### Tool Accuracy

Ensure documented tool names exactly match registered MCP tool names.

Do not document internal Python methods as public MCP tools.

### Deliverable

An accurate and useful MCP API reference.

---

## 12. Task K — Updating and Uninstallation

Provide clear update and removal procedures.

### uv Installation

Document the supported method for installing a newer release wheel.

Do not assume that `uv tool upgrade` can automatically discover newer versions from locally downloaded wheel files.

### pip Installation

Explain how to upgrade the package inside its dedicated virtual environment.

### Configuration Preservation

Explain which files are retained during upgrades:

- `.env`
- Capture Registry
- Session Registry
- User-defined settings

### Extension Updates

Explain how the RenderDoc extension is updated and whether RenderDoc must restart.

### Uninstallation

Document:

- Removing the Python application
- Removing agent MCP registrations
- Removing RenderDoc extension files
- Handling `RENDEREYE_ENV_FILE`
- Preserving user capture files
- Preserving registry data by default

Do not provide commands that indiscriminately delete directories containing user data.

### Deliverable

Safe, verified update and uninstall instructions.

---

## 13. Task L — Troubleshooting Documentation

Create or improve:

`docs/troubleshooting.md`

### Required Problems

Include solutions for:

- `uv` command not found
- `rendereye-mcp` command not found
- Python not found
- Unsupported Python version
- Wheel installation failure
- RenderDoc executable not found
- RenderDoc extension not detected
- RenderDoc extension fails to load
- MCP server fails to start
- Coding agent cannot connect
- Invalid MCP configuration
- `RENDEREYE_ENV_FILE` missing
- `.env` not found
- Incorrect RenderDoc executable path
- No `.rdc` captures discovered
- Capture not ready
- GUI state unavailable
- Window focus fails
- Protected session cannot be closed
- IPC connection failure
- Server restart loses connection temporarily

### Troubleshooting Format

For each issue, provide:

1. Symptom
2. Likely causes
3. Diagnostic command
4. Resolution
5. Related documentation link

Prefer actionable instructions over generic advice.

### Diagnostics

Use the actual implemented `doctor` functionality where available.

Do not invent diagnostic flags.

### Deliverable

A troubleshooting guide that resolves common installation and runtime problems.

---

## 14. Task M — Development Documentation

Keep development instructions separate from user installation instructions.

### README

Provide only a short development section.

Example:

```powershell
git clone <repository-url>
cd RenderEyeMCP
uv sync
uv run pytest
```

Replace placeholders with verified repository information when available.

### Detailed Documentation

Maintain:

`docs/development.md`

Include:

- Repository structure
- Development prerequisites
- `uv sync`
- Running tests
- Running lint checks
- Starting the MCP server from source
- Extension development
- Local RenderDoc testing
- Unity integration testing
- Building wheels
- Building release archives
- GitHub Actions workflows

### Unity Test Project

Document the optional Unity project:

`tests/TestProject`

Explain its purpose as an integration-testing environment.

Do not present Unity as a required dependency for end users.

### Development Isolation

Explain that development installations may use the repository-local `.venv`.

Do not confuse this environment with `uv tool install`.

### Deliverable

Clean separation between user documentation and developer documentation.

---

## 15. Task N — GitHub Releases Documentation

Align installation instructions with Phase 5.2 GitHub Actions release artifacts.

### Requirements

Inspect the actual release packaging scripts and workflows.

Verify:

- Wheel filename conventions
- Extension archive filename
- Manual installation bundle filename
- Source distribution
- Checksums
- Release versioning

### GitHub Links

Use the actual repository URL.

Do not invent GitHub owner or repository names.

### Release Assets

Explain which asset a user should download for:

- Recommended uv installation
- pip installation
- Manual extension installation
- Manual installation bundle

### Checksums

If `SHA256SUMS.txt` is actually generated, document how to verify it.

### Compatibility

Explain which versions of RenderDoc, Python, and operating systems have actually been tested.

Do not claim compatibility solely because CI unit tests pass.

### Deliverable

Release documentation consistent with the real GitHub Actions outputs.

---

## 16. Task O — Documentation Consistency and Navigation

Review the documentation as a complete system.

### Navigation

Ensure that:

- README links to detailed guides.
- Every linked local document exists.
- Relative paths are correct.
- Headings generate the intended anchors.
- Users can return to the README from major guides.
- Similar topics use consistent terminology.

### Terminology

Standardize:

- RenderEyeMCP
- RenderDoc
- Capture
- Capture ID
- Instance
- Window
- Session
- Session ID
- RenderDoc Extension
- MCP Server
- Coding Agent

### Duplication

Avoid copying large installation procedures into multiple files.

Prefer:

- Short README instructions
- Detailed installation documentation
- Agent-specific configuration guides
- Shared configuration reference

### Markdown Quality

Ensure:

- Valid Markdown syntax
- Correct fenced code blocks
- Appropriate language identifiers
- Readable tables
- Consistent heading hierarchy
- No placeholder documentation
- No empty sections
- No broken links
- No duplicate contradictory instructions

### Deliverable

A coherent, easy-to-navigate documentation structure.

---

## 17. Task P — Documentation Validation

Documentation correctness must be tested.

### Command Validation

Verify documented commands against the installed application.

At minimum, test:

- Application version
- Help output
- Setup command
- Diagnostic command
- Agent setup command
- MCP startup command

Avoid running destructive or user-modifying setup commands against real configurations without authorization.

Use isolated directories and test accounts where appropriate.

### Package Validation

Build the wheel and install it in a clean environment.

Verify that documented installation commands work without relying on the source checkout.

### Configuration Validation

Validate:

- `.env.example`
- JSON examples
- TOML examples
- Supported agent configuration files
- RenderDoc path examples

### Link Validation

Check all local Markdown links.

Check external links where network access is available.

Do not mark unverified links as successfully checked.

### Windows and Linux

Validate platform-specific commands in the corresponding environment where available.

Do not claim Linux command verification based on Windows testing.

### Documentation Testing

Add lightweight automated checks where useful.

Examples:

- Markdown linting
- Local link validation
- CLI documentation consistency tests
- Configuration example parsing
- Release asset naming checks

Avoid introducing a heavy documentation framework for a small repository.

### Deliverable

Evidence that the rewritten documentation corresponds to working functionality.

---

## 18. Task Q — User Experience Review

Evaluate the documentation from the perspective of a new user.

### Scenario A — uv User

A user has `uv` installed but has never used RenderEyeMCP.

Can they:

1. Find the correct release asset?
2. Install RenderEyeMCP?
3. Configure RenderDoc?
4. Register Claude Code?
5. Verify the connection?
6. Open a capture?

### Scenario B — Windows User Without uv

A user has Python and RenderDoc installed.

Can they install the application without cloning the repository?

### Scenario C — Manual Installation

A user does not want to run the automatic installer.

Can they manually install the wheel, copy the extension, configure `.env`, and register their coding agent?

### Scenario D — Alternative Coding Agent

A user prefers Codex, Cursor, VS Code/Copilot, or Gemini CLI.

Can they find the correct setup instructions without reading the Claude Code guide?

### Scenario E — Existing Installation

A user wants to update RenderEyeMCP without losing configuration or capture history.

Are the update instructions clear and safe?

### Scenario F — Troubleshooting

A user installs RenderEyeMCP, but the agent cannot connect.

Can they identify the relevant diagnostic commands and likely solutions?

### Review Criteria

For each scenario, identify:

- Missing prerequisites
- Ambiguous steps
- Unnecessary complexity
- Incorrect assumptions
- Missing verification steps
- Confusing links
- Unsupported claims

Fix the documentation rather than merely listing usability issues.

### Deliverable

A user-oriented documentation usability review with corrections applied.

---

## 19. Documentation Scope Boundaries

Phase 5.5 is primarily a documentation task.

Do not implement unrelated features.

Do not introduce:

- GPU analysis
- Shader debugging
- Texture inspection
- Automatic frame comparison
- New session-management functionality
- New networking infrastructure
- Unrelated architectural refactoring

### Missing Implementation

If documentation review reveals that an expected setup command or installation mechanism is missing:

1. Verify that it is genuinely absent.
2. Determine whether a working alternative already exists.
3. Document the verified alternative.
4. Record the implementation discrepancy.
5. Fix small documentation-support defects only when necessary and safely within scope.

Do not silently expand Phase 5.5 into a large application implementation phase.

Do not claim completion of unsupported workflows.

---

## 20. Definition of Done

Phase 5.5 is complete when:

- [ ] `README.md` has been substantially reviewed and updated.
- [ ] README accurately explains RenderEyeMCP.
- [ ] README lists only verified features.
- [ ] Recommended `uv tool install` instructions are correct.
- [ ] Installation without `uv` is documented.
- [ ] Manual installation is documented.
- [ ] Development setup is separate from end-user installation.
- [ ] RenderDoc extension installation is documented.
- [ ] `.env` configuration is documented.
- [ ] `RENDEREYE_ENV_FILE` behavior is explained.
- [ ] RenderDoc executable discovery is explained.
- [ ] Claude Code setup is documented.
- [ ] Codex setup is documented.
- [ ] Cursor setup is documented.
- [ ] VS Code / GitHub Copilot setup is documented.
- [ ] Gemini CLI setup is documented.
- [ ] Automatic and manual agent configuration are explained.
- [ ] Quick Start examples are provided.
- [ ] Public MCP tools are accurately documented.
- [ ] Update instructions are correct.
- [ ] Uninstallation instructions are safe.
- [ ] Troubleshooting documentation is useful.
- [ ] GitHub Release assets are documented accurately.
- [ ] Windows and Linux compatibility claims are evidence-based.
- [ ] Local documentation links are valid.
- [ ] Configuration examples are syntactically valid.
- [ ] Documented commands correspond to implemented functionality.
- [ ] Existing application tests remain passing.
- [ ] Documentation validation has been executed.
- [ ] No misleading placeholder instructions remain.

### Mandatory README Gate

**Phase 5.5 must not be marked complete if README.md remains essentially unchanged.**

The final report must explicitly show which README sections were added, replaced, reorganized, or corrected.

Documentation planning without modifying README.md is not an acceptable outcome.

---

## 21. Execution Instructions

Execute the following sequence:

1. Inspect the repository and existing README.
2. Read existing documentation.
3. Inspect CLI commands and packaging.
4. Inspect installation and setup implementation.
5. Inspect coding agent integration.
6. Inspect GitHub Release workflows.
7. Verify available application functionality.
8. Identify outdated documentation.
9. Rewrite and reorganize README.md.
10. Correct Quick Installation with uv.
11. Correct installation without uv.
12. Improve manual installation instructions.
13. Document centralized `.env` configuration.
14. Update all coding agent setup guides.
15. Add or correct Quick Start examples.
16. Update MCP tool documentation.
17. Update upgrade and uninstallation guides.
18. Improve troubleshooting documentation.
19. Separate development documentation.
20. Verify all documentation links.
21. Validate command and configuration examples.
22. Run relevant automated tests.
23. Review the documentation as a new user.
24. Correct remaining inconsistencies.
25. Review all acceptance criteria.
26. Produce the final report.

### Execution Rules

Work autonomously using the repository and available tools.

**Actually edit README.md and the necessary documentation files.**

Do not stop after generating a documentation outline.

Do not claim commands work unless the implementation or tests support them.

Do not retain obsolete installation procedures simply because they existed previously.

Do not copy earlier instructions without checking the current codebase.

Do not invent GitHub Releases or package index availability.

Do not modify the production engine.

Do not modify RenderDoc source code.

Do not implement unrelated application features.

Do not publish a GitHub Release without authorization.

---

## 22. Final Report

After completing Phase 5.5, provide:

### 1. Documentation Summary

Describe the documentation improvements.

### 2. README Changes

List the exact sections that were:

- Added
- Rewritten
- Reorganized
- Removed
- Corrected

This section is mandatory.

### 3. Files Changed

List all documentation files modified or created.

### 4. Installation Documentation

Report which installation methods were verified.

### 5. Coding Agent Documentation

Report the documentation status for:

- Claude Code
- Codex
- Cursor
- VS Code / GitHub Copilot
- Gemini CLI

### 6. Configuration Documentation

Describe verified `.env` and environment-variable behavior.

### 7. MCP API Documentation

Report whether documented tool names match the actual MCP server.

### 8. Validation Results

Include:

- Commands executed
- Link validation results
- Configuration example validation
- Relevant automated test results
- Real installation tests where available

### 9. Discrepancies

List expected functionality that is missing or differs from previous instructions.

### 10. Remaining Issues

List only unresolved documentation problems or implementation dependencies.

### 11. Phase 5.5 Status

Classify the result as:

- COMPLETE
- PARTIALLY VERIFIED
- BLOCKED

Do not report COMPLETE if README.md was not meaningfully updated.

Do not report successful validation of commands that were not actually executed.

**Primary Goal: Transform RenderEyeMCP documentation into a clear, accurate, friendly, and complete user experience, with README.md serving as the reliable entry point from first installation to successful coding agent integration.**
