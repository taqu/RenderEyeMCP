# Contributing to RenderEyeMCP

Thanks for helping. Issues and pull requests are welcome in English or Japanese.

## Development setup

```bash
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
go build ./cmd/rendereye-mcp/
go test ./...
go vet ./...
```

Architecture overview: [docs/en/architecture.md](docs/en/architecture.md).

## Checks to run before a pull request

```bash
go test ./...
go vet ./...
```

CI runs `go test ./...` and `go vet ./...` on Ubuntu. It also builds Windows and Linux
binaries and assembles the release archives.

Tests that need RenderDoc's embedded Python API are skipped in CI.
If you change the RenderDoc extension (`extensions/rendereye/`), also test it against a
real RenderDoc 1.46 GUI and describe in the pull request what you ran.

## Guidelines

- Keep pull requests focused; one topic per PR.
- The extension (`extensions/rendereye/`) runs inside RenderDoc's embedded Python
  interpreter: standard library only, and no syntax newer than Python 3.6.
- Inspection tools must stay read-only: never change the user's selected event or
  loaded capture.
- User-facing documentation exists in English (`docs/en/`) and Japanese (`docs/ja/`).
  Update both, or note in the PR that a translation is needed.
- Do not attach proprietary captures, screenshots or logs to issues or PRs without
  permission.

## Reporting bugs

Use the bug report template. Include the RenderDoc version, the graphics API of the
capture, the coding agent, and `rendereye-mcp version` output. Security problems:
see [SECURITY.md](SECURITY.md).
