"""Pydantic component models for a generated SDK's vendored extras.

Each component carries a `type` (its built-in strategy name, validated by the
loader against a registry) and the config the matching Jinja template needs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from phantasos.generator.cli.ir import CredentialField


class _Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class AuthComponent(_Component):
    """Base class for all auth components.

    Subclasses MUST override ``credential_fields()`` — the contract is enforced
    at class definition time so a missing override is caught immediately, not at
    runtime when a generated CLI tries to enumerate credentials.
    """

    def __init_subclass__(cls, **kw: object) -> None:
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
            ),
        ]


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


class RetryConfig(_Component):
    """Retry policy with jitter (urllib3.Retry subclass) — on by default."""

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    jitter_frac: float = 0.25
    statuses: list[int] = [408, 429, 500, 502, 503, 504]
    respect_retry_after: bool = True
    template: str = "retry/jittered_retry.py.jinja"


# Built-in strategy registries: category -> {type name: model}. The loader uses
# these to dispatch a YAML block's `type` to the right model (or a custom path).
BUILTIN_AUTH = {"scm_oauth": ScmOAuth}
BUILTIN_PAGINATION = {"cursor": CursorPagination}
BUILTIN_ERRORS = {"nested": NestedError}
BUILTIN_FACADE = {"default": Facade}
BUILTIN_RETRY = {"default": RetryConfig}
