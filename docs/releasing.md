# RenderEyeMCP — Release Guide

## Prerequisites

- Git access to the repository with permission to push tags
- All CI checks passing on the target commit
- Version updated in source (see [Versioning Policy](#versioning-policy))

## Versioning Policy

All three version strings must match before a release:

| Location | Format |
|---|---|
| `src/rendereye_mcp/__init__.py` | `__version__ = "1.0.0"` |
| `pyproject.toml` | `version = "1.0.0"` |
| `extensions/rendereye/extension.json` | `"version": "1.0.0"` |

Versions follow [Semantic Versioning](https://semver.org/):

- `MAJOR` — breaking changes
- `MINOR` — new features, backward-compatible
- `PATCH` — bug fixes

Pre-release versions use a hyphen suffix: `1.1.0-rc.1`, `1.1.0-beta.1`.

Validate version consistency at any time:

```bash
python scripts/validate_release.py --check-versions
```

## Tag Conventions

Tags must use the `v` prefix followed by the semantic version:

```
v1.0.0
v1.0.1
v1.1.0
v1.1.0-rc.1
```

Tags without the `v` prefix are not recognized by the release workflow.

## CI Requirements

Before tagging a release, confirm that CI passes on the target commit:

- All unit tests pass on Windows and Linux
- All lint checks pass
- Package builds successfully
- Installation without `uv` succeeds

## Release Dry Run

Validate the release pipeline without publishing:

1. Open **Actions → Release** in the GitHub repository.
2. Click **Run workflow**.
3. Set `publish` to `false` (the default).
4. Click **Run workflow**.

The workflow will:
- Validate version consistency
- Run the full test suite
- Build wheel, sdist, and release archives
- Validate all artifacts
- Generate checksums
- Upload workflow artifacts (visible in the Actions run summary)

No GitHub Release will be created.

Download and inspect artifacts from the workflow run to verify the release package.

## Release Publication Procedure

### Step 1 — Update Version

Edit all three version strings to the target version:

```bash
# src/rendereye_mcp/__init__.py
__version__ = "1.1.0"

# pyproject.toml
version = "1.1.0"

# extensions/rendereye/extension.json
"version": "1.1.0"
```

### Step 2 — Update CHANGELOG

Add an entry to `CHANGELOG.md` describing the release.

### Step 3 — Commit and Push

```bash
git add src/rendereye_mcp/__init__.py pyproject.toml extensions/rendereye/extension.json CHANGELOG.md
git commit -m "Release v1.1.0"
git push origin main
```

Wait for CI to pass on `main`.

### Step 4 — Create and Push the Tag

```bash
git tag v1.1.0
git push origin v1.1.0
```

This triggers the release workflow automatically.

### Step 5 — Monitor the Release Workflow

Open **Actions → Release** and follow the run.

If any job fails, no release will be published. Fix the issue, delete the tag, re-tag, and push again.

### Step 6 — Verify the Published Release

After the workflow completes:

1. Open **Releases** in the GitHub repository.
2. Confirm the correct assets are attached.
3. Download `SHA256SUMS.txt` and verify at least one artifact.

```bash
sha256sum -c SHA256SUMS.txt
```

## Artifact Verification

Verify checksums after downloading:

```bash
# Linux / macOS
sha256sum -c SHA256SUMS.txt

# Windows (PowerShell)
Get-FileHash *.whl, *.tar.gz, *.zip | Format-List
```

Compare against the values in `SHA256SUMS.txt`.

## Rollback and Recovery

### Failed Release Build

If the workflow fails before the release is published:

- No release exists — simply fix the issue, delete the tag, and re-tag.

```bash
git tag -d v1.1.0
git push origin :refs/tags/v1.1.0
# fix the issue
git tag v1.1.0
git push origin v1.1.0
```

### Failed Partial Publication

If the release was created but not all assets were uploaded:

1. Delete the release from the GitHub Releases page.
2. Delete the tag locally and remotely (see above).
3. Re-tag and push.

The release workflow will not overwrite an existing release — it will fail with a diagnostic message if a release for that tag already exists.

### Hotfix Release

For a patch release on an older minor version:

1. Create a branch from the release tag: `git checkout -b hotfix/1.0.1 v1.0.0`
2. Apply the fix.
3. Update version strings to `1.0.1`.
4. Commit, push the branch, and tag it: `git tag v1.0.1 && git push origin v1.0.1`.

## Release Security

- CI jobs use read-only permissions (`contents: read`).
- Only the publishing job uses `contents: write`.
- The workflow uses the automatically provided `GITHUB_TOKEN` — no personal access token is required.
- Secrets are never printed or stored in artifacts.
- Release assets are built by the same workflow run that publishes them.

## Running CI Checks Locally

```bash
# Tests (all platforms)
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Build distributions
uv build

# Validate with twine
uvx twine check dist/*.whl dist/*.tar.gz

# Version consistency
python scripts/validate_release.py --check-versions

# Assemble release package
python scripts/create_release_package.py

# Create archives
python scripts/build_release.py --create-archives --version 1.0.0

# Generate checksums
python scripts/generate_checksums.py dist/*.whl dist/*.tar.gz dist/packages/*.zip --output dist/packages/SHA256SUMS.txt
```

## Release checklist

Complete every item before pushing a release tag. Record results in
[release_testing.md](release_testing.md) and update [release_readiness.md](release_readiness.md).

- [ ] Version identical in `pyproject.toml`, `src/rendereye_mcp/__init__.py`,
      `extensions/rendereye/extension.json` and `_extension_data/extension.json`
      (`scripts/validate_release.py --check-versions`).
- [ ] `CHANGELOG.md` entry dated; `docs/release_notes_v<version>.md` no longer marked draft.
- [ ] CI green on `main` (Windows + Ubuntu, Python 3.11/3.12): tests, ruff, docs check,
      build, clean install.
- [ ] Release workflow dry run (`workflow_dispatch`, `publish: false`) green.
- [ ] Clean Windows VM: install from `RenderEyeMCP-v<version>.zip`, `setup`, enable the
      extension, `setup-agent claude-code` and `codex`, `doctor` clean.
- [ ] Live quick start on that VM with RenderDoc 1.46: select draw calls **by clicking in
      the GUI**; `get_selected_event` matches every time.
- [ ] Live scenarios A–F against at least one capture; note the graphics API.
- [ ] Two agents connected at the same time return consistent results.
- [ ] README and docs claims still match `docs/release_readiness.md`;
      `scripts/check_docs.py` passes.
- [ ] No proprietary capture data, paths or names in docs, examples or test fixtures.
- [ ] Tag `v<version>` pushed only after all of the above.

## Known Limitations

- macOS is not an official release target. RenderDoc GUI integration is not supported on macOS.
- GPU frame capture tests require a real RenderDoc installation and are excluded from standard CI.
- Unity integration tests require a licensed Unity project and are not run in automated CI.
- GitHub-hosted runners do not have RenderDoc installed; tests that require it must run on a dedicated runner.
