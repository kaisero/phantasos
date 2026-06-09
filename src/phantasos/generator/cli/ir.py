"""The CLI intermediate representation: the fully-resolved command tree.

Rendered by templates, reported by discovery, and serialized to _generated/ir.json.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

FlagKind = Literal["scalar", "enum", "json", "file", "id"]
Verb = Literal["set", "del", "show", "request", "load", "backup"]
SubVerb = Literal[
    "create", "patch", "update", "get", "list", "delete", "bulk_create", "bulk_delete"
]


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # CLI flag, e.g. "--name"
    param: str  # SDK parameter name, e.g. "name"
    py_type: str  # rendered annotation, e.g. "str"
    kind: FlagKind
    required: bool
    default: Any | None = None
    help: str = ""
    choices: list[str] | None = None  # enum values; flag stays permissive


class MethodBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sdk_method: str          # e.g. "create_application"
    sub_verb: SubVerb
    requires: list[str] = []  # path-param names that select this binding at runtime
    body_param: str | None = None   # SDK parameter name carrying the request body
    body_model: str | None = None   # model class to instantiate (variant or direct)
    body_wrapper: str | None = None  # oneOf wrapper to construct around body_model


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verb: Verb
    object: str               # kebab-case noun, e.g. "application"
    variant: str | None = None  # union variant subcommand, if any
    # path param name carrying the variant discriminator
    variant_param: str | None = None
    key: str                  # canonical "verb:object[:variant]"
    sdk_resource: str         # facade attribute, e.g. "applications"
    # candidate SDK methods; runtime dispatch picks one by args
    bindings: list[MethodBinding] = []
    # ALL required path params (id + discriminators like --type)
    path_params: list[Flag] = []
    body_flags: list[Flag] = []
    query_flags: list[Flag] = []
    summary: str = ""
    description: str = ""
    paginated: bool = False


class CliIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sdk_package: str
    sdk_version: str
    # module exposing Client.from_env, e.g. "prisma_browser.extras.facade"
    facade_module: str = ""
    commands: list[Command] = []
