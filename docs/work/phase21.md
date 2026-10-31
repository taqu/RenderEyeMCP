# Phase 21 Addendum — Aggressive Legacy Python Cleanup

## Revised Cleanup Policy

The development work will be performed on a dedicated Git branch. The previous Python implementation remains available through Git history.

Therefore, do not preserve obsolete Python code, compatibility layers, tests, or documentation merely for historical reference.

**Aggressively remove all legacy Python MCP and Shared IPC infrastructure.**

The goal is a clean Go-based codebase, not a repository that maintains both implementations.

## Required Actions

1. Delete the complete legacy Python MCP Bridge implementation.
2. Delete the complete legacy Python Shared IPC Service implementation.
3. Delete obsolete Python IPC clients, adapters, serializers, and utilities that are not required by the RenderDoc Extension.
4. Delete tests that exclusively validate the removed Python infrastructure.
5. Delete Python-specific packaging files, dependency locks, installation scripts, and publishing workflows that are no longer necessary.
6. Delete obsolete compatibility layers, fallback implementations, and migration utilities.
7. Delete outdated Python server documentation rather than preserving it as legacy documentation.
8. Remove unused directories, imports, environment variables, configuration options, and CI/CD jobs.
9. Update README.md and active documentation to describe only the current Go implementation.
10. Simplify the repository structure wherever removal of the old infrastructure makes it possible.

Do not create a `legacy/`, `archive/`, or `deprecated/` directory to retain deleted code.

Do not leave commented-out Python implementations.

Do not introduce compatibility shims for removed Python server components.

## Explicitly Retained Components

Preserve only Python code that is still necessary for:

- The RenderDoc Python Extension.
- Communication between the Extension and the Go Shared IPC Service.
- RenderDoc API integration.
- Tests and development tooling for the retained Extension.

Remove unused Python tooling even if it was previously part of the development workflow.

Protocol fixtures should be retained only if actively used by the Go or Extension test suites.

## Validation

After cleanup:

- Run all Go tests.
- Run applicable RenderDoc Extension tests.
- Verify Go MCP Bridge and Go Shared IPC Service startup.
- Verify `collect_gpu_counters` and other supported operations.
- Verify multi-agent operation.
- Verify release packaging.
- Search the repository for obsolete Python server references.
- Confirm that no active runtime or build path depends on removed files.

Delete obsolete tests rather than rewriting them solely to preserve historical coverage. However, preserve or add Go tests where needed to protect current functionality.

## Git Policy

- Assume the developer has created the cleanup branch.
- Do not create or switch Git branches.
- Do not preserve dead code for rollback purposes.
- Do not create backup copies of deleted files.
- Use Git history as the source for any retired implementation.
- Do not modify unrelated user changes.
- Do not commit, push, tag, or publish unless explicitly requested.

## Completion Criteria

Phase 21 is complete when:

- The repository has one MCP Bridge implementation: Go.
- The repository has one Shared IPC Service implementation: Go.
- Python is used only for the RenderDoc Extension and its necessary tooling.
- All obsolete Python server code and dependencies have been deleted.
- All active documentation and release workflows describe the Go distribution.
- The retained functionality passes applicable regression tests.

**Prefer deleting obsolete code over maintaining unnecessary backward compatibility. Keep the working architecture intact, but remove the historical implementation completely.**
