# Phase 5.6 verification report

Status: **partially verified**. The extension loads in the real GUI and its
lifecycle/IPC smoke checks pass. Real capture replay remains an outstanding release
gate. No GitHub Release was published.

## Root causes and corrections

The old parameterless register function could not accept RenderDoc's version and
CaptureContext arguments, so its loader would raise TypeError before starting IPC.
The audit also found invented context constructors and module-level capture APIs,
wrong LoadCapture arguments, GUI reads from polling workers, GUI command calls
from IPC workers, an ignored metadata minimum-version key, stale offline state,
and a wheel resource copy containing the same defects.

The corrected runtime receives the real context, validates required capabilities,
dispatches initial and periodic state reads and GUI commands through MiniQt,
and performs socket writes only on the IPC worker. Shutdown cancels queued work,
stops and joins workers, closes connections, and clears context references.
Thread-start failures are reversible. Re-registration first closes the old runtime;
RenderDoc's package-relative module reload mechanism can now reload sibling files.
No persistent CaptureViewer/menu callbacks are registered. Polling uses actual
CaptureContext state and has the sampling limitations described in integration docs.

Real testing exposed a further issue: registration and MiniQt callbacks must not
be assumed to share a Python thread. Ownership is now established inside the first
dispatched callback, with a regression test covering registration from another
thread. Root logging configuration and sys.path mutation were also removed.

The metadata uses `extension_api: 1`, `minimum_renderdoc: 1.46`, and version 1.0.0.
The minimum intentionally restricts the release to the audited API baseline.

## Official evidence and API audit

All current API decisions use the installed release's **v1.46** source. Earlier
v1.x documentation and v1.43 source were consulted only for orientation.
The [integration document](renderdoc_integration.md) links the exact official
tutorial, manifest specification, Python loader, CaptureContext/MainWindow and
MiniQt/ExtensionManager definitions. The [compatibility matrix](renderdoc_api_compatibility.md)
records each API's evidence and verification limits.

Unsupported `renderdoc.CaptureContext()`, module-level `qrenderdoc.LoadCapture`,
`qrenderdoc.CurCaptureFilename`, and speculative version properties were removed.
Capture commands use the supplied context and full documented arguments.
PromptCloseCapture preserves RenderDoc's save/cancel workflow. A void LoadCapture
return is never treated as proof of success; resulting state is checked.
MCP APIs, protocol version, Capture Registry, and Session Manager were preserved.

## Files changed

- All five existing extension modules/metadata, plus new `gui_dispatcher.py`;
  matching `_extension_data` resources (entry point named `rendereye_init.py`).
- Extension context/observer tests, new lifecycle and packaged artifact tests,
  packaging metadata/dispatcher checks, and the server subprocess stdin fixture.
- `scripts/install_extension.py` Linux path handling, release package completeness
  and audit-document inclusion, and `scripts/validate_renderdoc_extension.py`.
- README, architecture, development, installation/manual, troubleshooting,
  integration, compatibility matrix, and this report.

## Automated and packaged checks

Commands are run from the repository root using the existing virtual environment:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check extensions/rendereye tests/extensions scripts/validate_renderdoc_extension.py scripts/install_extension.py
uv build --wheel --no-sources
uv build --sdist --no-sources --out-dir dist/phase56-packages
.venv/Scripts/python.exe scripts/create_release_package.py --output-dir dist/phase56-packages
.venv/Scripts/python.exe scripts/build_release.py --create-archives --version 1.0.0 --output-dir dist/phase56-packages
Copy-Item dist/rendereye_mcp-1.0.0-py3-none-any.whl dist/phase56-packages/
.venv/Scripts/python.exe scripts/generate_checksums.py --dir dist/phase56-packages --output dist/phase56-packages/SHA256SUMS.txt
.venv/Scripts/python.exe scripts/validate_release.py --check-versions --artifacts-dir dist/phase56-packages --version 1.0.0
.venv/Scripts/python.exe scripts/validate_renderdoc_extension.py --renderdoc D:/Programs/RenderDoc/qrenderdoc.exe
```

Final outcomes: **478 passed in 17.80 seconds, no warnings**. Scoped Ruff checks
and `git diff --check` pass. Wheel, sdist, both ZIP archives, version checks, and
SHA-256 manifest validation pass. The final reproducible GUI harness exits 0,
with `summary.json` reporting `passed: true`, two reconnected instances, and a
maximum of two active connections. Final owned GUI process IDs were 8748 and
18672; both exited 0. Their four load results were empty error strings and their
worker lists were empty after unregister. No simulated result is counted as a
real capture replay result.

Unit coverage
includes the two-argument contract, missing context/API, construction/startup
failure, repeated register/unregister, partial startup cleanup, late callback
cancellation, offline state caching, queue-only GUI updates, worker shutdown,
Python 3.6 syntax, and source/wheel resource parity.

Artifact tests unpack the actual wheel and extension ZIP. A fresh Python process
runs with `-I -S` from a temporary directory, installs wheel resources through setup
or imports the manually extracted ZIP, and registers/unregisters three times.
It cannot access development site-packages, uv, or repository-relative imports.
Those tests simulate the GUI contract; real GUI checks are separately described.

## Real RenderDoc observations

Executable `D:\Programs\RenderDoc\qrenderdoc.exe`, file version **1.46.0.0**.
The embedded interpreter reported **Python 3.8.20**. Two owned hidden GUI processes
were used; no unrelated process or user-created window was closed. A unique test
extension name avoided overwriting the user's existing rendereye extension.
Only the unique test install was removed after each run. No capture was deleted.

Observed successful runs loaded the wheel-installed extension four times in each
GUI with empty LoadExtension error strings. Context type was
`qrenderdoc.CaptureContext`. Each GUI retained exactly one observer and one IPC
worker; explicit unregister left no extension workers. Both connected through the
real IPCTransport/ExtensionConnectionManager with authentication and distinct IDs.
State requests returned `unloaded`; unsupported focus commands returned
`unsupported`, with no cross-thread error. Closing the listener and its accepted
connections, rotating the token, and starting a new listener produced a new
connection for both final instance IDs and fresh revision-1 idle snapshots.
At most two active connections were observed. Both owned GUIs exited normally.

The reproducible harness stores per-process GUI reports, IPC observations, request
results and a summary under `dist/phase56-real/`. Its PySide usage is limited to
closing the owned test window; the production extension does not require PySide.
This exercises real IPC transport requests, not a separate MCP client session.
Existing MCP regression tests cover the preserved server-facing interfaces.

## Remaining issues and release readiness

The checkout has no `tests/TestProject` and no `.rdc` fixtures. Real open, capture
A/B replacement, close/save/cancel, loading transitions, and failed replay have
therefore **not** been verified. Strict fake contexts verify API arguments and
state logic, but cannot establish driver/replay compatibility. This is the
outstanding integration release gate; hold a fully verified release claim until
compatible real captures pass those scenarios. Linux GUI behavior and other
RenderDoc releases remain unverified. Polling can miss states shorter than 250 ms.

The registration incompatibility is fixed and real idle lifecycle/IPC behavior is
verified. These results do not establish full capture workflow readiness.

During validation, two harness-only setup failures were corrected (an invalid
zero port passed to Config, and indentation in a generated startup script).
The final harness validates generated Python before launching, cleans partial
startup, and checks its results rather than treating process startup as success.
The first artifact validation correctly rejected an incomplete local artifact set;
adding the sdist and checksum manifest produced a complete passing set. Early
packaged subprocess decoding warnings were removed by capturing raw bytes.
