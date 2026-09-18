"""MCP resources — read-only URIs the client can pull without a tool call."""

from __future__ import annotations

from ado_client import as_json, client
from mcp_app import mcp
from tools.boards import _default_team_name


@mcp.resource("ado://projects")
def resource_projects() -> str:
    """All projects in the organisation."""
    return as_json([
        {"id": p.id, "name": p.name, "state": p.state}
        for p in client().core().get_projects()
    ])


@mcp.resource("ado://teams")
def resource_teams() -> str:
    """All teams in the configured project."""
    return as_json([
        {"id": t.id, "name": t.name, "description": t.description}
        for t in client().core().get_teams(client().project)
    ])


@mcp.resource("ado://iterations/current")
def resource_current_iteration() -> str:
    """Currently active sprint / iteration."""
    data = client().rest(
        "GET",
        f"/{client().project}/{_default_team_name()}/_apis/work/teamsettings/iterations"
        "?$timeframe=current&api-version=7.1",
    )
    iterations = data.get("value", [])
    if not iterations:
        return as_json({"message": "No active iteration."})
    it = iterations[0]
    return as_json({
        "name": it["name"],
        "path": it["path"],
        "start_date": it.get("attributes", {}).get("startDate"),
        "finish_date": it.get("attributes", {}).get("finishDate"),
    })


@mcp.resource("ado://pipelines")
def resource_pipelines() -> str:
    """All pipeline definitions in the project."""
    data = client().rest("GET", f"/{client().project}/_apis/pipelines?api-version=7.1")
    return as_json([
        {"id": p["id"], "name": p["name"], "folder": p.get("folder", "\\")}
        for p in data.get("value", [])
    ])
