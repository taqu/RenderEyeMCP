# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Use GitHub's
[private vulnerability reporting](https://github.com/taqu/RenderEyeMCP/security/advisories/new)
for this repository. If that option is not available, open an issue that only asks for
a private contact channel, without any details. Include the affected version, your OS
and RenderDoc version, and steps to reproduce. You will get an acknowledgement as soon as the maintainer can review
it; this is a small volunteer project with no guaranteed response time.

## Supported versions

Only the latest release (and `main`) receive fixes.

## Security model and limits

RenderEyeMCP is designed for a **single user on a local machine**:

- The shared IPC service listens on `127.0.0.1` only; binding to `0.0.0.0` is refused.
- RenderDoc extensions must present a random per-run token written to the user's temp
  directory. Any process running as the same user can read that token.
- MCP tools do not expose shell execution or arbitrary process termination. Inspection
  tools are read-only; window management tools only act on windows RenderEyeMCP launched.
- Tool results can contain capture paths, resource and shader names, shader source and
  rendered images. They are sent to your coding agent and, through it, to the model
  provider you use.

It has **not** been reviewed for use across machines, containers with shared networks,
or multi-user hosts. Do not forward or expose the IPC port.
