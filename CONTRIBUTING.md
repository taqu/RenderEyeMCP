# Contributing to RenderEyeMCP

Thanks for helping. Issues and pull requests are welcome in English or Japanese.

## Development setup

```powershell
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
uv sync                      # Python 3.11+ and dev dependencies
uv run rendereye-mcp --help
```

More detail (project layout, running the service, installing the extension from source):
[docs/development.md](docs/development.md). Architecture:
[docs/en/architecture.md](docs/en/architecture.md).

## Checks to run before a pull request

```powershell
uv run pytest                          # unit tests
uv run ruff check src/ tests/          # lint (CI fails on any finding)
uv run python scripts/check_docs.py    # documentation links and EN/JA parity
```

CI runs the same checks on Windows and Ubuntu with Python 3.11 and 3.12, builds the
wheel and installs it into a clean virtual environment.

Tests that need RenderDoc's `renderdoc` Python module are skipped outside RenderDoc.
If you change code that talks to RenderDoc (`src/rendereye_mcp/_extension_data/`),
also check it against a real RenderDoc 1.46 GUI and say in the pull request what you
ran. `docs/renderdoc_api_compatibility.md` lists what has been verified.

## Guidelines

- Keep pull requests focused; one topic per PR.
- `extensions/rendereye/` and `src/rendereye_mcp/_extension_data/` must stay identical.
- The extension runs in RenderDoc's embedded Python: standard library only, and no
  syntax newer than Python 3.6 (the extension's compatibility target).
- Inspection tools must stay read-only: never change the user's selected event or
  loaded capture.
- User-facing documentation exists in English (`docs/en/`) and Japanese (`docs/ja/`).
  Update both, or note in the PR that a translation is needed.
- Do not attach proprietary captures, screenshots or logs to issues or PRs without
  permission.

## Reporting bugs

Use the bug report template. Include the RenderDoc version, the graphics API of the
capture, the coding agent, and `rendereye-mcp doctor` output. Security problems:
see [SECURITY.md](SECURITY.md).
