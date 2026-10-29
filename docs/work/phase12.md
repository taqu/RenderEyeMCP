# Phase 12 — Release Preparation & Bilingual Documentation

## Objective

Prepare RenderEyeMCP for its first public open-source release by improving documentation, installation experience, practical usage examples, project presentation, and release readiness.

The primary goal is to make RenderEyeMCP accessible to developers who are unfamiliar with its architecture and have never used it before.

A new user should be able to:

1. Understand what RenderEyeMCP does.
2. Understand how it integrates RenderDoc with AI coding agents.
3. Install and configure it on a clean machine.
4. Connect a supported coding agent.
5. Open a capture using RenderDoc, Unity, or Unreal Engine.
6. Inspect the existing capture through an AI coding agent.
7. Follow practical rendering-debugging examples.
8. Troubleshoot common installation and runtime problems.

**Provide equivalent English and Japanese documentation.**

English will be the default documentation language, with Japanese documentation maintained alongside it.

This phase prioritizes documentation, usability, validation, and release preparation.

Do not introduce unrelated rendering inspection features.

---

## 1. Investigate the Current Project

Before making changes, inspect the entire repository.

Identify:

- Current README and documentation.
- Project architecture and components.
- Existing installation mechanisms.
- Supported operating systems.
- Supported RenderDoc versions.
- Supported Python versions.
- Runtime dependencies.
- RenderDoc extension installation.
- MCP server installation.
- Shared IPC Service configuration.
- Environment variable handling.
- Supported coding agents.
- Existing MCP tool definitions.
- Existing automated tests.
- Existing CI workflows.
- Release packaging and distribution mechanisms.
- Project license and third-party dependencies.

Review the implementation status of Phases 0–11.

Do not assume that every previously planned feature has been implemented successfully.

### 1.1 Establish the Actual Feature Inventory

Produce a feature inventory based on the repository.

Distinguish:

- Implemented and tested.
- Implemented but not fully tested.
- Partially implemented.
- Planned but not implemented.
- Unsupported.

Use this inventory as the source of truth for documentation.

**Do not document planned features as currently available.**

### 1.2 Preserve Existing Architecture

Retain the established architecture:

```text
AI Coding Agent
      |
      v
MCP Server
      |
      v
Shared IPC Service
      |
      v
RenderDoc Extension
      |
      v
RenderDoc GUI / Replay Context
```

Update this diagram if the actual repository architecture differs.

Use the implementation as the authoritative reference.

Avoid unnecessary architectural changes during release preparation.

---

## 2. Documentation Structure

Establish a consistent bilingual documentation structure.

Suggested layout:

```text
README.md
README.ja.md

docs/
  en/
    installation.md
    configuration.md
    quickstart.md
    tools.md
    troubleshooting.md
    architecture.md

    examples/
      active-capture.md
      missing-object.md
      shader-resources.md
      render-target.md
      depth-debugging.md
      compute-dispatch.md

  ja/
    installation.md
    configuration.md
    quickstart.md
    tools.md
    troubleshooting.md
    architecture.md

    examples/
      active-capture.md
      missing-object.md
      shader-resources.md
      render-target.md
      depth-debugging.md
      compute-dispatch.md
```

Adapt the structure if the repository already has a suitable documentation organization.

Avoid duplicating files unnecessarily.

### 2.1 Language Policy

Use:

- English for `README.md`.
- Japanese for `README.ja.md`.
- English documentation under `docs/en/`.
- Japanese documentation under `docs/ja/`.

Both languages must provide equivalent technical information.

They do not need to be literal sentence-by-sentence translations.

Preserve technical meaning, command syntax, API names, and configuration keys.

### 2.2 Language Navigation

Provide visible language links at the beginning of each document.

For example:

```markdown
[English](README.md) | [日本語](README.ja.md)
```

Use corresponding links for documents under `docs/en/` and `docs/ja/`.

Ensure all relative links work when viewed on GitHub.

### 2.3 Documentation Consistency

Maintain consistent:

- Terminology.
- Section organization.
- Feature descriptions.
- Installation commands.
- Configuration examples.
- Tool names.
- Troubleshooting procedures.
- Platform support statements.

Avoid creating different installation procedures for English and Japanese readers.

---

## 3. Rewrite the Main README

Rewrite `README.md` to serve as the primary entry point for new users.

Create a Japanese equivalent in `README.ja.md`.

The README should explain the project clearly without requiring readers to understand MCP internals.

### 3.1 Project Introduction

Explain:

- What RenderEyeMCP is.
- What problem it solves.
- Who it is intended for.
- How it connects RenderDoc and AI coding agents.
- Why active GUI capture inspection is useful.

Emphasize the project's core value:

**RenderEyeMCP allows AI coding agents to inspect rendering information from captures already opened in RenderDoc.**

A developer should not need to reopen a capture through the coding agent.

### 3.2 Typical Workflow

Introduce a simple workflow:

```text
Game Engine
    |
    | Capture Frame
    v
RenderDoc GUI
    |
    | Loaded Capture
    v
RenderEyeMCP
    |
    | MCP Tools
    v
AI Coding Agent
    |
    v
Rendering Debugging Assistance
```

Explain that RenderDoc remains the primary capture and replay application.

RenderEyeMCP provides an interface for AI agents to retrieve inspection information.

### 3.3 README Sections

Include:

1. Project overview.
2. Key features.
3. Supported platforms.
4. Requirements.
5. Quick installation.
6. Coding agent configuration.
7. Quick usage example.
8. Documentation links.
9. Troubleshooting links.
10. Development and contribution information.
11. License.

Keep the README concise.

Detailed information belongs in dedicated documentation pages.

### 3.4 Feature Description

Describe verified capabilities, potentially including:

- Existing RenderDoc session discovery.
- Active capture information.
- Draw call and event inspection.
- Pipeline state inspection.
- Resource and buffer inspection.
- Shader reflection.
- Texture and pixel inspection.
- Shared IPC and multi-agent support.

Only include features confirmed by repository inspection.

Clearly describe limitations.

### 3.5 Project Positioning

Avoid presenting RenderEyeMCP as:

- A replacement for RenderDoc.
- A complete autonomous graphics debugger.
- A GPU profiler, unless profiling tools are actually implemented.
- A tool that automatically identifies every rendering problem.
- A tool that guarantees support for every graphics API.

Position it as a bridge between RenderDoc and coding agents.

### 3.6 Visual Materials

Consider adding a small number of useful screenshots or diagrams.

Recommended visuals:

- RenderDoc with a loaded capture.
- Coding agent inspecting the active capture.
- Example pipeline or resource inspection results.
- Architecture overview.

Use genuine screenshots from the project when possible.

Do not create fake screenshots implying functionality that has not been implemented.

Avoid large decorative images that make the README difficult to navigate.

---

## 4. Installation Documentation

Create detailed installation guides in both languages.

Prioritize a straightforward installation experience for Windows users.

Do not intentionally restrict the project to Windows if other platforms are supported by the implementation.

### 4.1 Installation Goals

A user should be able to install RenderEyeMCP without:

- Cloning the development repository unless necessary.
- Understanding the Python package architecture.
- Modifying source code.
- Manually debugging Python import paths.
- Understanding IPC implementation details.

Prefer the simplest supported release installation method.

### 4.2 Installation Methods

Investigate and document the actual supported installation methods.

Potential methods include:

- Packaged release installation.
- Installation through `uv`.
- Manual installation.
- Development installation from source.

Do not document hypothetical commands as working installation methods.

Validate the installation commands against the actual package and release structure.

### 4.3 Windows Installation

Provide instructions for a clean Windows environment.

Cover:

- Prerequisites.
- Installing RenderEyeMCP.
- Installing the RenderDoc extension.
- RenderDoc installation detection.
- Environment configuration.
- MCP server setup.
- Verifying successful installation.

Where supported, detect the default RenderDoc installation location:

```text
C:\Program Files\RenderDoc\
```

Do not assume RenderDoc is always installed there.

Explain how users with custom installation paths can configure them.

### 4.4 Environment Configuration

Document the actual environment configuration mechanism.

Inspect the current implementation before writing instructions.

The existing project design has used:

- An installation-local `.env` file.
- Automatic RenderDoc path detection.
- `RENDEREYE_ENV_FILE` for locating configuration.

Verify that these mechanisms are implemented and supported.

If confirmed, explain them clearly.

Do not ask users to configure unnecessary global environment variables.

### 4.5 Installation Verification

Provide a practical verification procedure.

The user should be able to confirm:

1. MCP server starts successfully.
2. RenderDoc extension loads.
3. Shared IPC communication works.
4. A RenderDoc GUI session can be discovered.
5. An already-loaded capture can be inspected.

Avoid presenting a successful process launch as proof that all components are connected.

### 4.6 Clean Machine Testing

Test the documented process in a clean environment where practical.

Document exactly which environments were validated.

Do not claim clean installation was tested if only a development virtual environment was used.

---

## 5. Coding Agent Configuration

Provide configuration instructions for the coding agents actually supported by the project.

Potential targets include:

- Claude Code.
- Codex.
- Other MCP-compatible coding agents.

Do not assume that all agents use identical MCP configuration formats.

### 5.1 Agent-Specific Instructions

For each verified agent, document:

- Required prerequisites.
- MCP server registration.
- Executable command.
- Required arguments.
- Environment configuration.
- How to confirm tool discovery.
- How to test RenderDoc connectivity.
- Common agent-specific errors.

### 5.2 Copyable Configuration

Provide copyable examples using the actual supported command and configuration syntax.

Avoid hardcoding developer-specific directories such as:

```text
D:\Projects\python\RenderEyeMCP\
```

Prefer installation-relative or automatically resolved paths where supported.

If absolute paths are unavoidable, clearly mark them as placeholders.

### 5.3 Multiple Agents

Explain the Shared IPC Service architecture.

Document that multiple MCP client processes can connect to the same RenderDoc environment when supported.

Provide a simple example using two coding agents.

Do not require users to manually allocate separate IPC ports unless the actual implementation requires it.

### 5.4 Verification Prompts

Include simple agent prompts that verify the connection.

For example:

> List the available RenderDoc sessions.

> What capture is currently loaded in RenderDoc?

> Show the selected draw call and its pipeline state.

These are natural-language prompts, not exact MCP tool names.

Explain the difference.

---

## 6. Quick Start Tutorial

Create a short first-use tutorial.

The tutorial should demonstrate the project's most important workflow:

**Inspecting a capture already open in RenderDoc.**

### 6.1 Recommended Steps

1. Install RenderEyeMCP.
2. Configure a supported coding agent.
3. Start RenderDoc.
4. Open an `.rdc` capture.
5. Select a draw call.
6. Ask the coding agent to inspect the current capture.
7. Inspect pipeline state or resource information.
8. Understand the returned results.

### 6.2 Example Prompt

> Inspect the capture currently open in RenderDoc. Identify the selected draw call and summarize its pipeline state.

### 6.3 Expected Behavior

Explain that the agent should:

- Discover the active RenderDoc GUI session.
- Identify the loaded capture.
- Retrieve the selected event.
- Query the relevant inspection tools.
- Summarize the returned information.

The agent should not reopen the capture unnecessarily.

### 6.4 Tutorial Validation

Run the tutorial against the actual implementation where possible.

Verify that:

- Tools exist.
- Parameters are correct.
- Information is available.
- The workflow can be completed without undocumented steps.

If the workflow cannot be validated, explicitly mark it as unverified.

---

## 7. Practical Coding Agent Debugging Scenarios

Create scenario-oriented documentation.

These examples are a major deliverable of Phase 12.

Each scenario must explain how a developer can use a coding agent and RenderEyeMCP to investigate a real rendering problem.

Do not write examples that simply list MCP tools.

Focus on the user's debugging objective.

### 7.1 Common Scenario Format

Use a consistent structure:

1. **Problem** — What the developer observes.
2. **Preparation** — What to do in RenderDoc.
3. **Example Agent Prompt** — What to ask the coding agent.
4. **Investigation Workflow** — Information the agent should retrieve.
5. **Expected Observations** — What can be checked.
6. **Interpretation** — How observations relate to possible causes.
7. **Limitations** — What the tools cannot determine.
8. **Related Tools** — Relevant MCP tool references.

Provide equivalent English and Japanese content.

Use natural language appropriate for each language.

Do not merely translate the same English prompt word-for-word when a more natural Japanese prompt communicates the same intent.

### 7.2 Scenario A — Inspect an Already-Open Capture

File:

`examples/active-capture.md`

Goal:

Demonstrate that the coding agent can inspect a capture opened directly through RenderDoc or a game engine.

Example prompt:

> Inspect the capture currently open in RenderDoc. Tell me which graphics API it uses, what frame is captured, and which event is selected.

Explain:

- GUI session discovery.
- Capture identification.
- Event selection.
- Basic capture metadata.

This should be the simplest scenario.

### 7.3 Scenario B — An Object Is Not Visible

File:

`examples/missing-object.md`

Problem:

An object expected to appear in the frame is missing.

Example prompt:

> This object is not appearing in the frame. Inspect the selected draw call and check its vertex input, shaders, rasterizer state, depth state, and render targets. Identify suspicious settings.

Investigation topics:

- Draw call parameters.
- Vertex/index buffer bindings.
- Input layout.
- Vertex shader inputs.
- Rasterizer culling.
- Depth testing.
- Render target configuration.

Important:

Do not claim the absence of an object can always be diagnosed from one draw call.

Separate confirmed findings from possible causes.

If geometry inspection is not yet implemented, document the relevant limitation.

### 7.4 Scenario C — Incorrect Texture or Material

File:

`examples/shader-resources.md`

Problem:

A material displays an incorrect texture or unexpected values.

Example prompt:

> Inspect the pixel shader used by the selected draw call. List its texture and sampler bindings, identify the actual bound resources, and check the relevant material constants.

Investigation topics:

- Shader reflection.
- Declared resource bindings.
- Actual pipeline bindings.
- Texture metadata.
- Constant buffer values.
- Missing or incorrect resources.

Use the Phase 9 and Phase 10 functionality.

### 7.5 Scenario D — Black or Incorrect Render Target

File:

`examples/render-target.md`

Problem:

A render target appears black or contains unexpected colors.

Example prompt:

> Inspect the render target bound to the selected draw call. Show its contents, check the format and dimensions, and inspect representative pixel values.

Investigation topics:

- Render target bindings.
- Texture format.
- Image visualization.
- Pixel values.
- Component interpretation.
- Min/max statistics when supported.

Explain that a black displayed image does not necessarily mean all underlying pixel values are zero.

Discuss floating-point display ranges where relevant.

### 7.6 Scenario E — Depth Testing Problems

File:

`examples/depth-debugging.md`

Problem:

An object disappears or is incorrectly occluded.

Example prompt:

> Inspect the depth state of the selected draw call and the associated depth texture. Check the depth comparison function, depth writes, and relevant depth pixel values.

Investigation topics:

- Depth test enablement.
- Depth write state.
- Depth comparison function.
- Depth attachment.
- Depth texture format.
- Available depth values.

Do not claim that Pixel History is available unless that feature has actually been implemented.

Explain that determining the exact cause of a failed fragment may require advanced debugging features.

### 7.7 Scenario F — Compute Shader Output Is Incorrect

File:

`examples/compute-dispatch.md`

Problem:

A compute shader writes unexpected results.

Example prompt:

> Inspect the selected compute dispatch. Check its dispatch dimensions, shader resource bindings, constant buffers, and output storage buffers. Examine the first few elements of the output.

Investigation topics:

- Dispatch group counts.
- Compute shader identity.
- Shader reflection.
- Storage/UAV bindings.
- Constant buffer values.
- Bounded buffer inspection.
- Structured buffer interpretation.

Explain the difference between dispatch dimensions and actual logical workload size.

Do not imply that the tool can step through individual shader invocations unless that capability exists.

---

## 8. Agent Prompt Examples

Provide useful copyable prompts in both languages.

Organize them by debugging goal rather than by implementation details.

### 8.1 General Inspection

English:

> Inspect the currently selected draw call in RenderDoc and summarize the important pipeline state.

Japanese:

> RenderDocで現在選択しているDrawCallを調査し、重要なPipeline Stateをまとめてください。

### 8.2 Resource Binding

English:

> Check which textures and buffers are bound to the selected pixel shader and identify any missing bindings.

Japanese:

> 現在選択しているPixel ShaderにBindされているTextureとBufferを確認し、未設定のBindingがないか調べてください。

### 8.3 Constant Buffer

English:

> Inspect the constant buffers used by the selected draw call and show the relevant transformation and material parameters.

Japanese:

> 現在選択しているDrawCallで使用されているConstant Bufferを調査し、変換行列とMaterial Parameterの値を確認してください。

### 8.4 Render Target

English:

> Show the current render target and inspect the pixel values around the suspicious area.

Japanese:

> 現在のRender Targetを表示し、問題がある領域のPixel値を調べてください。

### 8.5 Compute Dispatch

English:

> Inspect the selected compute dispatch and examine the output buffer values.

Japanese:

> 現在選択しているCompute Dispatchを調査し、出力Bufferの値を確認してください。

Only include prompts that correspond to implemented functionality.

### 8.6 Prompt Design Principles

Prompts should:

- Describe the observed problem.
- Use the currently selected RenderDoc context.
- Encourage evidence-based inspection.
- Avoid assuming the cause.
- Avoid requesting unsupported operations.

Encourage agents to distinguish observations from hypotheses.

---

## 9. MCP Tool Reference

Create an accurate tool reference in both languages.

Document all publicly exposed MCP tools.

Do not rely on old phase design documents for tool signatures.

Inspect the actual registered tool definitions.

### 9.1 Tool Documentation

For each tool, include:

- Tool name.
- Description.
- Parameters.
- Required parameters.
- Optional parameters.
- Default behavior.
- Response structure.
- Common errors.
- Size or pagination limits.
- Whether it changes GUI state.

### 9.2 Organize by Capability

Suggested categories:

- Session and Capture.
- Events and Draw Calls.
- Pipeline State.
- Resources and Buffers.
- Shaders and Reflection.
- Textures and Pixels.
- Other implemented capabilities.

### 9.3 Avoid Redundant Documentation

Where practical, generate portions of the reference from tool definitions or schemas.

However, do not introduce a complex documentation-generation framework for a small project.

### 9.4 Tool Examples

Provide short realistic examples demonstrating:

- Default current-session resolution.
- Explicit session selection.
- Explicit event selection.
- Resource ID usage.
- Bounded buffer reads.
- Texture and pixel requests.

Clearly distinguish example parameter values from actual runtime identifiers.

---

## 10. Troubleshooting Guide

Create practical troubleshooting documentation in both languages.

Prioritize issues likely to occur during initial installation.

### 10.1 Installation Problems

Cover:

- RenderDoc not found.
- Unsupported or incompatible RenderDoc installation.
- MCP executable not found.
- Python environment issues, if relevant.
- Incorrect environment configuration.
- Extension installation failure.

### 10.2 Connection Problems

Cover:

- MCP server starts but no RenderDoc session is discovered.
- RenderDoc extension is not loaded.
- Shared IPC Service is unavailable.
- Multiple MCP clients conflict.
- Connection is lost after RenderDoc restarts.

### 10.3 Capture Problems

Cover:

- RenderDoc is connected but no capture is loaded.
- Capture is loaded but the agent reports no capture.
- Multiple RenderDoc sessions are found.
- Capture changes invalidate resource IDs.
- Selected event is unavailable.

### 10.4 Inspection Problems

Cover:

- Unsupported graphics API.
- Replay controller unavailable.
- Resource ID not found.
- Shader reflection unavailable.
- Buffer read exceeds limits.
- Texture image is unavailable.
- Pixel values differ from displayed colors.

### 10.5 Diagnostic Information

Explain:

- Where logs are written.
- How logging verbosity is configured.
- Which diagnostic information should be included in bug reports.
- How to distinguish MCP, IPC, extension, and replay errors.

Use verified configuration settings.

Do not document imaginary diagnostic flags.

### 10.6 Security and Privacy

Warn users to review logs and captures before sharing them publicly.

Capture files and debug logs may contain:

- Application paths.
- Resource names.
- Shader information.
- Proprietary application data.
- Potentially sensitive rendered content.

Avoid encouraging users to upload proprietary capture files without authorization.

---

## 11. Architecture Documentation

Create a concise technical architecture document.

This is primarily for contributors and advanced users.

Explain:

- MCP server responsibilities.
- Shared IPC Service responsibilities.
- RenderDoc extension responsibilities.
- GUI session discovery.
- Active capture state synchronization.
- Replay-controller interaction.
- Request routing.
- Multiple-agent concurrency.
- Resource and event identity.
- Error handling.
- Lifecycle management.

### 11.1 Architecture Diagram

Provide a simple diagram.

Mermaid is acceptable if it renders correctly on GitHub.

Avoid introducing unnecessary diagram-generation dependencies.

### 11.2 State and Ownership

Explain which component owns:

- GUI session state.
- Capture state.
- Replay operations.
- IPC communication.
- MCP request handling.

Clarify that AI agents do not own the loaded RenderDoc capture.

### 11.3 Threading

Document relevant GUI and replay-thread restrictions.

Do not expose internal implementation details that are unnecessary for contributors.

### 11.4 Extension Architecture

Explain how the RenderDoc extension is installed, loaded, and connected.

Use actual implementation details.

---

## 12. Release Packaging Validation

Inspect the release and installation mechanisms.

Verify:

- Package metadata.
- Version information.
- Executable entry points.
- Included extension files.
- Included configuration templates.
- Dependency declarations.
- Release artifacts.
- Installation instructions.

### 12.1 Clean Installation

Validate the installation procedure against produced distribution artifacts.

Do not rely exclusively on a developer's editable installation.

### 12.2 RenderDoc Detection

Verify whether the installer can detect RenderDoc.

If automatic detection is supported, test:

- Standard installation path.
- Custom installation path.
- Missing RenderDoc installation.

Ensure failure messages provide actionable guidance.

### 12.3 Default Configuration

Verify that default configuration files are generated or installed correctly.

Do not overwrite existing user configuration silently.

### 12.4 Release Artifacts

Verify that a release package contains everything required for the documented installation.

Do not assume files present in the development repository are automatically included in the distributed package.

### 12.5 Platform Support

Document only tested platform combinations as fully supported.

Distinguish:

- Officially tested.
- Expected to work but unverified.
- Experimental.
- Unsupported.

Windows may be the primary validation target, but do not introduce an unnecessary Windows-only restriction.

---

## 13. CI and Release Readiness

Review existing GitHub Actions workflows.

Do not replace working CI infrastructure unnecessarily.

### 13.1 Required Checks

Where practical, ensure CI validates:

- Unit tests.
- Python packaging.
- Import and startup sanity checks.
- Static analysis or linting already used by the project.
- Documentation link integrity.
- Release artifact construction.

### 13.2 Documentation Validation

Add lightweight checks for:

- Broken relative links.
- Missing corresponding Japanese or English pages.
- Invalid Markdown links.
- Missing referenced documentation files.

Prefer simple scripts or existing tools.

Avoid introducing a heavy documentation site framework solely for these checks.

### 13.3 Version Consistency

Ensure version references are consistent across:

- Package metadata.
- Release workflows.
- Documentation.
- Release notes.
- Generated artifacts.

Do not invent a release version.

Use the existing versioning scheme.

### 13.4 Release Notes

Prepare release notes based on actual implemented functionality.

Include:

- Highlights.
- Installation information.
- Supported environments.
- Known limitations.
- Breaking changes, if any.
- Relevant migration instructions.

Do not claim that a public release has been published unless it has actually occurred.

---

## 14. OSS Project Readiness

Inspect the repository for essential open-source project information.

### 14.1 License

Verify that a license file exists.

Do not choose or change the license without explicit project authorization.

Ensure README and package metadata reference the actual license.

### 14.2 Contribution Guidelines

If appropriate, provide:

- `CONTRIBUTING.md`
- Development environment setup.
- Test instructions.
- Pull request guidelines.

Avoid introducing unnecessary contribution bureaucracy.

### 14.3 Issue Templates

Consider lightweight issue templates for:

- Bug reports.
- Feature requests.

A bug report should ask for:

- Operating system.
- RenderDoc version.
- RenderEyeMCP version.
- Coding agent.
- Graphics API.
- Relevant logs.
- Reproduction steps.

### 14.4 Security

Provide a simple security reporting policy if appropriate.

Document any restrictions on exposing local IPC services beyond trusted environments.

Do not claim the system is secure for internet exposure without a security review.

### 14.5 Dependencies and Licensing

Review third-party dependencies and bundled files.

Check that release packaging respects their redistribution requirements.

Do not bundle RenderDoc binaries or third-party assets without verifying redistribution permissions.

---

## 15. Documentation Quality Requirements

Documentation must be practical and concise.

### 15.1 Write for New Users

Assume readers understand software development but may not know:

- MCP server architecture.
- Python packaging.
- RenderDoc extension APIs.
- Shared IPC internals.

Explain necessary concepts without overwhelming the user.

### 15.2 Prefer Task-Oriented Documentation

Use headings such as:

- Install RenderEyeMCP.
- Connect Claude Code.
- Connect Codex.
- Inspect an Open Capture.
- Diagnose a Missing Object.
- Inspect a Constant Buffer.

Avoid organizing all user documentation around internal implementation classes.

### 15.3 Copyable Commands

Commands and configuration examples must be:

- Correct.
- Copyable.
- Platform-appropriate.
- Validated where possible.

Do not use development-only paths in general installation instructions.

### 15.4 Avoid Unsupported Claims

Do not advertise:

- Unsupported coding agents.
- Unsupported graphics APIs.
- Unimplemented tools.
- Unverified installation platforms.
- Automatic bug diagnosis.
- Full shader debugging.
- GPU profiling capabilities that are not implemented.

### 15.5 Japanese Technical Terminology

Use natural Japanese while preserving familiar graphics programming terminology.

It is acceptable to retain technical words such as:

- DrawCall.
- Pipeline State.
- Render Target.
- Shader Reflection.
- Constant Buffer.
- Resource Binding.
- Replay.
- Capture.
- MCP Tool.

Do not translate programming identifiers or configuration names.

---

## 16. Documentation Validation

Validation is a core requirement of Phase 12.

### 16.1 Link Validation

Verify:

- README links.
- Cross-language navigation.
- Internal documentation links.
- Example links.
- Referenced images and diagrams.

### 16.2 Command Validation

Execute installation and configuration commands where practical.

Document which commands were actually tested.

### 16.3 Tool Validation

Compare tool documentation against the actual MCP tool registrations.

Verify:

- Tool names.
- Parameter names.
- Required fields.
- Defaults.
- Supported options.

### 16.4 Scenario Validation

Execute representative scenarios against a real RenderDoc capture where possible.

At minimum, validate:

1. Active capture discovery.
2. Selected event inspection.
3. Shader/resource inspection.
4. Render-target or pixel inspection, if implemented.

Record failures or unavailable capabilities.

### 16.5 Translation Consistency

Check that every English page has a corresponding Japanese page.

Verify that essential details match:

- Installation commands.
- Tool identifiers.
- Supported platforms.
- Warnings.
- Limitations.
- Troubleshooting procedures.

Do not require literal sentence-level correspondence.

### 16.6 Fresh Installation Validation

Where an isolated Windows test environment is available:

1. Install RenderDoc.
2. Install RenderEyeMCP using a release artifact.
3. Configure a coding agent.
4. Open RenderDoc.
5. Load a capture.
6. Execute the quickstart prompts.

Record the exact environment and result.

If a clean environment is unavailable, report that the test could not be performed.

---

## 17. Scope Restrictions

Do not implement unrelated features.

Specifically, avoid:

- New geometry inspection functionality.
- Pixel History.
- Shader stepping/debugging.
- GPU profiling.
- New capture analysis engines.
- Large IPC architecture changes.
- Major MCP tool API redesign.
- New GUI frameworks.
- New documentation hosting platforms unless necessary.
- Broad dependency upgrades unrelated to release readiness.

Small bug fixes necessary for installation, packaging, documentation accuracy, or release stability are allowed.

Keep changes focused and reviewable.

---

## 18. Implementation Priorities

Implement in this order.

### Priority 1 — Repository Audit

- Verify actual features.
- Verify installation mechanisms.
- Verify supported coding agents.
- Verify release artifacts.
- Identify documentation gaps.

### Priority 2 — README and Quickstart

- English README.
- Japanese README.
- English Quickstart.
- Japanese Quickstart.

### Priority 3 — Installation and Configuration

- Windows installation.
- Supported platform installation.
- Claude Code configuration.
- Codex configuration.
- Environment settings.
- Installation verification.

### Priority 4 — Practical Debugging Examples

- Active capture.
- Missing object.
- Shader resources.
- Render target.
- Depth debugging.
- Compute dispatch.

### Priority 5 — Technical Documentation

- MCP tool reference.
- Architecture.
- Troubleshooting.
- Contribution information.

### Priority 6 — Release Validation

- Packaging verification.
- CI checks.
- Link validation.
- Clean installation.
- Release checklist.
- Release notes.

Do not prioritize visual polish over technical correctness.

---

## 19. Deliverables

Provide the following.

### A. Bilingual Documentation

- English README.
- Japanese README.
- English installation and configuration guides.
- Japanese installation and configuration guides.
- English and Japanese quickstarts.
- English and Japanese tool references.
- English and Japanese troubleshooting guides.
- English and Japanese architecture documents.

### B. Debugging Scenarios

Provide at least six bilingual scenario guides covering:

1. Active capture inspection.
2. Missing objects.
3. Shader and resource bindings.
4. Render target inspection.
5. Depth-related problems.
6. Compute shader output inspection.

If an example depends on an unimplemented feature, revise it to use supported functionality or explicitly mark the missing capability.

Do not present a hypothetical example as a verified working workflow.

### C. Release Readiness

- Verified package structure.
- Verified executable entry points.
- Validated installation instructions.
- Reviewed CI/release workflows.
- Release checklist.
- Draft release notes.
- Known limitations.

### D. Validation Report

Provide:

- Documentation created or modified.
- Feature inventory.
- Platforms tested.
- Coding agents tested.
- Installation methods tested.
- Debugging scenarios validated.
- Packaging results.
- CI results.
- Known blockers.

---

## 20. Acceptance Criteria

Phase 12 is complete when:

- [ ] The main README clearly explains RenderEyeMCP's purpose.
- [ ] English and Japanese READMEs are available.
- [ ] Both READMEs link to each other.
- [ ] English and Japanese installation guides are available.
- [ ] Installation commands match the actual implementation.
- [ ] Windows installation is documented and validated where possible.
- [ ] Supported coding-agent configuration is documented.
- [ ] Claude Code and Codex instructions are verified where available.
- [ ] A new user can follow the quickstart without reading internal architecture documentation.
- [ ] An already-open RenderDoc capture is the primary quickstart workflow.
- [ ] English and Japanese MCP tool references reflect actual tool registrations.
- [ ] At least six practical debugging scenarios are documented in both languages.
- [ ] Example prompts are realistic and aligned with implemented tools.
- [ ] No documentation falsely advertises planned functionality as implemented.
- [ ] Troubleshooting covers common installation and connection failures.
- [ ] Architecture documentation explains the Shared IPC Service and RenderDoc extension.
- [ ] Release artifacts contain the required runtime components.
- [ ] Existing user configuration is not silently overwritten during installation.
- [ ] Relevant CI and packaging checks pass, or failures are documented.
- [ ] Documentation links are validated.
- [ ] English and Japanese documentation are technically consistent.
- [ ] The project license is correctly represented.
- [ ] Known limitations are documented.
- [ ] A release checklist is prepared.
- [ ] Draft release notes are prepared from verified features.
- [ ] No unrelated rendering inspection features are introduced.

If a required validation cannot be performed, clearly report the reason.

Do not declare the project release-ready while known release-blocking issues remain unresolved.

---

## 21. Final Implementation Report

At completion, provide a structured report with the following sections.

### 21.1 Documentation Changes

List all created and modified documentation files.

### 21.2 Feature Verification

Summarize which documented capabilities were confirmed.

### 21.3 Installation Verification

Report tested installation paths and results.

### 21.4 Agent Configuration Verification

Report tested coding agents and MCP integration results.

### 21.5 Scenario Verification

Identify which debugging examples were executed successfully.

### 21.6 Release Readiness

Classify the release state as:

- Ready for release.
- Ready with documented non-blocking limitations.
- Not ready — blocking issues remain.

Provide concrete evidence for the classification.

### 21.7 Remaining Work

List unresolved release blockers separately from optional future improvements.

Do not mark untested functionality as verified.

---

## Final Goal

After Phase 12, a developer who has never used RenderEyeMCP should be able to discover the project on GitHub and understand its value immediately.

They should be able to:

1. Read the documentation in English or Japanese.
2. Install RenderEyeMCP.
3. Connect their preferred supported coding agent.
4. Open a capture in RenderDoc through their normal development workflow.
5. Ask the agent to inspect the active capture.
6. Follow practical examples to investigate rendering problems.

The documentation should demonstrate that RenderEyeMCP does not replace RenderDoc or require a separate capture-management workflow.

**RenderEyeMCP connects the developer's existing RenderDoc debugging environment to AI coding agents.**

Phase 12 should make that capability discoverable, understandable, reliable, and ready for public release.

Do not automatically publish a GitHub release, push release tags, or upload distribution artifacts.

Prepare and validate the release, then report the final readiness status for review.
