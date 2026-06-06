"""Error handling for the OpenAPI-Generator SDK.

OAG already raises a typed exception hierarchy on non-2xx responses
(`ApiException` base; `BadRequestException` 400, `UnauthorizedException` 401,
`ForbiddenException` 403, `NotFoundException` 404, `ServiceException` 5xx), each
carrying `.status`, `.reason`, `.body`/`.data`, `.headers`. This module re-exports
them under the names the prototype used and adds small conveniences:

- `RateLimitedError` alias for 429 detection (429 falls to base `ApiException`).
- `error_message(exc)` — pull a human message out of the JSON `{error:{message}}` body.

Hand-maintained — copied into `prisma_browser/extras/` by the build.
"""

from __future__ import annotations

import json
from typing import Any

from ..exceptions import (  # noqa: F401  (re-exported)
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceException,
    UnauthorizedException,
)

__all__ = [
    "ApiException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ServiceException",
    "is_rate_limited",
    "error_message",
]


def is_rate_limited(exc: ApiException) -> bool:
    """True if the exception is a 429 (OAG maps it to the base ApiException)."""
    return getattr(exc, "status", None) == 429


def error_message(exc: ApiException) -> str:
    """Extract a human-readable message from an ApiException's JSON error body."""
    body = getattr(exc, "body", None) or getattr(exc, "data", None)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    if isinstance(body, str) and body.strip():
        try:
            body = json.loads(body)
        except ValueError:
            return body.strip()[:500]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            code = err.get("code")
            return f"{code}: {err['message']}" if code else err["message"]
        for key in ("message", "detail", "title"):
            if isinstance(body.get(key), str):
                return body[key]
    return getattr(exc, "reason", None) or "request failed"
