# Azure DevOps MCP Server

A local **Model Context Protocol (MCP)** server that exposes Azure DevOps as tools, resources, and prompts for AI assistants like Claude Desktop and Cursor.

Supports **Personal Access Token (PAT)**, **OAuth**, **Managed Identity**, and **Service Principal** authentication.

---

## Features

**53 Tools** across all major Azure DevOps areas:

| Category | Tools |
|----------|-------|
| **Work Items** | get, create, update, delete, WIQL query, list by state, comments, history, linking, types |
| **Repos & Commits** | list repos, branches, file content, commit history, list/get/create/approve/merge PRs, PR comments |
| **Pull Requests** | list, get, create, approve, complete (merge), abandon, list/add comments & threads |
| **Pipelines** | list, trigger with variables, get run status, list recent runs, cancel, get logs, artifacts |
| **Boards & Sprints** | list iterations, current sprint, backlog levels, backlog items, sprint capacity, team members |
| **Backlogs** | list backlogs, get backlog work items, area paths, iteration paths |
| **Saved Queries** | list, get, run saved WIQL queries |
| **Wikis** | list wikis, browse pages, read page content |
| **Test Plans** | list plans, test suites, test cases |
| **Identity** | whoami, list projects, list teams |
| **Resources** | `ado://projects`, `ado://teams`, `ado://iterations/current`, `ado://pipelines` |
| **Prompts** | sprint summary, PR review checklist, pipeline failure report, bug triage |

---

## Quick Start

### Transport modes

- `stdio` (default): local desktop clients like Claude Desktop/Cursor
- `streamable-http`: hosted/public MCP endpoint

Configure transport with env vars:

```env
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PATH=/mcp
```

### 1. Install dependencies

```bash
pip install -e .
```

Or with `uv` (faster):
```bash
uv pip install -e .
```

### 2. Set up authentication

#### Which auth mode should I use?

Choose the mode based on how the MCP server is running and whether the workload is interactive or automated.

| Mode | Use when | Interactive? | Typical environment |
|------|----------|--------------|----------------------|
| `pat` | Fastest local setup, personal use, or CI/CD pipelines with a stored secret | No | Local dev, CI/CD |
| `oauth` | You want to sign in as yourself using Microsoft identity | Yes | Local dev, Claude Desktop, Cursor |
| `managed_identity` | The app runs inside Azure and can use a platform-assigned identity | No | Azure Container Apps, App Service, VM |
| `service_principal` | You need a non-interactive enterprise identity for automation | No | Docker, Kubernetes, on-prem, non-Azure hosts |
| `auto` | You want the app to pick the best default automatically | Depends | Quick local testing only |

Step-by-step decision guide:

1. If the MCP server is running inside Azure, prefer `managed_identity`.
   - Set:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=managed_identity
     ```
   - This is the recommended option for Azure Container Apps and other Azure-hosted services.

2. If the server is local or in a developer machine, and you want the easiest setup, use `pat`.
   - Set:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=pat
     AZURE_DEVOPS_PAT=your_personal_access_token_here
     ```
   - Best for quick local testing and simple scripts.

3. If you are authenticating as a user in an interactive session, use `oauth`.
   - Set:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=oauth
     AZURE_DEVOPS_TENANT_ID=common
     ```
   - Then run:
     ```bash
     python oauth_login.py
     ```

4. If this is a headless or automated deployment without a human sign-in, use `service_principal`.
   - Set:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=service_principal
     AZURE_DEVOPS_SP_TENANT_ID=your-tenant-id
     AZURE_DEVOPS_SP_CLIENT_ID=your-app-client-id
     AZURE_DEVOPS_SP_CLIENT_SECRET=your-client-secret
     ```
   - Or use certificate-based auth with `AZURE_DEVOPS_SP_CERT_PATH` and optional password.

5. If you are unsure, leave the mode unset and let the app use `auto`.
   - The project falls back to `pat` if a PAT is present; otherwise it uses the OAuth flow.
   - In production, prefer setting the mode explicitly.

> Before handoff or deployment, always set `AZURE_DEVOPS_AUTH_MODE` explicitly instead of relying on `auto`.

**Manual setup**

Copy and edit `.env.example`:
```bash
copy .env.example .env
```

#### PAT Mode (default, simplest)

```env
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project

# Generate PAT at: https://dev.azure.com/your-org/_usersSettings/tokens
# Scopes: Work Items (Read & Write), Code (Read & Write), Build (Read & Execute)
AZURE_DEVOPS_PAT=your_personal_access_token_here
```

#### OAuth Mode (via Microsoft identity)

```env
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project

# Use OAuth mode explicitly. If PAT is also set, oauth mode still uses OAuth.
AZURE_DEVOPS_AUTH_MODE=oauth
AZURE_DEVOPS_TENANT_ID=common    # or your Azure Entra tenant ID
AZURE_DEVOPS_CLIENT_ID=ID  # built-in app
```

Run interactive OAuth login once:

```bash
python oauth_login.py
```

Token cache files:
- `~/.claude/auth_cache/ado_token.json` (token snapshot)
- `~/.claude/auth_cache/ado_msal_cache.bin` (MSAL silent-refresh cache)

#### Managed Identity Mode (recommended for Azure Container Instance)

```env
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project

AZURE_DEVOPS_AUTH_MODE=managed_identity
# Optional for user-assigned identity:
# AZURE_DEVOPS_MI_CLIENT_ID=your-user-assigned-managed-identity-client-id
```

#### Service Principal Mode (non-interactive OAuth)

```env
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project

AZURE_DEVOPS_AUTH_MODE=service_principal
AZURE_DEVOPS_SP_TENANT_ID=your-tenant-id
AZURE_DEVOPS_SP_CLIENT_ID=your-app-client-id

# Choose ONE method:
AZURE_DEVOPS_SP_CLIENT_SECRET=your-client-secret
# OR
# AZURE_DEVOPS_SP_CERT_PATH=/absolute/path/to/certificate.pem
# AZURE_DEVOPS_SP_CERT_PASSWORD=optional-cert-password
```

### 3. Verify the server starts

```bash
python server.py
```

You should see:
```
2024-xx-xx [INFO] Starting Azure DevOps MCP (stdio)
```

Press `Ctrl+C` to stop.

### 4. Check your auth status

```bash
python auth_utils.py status
```

Output shows current org, project, and auth mode.

To log out (clear cached OAuth tokens):
```bash
python auth_utils.py logout
```

To force a fresh login:
```bash
python oauth_login.py --relogin
```

### 5. Dockerize (secure runtime)

Build image:

```bash
docker build -t azure-devops-mcp:latest .
```

The image runs the MCP server over stdio (`python server.py`) as a non-root user.

Run quickly with PAT:

```bash
docker run --rm -i \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org \
  -e AZURE_DEVOPS_PROJECT=your-project \
  -e AZURE_DEVOPS_AUTH_MODE=pat \
  -e AZURE_DEVOPS_PAT=your_pat_token_here \
  azure-devops-mcp:latest
```

Run as HTTP endpoint (`/mcp`):

```bash
docker run --rm -it -p 8000:8000 \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8000 \
  -e MCP_PATH=/mcp \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org \
  -e AZURE_DEVOPS_PROJECT=your-project \
  -e AZURE_DEVOPS_AUTH_MODE=managed_identity \
  azure-devops-mcp:latest
```

Endpoint: `http://localhost:8000/mcp`

---

## Connect to Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

**Using PAT:**

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "python",
      "args": ["c:/Users/your-name/AZ Devops/server.py"],
      "env": {
        "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/your-org",
        "AZURE_DEVOPS_PROJECT": "your-project",
        "AZURE_DEVOPS_PAT": "your_pat_token_here"
      }
    }
  }
}
```

**Using OAuth:**

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "python",
      "args": ["c:/Users/your-name/AZ Devops/server.py"],
      "env": {
        "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/your-org",
        "AZURE_DEVOPS_PROJECT": "your-project"
      }
    }
  }
}
```

OAuth tokens are cached locally, so you only need to log in once.

Restart Claude Desktop. The ADO tools will appear automatically.

### Claude Desktop with Docker (ready to paste)

Edit `%APPDATA%\\Claude\\claude_desktop_config.json` and use one of the blocks below.

**Docker + PAT (recommended local default):**

```json
{
  "mcpServers": {
    "azure-devops-docker": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org",
        "-e", "AZURE_DEVOPS_PROJECT=your-project",
        "-e", "AZURE_DEVOPS_AUTH_MODE=pat",
        "-e", "AZURE_DEVOPS_PAT=your_pat_token_here",
        "azure-devops-mcp:latest"
      ]
    }
  }
}
```

**Docker + Managed Identity (for Azure-hosted containers):**

```json
{
  "mcpServers": {
    "azure-devops-mi": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org",
        "-e", "AZURE_DEVOPS_PROJECT=your-project",
        "-e", "AZURE_DEVOPS_AUTH_MODE=managed_identity",
        "azure-devops-mcp:latest"
      ]
    }
  }
}
```

**Docker + Service Principal (non-Azure hosts):**

```json
{
  "mcpServers": {
    "azure-devops-sp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org",
        "-e", "AZURE_DEVOPS_PROJECT=your-project",
        "-e", "AZURE_DEVOPS_AUTH_MODE=service_principal",
        "-e", "AZURE_DEVOPS_SP_TENANT_ID=your-tenant-id",
        "-e", "AZURE_DEVOPS_SP_CLIENT_ID=your-app-client-id",
        "-e", "AZURE_DEVOPS_SP_CLIENT_SECRET=your-client-secret",
        "azure-devops-mcp:latest"
      ]
    }
  }
}
```

Notes:
- `oauth` device-code login is for interactive local sessions; it is not ideal for Azure Container Instance runtime.
- For production deployments, prefer managed identity where supported.
- Avoid storing real secrets directly in JSON; use secret injection where possible.

---

## Connect to Cursor

Edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "python",
      "args": ["/path/to/AZ Devops/server.py"]
    }
  }
}
```

Cursor reads your `.env` from the project directory automatically.

---

## Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

Open `http://localhost:5173` in your browser to interactively call tools.

---

## Example Prompts

Once connected to Claude Desktop or Cursor:

```
List all my active bugs in Azure DevOps
```
```
Show me backlogs and the current sprint
```
```
Create a Task titled "Implement new feature" assigned to me
```
```
What files changed in the last 10 commits?
```
```
Get file content: src/main.py from the repo
```
```
Show me open pull requests and pending reviews
```
```
What's in the current sprint?   ← uses the "sprint_summary" prompt
```
```
Triage my open bugs by priority ← uses the "triage_bugs" prompt
```
```
Generate a review checklist for PR #42 ← uses the "pr_review_checklist" prompt
```

---

## Project Structure

```
AZ Devops/
├── server.py                ← MCP server entrypoint
├── ado_client.py           ← Azure DevOps SDK connection
├── auth.py                 ← PAT & OAuth handler
├── auth_utils.py           ← Auth management (status, logout)
├── mcp_app.py              ← Shared FastMCP instance
├── resources.py            ← MCP resources (read-only URIs)
├── prompts.py              ← MCP prompt templates
├── tools/
│   ├── __init__.py         ← Aggregates all tool modules
│   ├── work_items.py       ← CRUD, comments, history, linking, types
│   ├── repos.py            ← Repos, files, commits, PRs, comments
│   ├── pipelines.py        ← Pipelines, runs, builds, logs, artifacts
│   ├── boards.py           ← Iterations, backlogs, teams, paths
│   ├── queries.py          ← Saved WIQL queries
│   ├── wiki.py             ← Wiki pages
│   ├── test_plans.py       ← Test plans, suites, cases
│   └── identity.py         ← User, projects, teams
├── test_client.py          ← Connection smoke test
├── pyproject.toml
├── .env                    ← Your credentials (never commit!)
└── .env.example            ← Template
```

---

## Authentication Details

### PAT Mode

- Simple, works offline
- Token never refreshed (expires per your PAT settings)
- Best for local development and CI/CD

### OAuth Mode

- Uses Microsoft identity platform (Entra ID / Microsoft Account)
- Device code flow: user-friendly, no client secret needed
- Tokens auto-refresh (cached locally, 5-min buffer before expiry)
- Best for local interactive development with user identity

### Managed Identity Mode

- Non-interactive Azure AD token flow
- No secret storage required in code or local files
- Best for Azure-hosted deployments (for example ACI)

### Service Principal Mode

- Non-interactive Azure AD token flow
- Supports client secret and certificate credentials
- Best for server-to-server and non-Azure hosts

---

## Troubleshooting

**"Missing env vars" error:**
- Ensure `AZURE_DEVOPS_ORG_URL` and `AZURE_DEVOPS_PROJECT` are set in `.env`

**"PAT is required for PAT mode":**
- Either set `AZURE_DEVOPS_PAT` in `.env`, or leave it unset to enable OAuth

**OAuth login prompts every time:**
- Token cache may be corrupt. Run: `python auth_utils.py logout`
- Re-authenticate with: `python oauth_login.py --relogin`
- Check `~/.claude/auth_cache/ado_token.json` is readable

**Managed identity auth fails locally:**
- Managed identity is available only in supported Azure runtimes
- For local development, use PAT or oauth mode

**Service principal auth fails at startup:**
- Ensure `AZURE_DEVOPS_SP_TENANT_ID` and `AZURE_DEVOPS_SP_CLIENT_ID` are set
- Set exactly one credential method: `AZURE_DEVOPS_SP_CLIENT_SECRET` or `AZURE_DEVOPS_SP_CERT_PATH`

**Tools not appearing in Claude Desktop:**
- Restart Claude Desktop after updating `.env`
- Check server logs: `python server.py` (will show any connection errors)

---

## Implementation Notes

- Built with **FastMCP** — modern, decorator-based tool registration
- Shared singleton connection — all tools use one authenticated client
- Comprehensive error handling with clear messages
- Auth abstraction allows easy addition of other auth methods (service principal, etc.)
