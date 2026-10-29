[English](publishing.md) | [日本語](../ja/publishing.md)

# PyPI Publishing Guide

This document describes how to publish RenderEyeMCP to PyPI and TestPyPI using
GitHub Actions and PyPI Trusted Publishing (OIDC).

## Overview

RenderEyeMCP uses **PyPI Trusted Publishing** (OpenID Connect) instead of long-lived
API tokens. No `PYPI_API_TOKEN` or `TEST_PYPI_API_TOKEN` secrets are stored in the
repository. Authentication happens automatically through GitHub Actions OIDC when the
workflow runs inside the configured GitHub Environment.

Two publishing destinations are supported:

| Destination | Tag format | Version | Use |
|---|---|---|---|
| PyPI | `v1.0.0` | `1.0.0` | Official releases |
| TestPyPI | `v1.0.0-test.1` | `1.0.0.dev1` | Validation before first release |

---

## Tag Naming Convention

### Production tags

```
vMAJOR.MINOR.PATCH
```

Examples: `v0.1.0`, `v1.0.0`, `v1.2.3`

These tags trigger the `pypi` publishing job. The package version is the tag with
the leading `v` removed.

### Test tags

```
vMAJOR.MINOR.PATCH-test.N
```

Examples: `v0.1.0-test.1`, `v0.1.0-test.2`, `v1.0.0-test.1`

`N` must be a positive integer (`>= 1`). These tags trigger the `testpypi` publishing
job. The package version is normalized to a PEP 440 development version:

| Git tag | Package version |
|---|---|
| `v0.1.0-test.1` | `0.1.0.dev1` |
| `v0.1.0-test.2` | `0.1.0.dev2` |
| `v1.0.0-test.3` | `1.0.0.dev3` |

Each test iteration requires a unique `N` — TestPyPI does not allow re-uploading the
same version.

### Invalid tags

The following tag formats are **rejected** — no publishing occurs:

| Tag | Reason |
|---|---|
| `v0.1` | Missing patch segment |
| `v0.1.0-test` | Unnumbered test suffix |
| `v0.1.0-test.0` | Test iteration must be ≥ 1 |
| `v0.1.0-test.foo` | Non-numeric iteration |
| `v0.1.0-debug` | Unknown suffix |
| `release-0.1.0` | Wrong prefix |

---

## Workflow: `publish-pypi.yml`

The workflow file is `.github/workflows/publish-pypi.yml`.

### Job structure

```
Tag Push (v*)
    |
    classify ── validates tag, outputs: kind=production|test|invalid, version=x.y.z
    |
    build ── checkout, (inject version if test), uv build, twine check, smoke test
    |
    +------ publish-pypi    (if kind == production) → environment: pypi
    |
    +------ publish-testpypi (if kind == test)      → environment: testpypi
```

### Key properties

- `id-token: write` is granted **only** to publishing jobs, not to build or test jobs.
- Both publishing jobs have an explicit guard step that verifies the classification
  before requesting OIDC credentials.
- The workflow uses `concurrency` to prevent duplicate uploads for the same tag.
- The build job verifies the wheel version matches the tag before uploading.
- Invalid tags fail at the `classify` job without reaching publishing.

---

## Setting Up Trusted Publishing

Before publishing can succeed you must register a Trusted Publisher on each index.

### Required accounts

- A PyPI account at https://pypi.org/ with owner or maintainer access to the
  `rendereye-mcp` project.
- A TestPyPI account at https://test.pypi.org/ (separate from PyPI).

### GitHub Environment setup

Create two GitHub Environments in the repository settings
(**Settings → Environments**):

| Environment | Recommended protection rules |
|---|---|
| `pypi` | Require manual approval; restrict to production-tag branches/refs |
| `testpypi` | No required approval (or auto-approve for maintainers) |

### Trusted Publisher registration

Register a Trusted Publisher on each index. Use these exact values:

| Field | PyPI | TestPyPI |
|---|---|---|
| Repository owner | `taqu` | `taqu` |
| Repository name | `RenderEyeMCP` | `RenderEyeMCP` |
| Workflow filename | `publish-pypi.yml` | `publish-pypi.yml` |
| Environment name | `pypi` | `testpypi` |

**PyPI**: https://pypi.org/manage/account/publishing/

**TestPyPI**: https://test.pypi.org/manage/account/publishing/

If the `rendereye-mcp` project does not yet exist on an index, register a
**Pending Publisher** using the same fields above. The project is created
automatically on first upload.

---

## Publishing a Test Release

Use test releases to validate the packaging pipeline before the first official release.

### Step 1 — Create and push a test tag

```bash
# First time
git tag v1.0.0-test.1
git push origin v1.0.0-test.1

# If you need to republish after a fix (use a higher N)
git tag v1.0.0-test.2
git push origin v1.0.0-test.2
```

### Step 2 — Monitor the workflow

Open the **Actions** tab in the repository. The `Publish to PyPI` workflow runs:

1. `Classify Tag` — verifies the tag format, outputs `kind=test`
2. `Build Distributions` — injects version `1.0.0.dev1`, builds wheel and sdist, runs smoke test
3. `Publish to TestPyPI` — authenticates via OIDC, uploads to TestPyPI

### Step 3 — Verify on TestPyPI

The published package appears at:

```
https://test.pypi.org/project/rendereye-mcp/1.0.0.dev1/
```

### Step 4 — Install from TestPyPI

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "rendereye-mcp==1.0.0.dev1"
```

**Note**: Using `--extra-index-url` with PyPI allows pip to resolve dependencies that
are not mirrored on TestPyPI. Be aware that this means dependencies are resolved from
production PyPI, not TestPyPI. Verify that all expected dependencies install correctly.

### Step 5 — Smoke test the installed package

```bash
python -c "import rendereye_mcp; print(rendereye_mcp.__version__)"
rendereye-mcp --help
```

Expected output: version `1.0.0.dev1` and the help text for the MCP server.

---

## Publishing an Official Release

### Prerequisites

1. The `rendereye-mcp` project exists on PyPI (or a Pending Publisher is registered).
2. The `pypi` GitHub Environment exists with appropriate protection rules.
3. Version in `pyproject.toml`, `src/rendereye_mcp/__init__.py`, and
   `extensions/rendereye/extension.json` all match the intended release version.
4. All tests pass on `main`.

### Step 1 — Update the version in source

Edit these three files and set the same version string:

- `pyproject.toml` → `version = "1.0.0"`
- `src/rendereye_mcp/__init__.py` → `__version__ = "1.0.0"`
- `extensions/rendereye/extension.json` → `"version": "1.0.0"`

Commit and push to `main`. CI validates consistency via `validate_release.py --check-versions`.

### Step 2 — Create and push the production tag

```bash
git tag v1.0.0
git push origin v1.0.0
```

⚠️ **PyPI does not allow replacing a distribution once published.** Double-check the
version before pushing the tag. You cannot re-upload `rendereye_mcp-1.0.0-py3-none-any.whl`
if it already exists on PyPI.

### Step 3 — Approve the release (if required)

If the `pypi` GitHub Environment requires manual approval, a maintainer must approve
the `Publish to PyPI` job in the Actions UI before the upload proceeds.

### Step 4 — Verify on PyPI

```
https://pypi.org/project/rendereye-mcp/1.0.0/
```

```bash
python -m pip install "rendereye-mcp==1.0.0"
python -c "import rendereye_mcp; print(rendereye_mcp.__version__)"
```

---

## Security Notes

- `id-token: write` is granted only to `publish-pypi` and `publish-testpypi` jobs.
  The `classify` and `build` jobs do not receive OIDC permissions.
- Each publishing job has an explicit guard step that re-checks the tag classification
  before publishing, providing defense in depth.
- No long-lived PyPI tokens are stored as GitHub Secrets.
- A mismatch between the GitHub Environment name and the registered Trusted Publisher
  causes OIDC authentication to fail — misconfiguration cannot silently publish to the
  wrong index.
- Concurrency is set to `cancel-in-progress: false` to avoid partial uploads.

---

## Troubleshooting

### Trusted Publisher not configured

**Symptom**: `403 Forbidden` during upload or OIDC token exchange failure.

**Fix**: Ensure the Trusted Publisher is registered on the index with the exact
repository owner (`taqu`), repository name (`RenderEyeMCP`), workflow filename
(`publish-pypi.yml`), and environment name (`pypi` or `testpypi`).

### Wrong environment name

**Symptom**: OIDC authentication fails even though the publisher is registered.

**Fix**: Verify the GitHub Environment name in the workflow (`environment: pypi` or
`environment: testpypi`) matches exactly what is registered on the index.

### Duplicate distribution version

**Symptom**: `400 File already exists` during upload.

**Fix**: Use a higher test iteration number (e.g., `v1.0.0-test.2` instead of
`v1.0.0-test.1`). For production, you cannot re-publish the same version — increment
the patch version.

### Invalid package metadata

**Symptom**: `twine check` fails during the build job.

**Fix**: Check `pyproject.toml` for missing required fields (`description`, `authors`,
`license`, etc.) and ensure the version string is PEP 440-compliant.

### Version mismatch between tag and source

**Symptom**: The build job fails with "Version mismatch" for a production tag.

**Fix**: Update `pyproject.toml`, `__init__.py`, and `extension.json` to match the
production tag version before pushing the tag.

### Wheel installation failure

**Symptom**: The smoke-test step in the build job fails.

**Fix**: Check that all runtime dependencies in `pyproject.toml` are available on
PyPI and that `src/rendereye_mcp/__main__.py` exports `main`.

### Dependency resolution on TestPyPI

**Symptom**: `pip install` from TestPyPI fails because a dependency is not mirrored.

**Fix**: Add `--extra-index-url https://pypi.org/simple/` as shown above. If a
dependency is too new for TestPyPI to have it, pin older compatible versions for the
test install.

---

## What Has and Has Not Been Tested

| Item | Status |
|---|---|
| Tag classification logic | ✅ Tested (59 unit tests) |
| Version normalization | ✅ Tested (PEP 440 validation) |
| Destination isolation | ✅ Tested (production/test/invalid cannot cross) |
| Wheel build and smoke test | ✅ Tested locally via `uv build` |
| `twine check` metadata validation | ✅ Passes locally |
| OIDC Trusted Publisher registration | ⏳ Pending external setup (PyPI + TestPyPI accounts) |
| Actual TestPyPI upload | ⏳ Pending Trusted Publisher registration |
| Actual PyPI upload | ⏳ Pending TestPyPI validation and explicit authorization |
| Post-upload installation from TestPyPI | ⏳ Pending upload |

The end-to-end publishing flow is **not verified** until a real TestPyPI upload
succeeds. OIDC authentication cannot be fully tested without contacting the index.
