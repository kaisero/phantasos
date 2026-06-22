"""Pydantic component models for a generated SDK's vendored extras.

Each component carries a `type` (its built-in strategy name, validated by the
loader against a registry) and the config the matching Jinja template needs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from phantasos.generator.cli.ir import CredentialField, ErrorEnvelope


class _Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class AuthComponent(_Component):
    """Base class for all auth components.

    Subclasses MUST override ``credential_fields()`` — the contract is enforced
    at class definition time so a missing override is caught immediately, not at
    runtime when a generated CLI tries to enumerate credentials.
    """

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        # Every direct or indirect subclass must override credential_fields().
        # Intermediate abstract bases are not supported without also overriding it.
        if cls.credential_fields is AuthComponent.credential_fields:
            raise TypeError(f"{cls.__name__} must override credential_fields()")

    def credential_fields(self) -> list[CredentialField]:
        raise NotImplementedError


class ScmOAuth(AuthComponent):
    """Strata Cloud (SCM/SASE) OAuth2 client-credentials provider."""

    token_url: str = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"  # noqa: S105
    scope_env: str = "SCOPE"
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"  # noqa: S105  env-var name, not a secret
    base_url_env: str = "BASE_URL"
    config_class_name: str = "SdkConfiguration"
    template: str = "auth/scm_oauth.py.jinja"

    def credential_fields(self) -> list[CredentialField]:
        return [
            CredentialField(name="client_id", env_var=self.client_id_env),
            CredentialField(
                name="client_secret",
                env_var=self.client_secret_env,
                secret=True,
            ),
            CredentialField(name="scope", env_var=self.scope_env),
            CredentialField(
                name="base_url",
                env_var=self.base_url_env,
                client_kwarg="host",
                required=False,  # host has an SDK default; not required for auth
            ),
        ]


class CursorPagination(_Component):
    """Cursor pagination: items under `data_field`, cursor under page_info."""

    data_field: str = "data"
    page_info_field: str = "page_info"
    cursor_field: str = "cursor"
    has_next_field: str = "has_next_page"
    template: str = "pagination/cursor.py.jinja"


class OffsetPagination(_Component):
    """Offset/limit pagination: items under `data_field`, `total_field` optional.

    The runtime forwards a query kwarg only when the user passed the flag, so under
    a bare ``--all`` neither limit nor offset is present — the template OWNS the
    defaults (`default_page_size`, offset 0).
    """

    data_field: str = "data"
    limit_field: str = "limit"
    offset_field: str = "offset"
    total_field: str = "total"
    default_page_size: int = 100
    template: str = "pagination/offset.py.jinja"


class NestedError(_Component):
    """Error message at ``body[error_field][message_field]`` (+ optional code)."""

    error_field: str = "error"
    message_field: str = "message"
    code_field: str = "code"
    # Outer envelope keys peeled before reading error_field (e.g. SASE's
    # `{"errorResponse": {"error": {...}}}`). Documented config, not a magic string.
    wrappers: tuple[str, ...] = ("errorResponse", "error_response")
    template: str = "errors/nested_error.py.jinja"

    def error_fields(self) -> ErrorEnvelope:
        return ErrorEnvelope(
            wrappers=self.wrappers,
            error_field=self.error_field,
            message_field=self.message_field,
            code_field=self.code_field,
        )


class ListError(_Component):
    """Errors as a list under ``body[errors_field]``; each entry {code, message}."""

    errors_field: str = "_errors"
    message_field: str = "message"
    code_field: str = "code"
    request_id_field: str = "_request_id"
    template: str = "errors/list_error.py.jinja"

    def error_fields(self) -> ErrorEnvelope:
        return ErrorEnvelope(
            errors_field=self.errors_field,
            message_field=self.message_field,
            code_field=self.code_field,
        )


class Facade(_Component):
    """Resource facade: binds generated *Api classes as client.<resource>."""

    template: str = "facade/client.py.jinja"


class RetryConfig(_Component):
    """Retry policy with jitter (urllib3.Retry subclass) — on by default."""

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    jitter_frac: float = 0.25
    statuses: list[int] = [408, 429, 500, 502, 503, 504]
    respect_retry_after: bool = True
    template: str = "retry/jittered_retry.py.jinja"


class OperationOverride(BaseModel):
    """Declarative rename of a single SDK operation (keyed by ``resource.method``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    resource: str | None = None
    method: str | None = None
    verb: Literal["create", "update", "delete", "show", "request"] | None = None
    # Drop the op from the generated wrapper entirely (no wrapper method emitted,
    # and the anchorless None-classified gate is NOT tripped for it). The SDK-side
    # analog of ``cli.yml hide:`` — used for ops the SDK should not surface (e.g.
    # multipart file uploads with no introspectable body, or full-replace PUTs).
    hide: bool = False


# Built-in strategy registries: category -> {type name: model}. The loader uses
# these to dispatch a YAML block's `type` to the right model (or a custom path).
BUILTIN_AUTH = {"scm_oauth": ScmOAuth}
BUILTIN_PAGINATION = {"cursor": CursorPagination, "offset": OffsetPagination}
BUILTIN_ERRORS = {"nested": NestedError, "list_error": ListError}
BUILTIN_FACADE = {"default": Facade}
BUILTIN_RETRY = {"default": RetryConfig}
