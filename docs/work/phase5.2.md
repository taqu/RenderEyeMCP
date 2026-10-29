# RenderEyeMCP — Phase 5.2 Implementation Instructions

## Objective

Implement **Phase 5.2: GitHub Actions CI/CD & Automated GitHub Releases** for RenderEyeMCP.

Previous phases established:

- **Phase 0–4:** MCP server, Capture Registry, Session Manager, RenderDoc Extension, IPC integration, and coding agent workflows.
- **Phase 5:** Reliability improvements, testing, packaging, and release readiness.
- **Phase 5.1:** Clean installation without `uv`, manual installation, automatic installation, and integration with major coding agents.

Phase 5.2 must establish a reliable GitHub Actions pipeline that automatically tests, builds, validates, packages, and releases RenderEyeMCP.

The resulting GitHub Releases must provide downloadable distributions suitable for users who do not have `uv` or a development environment.

**Implement working GitHub Actions workflows, release packaging scripts, automated verification, and release documentation. Do not stop at writing workflow proposals.**

Do not publish an actual release or create a version tag unless explicitly authorized.

---

## 1. Requirements and Constraints

### Supported Platforms

- Windows: Primary release target.
- Linux: Supported release target where functionality has been verified.
- macOS: No official RenderDoc GUI integration target.

### Python Environment

- The development environment may use `uv`.
- GitHub Actions may use `uv` internally when appropriate.
- End-user installations must not require `uv`.
- Python wheel and source distributions must support standard Python packaging tools.
- CI must verify installation through `pip`.

### RenderDoc

The preferred Windows executable location is:

`C:\Program Files\RenderDoc\qrenderdoc.exe`

Do not hardcode this path into release workflows.

RenderDoc executable discovery must remain configurable and platform-independent.

### Existing Components

Preserve:

- MCP server and public tools
- Capture Registry
- Session Manager
- RenderDoc Python Extension
- IPC communication
- Manual installation
- Automatic installation
- Agent configuration generator
- Diagnostics and uninstall functionality

Do not introduce GPU frame analysis or unrelated features.

### Release Principles

1. CI failures must prevent release publication.
2. Release artifacts must be built from the intended Git revision.
3. Release versions must be consistent.
4. Published artifacts must be verified before publication.
5. No privileged release operations should run on untrusted pull-request code.
6. Avoid unnecessary GitHub secrets.
7. End users must not need `uv` or Git.
8. Preserve Windows and Linux portability.
9. Do not label unverified platform integrations as officially supported.
10. Do not overwrite existing release assets silently.

---

## 2. Task A — Repository and Release Audit

Before implementation:

1. Inspect the repository structure.
2. Review `pyproject.toml`.
3. Inspect current package build configuration.
4. Review RenderDoc extension packaging.
5. Review Phase 5.1 installation scripts.
6. Inspect existing GitHub Actions workflows.
7. Review current version management.
8. Review release documentation.
9. Run the existing test suite.
10. Identify release blockers.

### Required Findings

Determine:

- Python package name
- Console entry point
- Supported Python versions
- Build backend
- Supported operating systems
- Extension distribution structure
- Whether native platform-specific dependencies exist
- Existing testing commands
- Existing linting and type-checking commands
- Whether tests require RenderDoc or Unity
- Existing release naming conventions

Do not replace existing working CI pipelines unnecessarily.

### Deliverable

A concise CI/CD implementation plan based on the actual repository.

---

## 3. Task B — GitHub Actions Workflow Structure

Implement separate workflows for continuous integration and releases.

Recommended structure:

```text
.github/
└── workflows/
    ├── ci.yml
    └── release.yml

scripts/
├── build_release.py
├── validate_release.py
└── generate_checksums.py
```

The structure is illustrative.

Reuse existing build scripts where possible.

### CI Workflow

File:

`.github/workflows/ci.yml`

Triggers:

- Pull requests targeting the main development branch
- Pushes to the main development branch
- Manual execution where useful

Responsibilities:

- Run automated tests
- Run lint checks
- Run type checks where configured
- Verify Python package builds
- Verify installation without `uv`
- Validate extension packaging
- Validate agent configuration examples

The CI workflow must never publish a GitHub Release.

### Release Workflow

File:

`.github/workflows/release.yml`

Triggers:

- Version tags matching the documented release pattern
- Manual dry-run execution through `workflow_dispatch`

Responsibilities:

- Validate version information
- Execute required release tests
- Build distributions
- Assemble downloadable packages
- Validate package contents
- Generate checksums
- Generate release notes
- Publish GitHub Releases for authorized version-tag events

### Workflow Independence

CI must remain usable without GitHub release permissions.

The release workflow must not bypass mandatory checks simply because it was manually triggered.

### Deliverable

A maintainable, clearly separated CI and release workflow design.

---

## 4. Task C — Windows and Linux CI

Implement cross-platform automated testing.

### Operating System Matrix

Use GitHub-hosted runners appropriate for the repository.

Minimum targets:

- Windows
- Ubuntu Linux

Pin supported runner environments appropriately for reproducibility.

### Python Version Matrix

Determine supported Python versions from project metadata.

Test at least:

- The minimum supported Python version
- The primary recommended Python version

Additional supported versions may be included where practical.

Do not invent support for interpreter versions not compatible with project dependencies.

### Required Checks

Run:

- Python dependency installation
- Unit tests
- Integration tests that do not require interactive GUI access
- Ruff linting
- Configured static type checks
- Package build validation

### GUI-Dependent Tests

Do not assume GitHub-hosted runners have RenderDoc installed or a suitable GPU.

Separate:

**Headless Tests**

Must run in normal CI.

**Real RenderDoc GUI Tests**

May require a dedicated runner or explicitly prepared environment.

**Unity Integration Tests**

Remain optional unless a properly licensed and configured test environment is available.

### Platform-Specific Tests

On Windows, test:

- Windows path handling
- Process identity adapters
- Window control logic through mocks
- RenderDoc discovery
- Installation commands
- Paths containing spaces

On Linux, test:

- Linux path handling
- Process discovery
- Filesystem case sensitivity
- Installation commands
- IPC behavior

Do not claim that mocked GUI tests prove real RenderDoc functionality.

### Deliverable

A cross-platform automated CI test matrix.

---

## 5. Task D — Installation Without uv Verification

Phase 5.1 established installation without `uv`.

Phase 5.2 must verify that capability automatically.

### Requirements

Create a dedicated packaging test that:

1. Builds the Python wheel.
2. Creates a clean Python virtual environment.
3. Installs the wheel using `pip`.
4. Installs required runtime dependencies.
5. Executes the installed application.
6. Verifies the MCP server entry point.
7. Runs a real MCP initialization test.
8. Invokes `server_status`.
9. Shuts down the MCP server cleanly.

### Isolation

The verification environment must not inherit the developer environment's Python package installations.

Do not use `uv run` to launch the installed package during this test.

CI may use `uv` to prepare the build environment, but the installation compatibility test must use ordinary Python packaging commands.

### Additional Checks

- Launch from an unrelated working directory.
- Verify paths containing spaces.
- Verify Unicode paths where practical.
- Confirm MCP stdout remains protocol-clean.
- Confirm the package does not depend on source checkout paths.

### Deliverable

An automated clean-installation test that verifies end-user installation without `uv`.

---

## 6. Task E — Python Distribution Build

Build standard Python distributions.

### Required Artifacts

- Wheel (`.whl`)
- Source distribution (`.tar.gz`)

Use the existing Python build backend.

Suggested commands:

```bash
python -m pip install build
python -m build
```

Equivalent existing build commands are acceptable.

### Validation

Verify:

- Package metadata
- Python compatibility
- Declared dependencies
- Entry points
- Included Python modules
- Included resources
- Version consistency
- Valid wheel structure
- Valid source distribution structure

Use `twine check` or an equivalent validation mechanism where appropriate.

### Distribution Independence

Do not require:

- Git
- `uv`
- A development checkout
- Editable installation
- A local RenderDoc installation for basic MCP server startup

### Platform-Specific Dependencies

If the package includes native components, produce appropriately tagged platform-specific wheels.

Do not label a platform-specific distribution as universally compatible.

If the package is pure Python and legitimately platform-independent, a universal Python wheel is acceptable.

### Deliverable

Validated Python wheel and source distributions.

---

## 7. Task F — RenderDoc Extension Packaging

Package the RenderEye Python extension independently from the MCP server installation.

### Requirements

- Preserve the verified RenderDoc extension directory layout.
- Include all required extension Python files.
- Include valid extension metadata.
- Include extension version information.
- Include any necessary dependency-free shared protocol modules.
- Exclude test files and development-only resources.
- Exclude local configuration and authentication secrets.
- Avoid modifying RenderDoc binaries.

### Extension Archive

Produce a downloadable archive resembling:

`RenderEyeMCP-Extension-v1.0.0.zip`

The archive should contain a copyable extension directory.

Example:

```text
rendereye/
├── __init__.py
├── extension.json
├── ipc_client.py
├── gui_context.py
├── gui_dispatcher.py
└── state_observer.py
```

Use the actual verified layout.

### Compatibility

Document:

- Supported RenderDoc versions
- Required Python extension API features
- IPC protocol version
- Known unsupported versions

### Validation

Check that:

- Required files exist.
- Extension metadata is valid.
- The archive has the correct relative paths.
- Files can be extracted without unsafe path traversal.
- No accidental build artifacts are included.

### Deliverable

A validated, manually installable RenderDoc Extension archive.

---

## 8. Task G — Release Bundle Packaging

Create a convenient release bundle for manual installation.

### Recommended Artifacts

```text
RenderEyeMCP-v1.0.0/
├── python/
│   ├── rendereye_mcp-1.0.0-py3-none-any.whl
│   └── rendereye_mcp-1.0.0.tar.gz
│
├── renderdoc-extension/
│   └── rendereye/
│       └── ...
│
├── examples/
│   ├── claude-code/
│   ├── codex/
│   ├── cursor/
│   ├── vscode-copilot/
│   └── gemini-cli/
│
├── INSTALL-MANUAL.md
├── README.md
└── LICENSE
```

The filenames are illustrative.

Use actual package metadata when generating filenames.

### Bundle Requirements

- Support manual installation.
- Do not require `uv`.
- Include instructions for Windows.
- Include Linux instructions where supported.
- Include coding agent configuration examples.
- Include manual RenderDoc extension installation instructions.
- Exclude unrelated files.
- Exclude Unity project data.
- Exclude `.rdc` captures.
- Exclude virtual environments.
- Exclude cached dependencies.
- Exclude developer-specific configuration.

### Archive Names

Use stable, versioned names such as:

- `RenderEyeMCP-v1.0.0.zip`
- `RenderEyeMCP-v1.0.0.tar.gz`
- `RenderEyeMCP-Extension-v1.0.0.zip`

Do not create duplicate bundles with different filenames but identical contents unless justified.

### Offline Installation

Do not claim that a wheel bundle supports fully offline installation unless all required dependencies are also available.

If offline installation is supported, package and test a complete dependency wheelhouse with appropriate platform and Python compatibility.

Otherwise, document that `pip` may need internet access.

### Deliverable

A reproducible, manual-installation-friendly release bundle.

---

## 9. Task H — Version Management

Use a single authoritative application version.

### Requirements

- Preserve semantic versioning.
- Validate package version against Git tag.
- Validate extension version compatibility.
- Validate release artifact filenames.
- Validate release notes version.
- Avoid manually maintaining conflicting version strings.

### Git Tag Format

Use:

`vMAJOR.MINOR.PATCH`

Examples:

```text
v1.0.0
v1.0.1
v1.1.0
```

Pre-release tags may use:

```text
v1.1.0-rc.1
v1.1.0-beta.1
```

### Validation

A release tag must match the application version.

Example:

```text
Git tag:         v1.0.0
Python package:  1.0.0
Release bundle:  RenderEyeMCP-v1.0.0.zip
```

The IPC protocol version is independent and does not have to match the application version.

### Version Mismatch

Fail the release workflow if version metadata is inconsistent.

Do not silently modify package versions inside the CI workflow to make them match a tag.

### Deliverable

A reliable version validation mechanism.

---

## 10. Task I — Release Artifact Verification

Validate every release artifact before publication.

### Required Checks

- Artifact exists.
- Artifact is nonempty.
- Archive can be opened.
- Archive entries are safe and valid.
- Required files are present.
- Version information is consistent.
- Python wheel installs successfully.
- MCP server launches successfully.
- Extension metadata is valid.
- Example agent configurations are syntactically valid.
- No unexpected sensitive files are included.

### Forbidden Content

Release packages must not contain:

- Authentication tokens
- Private keys
- Local database files
- User capture files
- Unity project data
- Developer-specific absolute paths in active configuration
- Temporary logs
- Python virtual environments
- Git internal metadata
- Unrelated binaries

### Checksums

Generate SHA-256 checksums for downloadable release artifacts.

Recommended file:

`SHA256SUMS.txt`

### Artifact Reproducibility

Use deterministic packaging wherever practical.

Avoid embedding unnecessary build timestamps or machine-specific paths.

Do not require byte-for-byte reproducibility unless the project explicitly adopts that guarantee.

### Deliverable

Automated artifact verification and a SHA-256 checksum manifest.

---

## 11. Task J — GitHub Release Automation

Implement automated GitHub Releases publishing.

### Trigger

Publish releases from valid version-tag pushes.

Example:

```text
git tag v1.0.0
git push origin v1.0.0
```

These commands describe the intended release process.

Do not execute them without explicit authorization.

### Release Workflow

The release workflow must:

1. Check out the exact tagged revision.
2. Validate the tag format.
3. Validate application version.
4. Run mandatory release checks.
5. Build Python distributions.
6. Package the RenderDoc extension.
7. Assemble release bundles.
8. Validate all artifacts.
9. Generate checksums.
10. Generate release notes.
11. Publish the GitHub Release.
12. Upload release assets.
13. Verify that expected assets were attached.
14. Report the release URL and final status.

### Permissions

Use least-privilege GitHub Actions permissions.

Normal build and test jobs should require only read access.

Only the release publishing job should request:

```yaml
permissions:
  contents: write
```

Do not give write permissions to untrusted pull-request workflows.

### GitHub Authentication

Prefer GitHub's automatically provided `GITHUB_TOKEN` for publishing to the current repository.

Do not require a personal access token unless an actual platform limitation justifies it.

Never commit credentials.

### Publishing Mechanism

Use a maintained release action or the GitHub CLI.

For example, `gh release create` may be used when appropriate.

Verify the selected mechanism against current official documentation.

### Existing Releases

If the target release already exists:

- Do not silently overwrite assets.
- Do not delete unrelated assets.
- Do not replace release notes without explicit policy.
- Prefer failing with a clear diagnostic.

Document how maintainers can recover from partial publication failures.

### Prereleases

Tags containing recognized prerelease identifiers must be published as prereleases.

Stable tags must not automatically receive a prerelease designation.

### Deliverable

A secure, automated GitHub Release publishing workflow.

---

## 12. Task K — Release Notes Automation

Generate useful release notes.

### Contents

Include:

- Release version
- Summary
- Main changes
- Bug fixes
- Supported platforms
- Python requirements
- RenderDoc compatibility
- Installation instructions
- Upgrade notes
- Known limitations
- Links to documentation

### Changelog

Maintain or update:

`CHANGELOG.md`

Prefer existing repository conventions.

### Automation

GitHub-generated release notes may be used as a starting point.

Include manually maintained project-specific installation and compatibility information where necessary.

### Important Requirement

Do not fabricate change descriptions.

Release notes must reflect actual repository changes.

### Deliverable

Versioned release notes suitable for GitHub Releases.

---

## 13. Task L — Release Security

Apply GitHub Actions security best practices.

### Least Privilege

- Use read-only permissions by default.
- Grant write permissions only to the publishing job.
- Do not expose release credentials to pull requests.
- Do not use privileged pull-request execution to run untrusted code.
- Avoid unnecessary secrets.

### Action Dependencies

Use maintained GitHub Actions.

Pin third-party actions to verified immutable commit SHAs where practical.

Follow the repository's dependency update and action-pinning conventions.

Avoid unreviewed third-party publishing actions.

### GitHub Token

Do not print tokens or credentials in logs.

Do not store credentials in build artifacts.

### Artifact Integrity

The release job must publish artifacts produced by its verified build process.

Do not accept arbitrary release assets from an untrusted workflow run.

### Artifact Attestations

Evaluate GitHub artifact attestations.

Implement them when compatible with repository permissions, hosting configuration, and release requirements.

If enabled:

- Generate attestations for final release assets.
- Document how users can verify them.
- Avoid claiming provenance guarantees beyond those actually implemented.

### Dependency Security

Avoid introducing unnecessary release-time dependencies.

Use dependency locking or version pinning consistent with the repository.

### Deliverable

A release pipeline with explicitly reviewed trust boundaries.

---

## 14. Task M — Manual Release Dry Run

Provide a safe mechanism to validate the release pipeline without publishing.

### Workflow Dispatch

Support manual workflow execution with a clearly documented dry-run mode.

Suggested input:

```text
publish = false
```

### Dry-Run Behavior

A dry run must:

- Validate version metadata.
- Run required tests.
- Build release artifacts.
- Package distributions.
- Generate checksums.
- Validate package contents.
- Upload temporary GitHub Actions artifacts.
- Report validation results.

A dry run must not:

- Create a Git tag.
- Publish a GitHub Release.
- Replace release assets.
- Publish to PyPI.
- Modify repository contents.
- Push commits.

### Failure Handling

If any required build or validation step fails, the dry run must fail.

Do not disguise errors as warnings.

### Deliverable

A reproducible release dry-run workflow.

---

## 15. Task N — CI and Release Tests

Test workflow correctness and packaging behavior.

### Workflow Validation

- Validate YAML syntax.
- Validate GitHub Actions workflow structure.
- Validate required job dependencies.
- Validate trigger conditions.
- Validate permission declarations.
- Validate artifact paths.
- Validate release conditions.

Use tools such as `actionlint` when appropriate.

### Release Script Tests

- Valid version
- Invalid version
- Version/tag mismatch
- Missing package
- Invalid wheel
- Missing extension file
- Invalid extension metadata
- Missing documentation
- Unexpected files in archive
- Duplicate artifact name
- Checksum generation
- Repeated packaging execution

### Windows Packaging Tests

- Build Python wheel.
- Install without `uv`.
- Validate executable entry point.
- Validate user-installation paths.
- Validate paths containing spaces.

### Linux Packaging Tests

- Build Python wheel.
- Install without `uv`.
- Validate MCP entry point.
- Validate Linux paths.
- Validate extension archive structure.

### Publishing Tests

Use mocked publishing operations or dry-run execution to verify:

- Stable release classification
- Prerelease classification
- Correct artifact lists
- Publication skipped in dry-run mode
- Publication blocked after failed tests
- Existing-release conflict handling

Do not create real GitHub Releases during ordinary tests.

### Deliverable

Automated tests for the CI/CD and release-packaging infrastructure.

---

## 16. Task O — Release Documentation

Create or update the following documentation.

### docs/releasing.md

Include:

- Release prerequisites
- Versioning policy
- Tag conventions
- CI requirements
- Dry-run instructions
- Release publication procedure
- Artifact verification
- Rollback and recovery procedures
- Handling failed releases

### docs/installation.md

Update installation instructions to use GitHub Release assets.

### docs/installation-manual.md

Document which archive to download and how to install it.

### README.md

Include:

- Link to GitHub Releases
- Supported platforms
- Python requirements
- Installation instructions
- Manual installation instructions
- Coding agent setup links

Do not invent the GitHub repository URL.

Use the actual repository URL where available.

### CHANGELOG.md

Ensure version history and release notes are consistent.

### docs/development.md

Document:

- Running CI checks locally
- Building distribution packages
- Validating archives
- Generating checksums
- Testing release scripts

### Deliverable

A complete release and distribution guide.

---

## 17. Task P — Optional PyPI Publishing

PyPI publication is **not required for Phase 5.2**.

The primary distribution channel is GitHub Releases.

If the repository already publishes to PyPI, preserve the existing workflow and evaluate compatibility.

Otherwise, document PyPI publishing as a possible future improvement.

Do not introduce PyPI credentials.

Do not create a PyPI project.

Do not publish to TestPyPI or PyPI without explicit authorization.

If PyPI publishing is implemented in a later phase, prefer trusted publishing using GitHub Actions OIDC rather than long-lived API tokens.

---

## 18. Acceptance Scenarios

### Scenario A — Pull Request

A contributor opens a pull request.

Expected:

- Windows tests execute.
- Linux tests execute.
- Packaging validation executes.
- CI reports success or failure.
- No release is published.

### Scenario B — Main Branch Push

Changes are merged into the main development branch.

Expected:

- Standard CI runs.
- Build compatibility is checked.
- No release is published.

### Scenario C — Release Dry Run

A maintainer manually starts release validation.

Expected:

- Tests execute.
- Distributions are built.
- Release bundles are generated.
- Checksums are generated.
- GitHub Actions artifacts are available.
- No GitHub Release is created.

### Scenario D — Stable Version Tag

An authorized maintainer pushes a valid stable version tag.

Expected:

- Tag and package versions are validated.
- Mandatory tests pass.
- Distributions are built.
- Artifacts are validated.
- GitHub Release is published.
- Release assets are attached.
- Checksums are available.

### Scenario E — Prerelease Tag

A valid prerelease tag is pushed.

Expected:

- Artifacts are built and validated.
- GitHub Release is marked as a prerelease.
- Stable release metadata is not incorrectly applied.

### Scenario F — Failed Release Build

A mandatory release validation fails.

Expected:

- Publication is blocked.
- No successful release is reported.
- Failure diagnostics identify the reason.

### Scenario G — Manual Installation

A user downloads the published GitHub Release archive.

Expected:

- The Python wheel can be installed without `uv`.
- The RenderDoc extension can be manually copied.
- Agent configuration examples are available.
- The MCP server can be started through standard Python tooling.

---

## 19. Definition of Done

Phase 5.2 is complete when:

- [ ] GitHub Actions CI workflow exists.
- [ ] Windows CI is implemented.
- [ ] Linux CI is implemented.
- [ ] Supported Python versions are tested.
- [ ] Automated tests run on pull requests.
- [ ] Package builds are validated.
- [ ] Installation without `uv` is tested.
- [ ] Python wheel is generated.
- [ ] Source distribution is generated.
- [ ] RenderDoc extension ZIP is generated.
- [ ] Manual installation bundle is generated.
- [ ] Agent configuration examples are included.
- [ ] Version/tag validation is implemented.
- [ ] Release artifacts are verified.
- [ ] SHA-256 checksums are generated.
- [ ] GitHub Release workflow exists.
- [ ] Stable and prerelease behavior is implemented.
- [ ] Release publishing is blocked after failed mandatory checks.
- [ ] Release permissions follow least-privilege principles.
- [ ] Manual dry-run mode works.
- [ ] Existing release assets are not silently overwritten.
- [ ] Release documentation is updated.
- [ ] Existing application tests remain passing.
- [ ] CI/CD configuration is validated.
- [ ] Unverified platform functionality is documented honestly.

Successful local configuration validation alone does not prove that GitHub-hosted workflows execute correctly.

Where repository access permits, execute a real GitHub Actions dry run and record its result.

Do not publish an actual release without authorization.

---

## 20. Execution Instructions

Execute the implementation in this order:

1. Inspect the repository.
2. Review Phase 5 and Phase 5.1 release functionality.
3. Run existing tests.
4. Audit existing GitHub Actions workflows.
5. Confirm supported Python versions and platforms.
6. Implement Windows and Linux CI.
7. Implement installation-without-uv tests.
8. Validate Python distribution builds.
9. Implement RenderDoc extension packaging.
10. Implement release bundle assembly.
11. Implement version validation.
12. Implement archive validation.
13. Implement checksum generation.
14. Implement GitHub Release publishing workflow.
15. Implement release dry-run mode.
16. Add release security checks.
17. Add workflow and packaging tests.
18. Validate workflow YAML and job dependencies.
19. Execute the complete regression suite.
20. Execute a GitHub Actions dry run if authorized and available.
21. Update release documentation.
22. Review the acceptance criteria.
23. Produce the final report.

Work autonomously using the available repository and development tools.

Do not stop at designing workflows.

Do not create placeholder workflows that cannot execute.

Do not introduce unnecessary build dependencies.

Do not require `uv` for end users.

Do not create a real Git tag or publish a release without explicit authorization.

Do not implement unrelated RenderDoc debugging features.

---

## 21. Final Report

After implementation, report:

1. **Implementation Summary** — CI/CD capabilities implemented.
2. **Files Changed** — Workflows, scripts, tests, and documentation.
3. **CI Matrix** — Operating systems and Python versions.
4. **Build Artifacts** — Exact generated filenames.
5. **Package Verification** — Wheel, source distribution, extension, and bundle validation.
6. **Installation Tests** — Results without `uv`.
7. **Release Automation** — Trigger and publication behavior.
8. **Security** — Permissions, tokens, and artifact integrity.
9. **Dry-Run Results** — Tests and packaging validation executed.
10. **GitHub Actions Results** — Actual hosted workflow runs, if executed.
11. **Known Limitations** — Unverified platforms, runners, or distribution formats.
12. **Phase 5.2 Status** — Complete, partially verified, or blocked.
13. **Release Readiness** — Whether the release pipeline is ready for a version-tagged publication.

Do not claim successful execution of GitHub-hosted workflows that were not actually run.

Do not publish a release merely to verify the release workflow.

**Phase 5.2 Focus: Establish secure, automated, cross-platform GitHub Actions CI/CD and reproducible GitHub Releases for RenderEyeMCP, with verified installation packages that do not require uv.**
