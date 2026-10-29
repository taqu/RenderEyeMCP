# RenderEyeMCP — Phase 5.6 Implementation Instructions

## RenderDoc Extension API Compliance Audit & Fixes

## Objective

Perform a comprehensive API compliance audit of the RenderEyeMCP Python extension against the official RenderDoc documentation and the APIs supported by the installed RenderDoc version.

A potential incompatibility has already been identified in:

`extensions/rendereye/__init__.py`

The current implementation defines:

```python
def register():
    ...
```

However, the official RenderDoc UI Extension documentation specifies that RenderDoc invokes the registration function with two arguments:

```python
def register(version, pyrenderdoc):
    ...
```

Here:

- `version` is the RenderDoc major/minor version string.
- `pyrenderdoc` is the `qrenderdoc.CaptureContext` instance provided by RenderDoc.

This discrepancy may prevent the extension from loading correctly.

**Do not simply fix the registration signature. Audit the entire RenderDoc extension implementation for incorrect API assumptions, unsupported methods, lifecycle errors, and integration problems.**

Implement necessary corrections and verify the extension against a real RenderDoc installation wherever possible.

---

## 1. Environment

### Existing Project

Project: RenderEyeMCP

Relevant extension directory:

`extensions/rendereye/`

Expected Windows RenderDoc installation:

`C:\Program Files\RenderDoc\`

Unity integration test project:

`tests/TestProject`

Python environment management:

- `uv` is available for development.
- End-user runtime must not require `uv`.

### Supported Platforms

- Windows: Primary validation environment.
- Linux: Preserve compatibility with supported RenderDoc installations.
- macOS: No official native RenderDoc GUI integration target.

### Constraints

- Do not modify RenderDoc source code.
- Do not rebuild RenderDoc.
- Do not modify the production engine.
- Do not implement unrelated GPU analysis functionality.
- Do not replace the existing IPC architecture unnecessarily.
- Preserve existing MCP APIs.
- Preserve Capture Registry and Session Manager behavior.
- Do not terminate unrelated RenderDoc processes.
- Do not overwrite user-created `.rdc` captures.

---

## 2. Task A — Review Official RenderDoc Documentation

Before modifying implementation code, examine the official RenderDoc documentation.

### Primary References

RenderDoc Python API documentation:

https://github.com/baldurk/renderdoc/tree/v1.x/docs/python_api

UI Extension documentation:

https://github.com/baldurk/renderdoc/blob/v1.x/docs/python_api/ui_extensions.rst

Python extension implementation details:

https://github.com/baldurk/renderdoc/tree/v1.x/docs/how

RenderDoc source code:

https://github.com/baldurk/renderdoc

### Version-Specific Verification

The `v1.x` branch may differ from the installed RenderDoc release.

Determine the installed RenderDoc version before relying on a particular API.

Where possible:

1. Identify the installed release.
2. Locate corresponding documentation or source.
3. Inspect its Python extension implementation.
4. Verify registration and unregistration behavior.
5. Verify available `qrenderdoc` APIs.
6. Verify applicable thread-affinity requirements.

Use the source corresponding to the installed version as the primary compatibility reference.

Do not assume APIs available in the latest development branch exist in older releases.

### Deliverable

A list of documented APIs used by RenderEyeMCP, with compatibility evidence.

---

## 3. Task B — Audit Extension Entry Points

Inspect:

`extensions/rendereye/__init__.py`

### Registration Signature

Verify the required signature.

The expected documented interface is:

```python
def register(version, pyrenderdoc):
    ...
```

Determine exactly how RenderDoc invokes this function.

Correct the implementation if necessary.

### Registration Responsibilities

The registration function should:

1. Receive the RenderDoc version.
2. Receive the RenderDoc CaptureContext.
3. Validate required capabilities.
4. Initialize extension-owned state.
5. Register supported callbacks.
6. Initialize communication infrastructure.
7. Return control without blocking the GUI.

### CaptureContext

Do not create a new CaptureContext manually.

Use the context provided by RenderDoc.

If the implementation requires access to the context from other modules, pass it explicitly or store it in a carefully managed extension runtime object.

Avoid uncontrolled global state.

### Unregistration

Inspect the installed RenderDoc version's documented unregistration interface.

Implement the correct callback signature.

For RenderDoc versions where the documented callback is parameterless, the expected structure is:

```python
def unregister():
    ...
```

Verify rather than assume.

### Cleanup

Ensure unregistration:

- Stops extension-owned IPC activity.
- Releases registered observers.
- Releases supported menu or UI callbacks.
- Stops worker threads safely.
- Clears stale context references.
- Avoids accessing destroyed GUI objects.

### Reload Behavior

RenderDoc may reload Python extension modules without fully unloading their Python code.

The implementation must tolerate repeated registration and unregistration.

Do not create duplicate persistent callbacks or IPC workers after reload.

### Deliverable

Correct and lifecycle-safe extension entry points.

---

## 4. Task C — Audit extension.json

Inspect the actual extension metadata file.

Verify:

- Valid JSON syntax
- Required metadata fields
- Supported metadata schema
- Extension package name
- Extension version
- Minimum supported RenderDoc version, when applicable
- Extension discovery compatibility

Do not assume that generic Python packaging metadata is sufficient.

Compare the file against an extension generated by RenderDoc's own extension creation mechanism or an official example.

### Directory Layout

Verify that the packaged extension uses the correct layout.

Example:

```text
rendereye/
├── __init__.py
├── extension.json
├── ipc_client.py
├── gui_context.py
├── gui_dispatcher.py
└── state_observer.py
```

Adapt the example to the actual implementation.

### Installation Paths

Verify official user-level extension directories.

Windows candidate:

`%APPDATA%\qrenderdoc\extensions\`

Linux candidate:

`~/.local/share/qrenderdoc/extensions/`

Do not assume that the RenderDoc executable installation directory is also its extension directory.

### Deliverable

A correctly packaged, discoverable RenderDoc extension.

---

## 5. Task D — Audit All RenderDoc API Calls

Search the entire extension implementation for uses of:

- `renderdoc`
- `qrenderdoc`
- `pyrenderdoc`
- `CaptureContext`
- `CaptureViewer`
- `ExtensionManager`
- GUI callbacks
- Capture loading and unloading APIs
- Window-management APIs
- GUI-thread dispatch APIs
- Replay-related APIs

For every RenderDoc-specific call, verify:

1. The method or class actually exists.
2. Its signature is correct.
3. Its parameter types are correct.
4. Its return type is understood.
5. It is supported by the installed RenderDoc version.
6. It is invoked from an appropriate execution context.
7. The object remains valid during invocation.
8. Exceptions are handled appropriately.

### Avoid Speculative APIs

Do not assume that methods from previous implementation instructions actually exist.

Earlier roadmap documents may have described conceptual interfaces rather than verified RenderDoc API names.

Treat the installed API and official documentation as authoritative.

### Unsupported APIs

If an existing implementation calls an unsupported method:

- Identify the call site.
- Explain why it is incorrect.
- Find a supported equivalent where possible.
- Implement the correction.
- Add regression tests.

If no supported alternative exists, return an explicit unsupported result rather than silently pretending the operation succeeded.

### Deliverable

An API-compliant extension implementation with unsupported assumptions removed.

---

## 6. Task E — CaptureContext and Capture State

Verify that the extension uses RenderDoc's actual CaptureContext correctly.

### Required Capabilities

Investigate how to determine:

- Whether a capture is currently loaded
- The currently loaded capture path
- Whether the capture is loading
- Whether the capture has been closed
- Whether the capture has been replaced

Verify the exact available API methods.

### Capture Viewer Callbacks

Investigate RenderDoc's `CaptureViewer` interface.

Where supported, consider implementing a viewer object to receive capture-related callbacks.

The implementation must match the documented Python callback names and signatures.

Do not invent callback method names.

### Callback Registration

Verify how viewer objects are registered with the CaptureContext.

Maintain references to callback objects for as long as RenderDoc requires them.

Avoid allowing callback objects to be garbage-collected while still registered.

### Callback Removal

Remove viewers through the documented API when available.

Do not retain stale callback objects after extension unregistration.

### State Synchronization

Forward actual GUI state changes through the existing RenderEyeMCP IPC architecture.

Do not infer capture changes solely from filenames or window titles.

### Deliverable

Correct RenderDoc capture-state observation with verified callback behavior.

---

## 7. Task F — GUI Thread and IPC Safety

Audit the relationship between the extension's IPC workers and RenderDoc GUI operations.

### Requirements

- Do not execute GUI API calls directly from arbitrary IPC worker threads.
- Do not block RenderDoc's GUI thread on network reads.
- Use supported GUI-thread invocation mechanisms.
- Verify thread affinity for callbacks and GUI objects.
- Avoid deadlocks during extension shutdown.
- Avoid accessing invalid CaptureContext objects after unregister.
- Avoid invoking callbacks after the extension has been disabled.

### Dispatcher

Review the existing GUI dispatcher.

Verify the exact mechanism it uses.

If it relies on unsupported methods or unavailable Qt bindings, replace those assumptions with supported mechanisms.

Do not assume PySide is installed simply because RenderDoc uses Qt internally.

### IPC Lifecycle

Ensure that:

- Registration starts only one active IPC client per extension instance.
- Unregistration requests clean shutdown.
- Worker threads use bounded waits.
- Connections are released safely.
- Repeated extension reloads do not accumulate threads or sockets.

### Deliverable

GUI-safe IPC integration compatible with RenderDoc's supported execution model.

---

## 8. Task G — Extension Reload and Lifecycle Testing

Implement tests for repeated registration and unregistration.

### Required Tests

- Correct registration signature
- Correct unregistration signature
- Valid CaptureContext handling
- Initial registration
- Repeated registration
- Unregistration
- Register after unregister
- Registration failure
- Partial initialization failure
- Missing or unsupported API
- IPC startup failure
- IPC shutdown
- Worker thread cleanup
- Callback cleanup
- Extension reload

### Important Requirement

Unit tests must simulate RenderDoc invoking:

```python
register(version, pyrenderdoc)
```

with two arguments.

A test that directly invokes `register()` without arguments is insufficient.

### Mocking

Use a fake CaptureContext with the required supported methods.

Do not assume that importing the real `qrenderdoc` module works in an ordinary Python environment.

Keep tests independent of RenderDoc where possible.

### Deliverable

Automated regression tests covering the official extension lifecycle contract.

---

## 9. Task H — Verify Installation and Packaging

The extension must work when installed from the actual RenderEyeMCP release distribution.

### Required Checks

Verify:

- Python wheel package resources
- RenderDoc Extension ZIP contents
- Extension directory layout
- Extension metadata
- Required Python modules
- Internal imports
- Protocol version compatibility
- Installation scripts
- Manual copy installation
- `rendereye-mcp setup` installation

### Critical Requirement

Do not test only the source-tree extension.

Also test the extension copied from the packaged release artifact.

The installed extension must not depend on:

- Repository-relative Python imports
- Development virtual environments
- `uv`
- Missing external scripts
- Source checkout paths

### Deliverable

A packaged extension that behaves identically to the development version.

---

## 10. Task I — Real RenderDoc Validation

Use the actual installed RenderDoc application.

Preferred Windows location:

`C:\Program Files\RenderDoc\`

### Scenario A — Extension Discovery

1. Install the RenderEye extension.
2. Launch RenderDoc.
3. Open the Python Scripting or Extension Manager interface.
4. Verify that RenderEye appears in the extension list.

Expected:

RenderDoc discovers the extension without metadata errors.

### Scenario B — Registration

1. Enable the extension.
2. Observe RenderDoc's Python console and logs.
3. Verify that `register(version, pyrenderdoc)` executes.
4. Confirm that no Python TypeError occurs.
5. Confirm that initialization completes.

Expected:

The extension loads successfully.

### Scenario C — CaptureContext

1. Start RenderDoc with no capture loaded.
2. Query extension GUI state.
3. Load a valid `.rdc`.
4. Query GUI state again.

Expected:

The extension reports the actual loaded capture state.

### Scenario D — Capture Changes

1. Open Capture A.
2. Open Capture B manually.
3. Close the capture.
4. Observe extension callbacks.

Expected:

Capture changes are reflected accurately.

### Scenario E — IPC Connection

1. Start RenderEyeMCP Server.
2. Enable the extension.
3. Verify the extension connects.
4. Query the connected instance using MCP.

Expected:

The MCP server obtains a real GUI state report.

### Scenario F — Extension Reload

1. Load the extension.
2. Reload it through RenderDoc's supported mechanism.
3. Repeat the operation several times.
4. Inspect active IPC connections and worker threads.

Expected:

No duplicate workers, duplicate registrations, or stale callbacks remain.

### Scenario G — Multiple RenderDoc Instances

1. Launch two RenderDoc GUI instances where supported.
2. Enable or load RenderEye in both.
3. Load different captures.
4. Query the MCP server.

Expected:

Each instance is identified independently and reports the correct capture.

### Scenario H — Server Restart

1. Load the extension.
2. Connect to the MCP server.
3. Restart the MCP server.
4. Observe reconnection.
5. Query GUI state.

Expected:

The extension reconnects and provides a fresh GUI state snapshot.

### Test Safety

- Do not terminate unrelated RenderDoc processes.
- Do not close user-created windows automatically.
- Do not modify production engine code.
- Do not delete `.rdc` files.
- Use isolated test captures and managed sessions.

### Missing Environment

If RenderDoc is unavailable, execute unit tests and document real integration tests as unverified.

Do not claim success from mocked tests alone.

### Deliverable

A real RenderDoc integration report with observed results.

---

## 11. Task J — Audit Documentation

Review the project's documentation for RenderDoc extension development and installation.

### Files

Inspect and update as appropriate:

- README.md
- docs/architecture.md
- docs/renderdoc_integration.md
- docs/development.md
- docs/installation.md
- docs/installation-manual.md
- docs/troubleshooting.md

### Required Corrections

Document:

- Official extension entry-point signatures
- RenderDoc version compatibility
- Correct extension metadata format
- Extension discovery paths
- Installation procedure
- Enabling the extension
- Extension reload behavior
- CaptureContext lifecycle
- IPC initialization and shutdown
- Common Python exceptions
- Verification procedure

### Troubleshooting

Include specific guidance for:

```text
TypeError: register() takes 0 positional arguments
but 2 were given
```

Also document related extension loading failures.

### Documentation Evidence

Reference the exact official RenderDoc documentation or source used to verify implementation behavior.

Do not cite speculative third-party examples as definitive API contracts.

### Deliverable

Accurate extension implementation and troubleshooting documentation.

---

## 12. Task K — Compatibility Matrix

Create:

`docs/renderdoc_api_compatibility.md`

Document the compatibility of RenderEyeMCP with relevant RenderDoc releases.

### Recommended Matrix

| API or Feature | Required | Verified | Notes |
|---|---|---|---|
| Extension discovery | Yes | Status | |
| `register(version, pyrenderdoc)` | Yes | Status | |
| `unregister()` | Yes, if supported | Status | |
| CaptureContext access | Yes | Status | |
| Capture loaded state | Yes | Status | |
| CaptureViewer callbacks | If used | Status | |
| GUI thread dispatch | Yes | Status | |
| Extension reload | Yes | Status | |
| IPC connectivity | Yes | Status | |

Record the exact tested RenderDoc version.

Avoid claiming broad compatibility based on a single tested release.

### Deliverable

An evidence-based RenderDoc API compatibility document.

---

## 13. Definition of Done

Phase 5.6 is complete when:

- [ ] Official RenderDoc Python extension documentation has been reviewed.
- [ ] Installed RenderDoc version has been identified where available.
- [ ] `register` has the correct documented signature.
- [ ] `unregister` has the correct supported signature.
- [ ] Registration receives the actual CaptureContext.
- [ ] Extension metadata is valid.
- [ ] Extension discovery paths are correct.
- [ ] All RenderDoc-specific API calls have been audited.
- [ ] Unsupported API assumptions have been corrected.
- [ ] Capture state observation uses verified APIs.
- [ ] Capture callback registration and cleanup are correct.
- [ ] GUI thread constraints are respected.
- [ ] IPC initialization and shutdown are safe.
- [ ] Extension reload is handled correctly.
- [ ] Packaged extension files are valid.
- [ ] Unit tests cover the two-argument registration contract.
- [ ] Existing regression tests pass.
- [ ] Real extension loading has been verified where possible.
- [ ] Real IPC connection has been verified where possible.
- [ ] Documentation has been corrected.
- [ ] API compatibility results are recorded.

### Mandatory Release Gate

Do not mark Phase 5.6 fully verified if the extension has not been successfully loaded into an actual RenderDoc GUI.

If only mocked tests are available, report partial verification.

If the extension fails registration because of a signature mismatch or another API incompatibility, treat it as a release-blocking defect.

---

## 14. Execution Instructions

Execute the work in the following order:

1. Inspect the repository and extension implementation.
2. Identify the installed RenderDoc version.
3. Review the corresponding official documentation.
4. Audit extension entry points.
5. Correct registration and unregistration signatures.
6. Audit extension metadata.
7. Audit every RenderDoc API call.
8. Verify CaptureContext usage.
9. Verify capture callbacks.
10. Verify GUI thread dispatch.
11. Verify IPC lifecycle handling.
12. Fix identified API incompatibilities.
13. Add registration and lifecycle tests.
14. Build the extension distribution.
15. Validate packaged extension contents.
16. Install the extension in a controlled RenderDoc environment.
17. Test real registration and capture-state reporting.
18. Test extension reload and reconnection.
19. Run the complete regression suite.
20. Update documentation.
21. Create the API compatibility matrix.
22. Produce the final report.

Work autonomously using available repository files and tools.

**Do not stop after correcting `register()` unless the remaining extension has been audited.**

Do not implement unrelated features.

Do not modify RenderDoc source code.

Do not publish a GitHub Release without authorization.

---

## 15. Final Report

After implementation, provide:

1. **Root Cause Analysis** — Explain the registration signature mismatch and its observed or potential consequences.
2. **Official API References** — Documentation and source versions consulted.
3. **Files Changed** — Extension code, packaging, tests, and documentation.
4. **API Audit Results** — Valid, corrected, unsupported, and unverified API usages.
5. **Registration Lifecycle** — How initialization, cleanup, and reload now work.
6. **CaptureContext Integration** — Verified state reporting and callback behavior.
7. **IPC Integration** — Connection and reconnection results.
8. **Automated Tests** — Exact commands executed and outcomes.
9. **Real RenderDoc Tests** — Exact GUI version and verified behavior.
10. **Packaging Verification** — Source and release extension results.
11. **Compatibility Matrix** — Supported and unverified RenderDoc versions.
12. **Remaining Issues** — Unresolved incompatibilities and their severity.
13. **Phase 5.6 Status** — Complete, partially verified, or blocked.
14. **Release Readiness** — Whether the RenderDoc extension is safe to distribute.

Do not claim successful real GUI testing when only simulated tests were executed.

**Primary Goal: Ensure that the RenderEyeMCP Python extension conforms to the actual RenderDoc extension API, loads successfully, handles its lifecycle safely, and provides reliable CaptureContext and IPC integration.**
