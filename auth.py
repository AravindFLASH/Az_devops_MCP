"""Authentication handler for Azure DevOps.

Supports local PAT/OAuth flows and non-interactive cloud modes:
- auto (PAT first, OAuth fallback)
- pat
- oauth (device code + MSAL cache)
- managed_identity
- service_principal (secret or certificate)
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


CACHE_DIR = Path.home() / ".claude" / "auth_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_CACHE_FILE = CACHE_DIR / "ado_token.json"
MSAL_CACHE_FILE = CACHE_DIR / "ado_msal_cache.bin"

# Azure DevOps resource constants
AZURE_DEVOPS_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"
AZURE_DEVOPS_SCOPE = f"{AZURE_DEVOPS_RESOURCE_ID}/.default"
VALID_AUTH_MODES = {"auto", "pat", "oauth", "managed_identity", "service_principal"}


class AuthHandler:
    """Manages credentials for Azure DevOps across local and deployment auth modes."""

    def __init__(self) -> None:
        self.pat = os.environ.get("AZURE_DEVOPS_PAT")
        self.auth_mode = os.environ.get("AZURE_DEVOPS_AUTH_MODE", "auto").lower()
        self.tenant_id = os.environ.get("AZURE_DEVOPS_TENANT_ID", "common")
        self.client_id = os.environ.get("AZURE_DEVOPS_CLIENT_ID", "0cb91555-2a83-4dff-b034-61e7e0b81188")
        self.mi_client_id = os.environ.get("AZURE_DEVOPS_MI_CLIENT_ID")
        self.sp_tenant_id = os.environ.get("AZURE_DEVOPS_SP_TENANT_ID", "")
        self.sp_client_id = os.environ.get("AZURE_DEVOPS_SP_CLIENT_ID", "")
        self.sp_client_secret = os.environ.get("AZURE_DEVOPS_SP_CLIENT_SECRET", "")
        self.sp_cert_path = os.environ.get("AZURE_DEVOPS_SP_CERT_PATH", "")
        self.sp_cert_password = os.environ.get("AZURE_DEVOPS_SP_CERT_PASSWORD", "")
        self._token_cache: dict | None = None
        self._msal_cache = None
        self._msal_app = None
        self._managed_identity_credential = None
        self._service_principal_credential = None
        self._app_token_cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        if self.auth_mode not in VALID_AUTH_MODES:
            raise ValueError(
                "Invalid AZURE_DEVOPS_AUTH_MODE. Use one of: auto, pat, oauth, managed_identity, service_principal"
            )

        if self.auth_mode == "pat" and not self.pat:
            raise EnvironmentError(
                "AZURE_DEVOPS_AUTH_MODE is set to 'pat' but AZURE_DEVOPS_PAT is not configured"
            )

        if self.auth_mode == "service_principal":
            self._validate_service_principal_config()

    def get_effective_mode(self) -> str:
        """Return the actual auth mode used at runtime."""
        if self.auth_mode == "auto":
            return "pat" if self.pat else "oauth"
        return self.auth_mode

    def is_oauth_mode(self) -> bool:
        """Return True when local MSAL OAuth should be used."""
        return self.get_effective_mode() == "oauth"

    def is_bearer_mode(self) -> bool:
        """Return True when Azure AD bearer tokens are used."""
        return self.get_effective_mode() in {"oauth", "managed_identity", "service_principal"}

    def get_auth_tuple(self) -> tuple[str, str]:
        """Return (username, password) tuple for requests auth.

        For PAT: ("", pat_token)
        For bearer modes: ("", access_token)
        """
        if self.get_effective_mode() == "pat":
            if not self.pat:
                raise EnvironmentError("AZURE_DEVOPS_PAT is not configured")
            return ("", self.pat)

        # SDK path still consumes a token in the password slot.
        token = self._get_bearer_token(interactive=self.is_oauth_mode())
        return ("", token)

    def get_requests_auth(self) -> tuple[str, str] | None:
        """Return requests auth tuple for PAT mode, else None for bearer modes."""
        if self.is_bearer_mode():
            return None
        return self.get_auth_tuple()

    def get_requests_headers(self, force_refresh: bool = False) -> dict[str, str]:
        """Return auth headers for raw requests (Bearer for bearer modes, empty for PAT)."""
        if not self.is_bearer_mode():
            return {}
        token = self._get_bearer_token(
            interactive=self.is_oauth_mode() and not force_refresh,
            force_refresh=force_refresh,
        )
        return {"Authorization": f"Bearer {token}"}

    def get_msrest_auth(self):
        """Return msrest BasicAuthentication object for Azure SDK."""
        from msrest.authentication import BasicAuthentication
        username, password = self.get_auth_tuple()
        return BasicAuthentication(username, password)

    def _get_bearer_token(self, interactive: bool, force_refresh: bool = False) -> str:
        """Get bearer token based on the active auth mode."""
        mode = self.get_effective_mode()
        if mode == "oauth":
            return self._get_oauth_token(interactive=interactive, force_refresh=force_refresh)
        if mode == "managed_identity":
            return self._get_managed_identity_token(force_refresh=force_refresh)
        if mode == "service_principal":
            return self._get_service_principal_token(force_refresh=force_refresh)
        raise RuntimeError(f"Bearer token requested in non-bearer mode: {mode}")

    def _get_oauth_token(self, interactive: bool, force_refresh: bool = False) -> str:
        """Get OAuth access token, preferring silent acquisition before device flow."""
        with self._lock:
            if self._token_cache and not force_refresh and not self._is_token_expired(self._token_cache):
                return self._token_cache["access_token"]

            cached = self._load_cached_token()
            if cached and not force_refresh and not self._is_token_expired(cached):
                self._token_cache = cached
                return cached["access_token"]

            app = self._get_msal_app()
            accounts = app.get_accounts()
            if accounts:
                token_response = app.acquire_token_silent(
                    scopes=[AZURE_DEVOPS_SCOPE],
                    account=accounts[0],
                    force_refresh=force_refresh,
                )
                if token_response and "access_token" in token_response:
                    self._persist_msal_cache()
                    self._save_token_cache(token_response)
                    self._token_cache = token_response
                    return token_response["access_token"]

            if not interactive:
                raise RuntimeError(
                    "OAuth token refresh failed silently. Run 'python oauth_login.py --relogin' to authenticate again."
                )

            token_response = self._device_code_flow()
            self._persist_msal_cache()
            self._save_token_cache(token_response)
            self._token_cache = token_response
            return token_response["access_token"]

    def force_refresh_oauth(self) -> str:
        """Backward-compatible alias for forcing bearer token refresh."""
        return self.force_refresh_bearer()

    def force_refresh_bearer(self) -> str:
        """Force a non-interactive bearer token refresh, used for 401 retry paths."""
        return self._get_bearer_token(interactive=False, force_refresh=True)

    def _get_managed_identity_token(self, force_refresh: bool = False) -> str:
        """Acquire token using Azure Managed Identity."""
        with self._lock:
            cache_key = "managed_identity"
            cached = self._app_token_cache.get(cache_key)
            if cached and not force_refresh and not self._is_token_expired(cached):
                return cached["access_token"]

            credential = self._get_managed_identity_credential()
            access_token = credential.get_token(AZURE_DEVOPS_SCOPE)
            token_payload = {
                "access_token": access_token.token,
                "expires_on": access_token.expires_on,
                "token_type": "Bearer",
            }
            self._app_token_cache[cache_key] = token_payload
            return token_payload["access_token"]

    def _get_service_principal_token(self, force_refresh: bool = False) -> str:
        """Acquire token using Entra service principal credentials."""
        with self._lock:
            cache_key = "service_principal"
            cached = self._app_token_cache.get(cache_key)
            if cached and not force_refresh and not self._is_token_expired(cached):
                return cached["access_token"]

            credential = self._get_service_principal_credential()
            access_token = credential.get_token(AZURE_DEVOPS_SCOPE)
            token_payload = {
                "access_token": access_token.token,
                "expires_on": access_token.expires_on,
                "token_type": "Bearer",
            }
            self._app_token_cache[cache_key] = token_payload
            return token_payload["access_token"]

    def _get_managed_identity_credential(self):
        """Lazily construct ManagedIdentityCredential."""
        if self._managed_identity_credential is not None:
            return self._managed_identity_credential

        try:
            from azure.identity import ManagedIdentityCredential
        except ImportError:
            raise ImportError(
                "azure-identity is required for managed identity mode. Run: pip install azure-identity"
            )

        kwargs = {}
        if self.mi_client_id:
            kwargs["client_id"] = self.mi_client_id
        self._managed_identity_credential = ManagedIdentityCredential(**kwargs)
        return self._managed_identity_credential

    def _validate_service_principal_config(self) -> None:
        """Validate required env vars for service principal mode."""
        missing: list[str] = []
        if not self.sp_tenant_id:
            missing.append("AZURE_DEVOPS_SP_TENANT_ID")
        if not self.sp_client_id:
            missing.append("AZURE_DEVOPS_SP_CLIENT_ID")
        if missing:
            raise EnvironmentError(
                "Missing required service principal env vars: " + ", ".join(missing)
            )

        has_secret = bool(self.sp_client_secret)
        has_cert = bool(self.sp_cert_path)

        if has_secret and has_cert:
            raise EnvironmentError(
                "Set only one credential type for service_principal mode: "
                "AZURE_DEVOPS_SP_CLIENT_SECRET or AZURE_DEVOPS_SP_CERT_PATH"
            )

        if not has_secret and not has_cert:
            raise EnvironmentError(
                "service_principal mode requires either AZURE_DEVOPS_SP_CLIENT_SECRET "
                "or AZURE_DEVOPS_SP_CERT_PATH"
            )

        if has_cert and not Path(self.sp_cert_path).exists():
            raise EnvironmentError(
                f"AZURE_DEVOPS_SP_CERT_PATH does not exist: {self.sp_cert_path}"
            )

    def _get_service_principal_credential(self):
        """Lazily construct service principal credential (secret or cert)."""
        if self._service_principal_credential is not None:
            return self._service_principal_credential

        self._validate_service_principal_config()
        try:
            from azure.identity import ClientCertificateCredential, ClientSecretCredential
        except ImportError:
            raise ImportError(
                "azure-identity is required for service_principal mode. Run: pip install azure-identity"
            )

        if self.sp_client_secret:
            self._service_principal_credential = ClientSecretCredential(
                tenant_id=self.sp_tenant_id,
                client_id=self.sp_client_id,
                client_secret=self.sp_client_secret,
            )
            return self._service_principal_credential

        self._service_principal_credential = ClientCertificateCredential(
            tenant_id=self.sp_tenant_id,
            client_id=self.sp_client_id,
            certificate_path=self.sp_cert_path,
            password=self.sp_cert_password or None,
        )
        return self._service_principal_credential

    def _get_msal_app(self):
        """Build a cached MSAL PublicClientApplication instance."""
        try:
            import msal
        except ImportError:
            raise ImportError(
                "MSAL library not installed. Run: pip install msal\n"
                "Or set AZURE_DEVOPS_PAT to use simpler PAT authentication."
            )

        if self._msal_cache is None:
            self._msal_cache = msal.SerializableTokenCache()
            if MSAL_CACHE_FILE.exists():
                try:
                    self._msal_cache.deserialize(MSAL_CACHE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    # Corrupt cache: ignore and rebuild via interactive login.
                    self._msal_cache = msal.SerializableTokenCache()

        if self._msal_app is None:
            self._msal_app = msal.PublicClientApplication(
                client_id=self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                token_cache=self._msal_cache,
            )

        return self._msal_app

    def _device_code_flow(self) -> dict:
        """Perform Microsoft Entra ID OAuth device code flow.

        User-friendly for CLI: displays a code, user opens browser and logs in.
        """
        app = self._get_msal_app()

        print("\n" + "=" * 70)
        print("MICROSOFT ENTRA ID OAUTH - DEVICE CODE FLOW")
        print("=" * 70)
        print()

        # Initiate device code flow for Azure DevOps
        flow = app.initiate_device_flow(scopes=[AZURE_DEVOPS_SCOPE])

        if "user_code" not in flow:
            error_desc = flow.get("error_description", flow.get("error", "Unknown error"))
            if "error_description" in str(error_desc):
                error_msg = "Device code flow initiation failed. Check your tenant configuration."
            else:
                error_msg = error_desc
            raise RuntimeError(error_msg)

        print(f"Visit: {flow['verification_uri']}")
        print(f"Enter code: {flow['user_code']}")
        print()
        print("Waiting for browser authentication...")
        print()

        # Poll for user response
        result = app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            if "AADSTS" in str(error) or "error_uri" in str(error):
                error_msg = "OAuth authentication failed. Please check your credentials and try again."
            else:
                error_msg = error
            raise RuntimeError(error_msg)

        print("[OK] Authenticated successfully!\n")
        return result

    def _persist_msal_cache(self) -> None:
        """Persist MSAL token cache atomically if it changed."""
        if self._msal_cache is None or not self._msal_cache.has_state_changed:
            return

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = self._msal_cache.serialize()
        self._atomic_write_text(MSAL_CACHE_FILE, payload)
        self._safe_chmod(MSAL_CACHE_FILE)

    def _load_cached_token(self) -> dict | None:
        """Load cached token if it exists."""
        if not TOKEN_CACHE_FILE.exists():
            return None
        try:
            with open(TOKEN_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            return None

    def _save_token_cache(self, token: dict) -> None:
        """Save token to local cache."""
        try:
            payload = {
                "access_token": token.get("access_token"),
                "expires_on": token.get("expires_on"),
                "token_type": token.get("token_type", "Bearer"),
                "cached_at": int(datetime.now().timestamp()),
            }
            self._atomic_write_text(TOKEN_CACHE_FILE, json.dumps(payload))
            self._safe_chmod(TOKEN_CACHE_FILE)
        except Exception as e:
            print(f"[WARN] Could not cache token: {e}")

    def _is_token_expired(self, token: dict) -> bool:
        """Check if cached token is expired (with 5-min buffer)."""
        expires_on = token.get("expires_on")
        if not expires_on:
            return True
        try:
            expires_ts = float(expires_on)
            return datetime.now() >= datetime.fromtimestamp(expires_ts) - timedelta(minutes=5)
        except (TypeError, ValueError, OSError):
            return True

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        """Atomically write text content to avoid partial-token file corruption."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _safe_chmod(path: Path) -> None:
        """Best-effort permission tightening (effective on POSIX, no-op if unsupported)."""
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass

    @staticmethod
    def clear_cache() -> None:
        """Clear cached tokens (useful for logout or switching accounts)."""
        removed = False
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()
            print(f"Cleared auth cache: {TOKEN_CACHE_FILE}")
            removed = True
        if MSAL_CACHE_FILE.exists():
            MSAL_CACHE_FILE.unlink()
            print(f"Cleared auth cache: {MSAL_CACHE_FILE}")
            removed = True
        if not removed:
            print("No auth cache files found")


def get_auth_handler() -> AuthHandler:
    """Get authentication handler singleton."""
    global _auth_handler
    if _auth_handler is None:
        with _auth_handler_lock:
            if _auth_handler is None:
                _auth_handler = AuthHandler()
    return _auth_handler


_auth_handler: AuthHandler | None = None
_auth_handler_lock = threading.Lock()
