"""Prisma SASE OAuth2 authentication for the OpenAPI-Generator SDK.

The generated `Configuration` reads `access_token` per request when applying the
Bearer auth. We subclass it so `access_token` is a *property* backed by a token
manager that performs the client-credentials grant and auto-refreshes ~15-min tokens.

    POST https://auth.apps.paloaltonetworks.com/oauth2/access_token
        Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
        grant_type=client_credentials & scope=tsg_id:<TSG_ID>

Hand-maintained — copied into `prisma_browser/extras/` by the build (`make overlay`).
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time

import urllib3

from ..api_client import ApiClient
from ..configuration import Configuration

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TOKEN_URL",
    "TokenManager",
    "PrismaSaseConfiguration",
    "api_client_from_credentials",
    "api_client_from_env",
]

DEFAULT_BASE_URL = "https://api.sase.paloaltonetworks.com"
DEFAULT_TOKEN_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
_EXPIRY_SKEW = 60.0
_RETRY_STATUSES = (429, 500, 502, 503, 504)


class TokenManager:
    """Fetches and caches a client-credentials access token, refreshing on expiry."""

    def __init__(self, client_id, client_secret, scope, *, token_url=DEFAULT_TOKEN_URL, http=None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token_url = token_url
        self._http = http or urllib3.PoolManager()
        self._token = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def token(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._expires_at:
                self._fetch()
            return self._token

    def _fetch(self) -> None:
        cred = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        resp = self._http.request(
            "POST",
            self._token_url,
            headers={"Authorization": f"Basic {cred}", "Accept": "application/json"},
            fields={"grant_type": "client_credentials", "scope": self._scope},
            encode_multipart=False,  # -> application/x-www-form-urlencoded
        )
        if resp.status != 200:
            raise RuntimeError(
                f"token request to {self._token_url} failed: {resp.status} {resp.data[:300]!r}"
            )
        payload = json.loads(resp.data)
        self._token = payload["access_token"]
        self._expires_at = time.time() + float(payload.get("expires_in", 900)) - _EXPIRY_SKEW


class PrismaSaseConfiguration(Configuration):
    """Configuration whose `access_token` is supplied (and refreshed) by a TokenManager."""

    def __init__(self, *, token_manager: TokenManager, host: str = DEFAULT_BASE_URL, **kwargs):
        self._token_manager = token_manager
        super().__init__(host=host, **kwargs)  # base sets self.access_token=None -> setter no-op

    @property
    def access_token(self):
        return self._token_manager.token()

    @access_token.setter
    def access_token(self, value):
        # Managed by the token manager; ignore the base class's __init__ assignment.
        pass


def _retry(retries: int) -> urllib3.Retry:
    return urllib3.Retry(
        total=retries,
        status_forcelist=list(_RETRY_STATUSES),
        backoff_factor=0.5,
        respect_retry_after_header=True,
        allowed_methods=None,  # retry all methods (idempotent reads dominate here)
        raise_on_status=False,
    )


def api_client_from_credentials(
    *,
    client_id: str,
    client_secret: str,
    scope: str,
    host: str = DEFAULT_BASE_URL,
    token_url: str = DEFAULT_TOKEN_URL,
    retries: int = 3,
) -> ApiClient:
    """Build an authenticated `ApiClient` (retries + auto-refreshing bearer token)."""
    if not scope:
        raise ValueError("scope is required, e.g. 'tsg_id:1234567890'")
    tm = TokenManager(client_id, client_secret, scope, token_url=token_url)
    cfg = PrismaSaseConfiguration(token_manager=tm, host=host)
    cfg.retries = _retry(retries)
    return ApiClient(cfg)


def api_client_from_env(**overrides) -> ApiClient:
    """Build an authenticated `ApiClient` from CLIENT_ID / CLIENT_SECRET / SCOPE env vars."""
    client_id = overrides.pop("client_id", None) or os.environ.get("CLIENT_ID")
    client_secret = overrides.pop("client_secret", None) or os.environ.get("CLIENT_SECRET")
    scope = overrides.pop("scope", None) or os.environ.get("SCOPE")
    host = overrides.pop("host", None) or os.environ.get("PRISMA_SASE_BASE_URL") or DEFAULT_BASE_URL
    missing = [n for n, v in (("CLIENT_ID", client_id), ("CLIENT_SECRET", client_secret), ("SCOPE", scope)) if not v]
    if missing:
        raise RuntimeError(f"missing required auth environment variables: {', '.join(missing)}")
    return api_client_from_credentials(
        client_id=client_id, client_secret=client_secret, scope=scope, host=host, **overrides
    )
