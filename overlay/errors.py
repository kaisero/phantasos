"""Typed error handling for the Prisma Browser SDK.

This overlay turns the generator's "return ``None`` / ``ApiError`` on a 4xx-5xx"
pattern into an explicit, typed exception hierarchy and an ``unwrap`` helper.

Hand-maintained — lives in ``overlay/`` and is copied into
``prisma_browser_sdk/extras/`` by ``apply_overlay.py`` on every build.
"""

from __future__ import annotations

from typing import Any

from ..types import Response

try:  # ApiError is the spec's unified error body; import is best-effort.
    from ..models.api_error import ApiError
except Exception:  # pragma: no cover - defensive
    ApiError = None  # type: ignore[assignment]

__all__ = [
    "ApiException",
    "ClientError",
    "ServerError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitedError",
    "unwrap",
]


class ApiException(Exception):
    """Base class for all non-2xx API responses."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        error: Any = None,
        response: Response[Any] | None = None,
    ) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message
        self.error = error
        self.response = response


class ClientError(ApiException):
    """Any 4xx response without a more specific subclass."""


class ServerError(ApiException):
    """Any 5xx response."""


class BadRequestError(ClientError):
    """400 Bad Request."""


class UnauthorizedError(ClientError):
    """401 Unauthorized."""


class ForbiddenError(ClientError):
    """403 Forbidden."""


class NotFoundError(ClientError):
    """404 Not Found."""


class ConflictError(ClientError):
    """409 Conflict."""


class RateLimitedError(ClientError):
    """429 Too Many Requests. ``retry_after`` is seconds if the server sent it."""

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


_STATUS_MAP: dict[int, type[ApiException]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitedError,
}


def _exception_for_status(status_code: int) -> type[ApiException]:
    if status_code in _STATUS_MAP:
        return _STATUS_MAP[status_code]
    if 400 <= status_code < 500:
        return ClientError
    return ServerError


def _extract_message(parsed: Any, response: Response[Any]) -> str:
    """Pull a human-readable message out of an ApiError-shaped body.

    The spec's ApiError nests the message under ``error`` (``{error: {code,
    message, ...}}``); we also handle flatter shapes and a plain-string ``error``.
    """
    nested = getattr(parsed, "error", None)
    if nested is not None and not isinstance(nested, str):
        message = getattr(nested, "message", None)
        if isinstance(message, str) and message:
            code = getattr(nested, "code", None)
            code = getattr(code, "value", code)
            return f"{code}: {message}" if code else message
    for attr in ("message", "detail", "title", "description", "error"):
        value = getattr(parsed, attr, None)
        if isinstance(value, str) and value:
            return value
    body = (response.content or b"").decode("utf-8", "replace").strip()
    return body[:500] or "request failed"


def unwrap(response: Response[Any]) -> Any:
    """Return ``response.parsed`` for 2xx, otherwise raise a typed ``ApiException``.

    Use with the generated ``*_detailed`` endpoint functions::

        from prisma_browser_sdk.api.users import list_users
        from prisma_browser_sdk.extras import unwrap

        page = unwrap(list_users.sync_detailed(client=client, limit=50))
    """
    status_code = int(response.status_code)
    if 200 <= status_code < 300:
        return response.parsed

    parsed = response.parsed
    message = _extract_message(parsed, response)
    cls = _exception_for_status(status_code)

    if cls is RateLimitedError:
        retry_after = None
        raw = response.headers.get("Retry-After") if response.headers else None
        if raw:
            try:
                retry_after = float(raw)
            except ValueError:
                retry_after = None
        return _raise(RateLimitedError(
            status_code, message, error=parsed, response=response, retry_after=retry_after
        ))
    return _raise(cls(status_code, message, error=parsed, response=response))


def _raise(exc: ApiException) -> Any:
    raise exc
