# Docker Run Guide

## Build the image

```bash
docker build -t azure-devops-mcp .
```

## Transport modes

- `MCP_TRANSPORT=stdio` (default): best for Claude Desktop/Cursor local MCP integration
- `MCP_TRANSPORT=streamable-http`: serves MCP over HTTP for hosted/public endpoint use

## Which auth mode should I use?

Use the right mode depending on how the container runs and what kind of identity you want to use.

| Mode | Best fit | Example |
|------|----------|---------|
| `pat` | Fast local testing, scripts, CI/CD | Personal developer machine or pipeline |
| `oauth` | Interactive user login | Local dev with Claude Desktop/Cursor |
| `managed_identity` | Azure-hosted services | Azure Container Apps |
| `service_principal` | Headless automation | Docker, Kubernetes, remote worker |
| `auto` | Quick defaulting | Local testing only |

### Step-by-step selection guide

1. Is the container running in Azure?
   - Yes → use `managed_identity`
   - Example:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=managed_identity
     ```
   - This is the recommended mode for Azure Container Apps.

2. Is the deployment interactive or user-driven?
   - Yes → use `oauth`
   - Example:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=oauth
     AZURE_DEVOPS_TENANT_ID=common
     ```
   - Then run:
     ```bash
     python oauth_login.py
     ```

3. Is this a quick local test or a CI/CD secret-based flow?
   - Yes → use `pat`
   - Example:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=pat
     AZURE_DEVOPS_PAT=your_pat_token_here
     ```

4. Is this a non-interactive production workload with an app registration?
   - Yes → use `service_principal`
   - Example:
     ```bash
     AZURE_DEVOPS_AUTH_MODE=service_principal
     AZURE_DEVOPS_SP_TENANT_ID=your-tenant-id
     AZURE_DEVOPS_SP_CLIENT_ID=your-app-client-id
     AZURE_DEVOPS_SP_CLIENT_SECRET=your-client-secret
     ```

> Prefer explicit auth-mode configuration in production. Avoid relying on `auto` for long-lived or shared deployments.

## Run with different auth modes

### HTTP transport (public endpoint at /mcp)

```bash
docker run -it --rm \
  -p 8000:8000 \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8000 \
  -e MCP_PATH=/mcp \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=service_principal \
  -e AZURE_DEVOPS_SP_TENANT_ID=sp-tenant-id \
  -e AZURE_DEVOPS_SP_CLIENT_ID=sp-client-id \
  -e AZURE_DEVOPS_SP_CLIENT_SECRET=sp-secret \
  azure-devops-mcp
```

This exposes the MCP endpoint at `http://localhost:8000/mcp`.

### 1. OAuth (device code flow) — Local development

```bash
docker run -it --rm \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=oauth \
  -e AZURE_DEVOPS_TENANT_ID=your-tenant-id \
  -e AZURE_DEVOPS_CLIENT_ID=your-client-id \
  azure-devops-mcp
```

**Note:** Device code flow requires interactive browser login. The container will display a device code URL — copy it to your host machine's browser.

### 2. PAT (Personal Access Token) — CI/CD systems

```bash
docker run -it --rm \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=pat \
  -e AZURE_DEVOPS_PAT=your_pat_token_here \
  azure-devops-mcp
```

### 3. Managed Identity — Azure Container Instances / App Service

```bash
docker run -it --rm \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=managed_identity \
  azure-devops-mcp
```

For hosted HTTP mode, add the MCP transport variables:

```bash
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8000 \
  -e MCP_PATH=/mcp \
```

### 4. Service Principal — Kubernetes / Docker Swarm

**With secret:**
```bash
docker run -it --rm \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=service_principal \
  -e AZURE_DEVOPS_SP_TENANT_ID=sp-tenant-id \
  -e AZURE_DEVOPS_SP_CLIENT_ID=sp-client-id \
  -e AZURE_DEVOPS_SP_CLIENT_SECRET=sp-secret \
  azure-devops-mcp
```

**With certificate:**
```bash
docker run -it --rm \
  -e AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG \
  -e AZURE_DEVOPS_PROJECT=YOUR_PROJECT \
  -e AZURE_DEVOPS_AUTH_MODE=service_principal \
  -e AZURE_DEVOPS_SP_TENANT_ID=sp-tenant-id \
  -e AZURE_DEVOPS_SP_CLIENT_ID=sp-client-id \
  -e AZURE_DEVOPS_SP_CERT_PATH=/app/cert.pem \
  -e AZURE_DEVOPS_SP_CERT_PASSWORD=optional-password \
  -v /local/path/to/cert.pem:/app/cert.pem:ro \
  azure-devops-mcp
```

## Using .env file

Instead of `-e` flags, you can pass a `.env` file:

```bash
docker run -it --rm \
  --env-file .env \
  azure-devops-mcp
```

**Security note:** Don't commit `.env` to version control. Use Docker secrets in production.

## Azure Container Apps (public endpoint)

1. Build and push image to Docker Hub:

```bash
docker login
docker build -t docker.io/YOUR_DOCKERHUB_USER/azure-devops-mcp:v1 .
docker push docker.io/YOUR_DOCKERHUB_USER/azure-devops-mcp:v1
```

2. Create environment and app:

```bash
az group create --name rg-ado-mcp --location eastus
az containerapp env create --name cae-ado-mcp --resource-group rg-ado-mcp --location eastus
az containerapp create \
  --name ca-ado-mcp \
  --resource-group rg-ado-mcp \
  --environment cae-ado-mcp \
  --image docker.io/YOUR_DOCKERHUB_USER/azure-devops-mcp:v1 \
  --target-port 8000 \
  --ingress external \
  --env-vars MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000 MCP_PATH=/mcp AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YOUR_ORG AZURE_DEVOPS_PROJECT=YOUR_PROJECT AZURE_DEVOPS_AUTH_MODE=managed_identity
```

3. Assign managed identity:

```bash
az containerapp identity assign --name ca-ado-mcp --resource-group rg-ado-mcp --system-assigned
```

4. View endpoint and logs:

```bash
az containerapp show --name ca-ado-mcp --resource-group rg-ado-mcp --query properties.configuration.ingress.fqdn -o tsv
az containerapp logs show --name ca-ado-mcp --resource-group rg-ado-mcp --follow
```

## MCP Server Integration

The container runs the MCP server over stdio. To integrate with Claude Desktop:

1. Add to Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "docker",
      "args": ["run", "-i", "--rm", 
        "-e", "AZURE_DEVOPS_ORG_URL=...",
        "-e", "AZURE_DEVOPS_PROJECT=...",
        "-e", "AZURE_DEVOPS_AUTH_MODE=oauth",
        "-e", "AZURE_DEVOPS_TENANT_ID=...",
        "-e", "AZURE_DEVOPS_CLIENT_ID=...",
        "azure-devops-mcp"]
    }
  }
}
```

2. Restart Claude Desktop
3. Check Settings > Developer for "Connected" status

## Troubleshooting

### Permission denied on `.claude/auth_cache`

The container runs as non-root user `mcp`. Token cache directory is in `/home/mcp/.claude/auth_cache`. 

If you see permission errors, ensure the Docker volume is writable by the `mcp` user (UID 1000).

### Device code flow not working

Device code flow requires:
- Interactive terminal (`-it` flags)
- Network access to `login.microsoftonline.com`
- Ability to open browser on host machine

Not suitable for headless/CI systems — use **PAT** or **Service Principal** instead.

### Token caching across restarts

Token cache lives in `/home/mcp/.claude/auth_cache/` inside the container. To persist tokens between runs:

```bash
docker run -it --rm \
  -v auth-cache:/home/mcp/.claude/auth_cache \
  --env-file .env \
  azure-devops-mcp
```

This creates a named Docker volume for token persistence.
