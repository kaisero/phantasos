"""Pydantic component models for a generated SDK's vendored extras.

Each component carries a `type` (its built-in strategy name, validated by the
loader against a registry) and the config the matching Jinja template needs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class OAuthClientCredentials(_Component):
    """OAuth2 client-credentials auth (Basic creds, form body)."""

    token_url: str
    scope_env: str = "SCOPE"
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"  # noqa: S105  env-var name, not a secret
    base_url_env: str = "BASE_URL"
    config_class_name: str = "SdkConfiguration"
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    backoff_factor: float = 0.5
    template: str = "auth/oauth_client_credentials.py.jinja"


class CursorPagination(_Component):
    """Cursor pagination: items under `data_field`, cursor under page_info."""

    data_field: str = "data"
    page_info_field: str = "page_info"
    cursor_field: str = "cursor"
    has_next_field: str = "has_next_page"
    template: str = "pagination/cursor.py.jinja"


class NestedError(_Component):
    """Error message at ``body[error_field][message_field]`` (+ optional code)."""

    error_field: str = "error"
    message_field: str = "message"
    code_field: str = "code"
    template: str = "errors/nested_error.py.jinja"


class Facade(_Component):
    """Resource facade: binds generated *Api classes as client.<resource>."""

    template: str = "facade/client.py.jinja"


# Built-in strategy registries: category -> {type name: model}. The loader uses
# these to dispatch a YAML block's `type` to the right model (or a custom path).
BUILTIN_AUTH = {"oauth_client_credentials": OAuthClientCredentials}
BUILTIN_PAGINATION = {"cursor": CursorPagination}
BUILTIN_ERRORS = {"nested": NestedError}
BUILTIN_FACADE = {"default": Facade}
