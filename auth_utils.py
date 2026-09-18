#!/usr/bin/env python
"""Utility commands for Azure DevOps auth status/login/logout."""

from __future__ import annotations

import argparse
from datetime import datetime

from auth import TOKEN_CACHE_FILE, MSAL_CACHE_FILE, AuthHandler, get_auth_handler


def _format_expiry(epoch_value) -> str:
    if not epoch_value:
        return "unknown"
    try:
        ts = float(epoch_value)
    except (TypeError, ValueError):
        return "unknown"
    return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")


def cmd_status() -> int:
    handler = get_auth_handler()
    mode = handler.get_effective_mode()

    print("Azure DevOps auth status")
    print("-" * 32)
    print(f"Mode: {mode} (configured={handler.auth_mode})")

    if mode == "pat":
        print("PAT configured: yes")
        print(f"OAuth snapshot cache: {'present' if TOKEN_CACHE_FILE.exists() else 'missing'}")
        print(f"MSAL cache: {'present' if MSAL_CACHE_FILE.exists() else 'missing'}")
        return 0

    if mode == "managed_identity":
        mi_client = handler.mi_client_id or "system-assigned"
        print(f"Managed identity client id: {mi_client}")
        return 0

    if mode == "service_principal":
        print(f"SP tenant id set: {'yes' if bool(handler.sp_tenant_id) else 'no'}")
        print(f"SP client id set: {'yes' if bool(handler.sp_client_id) else 'no'}")
        cred_type = "certificate" if handler.sp_cert_path else "client-secret"
        print(f"SP credential type: {cred_type}")
        return 0

    snapshot = handler._load_cached_token()
    print(f"OAuth snapshot cache: {'present' if TOKEN_CACHE_FILE.exists() else 'missing'}")
    print(f"MSAL cache: {'present' if MSAL_CACHE_FILE.exists() else 'missing'}")

    if snapshot:
        print(f"Token expiry: {_format_expiry(snapshot.get('expires_on'))}")
        print(f"Expired (5m buffer): {'yes' if handler._is_token_expired(snapshot) else 'no'}")
    else:
        print("Token expiry: unknown")
        print("Expired (5m buffer): yes")

    return 0


def cmd_logout() -> int:
    AuthHandler.clear_cache()
    return 0


def cmd_login(force_relogin: bool) -> int:
    if force_relogin:
        AuthHandler.clear_cache()

    handler = get_auth_handler()
    if handler.get_effective_mode() != "oauth":
        print(
            "Interactive login is only for oauth mode. "
            "Set AZURE_DEVOPS_AUTH_MODE=oauth to use this command."
        )
        return 1

    token = handler._get_oauth_token(interactive=True)
    print("OAuth login complete.")
    print(f"Access token acquired: {'yes' if bool(token) else 'no'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Azure DevOps auth utility")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current auth mode and cache details")
    sub.add_parser("logout", help="Clear local OAuth caches")

    login_parser = sub.add_parser("login", help="Run OAuth login flow")
    login_parser.add_argument(
        "--relogin",
        action="store_true",
        help="Clear cache before login",
    )

    args = parser.parse_args()

    if args.command == "status":
        return cmd_status()
    if args.command == "logout":
        return cmd_logout()
    if args.command == "login":
        return cmd_login(args.relogin)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
