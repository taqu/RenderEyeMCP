[English](README.md) | [日本語](../../ja/examples/README.md)

# Debugging scenarios

Each scenario starts from a rendering problem and shows how to investigate it with a
coding agent and RenderEyeMCP. They share one structure: Problem → Preparation →
Example prompt → Investigation workflow → Expected observations → Interpretation →
Limitations → Related tools.

| Scenario | Use it when |
|----------|-------------|
| [A. Inspect an already-open capture](active-capture.md) | First contact: which capture, which API, which event |
| [B. An object is not visible](missing-object.md) | A draw call should produce something but nothing shows up |
| [C. Wrong texture or material values](shader-resources.md) | A material samples the wrong texture or has unexpected constants |
| [D. Black or wrong render target](render-target.md) | A target is black, saturated or has unexpected colors |
| [E. Depth testing problems](depth-debugging.md) | Objects disappear or are wrongly occluded |
| [F. Wrong compute shader output](compute-dispatch.md) | A dispatch writes unexpected results |

**Validation status.** The tools used in every scenario were run against a real D3D12
capture in RenderDoc 1.46 (Windows 11). The scenarios themselves are guidance on how to
reason; they are not recordings of a single agent session, and the conclusions an agent
draws always need your review.
