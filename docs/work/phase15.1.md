# Phase 15.1 Addendum — Separate PyPI and TestPyPI Publishing Workflows

## Objective

Modify the Phase 15.1 implementation so production PyPI publishing and TestPyPI publishing use **two completely separate GitHub Actions workflow YAML files**.

Do not implement a single publishing workflow containing conditional production and test publishing jobs.

## 1. Required Workflow Files

Create or update:

```text
.github/workflows/publish-testpypi.yml
.github/workflows/publish-pypi.yml
```

### TestPyPI Workflow

`publish-testpypi.yml` must:

- Trigger only for test-release tag patterns.
- Validate the complete tag format `vMAJOR.MINOR.PATCH-test.N`.
- Convert the tag to a PEP 440-compatible version such as `MAJOR.MINOR.PATCH.devN`.
- Build and validate wheel and source distributions.
- Verify package metadata matches the normalized version.
- Publish exclusively to `https://test.pypi.org/legacy/`.
- Use the GitHub Environment `testpypi`.
- Authenticate using TestPyPI Trusted Publishing and OIDC.
- Never contain a production publishing job.

### Production PyPI Workflow

`publish-pypi.yml` must:

- Trigger for candidate production version tags.
- Strictly validate `vMAJOR.MINOR.PATCH` before publishing.
- Reject any suffix, including `-test.N`.
- Build and validate production distributions.
- Verify package metadata matches the production version.
- Publish exclusively to production PyPI.
- Use the GitHub Environment `pypi`.
- Authenticate using production PyPI Trusted Publishing and OIDC.
- Never contain a TestPyPI publishing job.

GitHub Actions tag glob patterns are not regular expressions. Never rely on the trigger filter alone to authorize publishing.

## 2. Shared Build Logic

Avoid unnecessary duplication, but keep publishing responsibilities separate.

It is acceptable to share:

- A small tag/version validation script.
- A package metadata verification script.
- A reusable build script.
- Existing packaging configuration.

For example:

```text
.github/
  workflows/
    publish-testpypi.yml
    publish-pypi.yml

scripts/
  validate_release_tag.py
  verify_distribution.py
```

This structure is illustrative. Reuse existing scripts if suitable.

Do not introduce a shared publishing workflow that selects PyPI or TestPyPI dynamically.

Each YAML file must independently and explicitly specify its own publishing destination and GitHub Environment.

Within each workflow, keep build and publish jobs separate.

Only the publishing job should receive `id-token: write`.

## 3. Trusted Publisher Registration

Document two independent publisher registrations.

**TestPyPI**

- Repository: actual GitHub repository.
- Workflow: `publish-testpypi.yml`.
- Environment: `testpypi`.
- Index: `https://test.pypi.org/`.

**Production PyPI**

- Repository: actual GitHub repository.
- Workflow: `publish-pypi.yml`.
- Environment: `pypi`.
- Index: `https://pypi.org/`.

The workflow filename must match the corresponding Trusted Publisher registration exactly.

Do not use a single registration for both workflow files.

## 4. Production Safety

Configure the `pypi` GitHub Environment to require manual approval where the repository's plan and settings support it.

Restrict production tag creation and modification to authorized maintainers.

The production publishing job must reject every test-release tag, even if GitHub triggers the workflow because of a broad `v*` tag filter.

Do not publish to production PyPI as part of implementing or testing this change.

## 5. Validation

Add automated tests verifying:

| Git tag | TestPyPI workflow | PyPI workflow |
|---|---|---|
| `v0.1.0` | No publish | Publish |
| `v0.1.0-test.1` | Publish | No publish |
| `v0.1.0-test.2` | Publish | No publish |
| `v1.2.3` | No publish | Publish |
| `v1.2.3-test.1` | Publish | No publish |
| `v1.2.3-debug` | No publish | No publish |
| `v1.2` | No publish | No publish |

Verify both the tag classification logic and workflow-level job conditions.

Validate each workflow's YAML syntax.

Check that the publishing job cannot execute when tag validation fails.

Test version conversion and distribution metadata separately.

## 6. Documentation

Update English and Japanese publishing documentation.

Clearly distinguish:

- TestPyPI release commands.
- Production PyPI release commands.
- GitHub Actions workflow filenames.
- GitHub Environment configuration.
- Trusted Publisher registration.
- Package version normalization.
- Troubleshooting.

Document the publishing paths independently.

## 7. Acceptance Criteria

- [ ] `publish-testpypi.yml` exists and contains only TestPyPI publishing.
- [ ] `publish-pypi.yml` exists and contains only production PyPI publishing.
- [ ] Both workflows validate tags independently before publishing.
- [ ] Both workflows use the correct separate GitHub Environments.
- [ ] Both workflows use OIDC Trusted Publishing.
- [ ] Neither workflow requires long-lived publishing credentials.
- [ ] `-test.N` tags cannot trigger production publication.
- [ ] Production tags cannot trigger TestPyPI publication.
- [ ] Invalid tags cannot publish anywhere.
- [ ] Build artifacts are validated before publication.
- [ ] Tag and workflow isolation tests pass.
- [ ] Trusted Publisher registration instructions are provided for both indices.
- [ ] English and Japanese documentation is updated.
- [ ] Existing unrelated release workflows remain functional.
- [ ] No production PyPI release is published during validation.

## Final Goal

The two publishing workflows must be independently understandable, maintainable, and secure.

A maintainer should be able to open either YAML file and immediately identify its publishing destination without tracing conditional logic shared with the other package index.

**Keep the publication destination fixed at the workflow-file level, not selected dynamically at runtime.**
