"""Entry point for python -m rendereye_mcp."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the RenderEyeMCP MCP bridge."""
    from rendereye_mcp.config import Config
    from rendereye_mcp.logging_setup import configure_logging
    from rendereye_mcp.server import create_server

    from .bootstrap import initialize_environment

    initialize_environment()
    config = Config.from_env()
    configure_logging(config.log_level)

    async def _run() -> None:
        logger.info("[MCP] pid=%d connecting to shared service", os.getpid())

        from rendereye_mcp.service.startup import ensure_service_running

        service_client = await ensure_service_running(config)
        logger.info(
            "[MCP] pid=%d connected to shared service instance=%s",
            os.getpid(),
            service_client.service_instance_id,
        )

        server = create_server(config, service_client=service_client)

        try:
            logger.info("[MCP] pid=%d starting stdio server", os.getpid())
            await server.run_stdio_async()
        finally:
            logger.info("[MCP] pid=%d stdio server exited", os.getpid())
            await service_client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    import sys

    # Support subcommand dispatch when called as `python -m rendereye_mcp <cmd>`
    if len(sys.argv) > 1 and sys.argv[1] != "serve":
        from rendereye_mcp.cli import main as _cli_main

        _cli_main()
    else:
        main()
