# Phase 22 — Migrate GitHub Actions Release Workflow to Go

## Objective

Update `.github/workflows/release.yml` to build and publish the Go-based RenderEyeMCP distribution.

RenderEyeMCP has completed its migration from the legacy Python MCP server and Shared IPC Service to Go.

The release workflow must now produce self-contained native distributions containing:

- The compiled Go executable.
- Installation and setup scripts.
- The RenderDoc Python Extension.
- Essential project documentation and license files.

Remove all legacy Python MCP server packaging and publishing logic.

Keep the release process simple, reproducible, and maintainable.

## 1. Review the Existing Repository

Before modifying the workflow, inspect:

- `.github/workflows/release.yml`
- `go.mod`
- Go executable entry points
- Existing Go build scripts
- `scripts/` or equivalent installer directories
- `extension/` or `extensions/`
- Existing release archive conventions
- Other GitHub Actions workflows

Determine the actual project structure.

Do not assume that the directory names, executable entry points, or build commands match the examples in this instruction.

Reuse existing working Go build commands where appropriate.

## 2. Native Go Builds

Build the RenderEyeMCP executable for the supported platforms.

At minimum, consider:

| GOOS | GOARCH | Executable |
|---|---|---|
| windows | amd64 | rendereye-mcp.exe |
| linux | amd64 | rendereye-mcp |
| linux | arm64 | rendereye-mcp |

Preserve any other platforms already supported and validated by the project.

Do not advertise a platform as fully supported merely because Go cross-compilation succeeds.

For macOS, distinguish between successfully compiling the Go executable and actual RenderDoc availability and integration support.

Use the appropriate Go build configuration for the project.

Prefer reproducible builds with release version information embedded when the existing executable supports it.

Use `CGO_ENABLED=0` only if the implementation and all dependencies support building without CGO.

Do not introduce unnecessary platform-specific build machinery.

## 3. Release Package Layout

Each release archive must contain the executable and all required installation resources.

For example:

```text
RenderEyeMCP/
├── rendereye-mcp.exe
├── scripts/
│   └── install.ps1
├── extension/
│   └── ...
├── README.md
└── LICENSE
```

Use the actual repository structure.

If the existing portable installer expects `install.ps1` and the executable to be in the same directory, preserve that relationship in the packaged archive.

Do not move files into a different archive layout without updating and validating the installer.

The release package must work when extracted into an arbitrary permanent directory.

Do not require a separate executable installation step.

## 4. Include Scripts and RenderDoc Extension

Package the required installation scripts and RenderDoc Extension files with every relevant platform distribution.

Requirements:

- Preserve directory structure.
- Preserve all runtime files required by the Extension.
- Preserve shell-script executable permissions where applicable.
- Exclude caches, temporary files, generated test output, and unnecessary development files.
- Do not package legacy Python MCP or Shared IPC implementations.
- Do not package Python virtual environments.
- Do not package Go source code unless explicitly required for distribution.

The RenderDoc Extension is intentionally written in Python and must remain included.

Its presence does not imply that end users need to install a separate Python environment.

## 5. Archive Naming

Use consistent, versioned release artifact names.

For example:

```text
RenderEyeMCP-v1.0.0-windows-amd64.zip
RenderEyeMCP-v1.0.0-linux-amd64.tar.gz
RenderEyeMCP-v1.0.0-linux-arm64.tar.gz
checksums.txt
```

Keep naming consistent with the existing release conventions unless there is a clear reason to change them.

Avoid introducing multiple aliases for the same artifact.

Generate SHA-256 checksums for all release archives.

## 6. GitHub Actions Workflow

Update `.github/workflows/release.yml` to perform the following operations:

1. Trigger on the project's existing release-tag convention.
2. Check out the repository.
3. Set up the required Go toolchain.
4. Run Go tests.
5. Build the supported native binaries.
6. Assemble platform-specific distribution directories.
7. Package the release archives.
8. Generate SHA-256 checksums.
9. Upload the archives and checksums to the corresponding GitHub Release.

Prefer official or widely maintained GitHub Actions.

Pin actions to appropriate stable versions or immutable commits according to the repository's existing security policy.

Use minimal GitHub token permissions.

For release publishing, grant `contents: write` only where required.

Do not introduce Python setup, pip, uv, or PyPI publishing steps.

## 7. Tag and Release Behavior

Preserve the project's existing version-tag conventions where possible.

For example:

```text
v1.0.0
v1.1.0
v1.1.1
```

Ensure that a release artifact is built from the corresponding tagged commit.

Avoid silently building from the latest default branch when processing a tag.

If prerelease tags are supported, ensure they are correctly marked as prereleases.

Prevent duplicate artifact publication or conflicting concurrent release jobs.

Do not automatically publish a production release from ordinary branch pushes.

## 8. Validation

Add appropriate checks to verify the generated distributions.

At minimum:

- Go tests pass.
- All required binaries are produced.
- The required installer scripts exist.
- The RenderDoc Extension is included.
- The release archives have the expected layout.
- No legacy Python MCP server files are packaged.
- Archive checksums are valid.
- Version metadata matches the release tag.

For Windows distributions, verify that the packaged `install.ps1` can locate the executable and Extension in their actual packaged locations.

For Linux distributions, verify executable permissions and the documented installation layout.

Where runners permit, execute a basic executable smoke test, such as the existing version command.

Do not claim successful RenderDoc integration testing based solely on cross-compilation or executable startup.

## 9. Remove Legacy Release Logic

Remove obsolete workflow steps related to:

- Python MCP package builds.
- Python wheels and source distributions.
- pip and uv dependency installation for the legacy server.
- Python Shared IPC Service packaging.
- PyPI and TestPyPI publishing.
- Legacy Python executable generation.
- Unnecessary Python runtime bundling.

Remove obsolete release-specific configuration files if they are no longer used elsewhere.

Do not delete files required by the RenderDoc Python Extension.

## 10. Documentation

Update relevant release documentation to describe the new native distribution.

Explain that users should:

1. Download the appropriate GitHub Release archive.
2. Extract it to a permanent directory.
3. Run the relevant setup script.
4. Enable the RenderDoc Extension if required.
5. Configure their coding agent to execute the binary from the extracted directory.

Do not reintroduce the old `%LOCALAPPDATA%\RenderEyeMCP` executable-copy installation model.

Keep English and Japanese instructions consistent.

## 11. Acceptance Criteria

Phase 22 is complete when:

1. `release.yml` builds RenderEyeMCP using Go.
2. Supported native binaries are produced successfully.
3. Every release archive contains the required executable, scripts, and RenderDoc Extension.
4. The archive layout is compatible with the portable installer.
5. Release artifacts have consistent versioned filenames.
6. SHA-256 checksums are generated.
7. No legacy Python MCP or Shared IPC distribution is produced.
8. No Python development environment is required by end users.
9. The workflow can publish artifacts to GitHub Releases using the existing release-tag policy.
10. README and installation documentation match the new distribution layout.

## Deliverables

- Updated `.github/workflows/release.yml`.
- Updated release packaging steps or scripts.
- Updated documentation where necessary.
- Removal of obsolete release-related configuration.
- A concise summary of the generated artifacts and validation results.

## Constraints

- Do not modify MCP Tool contracts.
- Do not modify the IPC protocol.
- Do not change Go runtime behavior.
- Do not rewrite the RenderDoc Python Extension.
- Do not add a new package manager.
- Do not create Python-to-Go migration documentation.
- Do not create or push release tags.
- Do not publish an actual GitHub Release during implementation unless explicitly requested.

## Execution Policy

Inspect the existing workflow and repository structure first.

Implement the workflow changes directly.

Validate the build and archive generation locally or through available non-publishing CI checks where practical.

Report any platform builds or integration checks that could not be verified.

**The final release workflow should be a straightforward Go build-and-package pipeline, not a legacy Python packaging workflow with Go binaries added to it.**
