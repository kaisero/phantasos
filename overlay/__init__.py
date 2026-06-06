"""Hand-written conveniences layered on top of the generated SDK.

This subpackage is NOT produced by openapi-python-client. Its source of truth is
``overlay/`` at the repository root; ``apply_overlay.py`` copies it here on every
build, so regenerating the SDK never loses it. Do not edit files here directly —
edit ``overlay/`` and rebuild.

Provides:
- ``build_client`` / ``RetryTransport`` — a client with retries + default timeout.
- ``paginate`` / ``paginate_async`` — iterate every item across cursor pages.
- ``unwrap`` + a typed ``ApiException`` hierarchy — raise on non-2xx responses.
"""

from .auth import (
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_URL,
    PrismaSaseAuth,
    client_from_credentials,
    client_from_env,
)
from .errors import (
    ApiException,
    BadRequestError,
    ClientError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    UnauthorizedError,
    unwrap,
)
from .pagination import paginate, paginate_async
from .transport import RetryTransport, build_client

__all__ = [
    # auth
    "client_from_env",
    "client_from_credentials",
    "PrismaSaseAuth",
    "DEFAULT_BASE_URL",
    "DEFAULT_TOKEN_URL",
    # client / transport
    "build_client",
    "RetryTransport",
    # pagination
    "paginate",
    "paginate_async",
    # errors
    "unwrap",
    "ApiException",
    "ClientError",
    "ServerError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitedError",
]
