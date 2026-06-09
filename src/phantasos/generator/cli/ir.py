"""The CLI intermediate representation: the fully-resolved command tree.

Rendered by templates, reported by discovery, and serialized to _generated/ir.json.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

FlagKind = Literal["scalar", "enum", "json", "file", "id"]
Verb = Literal["set", "del", "show", "request", "load", "backup"]


class Flag(BaseModel):
    name: str  # CLI flag, e.g. "--name"
    param: str  # SDK parameter name, e.g. "name"
    py_type: str  # rendered annotation, e.g. "str"
    kind: FlagKind
    required: bool
    default: Any | None = None
    help: str = ""
    choices: list[str] | None = None  # enum values; flag stays permissive


class Command(BaseModel):
    verb: Verb
    object: str  # kebab-case noun, e.g. "application"
    variant: str | None = None  # union variant subcommand, if any
    sdk_resource: str  # facade attribute, e.g. "applications"
    sdk_method: str  # e.g. "create_application"
    path_params: list[Flag] = []
    body_flags: list[Flag] = []
    query_flags: list[Flag] = []
    summary: str = ""
    description: str = ""
    paginated: bool = False


class CliIR(BaseModel):
    sdk_package: str
    sdk_version: str
    commands: list[Command] = []
