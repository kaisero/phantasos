"""Declarative-in-Python configuration for a generated SDK.

A spec's `sdk.py` builds a `SdkConfig` and optionally defines `preprocess(spec)` /
`patch(pkg_dir)` hooks. Component params are plain dataclasses the framework maps to
Jinja templates at vendor time. Defaults are generic; a spec overrides what it needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---- pluggable component params -------------------------------------------------
@dataclass
class OAuthClientCredentials:
    """OAuth2 client-credentials auth (Basic creds, form body)."""

    token_url: str
    scope_env: str = "SCOPE"
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"  # noqa: S105  env-var name, not a secret value
    base_url_env: str = "BASE_URL"
    config_class_name: str = "SdkConfiguration"
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    backoff_factor: float = 0.5
    template: str = "auth/oauth_client_credentials.py.jinja"


@dataclass
class CursorPagination:
    """Cursor pagination: items under `data_field`, cursor under page_info."""

    data_field: str = "data"
    page_info_field: str = "page_info"
    cursor_field: str = "cursor"
    has_next_field: str = "has_next_page"
    template: str = "pagination/cursor.py.jinja"


@dataclass
class NestedError:
    """Error message lives at ``body[error_field][message_field]`` (+ optional code)."""

    error_field: str = "error"
    message_field: str = "message"
    code_field: str = "code"
    template: str = "errors/nested_error.py.jinja"


@dataclass
class Facade:
    """Resource facade: binds generated *Api classes as client.<resource>."""

    template: str = "facade/client.py.jinja"


# ---- the SDK config -------------------------------------------------------------
@dataclass
class SdkConfig:
    spec: str  # path or URL to the OpenAPI document
    package: str  # python package name (e.g. "acme_sdk")
    base_url: str  # default API host
    project_dir: str = "."  # where the SDK project is written
    library: str = "urllib3"  # OAG python library (sync)
    auth: OAuthClientCredentials | None = None
    pagination: CursorPagination | None = None
    errors: NestedError | None = None
    facade: Facade | None = field(default_factory=Facade)
    # generic codegen patches (apostrophe / lenient enums / oneOf first-match):
    # on by default
    apply_generic_patches: bool = True

    def components(self) -> list[object]:
        """Selected components in vendor order (skip None)."""
        return [
            c
            for c in (self.auth, self.pagination, self.errors, self.facade)
            if c is not None
        ]
