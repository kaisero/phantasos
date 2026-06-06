"""Hand-written conveniences layered on the OpenAPI-Generator SDK.

Source of truth is `overlay/` at the repo root; the build copies it here
(`prisma_browser/extras/`). Do not edit in place — edit `overlay/` and rebuild.
"""

from .auth import (
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_URL,
    PrismaSaseConfiguration,
    TokenManager,
    api_client_from_credentials,
    api_client_from_env,
)
from .errors import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceException,
    UnauthorizedException,
    error_message,
    is_rate_limited,
)
from .facade import Client
from .pagination import paginate

__all__ = [
    # facade
    "Client",
    # auth
    "api_client_from_env",
    "api_client_from_credentials",
    "PrismaSaseConfiguration",
    "TokenManager",
    "DEFAULT_BASE_URL",
    "DEFAULT_TOKEN_URL",
    # pagination
    "paginate",
    # errors
    "ApiException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ServiceException",
    "is_rate_limited",
    "error_message",
]
