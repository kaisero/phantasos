"""Prisma SASE OAuth2 authentication for the SDK.

The generated client only accepts a pre-acquired bearer token. Prisma SASE uses
the OAuth2 *client-credentials* grant:

    POST https://auth.apps.paloaltonetworks.com/oauth2/access_token
        Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
        grant_type=client_credentials & scope=tsg_id:<TSG_ID>
    -> { "access_token": "...", "token_type": "Bearer", "expires_in": 899 }

Tokens live ~15 minutes. ``PrismaSaseAuth`` is an ``httpx.Auth`` flow that fetches
a token on first use, caches it until shortly before expiry, and refreshes it
(also retrying once on a 401). It works for both sync and async clients.

Hand-maintained — copied into ``prisma_browser_sdk/extras/`` by ``apply_overlay.py``.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any, Iterator

import httpx

from ..client import Client
from .errors import ApiException
from .transport import RetryTransport

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TOKEN_URL",
    "PrismaSaseAuth",
    "client_from_credentials",
    "client_from_env",
]

# The API base URL per the OpenAPI `servers` block and the official pan.dev docs.
# Note the `api.` subdomain — `https://sase.paloaltonetworks.com` is the console, not the API.
DEFAULT_BASE_URL = "https://api.sase.paloaltonetworks.com"
DEFAULT_TOKEN_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"

# Refresh this many seconds before the server-reported expiry to avoid edge races.
_EXPIRY_SKEW = 60.0


class PrismaSaseAuth(httpx.Auth):
    """httpx auth flow implementing the Prisma SASE client-credentials grant."""

    requires_response_body = True  # so we can read the token response inside the flow

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scope: str,
        *,
        token_url: str = DEFAULT_TOKEN_URL,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token_url = token_url
        self._token: str | None = None
        self._expires_at: float = 0.0

    def _token_request(self) -> httpx.Request:
        credential = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        return httpx.Request(
            "POST",
            self._token_url,
            data={"grant_type": "client_credentials", "scope": self._scope},
            headers={
                "Authorization": f"Basic {credential}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    def _store_token(self, response: httpx.Response) -> None:
        if response.status_code != 200:
            raise ApiException(
                response.status_code,
                f"token request to {self._token_url} failed: {response.text[:300]}",
                response=None,
            )
        payload = response.json()
        self._token = payload["access_token"]
        self._expires_at = time.time() + float(payload.get("expires_in", 900)) - _EXPIRY_SKEW

    def _is_expired(self) -> bool:
        return self._token is None or time.time() >= self._expires_at

    def auth_flow(self, request: httpx.Request) -> Iterator[httpx.Request]:
        if self._is_expired():
            token_response = yield self._token_request()
            self._store_token(token_response)

        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request

        if response.status_code == 401:
            # Token may have been revoked/rotated early — refresh once and retry.
            token_response = yield self._token_request()
            self._store_token(token_response)
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


def client_from_credentials(
    *,
    client_id: str,
    client_secret: str,
    scope: str,
    base_url: str = DEFAULT_BASE_URL,
    token_url: str = DEFAULT_TOKEN_URL,
    timeout: float = 30.0,
    retries: int = 3,
    verify_ssl: bool = True,
    **kwargs: Any,
) -> Client:
    """Build a ``Client`` that authenticates via OAuth2 client-credentials.

    ``scope`` must be the fully-formed OAuth scope, e.g. ``"tsg_id:1234567890"``.
    The token is fetched lazily and auto-refreshed.
    """
    if not scope:
        raise ValueError("scope is required, e.g. 'tsg_id:1234567890'")

    auth = PrismaSaseAuth(client_id, client_secret, scope, token_url=token_url)
    httpx_args: dict[str, Any] = dict(kwargs.pop("httpx_args", {}))
    httpx_args.setdefault("auth", auth)
    httpx_args.setdefault("transport", RetryTransport(retries=retries, verify=verify_ssl))

    return Client(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        verify_ssl=verify_ssl,
        httpx_args=httpx_args,
        **kwargs,
    )


def client_from_env(**overrides: Any) -> Client:
    """Build an authenticated ``Client`` from environment variables.

    Reads ``CLIENT_ID``, ``CLIENT_SECRET``, and ``SCOPE`` (the fully-formed OAuth
    scope, e.g. ``tsg_id:1234567890``); base URL may be overridden via
    ``PRISMA_SASE_BASE_URL``. Any of these may also be passed as keyword overrides,
    which take precedence over the environment.
    """
    client_id = overrides.pop("client_id", None) or os.environ.get("CLIENT_ID")
    client_secret = overrides.pop("client_secret", None) or os.environ.get("CLIENT_SECRET")
    scope = overrides.pop("scope", None) or os.environ.get("SCOPE")
    base_url = (
        overrides.pop("base_url", None)
        or os.environ.get("PRISMA_SASE_BASE_URL")
        or DEFAULT_BASE_URL
    )

    missing = [
        name
        for name, value in (("CLIENT_ID", client_id), ("CLIENT_SECRET", client_secret), ("SCOPE", scope))
        if not value
    ]
    if missing:
        raise RuntimeError(f"missing required auth environment variables: {', '.join(missing)}")

    return client_from_credentials(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        base_url=base_url,
        **overrides,
    )
