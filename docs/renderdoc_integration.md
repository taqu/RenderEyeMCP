# RenderDoc extension integration

The Phase 5.6 audit targets the installed Windows RenderDoc **1.46** at
`D:\Programs\RenderDoc\qrenderdoc.exe` (file version `1.46.0.0`). Its embedded
interpreter reports Python **3.8.20**. Extension source retains Python 3.6 syntax
and uses only the standard library plus RenderDoc's embedded API. The host server
uses Python 3.11 or newer. No end-user `uv` installation is required.

## Extension contract and installation

RenderDoc calls `register(version, pyrenderdoc)` with its version string and its
existing `qrenderdoc.CaptureContext`; it calls `unregister()` before reloading.
Never construct `renderdoc.CaptureContext()` or use a module-global filename API.

Each extension is a package directory containing `__init__.py`, `extension.json`,
`gui_context.py`, `gui_dispatcher.py`, `state_observer.py`, and `ipc_client.py`.
Metadata uses `extension_api: 1` and **`minimum_renderdoc`**, not
`minimum_renderdoc_version`. RenderEye currently gates loading to 1.46 and newer;
newer releases still need independent validation.

Install with `rendereye-mcp setup`, or copy the `rendereye` directory from the
extension ZIP into the user extension root:

- Windows: `%APPDATA%\qrenderdoc\extensions\`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/qrenderdoc/extensions/`

Enable **RenderEyeMCP** under **Tools → Manage Extensions**. The Python Scripting
window and changed-extension status button provide RenderDoc's reload workflow.
The executable installation directory is not the user extension root.

## Lifecycle and threading

One runtime owns the supplied context, dispatcher, observer, and IPC worker.
Repeated registration first stops the previous runtime. Startup failures after
workers begin trigger cleanup and propagate an error to RenderDoc.

The observer requests a state sample every 250 ms, keeping at most one pending
sample. `MiniQtHelper.InvokeOntoUIThread(callback)` performs GUI access; no PySide
installation is assumed by the extension. Initial state is dispatched as well:
registration's Python execution thread must not be assumed to be the callback
thread. `IsCaptureLoaded()`, `IsCaptureLoading()`, and `GetCaptureFilename()` provide
actual state. A filename alone does not determine whether a capture is loaded.

CaptureViewer callbacks are deliberately not registered. Polling through MiniQt
also detects path changes after saving a capture, and avoids holding SWIG viewer
objects across reloads. State is sampled, so changes shorter than the sampling
interval may be missed. Loading state can be observed only when GUI dispatch is
serviced; no start-loading callback is invented.

GUI callbacks update cached state and enqueue messages; only the IPC worker writes
to the socket. Commands use the same dispatcher. Open uses
`LoadCapture(path, renderdoc.ReplayOptions(), path, False, True)` and checks the
resulting loaded state because LoadCapture returns no success boolean. Closing or
replacing a capture first uses `GetMainWindow().PromptCloseCapture()` so unsaved
work can be saved or the operation cancelled. Unsupported commands return an
explicit unsupported result.

Shutdown disables queued callbacks, stops the observer, closes the socket to wake
receives, joins workers with bounded waits, and clears the context. Workers never
wait for a GUI callback to finish during shutdown. Reconnect uses interruptible,
capped backoff without a permanent retry cutoff, rereads the token, and sends the
latest cached snapshot after registration. Protocol version remains 1.

## Verification

See [the API compatibility matrix](renderdoc_api_compatibility.md) and
[Phase 5.6 report](phase5.6_report.md) for observed results and remaining gates.
Source, wheel resources, and extension ZIP must contain identical Python modules.
The wheel stores its entry point as `_extension_data/rendereye_init.py`; setup
renames this file to `__init__.py` when installing.

Official references, pinned to the installed release:

- [UI extension tutorial](https://github.com/baldurk/renderdoc/blob/v1.46/docs/python_api/ui_extensions.rst)
- [Metadata and discovery](https://github.com/baldurk/renderdoc/blob/v1.46/docs/how/how_python_extension.rst)
- [Loader and reload implementation](https://github.com/baldurk/renderdoc/blob/v1.46/qrenderdoc/Code/pyrenderdoc/PythonContext.cpp)
- [CaptureContext and MainWindow API](https://github.com/baldurk/renderdoc/blob/v1.46/qrenderdoc/Code/Interface/QRDInterface.h)
- [MiniQt and ExtensionManager API](https://github.com/baldurk/renderdoc/blob/v1.46/qrenderdoc/Code/Interface/Extensions.h)
