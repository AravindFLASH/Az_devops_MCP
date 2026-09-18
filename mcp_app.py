"""Shared FastMCP instance — imported by every tool / resource / prompt module."""

# pyrefly: ignore [missing-import]
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("azure-devops")
