"""Azure DevOps client + shared helpers used across all tool modules."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from urllib.parse import quote

import requests
from azure.devops.connection import Connection
from dotenv import load_dotenv
from requests import HTTPError

from auth import get_auth_handler

load_dotenv()


class AzureDevOpsClient:
    def __init__(self) -> None:
        self.org_url = (os.environ.get("AZURE_DEVOPS_ORG_URL") or "").rstrip("/")
        self.project = os.environ.get("AZURE_DEVOPS_PROJECT")

        if not (self.org_url and self.project):
            raise EnvironmentError(
                "Missing required env vars. Set AZURE_DEVOPS_ORG_URL and "
                "AZURE_DEVOPS_PROJECT in .env"
            )

        # Get credentials (PAT or OAuth) — msrest format for SDK
        auth_handler = get_auth_handler()
        creds = auth_handler.get_msrest_auth()

        self.connection = Connection(
            base_url=self.org_url,
            creds=creds,
        )
        self._auth_handler = auth_handler

    # SDK service clients ------------------------------------------------------
    def work_items(self):
        return self.connection.clients.get_work_item_tracking_client()

    def git(self):
        return self.connection.clients.get_git_client()

    def build(self):
        return self.connection.clients.get_build_client()

    def core(self):
        return self.connection.clients.get_core_client()

    # Raw REST -----------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make HTTP request using auth credentials (requests format)."""
        req_headers = kwargs.pop("headers", {}).copy()
        if method.upper() != "GET":
            req_headers.setdefault("Content-Type", "application/json")
        timeout = kwargs.pop("timeout", 30)
        is_bearer = self._auth_handler.is_bearer_mode()

        for attempt in range(2):
            auth_tuple = self._auth_handler.get_requests_auth()
            if is_bearer:
                req_headers.update(
                    self._auth_handler.get_requests_headers(force_refresh=(attempt == 1))
                )

            resp = requests.request(
                method,
                f"{self.org_url}{path}",
                auth=auth_tuple,
                headers=req_headers,
                timeout=timeout,
                **kwargs,
            )
            try:
                resp.raise_for_status()
                return resp
            except HTTPError:
                if not (is_bearer and attempt == 0 and resp.status_code == 401):
                    raise

                # Bearer token likely expired between pre-check and request execution.
                self._auth_handler.force_refresh_bearer()

        # Unreachable: loop always returns or raises.
        raise RuntimeError("Unexpected request retry flow")

    def rest(self, method: str, path: str, **kwargs):
        """REST call returning parsed JSON (empty dict if the body is empty)."""
        resp = self._request(method, path, **kwargs)
        return resp.json() if resp.text else {}

    def rest_text(self, method: str, path: str, **kwargs) -> str:
        """REST call returning the raw response body as text (for file content, logs)."""
        return self._request(method, path, **kwargs).text


@lru_cache(maxsize=1)
def client() -> AzureDevOpsClient:
    """Process-wide singleton — all tool modules share one connection."""
    return AzureDevOpsClient()


# ── Shared formatting helpers ────────────────────────────────────────────────

def as_json(data) -> str:
    """Pretty-print a payload as a JSON string (used as tool return value)."""
    return data if isinstance(data, str) else json.dumps(data, indent=2, default=str)


def ref_name(branch: str) -> str:
    """Normalise a branch name to a full git ref."""
    return branch if branch.startswith("refs/") else f"refs/heads/{branch}"


def url_quote(value: str) -> str:
    """URL-encode a path segment (preserves nothing — good for query paths, wiki paths)."""
    return quote(value, safe="")
