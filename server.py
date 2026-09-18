"""Azure DevOps MCP server — entrypoint.

Runs over stdio, which is how Claude Desktop / Cursor / MCP Inspector connect.

    python server.py
"""

from __future__ import annotations

import logging
import os

from auth import get_auth_handler
from mcp_app import mcp

# Register tools / resources / prompts by importing them (decorators run).
import tools      # noqa: F401  -- registers every tool module
import resources  # noqa: F401
import prompts    # noqa: F401


def _parse_port(raw_value: str, default: int = 8000) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if 1 <= value <= 65535 else default


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger("azure-devops-mcp")
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()

    # Validate auth config early so misconfiguration fails fast on startup.
    handler = get_auth_handler()
    effective_mode = handler.get_effective_mode()

    if transport in {"http", "streamable-http", "streamable_http"}:
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = _parse_port(os.environ.get("MCP_PORT", "8000"), default=8000)
        path = os.environ.get("MCP_PATH", "/mcp")
        if not path.startswith("/"):
            path = f"/{path}"

        if effective_mode == "oauth":
            logger.warning(
                "Running HTTP transport with oauth mode. Device-code login is interactive; "
                "managed_identity or service_principal is recommended for unattended deployments."
            )

        logger.info(
            "Starting Azure DevOps MCP (streamable-http) on %s:%s%s (auth_mode=%s)",
            host,
            port,
            path,
            effective_mode,
        )
        # FastMCP (mcp 1.x) reads host/port/path from settings, not run() kwargs.
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.settings.streamable_http_path = path

        # DNS-rebinding protection rejects any Host header not in an allow-list,
        # which blocks hosted deployments behind a proxy (e.g. Azure Container
        # Apps, whose FQDN is dynamic). Configure via MCP_ALLOWED_HOSTS:
        #   unset or "*"  -> protection disabled (server sits behind TLS ingress)
        #   "a.com,b.com" -> protection enabled, only those Host/Origin values allowed
        from mcp.server.transport_security import TransportSecuritySettings

        raw_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "*").strip()
        allowed_hosts = [h.strip() for h in raw_hosts.split(",") if h.strip()]
        if not allowed_hosts or allowed_hosts == ["*"]:
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            )
            logger.info("DNS-rebinding protection disabled (MCP_ALLOWED_HOSTS=*)")
        else:
            raw_origins = os.environ.get("MCP_ALLOWED_ORIGINS", "").strip()
            allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins or allowed_hosts,
            )
            logger.info("DNS-rebinding protection enabled for hosts: %s", allowed_hosts)

        mcp.run(transport="streamable-http")
    elif transport == "stdio":
        logger.info("Starting Azure DevOps MCP (stdio) (auth_mode=%s)", effective_mode)
        mcp.run(transport="stdio")
    else:
        raise ValueError(
            "Invalid MCP_TRANSPORT. Use one of: stdio, streamable-http, http"
        )
