# Fix GitHub Actions Release Archive and SHA-256 Checksum Generation

## Objective

Fix the release workflow failure in `.github/workflows/release.yml`.

The Windows AMD64 release job fails during SHA-256 checksum generation:

```text
Run NAME="RenderEyeMCP-v0.9.0-windows-amd64"
  NAME="RenderEyeMCP-v0.9.0-windows-amd64"
  FILE="${NAME}.zip"
  sha256sum "${FILE}" > "${NAME}.sha256"
  cat "${NAME}.sha256"

sha256sum: RenderEyeMCP-v0.9.0-windows-amd64.zip:
No such file or directory

Error: Process completed with exit code 1.
```

The checksum step assumes the archive exists in the current working directory, but the file cannot be found.

**Investigate and fix the underlying release artifact path or packaging problem rather than suppressing the checksum error.**

## 1. Inspect the Release Workflow

Review the complete `.github/workflows/release.yml`, focusing on:

- Go binary compilation.
- Windows release staging.
- ZIP archive creation.
- Archive naming.
- Working directories.
- Artifact upload and download.
- SHA-256 checksum generation.
- GitHub Release publishing.

Trace the expected archive:

```text
RenderEyeMCP-v0.9.0-windows-amd64.zip
```

from its creation through checksum generation and publication.

Determine where the archive is actually created and whether its name matches the checksum step.

Do not assume the archive creation succeeded merely because the preceding step completed.

## 2. Identify the Root Cause

Check for the following possibilities:

1. The ZIP file is created in a different directory.
2. The packaging step produces a different filename.
3. The archive is created using an incorrect relative path.
4. The Windows runner uses a different working directory than expected.
5. The archive was uploaded as a GitHub Actions artifact but not downloaded into the checksum job.
6. The ZIP creation step silently skipped the expected output.
7. The checksum step is executed before the archive becomes available.
8. A build matrix or job output contains inconsistent artifact names.

Use the actual workflow and logs to identify the cause.

Do not introduce a workaround without understanding the artifact lifecycle.

## 3. Establish a Consistent Release Output Directory

Prefer a single, predictable output directory for release archives.

For example:

```text
dist/
├── RenderEyeMCP-v0.9.0-windows-amd64.zip
├── RenderEyeMCP-v0.9.0-windows-amd64.sha256
└── ...
```

The packaging and checksum steps must reference the same directory.

For example, if the archive is stored under `dist/`:

```bash
NAME="RenderEyeMCP-${VERSION}-windows-amd64"
FILE="dist/${NAME}.zip"

test -f "$FILE" || {
    echo "Release archive not found: $FILE" >&2
    exit 1
}

sha256sum "$FILE" > "dist/${NAME}.sha256"
```

This is an illustrative implementation.

Adapt it to the actual directory structure and GitHub Actions shell configuration.

Avoid mixing paths relative to the repository root with paths relative to temporary staging directories.

## 4. Verify Archive Creation

Ensure the Windows release archive is actually generated before checksum calculation.

The archive must contain:

- `rendereye-mcp.exe`
- Required installation scripts.
- RenderDoc Python Extension.
- README.md.
- LICENSE, if present.

Ensure the executable and installer are placed in the expected relative locations.

The Windows portable installer must still be able to locate `rendereye-mcp.exe` in the extracted archive.

Do not change the established portable distribution design.

## 5. Handle GitHub Actions Job Boundaries

If packaging and checksum generation execute in separate jobs, ensure the archive is explicitly transferred between them.

Use the existing artifact upload/download mechanism.

For example:

- Build job creates the archive.
- Build job uploads the archive as a workflow artifact.
- Release job downloads the archive.
- Release job verifies the downloaded file exists.
- Release job generates or validates its checksum.
- Release job publishes the verified files.

Do not rely on files created in another job being available automatically.

If the workflow uses a build matrix, ensure artifact names are unique per platform.

Avoid unnecessary transfers when packaging and checksums can safely be generated in the same job.

## 6. Make Checksum Generation Reliable

Generate checksums only after confirming that the final release archives exist.

Requirements:

- Fail clearly if an archive is missing.
- Use the actual archive filename.
- Use consistent relative paths.
- Avoid hardcoded version strings.
- Preserve the existing version-tag convention.
- Ensure generated `.sha256` files reference the corresponding archive filename.
- Do not generate checksums from temporary or intermediate files.

If a separate checksum file is generated for each archive, ensure it is valid when verified from the directory containing that archive.

For example:

```bash
cd dist

sha256sum "RenderEyeMCP-v0.9.0-windows-amd64.zip" \
    > "RenderEyeMCP-v0.9.0-windows-amd64.sha256"

sha256sum -c "RenderEyeMCP-v0.9.0-windows-amd64.sha256"
```

Use the dynamically determined release version in the actual workflow.

## 7. Improve Release Diagnostics

Add concise diagnostics near the packaging and checksum steps.

For example:

```bash
pwd
ls -lah
ls -lah dist/ || true
```

Use these diagnostics to verify the output paths.

Do not use `continue-on-error` for packaging or checksum failures.

Required release files must be present before GitHub Release publishing begins.

Prefer clear error messages identifying the missing file and expected location.

Avoid excessive debug output in normal successful builds.

## 8. Verify All Release Platforms

Although the reported failure occurs on Windows AMD64, inspect the corresponding Linux release workflow as well.

Ensure all platforms follow consistent rules for:

- Archive naming.
- Output directories.
- Artifact transfer.
- Checksum generation.
- Release publishing.

Do not duplicate a known path-handling bug across platform jobs.

Preserve the appropriate archive formats:

- Windows: `.zip`
- Linux: `.tar.gz`

Do not make unrelated platform or application changes.

## 9. Validation

Validate the corrected workflow as thoroughly as the available environment permits.

Required checks:

1. Go binaries compile successfully.
2. Windows ZIP archive is created.
3. The archive filename matches the checksum step.
4. The archive exists in the expected directory.
5. The ZIP contains the required distribution files.
6. SHA-256 checksum generation succeeds.
7. SHA-256 verification succeeds.
8. Linux archives follow the same reliable packaging conventions.
9. Artifact upload/download paths are correct.
10. The release publishing step references the generated archives.

Use the workflow's non-publishing manual validation mode, if available, to test the updated pipeline.

Do not create a release tag or publish a GitHub Release during this task.

## Acceptance Criteria

The fix is complete when:

- The root cause of the missing ZIP file is identified.
- Archive creation and checksum generation reference the correct file.
- The Windows AMD64 checksum step succeeds.
- Checksum verification passes.
- The final ZIP contains the required executable, scripts, and Extension.
- All existing supported platform jobs use consistent artifact handling.
- The workflow fails clearly if required output files are missing.
- No legacy Python release infrastructure is introduced.
- The portable Go installation model is preserved.

## Deliverables

- Corrected `.github/workflows/release.yml`.
- Any necessary minimal changes to packaging scripts.
- Clear explanation of the original failure.
- Validation results for archive creation and checksums.
- Summary of any remaining unverified GitHub Actions behavior.

## Constraints

- Do not modify Go application logic.
- Do not modify MCP Tool contracts.
- Do not modify the IPC protocol.
- Do not change RenderDoc Extension behavior.
- Do not suppress checksum errors.
- Do not create placeholder ZIP files.
- Do not publish a release.
- Do not perform unrelated refactoring.

## Execution Instructions

Inspect the existing workflow and trace the archive paths.

Identify the actual failure.

Implement the smallest reliable correction that makes release artifact handling consistent across all supported platforms.

Validate archive existence and checksum verification before considering the task complete.

**The goal is to ensure that release packaging, checksum generation, and publication all operate on the same verified archive files.**
