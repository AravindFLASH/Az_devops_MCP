"""MCP prompts — reusable, parameterised message templates."""

from __future__ import annotations

from mcp_app import mcp


@mcp.prompt()
def sprint_summary(team: str = "your team") -> str:
    """Summarise all work items in the current sprint."""
    return (
        f"Using the Azure DevOps tools, please:\n"
        f"1. Call `get_current_iteration` for team '{team}' to find the active sprint.\n"
        f"2. Call `query_work_items` with a WIQL query to fetch all items in that iteration.\n"
        f"3. Group them by state (New, Active/In Progress, Resolved, Closed).\n"
        f"4. Present a concise sprint summary table with counts and any blocked items."
    )


@mcp.prompt()
def pr_review_checklist(repo: str, pr_id: str) -> str:
    """Generate a thorough code-review checklist for a pull request."""
    return (
        f"Fetch PR #{pr_id} from repo '{repo}' using `get_pull_request`.\n"
        f"Then generate a detailed code-review checklist covering:\n"
        f"- Code quality and readability\n"
        f"- Security concerns\n"
        f"- Test coverage\n"
        f"- Breaking changes or backwards compatibility\n"
        f"- Documentation and inline comments\n"
        f"- CI/CD pipeline impact\n"
        f"Format as a markdown checklist."
    )


@mcp.prompt()
def pipeline_failure_report(pipeline_id: str, run_id: str) -> str:
    """Explain why a pipeline run failed and suggest fixes."""
    return (
        f"Use `get_pipeline_run` to fetch run {run_id} of pipeline {pipeline_id}.\n"
        f"Analyse the result and state, then:\n"
        f"1. Explain what likely caused the failure.\n"
        f"2. List the top 3 things an engineer should check first.\n"
        f"3. Suggest a fix or next action.\n"
        f"Be concise and actionable."
    )


@mcp.prompt()
def triage_bugs() -> str:
    """List all open bugs, group by priority, and suggest which to tackle first."""
    return (
        "Use `list_work_items_by_state` with type='Bug' and state='Active' "
        "to fetch all open bugs.\n"
        "Then:\n"
        "1. Group bugs by priority (Critical -> Low).\n"
        "2. Highlight any unassigned bugs.\n"
        "3. Recommend the top 5 to resolve first, with reasoning.\n"
        "Format the output as a prioritised markdown table."
    )
