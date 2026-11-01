# Phase 22.1 — Rebuild GitHub Actions Release Workflow from Scratch

## Objective

Completely replace `.github/workflows/release.yml` with a clean, reliable GitHub Actions release workflow designed specifically for the Go implementation of RenderEyeMCP.

The existing release workflow is failing and may contain unnecessary complexity or assumptions inherited from the previous Python implementation.

Do not attempt to preserve the existing workflow structure merely for compatibility.

**Rewrite the release workflow from scratch using a minimal, conventional Go build-and-release pipeline.**

The final workflow must build native Go binaries, package the necessary distribution files, and publish them through GitHub Releases.

## 1. Inspect the Repository

Before implementing the workflow, inspect:

- Current `.github/workflows/release.yml`.
- `go.mod` and `go.sum`.
- The actual Go executable entry point.
- Existing Makefile or Go build scripts, if any.
- Executable version handling.
- `scripts/` directory.
- `extension/` or `extensions/` directory.
- Existing installation scripts.
- Current release archive structure.
- Existing workflow failures, if logs are available.

Identify the correct Go build command and required distribution files.

Do not assume the Go entry point is located at the repository root.

Use the repository's actual implementation as the source of truth.

## 2. Replace release.yml Completely

Delete the existing workflow implementation and create a new one.

Do not retain:

- Python packaging steps.
- Python MCP server dependencies.
- uv or pip installation steps.
- PyPI or TestPyPI integration.
- Legacy Python executable packaging.
- Obsolete artifact handling.
- Unnecessary compatibility logic.

Keep the YAML simple and understandable.

Prefer standard GitHub Actions features over custom workflow frameworks.

## 3. Workflow Triggers

The workflow should support:

### Tagged Releases

Automatically build and publish when a release tag is pushed.

Use the existing version tag convention, such as:

```text
v1.0.0
v1.0.1
v1.1.0
```

Ensure that release builds use the tagged commit.

### Manual Validation

Provide `workflow_dispatch` support for manually validating the release pipeline.

Manual validation must not accidentally publish a production release.

Prefer a clearly separated validation mode that builds, packages, and uploads workflow artifacts without creating a GitHub Release.

Do not introduce automatic production publishing from ordinary branch pushes.

## 4. Go Build

Use a supported stable Go toolchain.

Prefer `actions/setup-go` with the Go version obtained from `go.mod`, where practical.

Run:

```bash
go test ./...
```

Use the correct module working directory if `go.mod` is not in the repository root.

Build native executables for the currently supported platforms.

Initial targets:

| Platform | GOOS | GOARCH | Output |
|---|---|---|---|
| Windows x64 | windows | amd64 | rendereye-mcp.exe |
| Linux x64 | linux | amd64 | rendereye-mcp |

Additional architectures may be included if they are already supported and validated.

Use `CGO_ENABLED=0` only if the project builds and runs correctly without CGO.

Do not require Python, uv, or pip to build the Go executable.

### Version Information

Preserve the application's existing version information mechanism.

If the application supports Go linker version injection, use the existing linker variables.

Do not invent package paths or linker symbols.

Validate that the compiled executable reports the expected version using its actual supported CLI command.

## 5. Package Release Files

Each distribution archive must include:

- Compiled platform-specific Go executable.
- Required installation scripts.
- RenderDoc Python Extension.
- README.md.
- LICENSE, if present.

The expected layout should be compatible with the portable installation design.

For example:

```text
RenderEyeMCP/
├── rendereye-mcp.exe
├── install.ps1
├── scripts/
├── extension/
├── README.md
└── LICENSE
```

The actual archive structure must be derived from the repository.

### Important

The current Windows installer expects the Go executable to be located relative to `install.ps1`.

Ensure the packaged directory layout satisfies that expectation.

If `install.ps1` is located under `scripts/` in the repository, either arrange the archive appropriately or make a minimal, justified installer path adjustment.

Do not create an archive that builds successfully but cannot be installed.

Preserve all files required by the RenderDoc Extension.

Do not include obsolete Python MCP or IPC server code.

## 6. Archive Formats

Use:

- `.zip` for Windows.
- `.tar.gz` for Linux.

Use consistent artifact names:

```text
RenderEyeMCP-vX.Y.Z-windows-amd64.zip
RenderEyeMCP-vX.Y.Z-linux-amd64.tar.gz
```

Create SHA-256 checksums:

```text
checksums.txt
```

Ensure checksums refer to the final archives rather than intermediate files.

## 7. GitHub Releases Publishing

Publish release assets to the GitHub Release corresponding to the pushed tag.

Use maintained GitHub Actions with appropriate permissions.

Requirements:

- Use `contents: write` only for the publishing job.
- Ensure all build and packaging steps succeed before publishing.
- Fail on missing required artifacts.
- Preserve exact release version identifiers.
- Prevent simultaneous jobs from corrupting the same release.
- Avoid partially successful releases being reported as successful.
- Do not silently overwrite release assets from unrelated commits.

Use the official GitHub release API or a maintained release action.

Do not introduce external release-management services.

### Failure Handling

A failed Go build, test, or packaging operation must stop the workflow.

Do not use `continue-on-error` to hide required failures.

Do not ignore missing extension or installer files.

Make failed steps easy to identify in the GitHub Actions logs.

## 8. Keep the Workflow Simple

Avoid unnecessary complexity.

Do not introduce:

- Docker-based release builds.
- A new package manager.
- Python-based packaging scripts.
- Custom CI frameworks.
- Unnecessary third-party actions.
- Multiple independent release publishers.
- Complicated cross-workflow dependencies.

A single workflow containing clearly separated build, package, and publish stages is sufficient.

A matrix build is appropriate if it reduces duplication without complicating artifact collection.

If matrix jobs are used, ensure each produces uniquely named artifacts and that the publishing job collects exactly the expected outputs.

## 9. Validation Before Publishing

Add validation steps that verify:

1. Go tests pass.
2. All expected native binaries exist.
3. Required scripts are packaged.
4. The RenderDoc Extension is packaged.
5. Archive directory structure is correct.
6. Windows installer path assumptions are satisfied.
7. Linux executable permissions are preserved.
8. Archive files are readable and not empty.
9. SHA-256 checksums match the generated archives.
10. No legacy Python MCP server is included.

Where supported, execute a basic binary smoke test on the corresponding runner.

Do not claim that a successful cross-compilation proves RenderDoc integration works.

### Dry-Run Requirement

The manually dispatched validation workflow must exercise the same build and packaging logic used by tagged releases.

It must upload the generated archives as GitHub Actions artifacts for inspection.

It must not create or modify a public GitHub Release.

## 10. Documentation

Update the release-related documentation as necessary.

Document:

- Supported release platforms.
- Archive naming conventions.
- Portable installation.
- Required extension setup.
- Version tag behavior.
- How maintainers can run the release workflow in validation mode.

Do not reintroduce the old Python installation model.

Do not create Python-to-Go migration instructions.

## 11. Acceptance Criteria

This phase is complete when:

1. The existing `release.yml` has been fully replaced.
2. The new workflow builds the actual Go application.
3. Go tests run successfully.
4. Windows and Linux release binaries are generated.
5. Archives include the required scripts and RenderDoc Extension.
6. Portable installation layout is correct.
7. SHA-256 checksums are generated and verified.
8. Manual validation builds release artifacts without publishing.
9. Tag-triggered execution publishes the corresponding GitHub Release.
10. No Python MCP server packaging remains.
11. The workflow is understandable without knowledge of the old Python implementation.

## Deliverables

- Completely rewritten `.github/workflows/release.yml`.
- Any minimal packaging adjustments required by the actual repository.
- Updated release documentation, where necessary.
- Validation results.
- A concise explanation of the new workflow.

## Execution Instructions

Inspect the repository and any available failure logs first.

Replace the workflow rather than incrementally patching its legacy structure.

Implement the complete Go release pipeline.

Validate the YAML, build commands, archive contents, and dry-run behavior as far as the available environment permits.

If GitHub-hosted execution cannot be performed, report that limitation rather than claiming the workflow has passed.

Do not push tags or publish an actual release.

**Prioritize a small, reliable, Go-native release workflow over preserving historical CI complexity.**
