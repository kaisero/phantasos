"""The CLI intermediate representation: the fully-resolved command tree.

Rendered by templates, reported by discovery, and serialized to _generated/ir.json.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FlagKind = Literal["scalar", "enum", "json", "file", "id"]


class CredentialField(BaseModel):
    """Describes one credential field exposed by an auth component.

    Used by later PRs to drive environment-variable prompting and validation
    in generated CLIs.  Defined here (ir.py) so it is included verbatim in
    the emitted spec.py alongside CliIR.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    env_var: str
    secret: bool = False
    required: bool = True
    client_kwarg: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_reserved(cls, v: str) -> str:
        # The generated `config environment create` command exposes a `name`
        # argument and a `--force` flag; a credential field of the same name
        # would collide with them. Caught at codegen, not CLI invocation.
        if v in {"name", "force"}:
            raise ValueError(
                f"credential field name {v!r} is reserved "
                "(collides with `create`'s name argument / --force flag)"
            )
        return v


class ErrorEnvelope(BaseModel):
    """Config-driven description of a product's error body, threaded onto the IR so
    the emitted CLI's error headline carries NO product-specific keys.

    Contributed by the resolved error component (`error_fields()`). The default is
    the no-error-component case: peel nothing, parse no documented envelope, and
    rely on the product-AGNOSTIC `fallback_keys`. Defined here (ir.py) so it ships
    verbatim in the emitted spec.py alongside CliIR.
    """

    model_config = ConfigDict(frozen=True)

    # Outer keys peeled before lookup (e.g. an `errorResponse` wrapper).
    wrappers: tuple[str, ...] = ()
    # Nested object holding the message (None = message is at the body top level).
    error_field: str | None = None
    # List-style envelope field holding [{code, message}, ...] (None = no list shape).
    errors_field: str | None = None
    message_field: str = "message"
    code_field: str = "code"
    # Product-AGNOSTIC fallback vocabulary (RFC 7807 + de-facto conventions + the
    # `msg` gateway/transport shape). Tried only after the configured envelope misses.
    fallback_keys: tuple[str, ...] = (
        "error",
        "message",
        "msg",
        "detail",
        "title",
        "description",
    )


Verb = Literal["create", "update", "delete", "show", "request", "load", "backup"]
SubVerb = Literal[
    "create",
    "patch",
    "put",
    "update",
    "get",
    "list",
    "delete",
    "bulk_create",
    "bulk_delete",
    "action",
]


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # CLI flag, e.g. "--name"
    param: str  # SDK parameter name, e.g. "name"
    py_type: str  # rendered annotation, e.g. "str"
    kind: FlagKind
    required: bool
    default: Any | None = None
    # cli.yml-injected flag default (rendered as the Typer option default and
    # therefore sent to the SDK unless overridden). Distinct from `default`,
    # which records the SDK/model default and is NEVER rendered — body flags
    # must stay None-by-default or PATCH would silently send model defaults.
    cli_default: Any | None = None
    help: str = ""
    choices: list[str] | None = None  # enum values; flag stays permissive


class MethodBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sdk_method: str  # e.g. "create_application"
    sub_verb: SubVerb
    requires: list[str] = []  # path-param names that select this binding at runtime
    body_param: str | None = None  # SDK parameter name carrying the request body
    body_model: str | None = None  # model class to instantiate (variant or direct)
    body_wrapper: str | None = None  # oneOf wrapper to construct around body_model


class ColumnSpec(BaseModel):
    """One table column: a header + a JMESPath evaluated against each row dict
    (snake_case keys — rows come from model_dump(mode="json") without by_alias)."""

    model_config = ConfigDict(extra="forbid")

    header: str
    path: str


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verb: Verb
    object: str  # kebab-case noun, e.g. "application"
    variant: str | None = None  # union variant subcommand, if any
    # path param name carrying the variant discriminator
    variant_param: str | None = None
    action: str | None = None  # request-namespace action segment (e.g. "suspend");
    # distinct from `variant` (oneOf discriminator).
    key: str  # canonical "verb:object[:variant_or_action]"
    sdk_resource: str  # facade attribute, e.g. "applications"
    # candidate SDK methods; runtime dispatch picks one by args
    bindings: list[MethodBinding] = []
    # ALL required path params (id + discriminators like --type)
    path_params: list[Flag] = []
    body_flags: list[Flag] = []
    query_flags: list[Flag] = []
    summary: str = ""
    description: str = ""
    paginated: bool = False
    # True ONLY for a `show` command that has get-by-id binding(s) requiring only
    # the id path param and NO list binding — i.e. the object can only be fetched
    # one-at-a-time by id (the API exposes no list endpoint). Drives the runtime
    # "has no list operation" diagnostic in _pick_binding.
    get_by_id_only: bool = False
    # list-envelope field holding the rows (e.g. "data"); None when the op
    # returns the item directly
    items_field: str | None = None
    # resolved table columns: cli.yml columns or model-derived defaults
    columns: list[ColumnSpec] = []


class CliIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sdk_package: str
    sdk_version: str
    # module exposing Client.from_env, e.g. "prisma_browser.extras.facade"
    facade_module: str = ""
    commands: list[Command] = []
    # Credential descriptors contributed by the resolved auth component.
    # Empty list when no auth component is configured (backward-compatible default).
    credential_fields: list[CredentialField] = []
    # Error-envelope descriptor contributed by the resolved error component.
    # Default is the no-component case (generic fallback only); see ErrorEnvelope.
    error_envelope: ErrorEnvelope = Field(default_factory=ErrorEnvelope)
