# Microsoft Entra ID OAuth Login Guide for Azure DevOps

This guide covers **interactive OAuth device-code login** for local development.
For non-interactive deployments (for example ACI), use `managed_identity` or `service_principal` mode from the main README.

## Quick Start

### Step 1: Run the login script

```bash
cd "C:\Users\aravind\AZ Devops"
python oauth_login.py
```

To force a full re-authentication and clear prior cache:

```bash
python oauth_login.py --relogin
```

You'll see:
```
======================================================================
MICROSOFT ENTRA ID OAUTH - DEVICE CODE FLOW
======================================================================

Visit: https://microsoft.com/devicelogin
Enter code: XXXXXXXXXX

Waiting for browser authentication...
```

### Step 2: Open browser and authenticate

1. Open your browser to the URL shown
2. Enter the device code
3. Log in with your Azure account
4. Approve the permissions for Azure DevOps

The script will automatically cache your token.

### Step 3: Restart Claude Desktop

1. Close Claude Desktop
2. Reopen Claude Desktop
3. Check **Settings > Developer** — MCP server should show **Connected**

## Technical Details

| Setting | Value |
|---------|-------|
| **OAuth Type** | Microsoft Entra ID (Modern) |
| **Flow** | Device Code (interactive, browser-based) |
| **Azure DevOps Resource ID** | `499b84ac-1321-427f-aa17-267ca6975798` |
| **Scope** | `499b84ac-1321-427f-aa17-267ca6975798/.default` |
| **Token Cache** | `~/.claude/auth_cache/ado_token.json` and `~/.claude/auth_cache/ado_msal_cache.bin` |
| **Token Lifetime** | ~1 hour (auto-refreshed) |

## Troubleshooting

### Device code flow error
If you see an error during browser authentication:

```bash
# Clear cache and try again
python -c "from auth import AuthHandler; AuthHandler.clear_cache()"
python oauth_login.py --relogin
```

### Token expired
The token is automatically refreshed. If you see "401 Unauthorized" after ~1 hour:

```bash
python oauth_login.py --relogin
```

### Switch to PAT (emergency fallback)
If OAuth isn't working, use a Personal Access Token instead:

1. Create a PAT at: https://dev.azure.com/your-org/_usersSettings/tokens
2. Edit `.env`:
   ```
   AZURE_DEVOPS_AUTH_MODE=pat
   AZURE_DEVOPS_PAT=your_pat_here
   ```
3. Restart Claude Desktop

### Use non-interactive auth for deployment
For containerized/cloud runtime where browser login is not possible:

1. Prefer `AZURE_DEVOPS_AUTH_MODE=managed_identity` in Azure hosts.
2. Use `AZURE_DEVOPS_AUTH_MODE=service_principal` for non-Azure hosts.
3. Keep `oauth` mode for local interactive development only.

## Why Microsoft Entra ID OAuth?

- ✅ **Modern**: Uses standard OAuth 2.0 protocol
- ✅ **Secure**: Better token management and security features
- ✅ **Recommended**: Official Microsoft recommendation for new apps
- ⚠️ **Note**: Old Azure DevOps OAuth is deprecated (removed 2026)

## Need Help?

- Check Claude Desktop logs: **Settings > Developer > Logs**
- Verify your Entra ID app registration in Azure Portal
- Ensure Azure DevOps is enabled in your tenant

