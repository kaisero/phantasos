"""Retry transport + a configured-client factory for the Prisma Browser SDK.

The generated client ships with no retries and no default timeout. This overlay
adds a single transport class that implements BOTH the sync and async httpx
transport interfaces (so it can be injected once via ``httpx_args`` and used by
the client's sync and async httpx clients alike), plus a ``build_client`` factory
that wires in sane defaults while preserving the generated client's lazy auth-
header injection.

Hand-maintained — copied into ``prisma_browser_sdk/extras/`` by ``apply_overlay.py``.
"""

from __future__ import annotations

import asyncio
import email.utils
import time
from typing import Any

import httpx

from ..client import AuthenticatedClient

__all__ = ["RetryTransport", "build_client"]

_DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class RetryTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Wraps httpx transports and retries idempotent failures with backoff.

    Retries on connection errors and on the configured status codes (default
    429/500/502/503/504), honouring a ``Retry-After`` header when present.
    """

    def __init__(
        self,
        *,
        retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 30.0,
        retry_statuses: frozenset[int] = _DEFAULT_RETRY_STATUSES,
        verify: bool = True,
    ) -> None:
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_statuses = retry_statuses
        self._sync = httpx.HTTPTransport(verify=verify, retries=retries)
        self._async = httpx.AsyncHTTPTransport(verify=verify, retries=retries)

    # ----- backoff helpers -------------------------------------------------
    def _backoff(self, attempt: int) -> float:
        return min(self.backoff_factor * (2 ** attempt), self.max_backoff)

    def _retry_after(self, response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        if raw.isdigit():
            return float(raw)
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed is None:
            return None
        delay = parsed.timestamp() - time.time()
        return max(0.0, delay)

    def _should_retry(self, response: httpx.Response, attempt: int) -> bool:
        return attempt < self.retries and response.status_code in self.retry_statuses

    # ----- sync ------------------------------------------------------------
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        attempt = 0
        while True:
            response = self._sync.handle_request(request)
            if not self._should_retry(response, attempt):
                return response
            sleep = self._retry_after(response)
            if sleep is None:
                sleep = self._backoff(attempt)
            response.close()
            time.sleep(sleep)
            attempt += 1

    # ----- async -----------------------------------------------------------
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        attempt = 0
        while True:
            response = await self._async.handle_async_request(request)
            if not self._should_retry(response, attempt):
                return response
            sleep = self._retry_after(response)
            if sleep is None:
                sleep = self._backoff(attempt)
            await response.aclose()
            await asyncio.sleep(sleep)
            attempt += 1

    def close(self) -> None:
        self._sync.close()

    async def aclose(self) -> None:
        await self._async.aclose()


def build_client(
    base_url: str,
    token: str,
    *,
    timeout: float = 30.0,
    retries: int = 3,
    backoff_factor: float = 0.5,
    verify_ssl: bool = True,
    raise_on_unexpected_status: bool = False,
    prefix: str = "Bearer",
    auth_header_name: str = "Authorization",
    **kwargs: Any,
) -> AuthenticatedClient:
    """Build an ``AuthenticatedClient`` with retries and an explicit timeout.

    Auth-header injection is left to the generated client (it adds the bearer
    header lazily when the httpx client is first built), so we only inject the
    transport via ``httpx_args``.
    """
    httpx_args: dict[str, Any] = dict(kwargs.pop("httpx_args", {}))
    httpx_args.setdefault(
        "transport",
        RetryTransport(retries=retries, backoff_factor=backoff_factor, verify=verify_ssl),
    )
    return AuthenticatedClient(
        base_url=base_url,
        token=token,
        prefix=prefix,
        auth_header_name=auth_header_name,
        timeout=httpx.Timeout(timeout),
        verify_ssl=verify_ssl,
        raise_on_unexpected_status=raise_on_unexpected_status,
        httpx_args=httpx_args,
        **kwargs,
    )
