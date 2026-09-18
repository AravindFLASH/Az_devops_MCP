#!/usr/bin/env python
"""
Complete OAuth login and cache token for Azure DevOps.

Run this ONCE to authenticate. Claude Desktop will then use the cached token.
"""

import argparse
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("AZURE DEVOPS OAUTH - DEVICE CODE FLOW LOGIN")
print("=" * 70)
print()
print("This will prompt you to log in via browser using device code flow.")
print()

parser = argparse.ArgumentParser(description="Azure DevOps OAuth device-code login")
parser.add_argument(
    "--relogin",
    action="store_true",
    help="Clear cached tokens first and force a fresh interactive login",
)
args = parser.parse_args()

try:
    # Import lazily after env has loaded.
    import auth

    if args.relogin:
        auth.AuthHandler.clear_cache()
        auth._auth_handler = None
        print("Cleared cached tokens. A fresh login will be requested.\n")
    else:
        print("Using cached session when available (use --relogin to force new sign-in).\n")

    print("Initiating OAuth login...\n")

    from ado_client import client
    ado = client()

    print("=" * 70)
    print("SUCCESS - OAuth authentication complete!")
    print("=" * 70)
    print()
    print(f"Connected to: {ado.org_url}")
    print(f"Project: {ado.project}")
    print()
    print("Token cache files:")
    print("  - ~/.claude/auth_cache/ado_token.json")
    print("  - ~/.claude/auth_cache/ado_msal_cache.bin")
    print()
    print("Next steps:")
    print("  1. Close Claude Desktop")
    print("  2. Reopen Claude Desktop")
    print("  3. Check Settings > Developer for 'Connected' status")
    print("  4. All tools will now work with your OAuth token")
    print()

except Exception as e:
    print(f"[ERROR] {e}")
    print()
    import traceback
    traceback.print_exc()
    sys.exit(1)
