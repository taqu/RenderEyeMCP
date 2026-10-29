# RenderDoc API compatibility

Audit date: 2026-10-27 (JST). Installed Windows GUI: **1.46.0.0**, reporting
RenderDoc **1.46**, embedded Python **3.8.20**. Metadata minimum is **1.46**.
Newer releases are not automatically verified by that minimum.

| API / feature | Required | 1.46 evidence | Notes |
|---|---|---|---|
| User extension discovery | Yes | Real GUI | Wheel resources installed under a unique user extension name |
| `register(version, pyrenderdoc)` | Yes | Real loader + unit tests | Receives `qrenderdoc.CaptureContext`, not a new object |
| `unregister()` | Yes | Real reload + unit tests | Parameterless; no workers remain after explicit unregister |
| `extension_api: 1`, `minimum_renderdoc` | Yes | Tagged documentation + real discovery | Corrected ignored minimum-version key |
| `CaptureContext.Extensions()` | Yes | Real GUI | Gets the supplied context's extension manager |
| `GetMiniQtHelper().InvokeOntoUIThread(callback)` | Yes | Real GUI commands + unit tests | Zero-argument callback; initial sampling dispatched too |
| `IsCaptureLoaded() -> bool` | Yes | Real no-capture state + mocks | Loaded captures still require replay validation |
| `IsCaptureLoading() -> bool` | Yes | Tagged source + real idle query | In-progress replay not exercised |
| `GetCaptureFilename() -> str` | Yes | Tagged source + strict fake context | Real loaded filename not exercised |
| `GetMainWindow().PromptCloseCapture() -> bool` | For close/replacement | Tagged source + unit tests | Save/cancel path not exercised with a real capture |
| `LoadCapture(path, ReplayOptions(), original, temporary, local) -> None` | For open | Tagged source + signature regression | Checks state after call; real replay unverified |
| `renderdoc.ReplayOptions()` | For open | Tagged signature + strict fake | Real replay unverified |
| CaptureViewer interface | No | Source audited; unused | No persistent viewers or menu callbacks to remove |
| Repeated load / reload | Yes | Real GUI | Four loads per GUI (initial plus three reloads) |
| Authenticated IPC / GUI state request | Yes | Real GUI + real IPC transport | Protocol 1, state `unloaded` |
| Two GUI instances | Yes | Real GUI | Separate process/instance IDs, at most two active connections |
| Listener restart / token rotation | Yes | Real GUI | Both final instances reconnected with fresh state snapshots |
| Wheel setup and extension ZIP | Yes | Isolated Python + real wheel GUI | Source/resource parity enforced |

## Phase 12 live inspection audit (2026-10-29)

Windows 11, RenderDoc 1.46, a D3D12 capture (2,370 events). Inspection requests went
through the shared service and the MCP stdio server. Event selection for the draw and
dispatch checks was set with `CaptureContext.SetEventID` from a `qrenderdoc --python`
startup script.

| API / feature | 1.46 evidence | Notes |
|---|---|---|
| `CurSelectedEvent()`, `CurEvent()`, `CurSelectedAction()`, `GetAction()` | Real GUI | Selection set via `SetEventID` is reported correctly. One manual GUI-click session kept reporting the post-load event; unresolved, needs a manual re-test |
| `CurPipelineState()` sections, `GetShader`, `GetShaderReflection` | Real GUI | Draw (VS+PS) and compute dispatch |
| `GetOutputTargets()` / `GetDepthTarget()` | Real GUI | Return `renderdoc.Descriptor` (`resource`, `firstMip`, `firstSlice`), **not** `resourceId`/`mip`/`slice`. Fixed in Phase 12; previously reported every target as unbound |
| `GetConstantBlocks` / `GetReadOnlyResources` / `GetReadWriteResources` | Real GUI | `UsedDescriptor.descriptor.resource` |
| `ReplayController.SaveTexture(TextureSave, path)` | Real GUI | `TextureSave.slice` is a `TextureSliceMapping` (`sliceIndex`), `sample` a `TextureSampleMapping`. Fixed in Phase 12 (assigning a `Subresource` raised) |
| `ReplayController.GetHistogram(tex, sub, typeCast, min, max, channels)` | Real GUI | Six arguments. Fixed in Phase 12 (was called with five) |
| `GetMinMax`, `PickPixel`, `GetBufferData`, `GetTexture`, `GetResources` | Real GUI | |
| PNG over IPC | Real GUI + MCP stdio | 2.25 MB base64 image delivered after raising the IPC message limit to 16 MiB |

Not exercised live: D3D11, Vulkan and OpenGL captures; MSAA targets; array/cube slices;
shader debug info with full source-level debug data.

## Release/platform scope

- Windows RenderDoc 1.46: discovery, lifecycle, dispatch and idle IPC smoke verified.
  Capture A → B → close, loading transitions, and replay errors remain unverified.
- RenderDoc 1.43: earlier source consulted for orientation, **not a supported or
  tested target**. Versions below 1.46 are blocked by metadata.
- Newer RenderDoc: unverified; validate independently before claiming support.
- Linux: stdlib-only extension and XDG user path preserved; no native GUI run.
- macOS: no official native RenderDoc GUI target.

See [integration and pinned official references](renderdoc_integration.md) and
[Phase 5.6 verification report](phase5.6_report.md). **Phase 5.6 remains partially
verified pending tests with real compatible captures.**
