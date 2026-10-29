# Phase 15.1 — PyPI Trusted Publishing & TestPyPI Release Validation

## Objective

Implement secure, automated Python package publishing for RenderEyeMCP using GitHub Actions and PyPI Trusted Publishing.

Introduce two separate publishing destinations:

1. **PyPI** — Official package releases.
2. **TestPyPI** — Test releases triggered by version tags containing an explicit `-test` suffix.

The objective is to validate the entire packaging and publishing pipeline using TestPyPI before publishing official releases.

Use OpenID Connect (OIDC) Trusted Publishing instead of long-lived PyPI API tokens.

The workflow must ensure that:

- Official version tags publish exclusively to PyPI.
- Test version tags publish exclusively to TestPyPI.
- Test releases never accidentally publish to production PyPI.
- Invalid tag formats cannot trigger publishing.
- Package versions comply with PEP 440.
- Publishing artifacts are validated before upload.
- The published package can be installed and executed.
- Existing release workflows and artifacts remain compatible.

This task is release infrastructure work, not a new RenderDoc debugging feature.

Do not modify MCP functionality, RenderDoc extension behavior, or GPU inspection tools unless required to fix a verified packaging issue.

---

## 1. Investigate Existing Release Infrastructure

Before implementing changes, inspect the repository.

Identify:

1. `pyproject.toml` and other packaging configuration.
2. Package name and versioning configuration.
3. Python build backend.
4. Existing GitHub Actions workflows.
5. Existing release workflow.
6. Existing Git tag naming conventions.
7. Version extraction or generation scripts.
8. Existing wheel and source distribution generation.
9. Current PyPI publishing configuration.
10. Existing GitHub Releases automation.
11. Existing installer and executable entry points.
12. Package installation documentation.
13. Current test infrastructure.

Do not assume that all release processes use the same versioning mechanism.

Preserve the current project structure where possible.

### 1.1 Determine the Version Source

Identify how the package version is currently defined.

Possible approaches include:

- Static version in `pyproject.toml`.
- Version derived from Git tags.
- Hatch or setuptools-scm dynamic versioning.
- A custom version file.
- Another build-backend-specific version mechanism.

Choose an approach compatible with the existing build backend.

Do not introduce a new versioning library unless necessary.

### 1.2 Determine Existing Release Triggers

Inspect whether the repository currently publishes artifacts using:

- Tag pushes.
- GitHub Release events.
- Manual workflow dispatch.
- Another CI mechanism.

Avoid triggering duplicate releases from overlapping workflows.

Preserve existing non-PyPI artifacts such as installers or binary distributions.

---

## 2. Tag Naming Convention

Use explicit, predictable tag formats.

### 2.1 Production Tags

Production releases use:

```text
vMAJOR.MINOR.PATCH
```

Examples:

```text
v0.1.0
v0.1.1
v1.0.0
```

The corresponding Python package versions are:

```text
0.1.0
0.1.1
1.0.0
```

Production tags publish only to PyPI.

### 2.2 Test Tags

Test releases use:

```text
vMAJOR.MINOR.PATCH-test.N
```

Examples:

```text
v0.1.0-test.1
v0.1.0-test.2
v0.2.0-test.1
```

These tags publish only to TestPyPI.

Normalize the test tag suffix to a PEP 440-compatible development-release version.

Examples:

```text
v0.1.0-test.1 -> 0.1.0.dev1
v0.1.0-test.2 -> 0.1.0.dev2
v0.2.0-test.1 -> 0.2.0.dev1
```

The mapping must be deterministic and documented.

### 2.3 Optional Short Test Suffix

The user-facing naming convention may also permit:

```text
v0.1.0-test
```

However, an unnumbered suffix creates version-reuse problems.

Prefer requiring a numeric test iteration.

Do not support unnumbered test tags unless a deterministic, collision-safe package version can be generated.

### 2.4 Invalid Tags

Reject tags such as:

```text
v0.1
v0.1.0-test.foo
v0.1.0-test.
v0.1.0-test.0
v0.1.0-debug
release-0.1.0
```

Do not silently interpret unknown suffixes as production releases.

### 2.5 Version Validation

Implement or reuse a small validation mechanism.

Use an anchored tag parser.

Validate the final package version using a PEP 440-compatible parser, such as the `packaging` library where appropriate.

Do not rely solely on permissive GitHub Actions glob patterns for release classification.

---

## 3. Publishing Destination Isolation

Production and test publishing must be strictly separated.

### 3.1 Publishing Rules

| Tag | Destination |
|---|---|
| `v0.1.0` | PyPI |
| `v0.1.0-test.1` | TestPyPI |
| `v0.1.0-test.2` | TestPyPI |
| Invalid tag | Neither |

### 3.2 Production Safety

A `-test` tag must never:

- Trigger a production PyPI publishing job.
- Deploy to the `pypi` GitHub Environment.
- Use production publishing credentials.
- Produce an official production release automatically.

### 3.3 Test Safety

A production tag must not automatically upload to TestPyPI unless the repository already has an explicitly documented and justified release policy requiring it.

For this phase, prefer strict separation.

### 3.4 Defense in Depth

Use both:

1. GitHub Actions trigger filtering.
2. Explicit tag classification and validation.

Do not rely solely on a wildcard such as `v*`.

The production publish job must have an explicit production-tag guard.

The TestPyPI publish job must have an explicit test-tag guard.

### 3.5 GitHub Environment Isolation

Use separate GitHub Environments:

```text
pypi
testpypi
```

Apply appropriate protection rules.

For production, recommend manual approval and restrictions to authorized version tags.

For TestPyPI, allow controlled test-tag publishing without unnecessary manual steps.

Ensure environment protection rules match the selected tag convention.

---

## 4. Configure PyPI Trusted Publishing

Use PyPI's official Trusted Publishing mechanism.

Do not require long-lived PyPI API tokens in GitHub Secrets.

### 4.1 Production PyPI

Configure a GitHub Actions Trusted Publisher for the actual RenderEyeMCP package on:

https://pypi.org/

The registration must match:

- GitHub repository owner.
- GitHub repository name.
- Workflow filename.
- GitHub Environment name: `pypi`.

Use the actual repository information.

Do not invent or hardcode an unverified repository owner.

### 4.2 TestPyPI

Configure a separate Trusted Publisher on:

https://test.pypi.org/

Use:

- The same repository owner and name, when applicable.
- The actual publishing workflow filename.
- GitHub Environment name: `testpypi`.

TestPyPI and PyPI require separate publisher registrations.

### 4.3 Pending Publishers

If the package does not yet exist on an index, investigate whether a pending Trusted Publisher can be registered.

Document the required setup process.

Do not assume the same account or project configuration exists on both indices.

### 4.4 OIDC Permissions

Only publishing jobs should receive:

```yaml
permissions:
  id-token: write
```

Do not grant this permission globally to unrelated build or test jobs.

Avoid unnecessary repository write permissions.

### 4.5 Publishing Action

Prefer the official PyPA action:

```yaml
uses: pypa/gh-action-pypi-publish@release/v1
```

Follow the repository's existing dependency pinning policy.

If the project pins GitHub Actions by immutable commit SHA, preserve that security model.

Do not invent commit SHAs.

For TestPyPI, configure:

```yaml
with:
  repository-url: https://test.pypi.org/legacy/
```

Do not use the TestPyPI repository URL in the production publishing job.

### 4.6 No Stored Publishing Credentials

Do not introduce:

- `PYPI_API_TOKEN`
- `TEST_PYPI_API_TOKEN`
- Long-lived publishing passwords.
- Hardcoded publishing credentials.

Remove obsolete publishing secret references only after confirming they are no longer used by other workflows.

---

## 5. GitHub Actions Workflow Design

Prefer a clear, maintainable publishing workflow.

Suggested workflow filename:

```text
.github/workflows/publish-pypi.yml
```

Reuse an existing publishing workflow if that avoids duplication.

### 5.1 Trigger Rules

Trigger on relevant version tags.

For example, the workflow may initially match:

```yaml
on:
  push:
    tags:
      - "v*"
```

The broad trigger is only a discovery filter.

**The workflow must subsequently validate the complete tag and classify it as production, test, or invalid before executing publishing jobs.**

Do not use `startsWith(tag, "v")` as sufficient authorization for production publishing.

### 5.2 Job Structure

Prefer the following architecture:

```text
Tag Push
    |
    v
Validate Tag and Determine Version
    |
    v
Build Distribution
    |
    v
Validate Wheel and Source Distribution
    |
    +---------------------+
    |                     |
    v                     v
Production Tag        Test Tag
    |                     |
    v                     v
PyPI Environment      TestPyPI Environment
    |                     |
    v                     v
Publish to PyPI        Publish to TestPyPI
```

### 5.3 Build and Publish Separation

Keep package building separate from publishing.

The build job should:

- Check out the tagged commit.
- Validate the tag.
- Determine the package version.
- Build distribution artifacts.
- Validate artifacts.
- Upload artifacts to GitHub Actions storage.

The publishing job should:

- Download the validated artifacts.
- Authenticate using Trusted Publishing.
- Upload to the correct index.

Do not run arbitrary project build scripts inside the OIDC-authorized publishing job when avoidable.

### 5.4 Artifact Integrity

Publish the exact artifacts validated by the build job.

Do not rebuild the package in the publishing job.

Do not use artifacts from another workflow execution unless their identity and integrity are verified.

### 5.5 Workflow Concurrency

Use an appropriate concurrency strategy to prevent duplicate publishing of the same tag.

Do not cancel a publishing job once distribution upload may have started unless cancellation behavior is explicitly safe.

A failed or partially completed upload must be handled carefully because PyPI does not allow replacing an existing distribution with the same filename and version.

---

## 6. Package Version Generation

Ensure the built package version matches the release tag classification.

### 6.1 Production Version

Example:

```text
Git tag: v0.1.0
Package version: 0.1.0
```

### 6.2 Test Version

Example:

```text
Git tag: v0.1.0-test.3
Package version: 0.1.0.dev3
```

### 6.3 Version Source Consistency

Ensure consistent versions in:

- Wheel metadata.
- Source distribution metadata.
- Package filename.
- Runtime package version, where exposed.
- Installation metadata.

Do not modify only the wheel filename.

The package metadata itself must contain the correct version.

### 6.4 Build Backend Compatibility

If the current backend supports dynamic version overrides, use its supported mechanism.

If it derives versions from Git tags, configure the appropriate tag-to-version mapping.

If the version is static, investigate the safest way to generate test builds without committing temporary version changes.

Do not introduce brittle regular-expression modifications to arbitrary source files.

### 6.5 No Unnecessary Source Modification

The test publishing workflow should not create commits merely to update the version number.

Prefer deterministic version generation from the tag.

### 6.6 Version Uniqueness

Each TestPyPI publication must use a version not previously uploaded.

For example:

```text
v0.1.0-test.1
v0.1.0-test.2
v0.1.0-test.3
```

Do not automatically overwrite existing distributions.

Do not use `skip-existing` to conceal version collisions or broken publishing logic.

### 6.7 Production Release Consistency

Ensure a later production release has the expected final version.

For example:

```text
TestPyPI: 0.1.0.dev3
PyPI:     0.1.0
```

The production build must be validated independently.

Do not rename the TestPyPI wheel to simulate a production package.

---

## 7. Package Build Validation

Before publishing, validate the generated distributions.

### 7.1 Required Artifacts

Inspect the project's current packaging requirements.

Typically validate:

- Wheel (`.whl`).
- Source distribution (`.tar.gz`).

Do not introduce unnecessary additional formats.

### 7.2 Package Contents

Verify that the package includes required files such as:

- Python modules.
- MCP server entry point.
- RenderEyeMCP runtime dependencies.
- Required extension resources, if distributed through PyPI.
- Relevant package data.
- Configuration templates where applicable.

Do not assume the files present in the source checkout are included in the wheel.

### 7.3 Metadata Validation

Use existing packaging validation tools where practical.

For example:

```shell
python -m build
python -m twine check dist/*
```

Adapt to the actual build backend.

### 7.4 Wheel Installation

Install the wheel in an isolated environment.

Verify:

- Package installation succeeds.
- Package imports successfully.
- MCP executable entry point is available.
- Version metadata matches the expected version.

### 7.5 Source Distribution Validation

Where practical:

1. Extract or install the source distribution in an isolated environment.
2. Build the wheel from that source distribution.
3. Verify required project files are present.

Avoid validating only the source checkout.

### 7.6 Version Assertions

The workflow must explicitly check that the built distribution version equals the normalized version derived from the tag.

Fail the build before publishing if the versions differ.

---

## 8. TestPyPI Publishing Validation

TestPyPI must validate the real publishing path, not merely build artifacts locally.

### 8.1 Test Tag Scenario

Use an example such as:

```shell
git tag v0.1.0-test.1
git push origin v0.1.0-test.1
```

This is documentation only.

Do not create or push tags automatically without explicit authorization.

### 8.2 Expected Behavior

The workflow should:

1. Detect the test tag.
2. Classify it as TestPyPI-only.
3. Generate the PEP 440-compatible version.
4. Build the package.
5. Validate distribution metadata.
6. Publish through the `testpypi` GitHub Environment.
7. Authenticate using OIDC.
8. Upload the package to TestPyPI.
9. Report the published package URL.

### 8.3 Post-Publish Verification

After publishing, verify that the expected package version exists on TestPyPI.

Do not rely only on the upload action's exit status.

Where network access and permissions allow, install the published package in a clean environment.

### 8.4 Installation Example

Use the actual package name and version.

A conceptual command is:

```shell
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "PACKAGE_NAME==0.1.0.dev1"
```

This command illustrates the idea and must not be copied into the final documentation without reviewing dependency resolution and package-name correctness.

Using multiple package indices may permit dependencies or similarly named packages to be resolved from unintended locations.

Prefer a safer validated installation strategy where feasible, such as obtaining the exact distribution artifact from TestPyPI and installing it with appropriately controlled dependency resolution.

Document the selected strategy and its tradeoffs.

### 8.5 Runtime Smoke Test

Verify the installed distribution:

- Exposes the expected version.
- Provides its MCP executable.
- Can start or display startup diagnostics.
- Includes required runtime resources.

A full RenderDoc integration test may require a Windows GUI environment and should be reported separately.

### 8.6 Repeat Test

Publish another test tag, such as:

```text
v0.1.0-test.2
```

Verify that it produces:

```text
0.1.0.dev2
```

Ensure it is accepted as a distinct TestPyPI distribution.

Do not reuse the previous version.

---

## 9. Production PyPI Publishing

Implement the production publishing path, but do not publish a production release during this task without explicit authorization.

### 9.1 Production Tag

Use:

```text
vMAJOR.MINOR.PATCH
```

Example:

```text
v0.1.0
```

### 9.2 Production Job

The production job must:

- Require a valid production tag.
- Use the `pypi` GitHub Environment.
- Obtain OIDC credentials through Trusted Publishing.
- Upload the validated distribution.
- Never use the TestPyPI repository URL.

### 9.3 Protection Rules

Recommend:

- Authorized tag restrictions.
- Manual production approval.
- Restricted repository administration.
- Minimal workflow permissions.

Do not weaken existing repository protections.

### 9.4 Production Publishing Verification

Before the first production release, verify:

- Correct Trusted Publisher configuration.
- Correct workflow filename.
- Correct GitHub Environment.
- Correct package name.
- Correct version.
- Correct artifact contents.
- Correct destination.
- Validated production-tag conditions.

A dry run cannot fully validate OIDC publishing authentication without contacting the actual index.

Document what has and has not been tested.

---

## 10. Security Requirements

### 10.1 Least Privilege

Grant `id-token: write` only to publishing jobs.

Build and test jobs must not receive unnecessary OIDC permissions.

### 10.2 Trusted Workflow Identity

The GitHub repository, workflow filename, and Environment must match the publisher configuration registered on PyPI or TestPyPI.

A mismatch should cause authentication failure.

### 10.3 Avoid Token-Based Publishing

Do not use long-lived PyPI secrets as a fallback.

If OIDC authentication fails, report the configuration problem.

### 10.4 Tag Validation

Never infer that a tag is safe for production merely because it begins with `v`.

Validate the complete format.

### 10.5 Untrusted Workflow Code

Avoid running untrusted project code in the publishing job.

Build artifacts should be prepared and validated in a separate job before obtaining publishing credentials.

### 10.6 Branch and Tag Protection

Document recommended GitHub rulesets and Environment protection settings.

Do not assume repository rules can be configured entirely through committed workflow files.

### 10.7 Release Artifact Integrity

Use the project's existing artifact integrity practices.

Avoid downloading unverified distributions from arbitrary external locations.

---

## 11. Testing

Add tests for the publishing workflow and version classification.

### 11.1 Tag Classification Tests

Cover:

| Tag | Expected classification | Version |
|---|---|---|
| `v0.1.0` | production | `0.1.0` |
| `v1.2.3` | production | `1.2.3` |
| `v0.1.0-test.1` | test | `0.1.0.dev1` |
| `v0.1.0-test.2` | test | `0.1.0.dev2` |
| `v0.1.0-test.foo` | invalid | none |
| `v0.1.0-debug` | invalid | none |
| `v0.1` | invalid | none |
| `v0.1.0-test.0` | invalid | none |

### 11.2 Version Validation

Verify that every accepted tag produces a valid PEP 440 version.

Verify that the built artifact contains the expected version.

### 11.3 Destination Isolation

Test that:

- Production tags cannot activate TestPyPI publishing.
- Test tags cannot activate production PyPI publishing.
- Invalid tags cannot activate either publish job.

### 11.4 Package Build Tests

Verify:

- Wheel builds successfully.
- Source distribution builds successfully.
- Distribution metadata is valid.
- Required package files are included.
- Entry points are correct.
- Installation succeeds in an isolated environment.

### 11.5 TestPyPI Integration Test

When credentials, repository settings, and network access are available:

1. Register the Trusted Publisher.
2. Push a unique test tag.
3. Observe the GitHub Actions run.
4. Verify publication on TestPyPI.
5. Verify package installation.
6. Record the result.

Do not claim an actual TestPyPI publishing test passed without performing the upload.

### 11.6 Negative Tests

Verify that:

- Missing Trusted Publisher configuration causes a clear failure.
- Wrong Environment names do not authenticate.
- Invalid package versions are rejected.
- Existing distribution versions are not silently overwritten.
- Package metadata mismatches stop publishing.

Do not perform unsafe negative tests against production PyPI.

---

## 12. Documentation

Update both English and Japanese documentation.

Suggested files:

```text
docs/
  en/
    publishing.md

  ja/
    publishing.md
```

Update the relevant contributor and release documentation.

### 12.1 Required Topics

Document:

- Trusted Publishing overview.
- Required PyPI and TestPyPI accounts.
- GitHub Environment setup.
- Trusted Publisher registration.
- Supported tag patterns.
- Version normalization.
- TestPyPI publishing procedure.
- Production publishing procedure.
- Installation verification.
- Common errors.
- Security recommendations.

### 12.2 Trusted Publisher Registration

Provide a table containing the values users must configure.

| Field | PyPI | TestPyPI |
|---|---|---|
| Repository owner | Actual owner | Actual owner |
| Repository name | Actual name | Actual name |
| Workflow | Actual filename | Actual filename |
| Environment | `pypi` | `testpypi` |

Use the actual project identity after repository inspection.

Do not invent values.

### 12.3 Test Publishing Instructions

Provide copyable commands for creating and pushing test tags.

Explain:

- Why each tag needs a unique version.
- How the version is normalized.
- Where to view the GitHub Actions result.
- Where to find the published package.
- How to install and test it.

### 12.4 Production Publishing Instructions

Explain how to publish an official version.

Clearly warn that production PyPI does not permit replacing an already published distribution file.

### 12.5 Troubleshooting

Cover:

- Trusted Publisher not configured.
- OIDC authentication failure.
- Environment mismatch.
- Workflow filename mismatch.
- Duplicate distribution version.
- Invalid package metadata.
- Missing package data.
- Wheel installation failure.
- Dependency resolution problems on TestPyPI.

---

## 13. Scope Restrictions

Do not implement unrelated functionality.

Avoid:

- New RenderDoc debugging features.
- MCP API changes.
- Shared IPC Service redesign.
- Installer redesign unrelated to packaging.
- New binary release formats.
- Automatic GitHub Release publishing unless already integrated.
- Automatic production publication during validation.
- New long-lived publishing credentials.
- Major versioning-system replacement without justification.

Small packaging fixes necessary for correct publishing are allowed.

---

## 14. Deliverables

Provide:

### A. GitHub Actions

- Trusted Publishing workflow.
- Production/TestPyPI destination separation.
- Tag validation and classification.
- Distribution build and validation.
- OIDC publishing configuration.

### B. Versioning

- Test-tag normalization.
- PEP 440 version validation.
- Package metadata consistency checks.
- Versioning tests.

### C. Documentation

- English publishing documentation.
- Japanese publishing documentation.
- Trusted Publisher setup guide.
- TestPyPI release procedure.
- Production release procedure.

### D. Validation Report

- Tag classification tests.
- Package build results.
- Wheel installation results.
- TestPyPI publishing results, if executed.
- OIDC configuration status.
- Known limitations and blockers.

---

## 15. Acceptance Criteria

Phase 15.1 is complete when:

- [ ] Existing release workflows have been reviewed.
- [ ] The current package versioning mechanism is understood.
- [ ] Production tags follow a documented version format.
- [ ] Test tags follow the `-test.N` naming convention.
- [ ] Test tags produce valid PEP 440 package versions.
- [ ] Test versions are unique for distinct test iterations.
- [ ] Invalid tags are rejected.
- [ ] Production and test publishing jobs are strictly separated.
- [ ] Test tags cannot publish to production PyPI.
- [ ] Production publishing uses Trusted Publishing.
- [ ] TestPyPI publishing uses Trusted Publishing.
- [ ] No long-lived publishing tokens are required.
- [ ] OIDC permissions are limited to publishing jobs.
- [ ] GitHub Environments are separated.
- [ ] Production Environment protection is documented.
- [ ] Wheel and source distributions are built successfully.
- [ ] Package metadata matches the normalized tag version.
- [ ] Distribution contents are validated.
- [ ] Built wheels can be installed in an isolated environment.
- [ ] TestPyPI publication is performed when external setup and authorization are available.
- [ ] A published TestPyPI package can be installed when publication succeeds.
- [ ] Existing distribution version collisions are handled safely.
- [ ] The workflow does not automatically publish a production release during validation.
- [ ] English documentation is updated.
- [ ] Japanese documentation is updated.
- [ ] Existing release artifacts remain compatible.
- [ ] Test results and unresolved external setup steps are reported accurately.

If Trusted Publisher registration or a real TestPyPI upload cannot be performed, mark those criteria as pending external configuration or unverified.

Do not report the end-to-end publishing flow as verified until a real TestPyPI publication succeeds.

---

## Final Goal

After Phase 15.1, RenderEyeMCP should support a simple, secure release workflow.

For test publishing:

```text
git tag v0.1.0-test.1
git push origin v0.1.0-test.1
```

Expected result:

```text
Package: RenderEyeMCP
Version: 0.1.0.dev1
Index: TestPyPI
Authentication: GitHub OIDC Trusted Publishing
```

For an official release:

```text
git tag v0.1.0
git push origin v0.1.0
```

Expected result, after the configured production approval:

```text
Package: RenderEyeMCP
Version: 0.1.0
Index: PyPI
Authentication: GitHub OIDC Trusted Publishing
```

The production and test release paths must be independent, deterministic, and protected against accidental cross-publication.

The actual distribution name, executable name, and versioning implementation must be taken from the repository.

**Phase 15.1 should establish a safe, repeatable TestPyPI publishing process that can validate packaging and Trusted Publishing before the first official PyPI release.**
