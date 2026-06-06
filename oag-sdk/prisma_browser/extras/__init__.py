"""Hand-written conveniences layered on the OpenAPI-Generator SDK.

Source of truth is `oag-overlay/` at the repo root; the build copies it here
(`prisma_browser/extras/`). Do not edit in place — edit `oag-overlay/` and rebuild.
"""

from .auth import (
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_URL,
    PrismaSaseConfiguration,
    TokenManager,
    api_client_from_credentials,
    api_client_from_env,
)

__all__ = [
    "api_client_from_env",
    "api_client_from_credentials",
    "PrismaSaseConfiguration",
    "TokenManager",
    "DEFAULT_BASE_URL",
    "DEFAULT_TOKEN_URL",
]
