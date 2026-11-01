[English](publishing.md) | [日本語](../ja/publishing.md)

# Release Guide

This page describes how to build, validate, and publish a RenderEyeMCP release.

- [Supported platforms](#supported-platforms)
- [Archive naming](#archive-naming)
- [How the release workflow works](#how-the-release-workflow-works)
- [Validate before publishing (dry run)](#validate-before-publishing-dry-run)
- [Publish a release](#publish-a-release)
- [Portable installation](#portable-installation)
- [Required extension setup](#required-extension-setup)
- [Troubleshooting](#troubleshooting)

## Supported platforms

| Platform | Archive | Go binary | Installer |
|----------|---------|-----------|-----------|
| Windows x64 | `.zip` | `rendereye-mcp.exe` | `install.ps1` |
| Linux x64 | `.tar.gz` | `rendereye-mcp` | `install.sh` |

RenderDoc runs on Windows and Linux. macOS is not a supported target because
RenderDoc does not have a macOS release.

## Archive naming

```text
RenderEyeMCP-v1.0.0-windows-amd64.zip
RenderEyeMCP-v1.0.0-linux-amd64.tar.gz
checksums.txt
```

The version comes from the git tag (e.g. `v1.0.0` → `1.0.0`).
Pre-release tags such as `v1.1.0-beta.1` are marked as prereleases on GitHub.

## How the release workflow works

The workflow in `.github/workflows/release.yml` has four sequential jobs:

| Job | What it does |
|-----|-------------|
| `test` | Runs `go test ./...` and `go vet ./...` |
| `build` | Builds the binary, assembles the archive, verifies contents, creates checksum |
| `checksums` | Combines per-platform `.sha256` files into a single `checksums.txt` |
| `publish` | Creates the GitHub Release and uploads all archives — **tag pushes only** |

The `publish` job is skipped on manual `workflow_dispatch` runs.
Archives are still uploaded as workflow artifacts, which you can download and inspect.

## Validate before publishing (dry run)

To test the full build and packaging pipeline without creating a GitHub Release:

1. Go to **Actions → Release** on GitHub.
2. Click **Run workflow**.
3. Choose the branch to test from.
4. Click **Run workflow**.

The workflow runs all jobs except `publish`. Download the generated archives from the
**Artifacts** section of the completed run and verify them locally:

```bash
# Extract and inspect Linux archive
tar -tzf RenderEyeMCP-dev-*-linux-amd64.tar.gz
```

```powershell
# Extract and inspect Windows archive
Expand-Archive RenderEyeMCP-dev-*-windows-amd64.zip -DestinationPath test-extract\
Get-ChildItem test-extract\ -Recurse
```

## Publish a release

1. Ensure `extensions/rendereye/extension.json` contains the correct version.

2. Create and push a tag:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. The `Release` workflow triggers automatically. Monitor it on the **Actions** tab.

4. When the workflow completes, the GitHub Release is published with:
   - `RenderEyeMCP-v1.0.0-windows-amd64.zip`
   - `RenderEyeMCP-v1.0.0-linux-amd64.tar.gz`
   - `checksums.txt`

To publish a pre-release, use a tag with a hyphen-separated identifier,
for example `v1.1.0-rc.1`. The release is automatically flagged as a pre-release.

## Portable installation

Each archive is self-contained and installs from the extracted directory.
The binary is never copied to a system path — users configure their coding agent to
point directly to the extracted `rendereye-mcp.exe` (or `rendereye-mcp`).

**Windows archive layout:**

```text
RenderEyeMCP-v1.0.0-windows-amd64/
├── rendereye-mcp.exe
├── install.ps1          ← run this from the extracted directory
├── extensions/          ← installed to %APPDATA%\qrenderdoc\extensions\rendereye\
│   ├── __init__.py
│   ├── extension.json
│   └── ...
├── README.md
└── LICENSE
```

**Linux archive layout:**

```text
RenderEyeMCP-v1.0.0-linux-amd64/
├── rendereye-mcp
├── install.sh           ← run this from the extracted directory
├── extension/           ← installed to ~/.local/share/qrenderdoc/extensions/rendereye/
│   ├── __init__.py
│   ├── extension.json
│   └── ...
├── README.md
└── LICENSE
```

Both installers require the archive to be fully extracted before running.
Do not run `install.ps1` or `install.sh` from a different directory.

See [Installation](installation.md) for end-user instructions.

## Required extension setup

The RenderDoc Python Extension (`extensions/rendereye/`) is included in every archive.
It must be installed into RenderDoc's per-user extension directory by running the
installer script.

The extension is written in Python and uses RenderDoc's embedded Python interpreter.
End users do not need to install Python separately.

After installing the extension, users must enable it once in RenderDoc:
**Tools → Manage Extensions → RenderEyeMCP → Always Load**.

## Troubleshooting

**Build fails with `go: toolchain constraint`**

The `go.mod` file specifies a minimum Go version. Ensure the runner's Go version
satisfies that constraint. The workflow uses `go-version-file: go.mod` to pick
the correct version automatically.

**`extensions/__init__.py` or `extension/extension.json` missing from archive**

Verify that `extensions/rendereye/` exists in the repository root and contains the
expected files. The workflow copies this directory into the archive during assembly.

**Checksum verification fails**

The checksum file uses the archive filename as produced on the build runner.
Verify using the original, unmodified filename.

**Release already exists**

The `publish` job checks that no release exists for the tag before creating one.
To republish, delete the existing release on GitHub before re-running the workflow.
