"""Typed output of SDK introspection (the input to classification)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..cli.ir import FlagKind

Location = Literal["path", "query", "body"]


class ParamInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    annotation: str
    location: Location
    required: bool
    default: Any | None = None
    description: str = ""
    enum_values: list[str] | None = None
    body_model: str | None = None  # set when location == "body"
    # variant model names if the body is a oneOf wrapper
    union_members: list[str] | None = None
    # normalized: "str" | "int" | "bool" (for path/query scalar coercion)
    scalar_type: str = "str"


class FieldInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    annotation: str
    kind: FlagKind
    required: bool
    default: Any | None = None
    description: str = ""
    enum_values: list[str] | None = None
    # normalized scalar type for body-flag coercion: "str" | "int" | "bool" | "float"
    scalar_type: str = "str"


class OperationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: str
    method: str
    summary: str = ""
    description: str = ""
    params: list[ParamInfo] = []
    body_fields: dict[str, list[FieldInfo]] = {}  # model/variant name -> fields
    return_type: str = ""
    # Response capture (for table columns): the return annotation's model, the
    # list-envelope field holding list[Model] (e.g. "data"), and the ITEM model's
    # fields (envelope unwrapped; == the return model's own fields when not a list op).
    return_model: str | None = None
    items_field: str | None = None
    response_fields: list[FieldInfo] = []
    # Wrapper-rebase dispatch routing (set only by cli_operations, which walks the
    # facade's `_WRAPPERS`/`_bindings`). `object_attr` is the snake `client.<object>`
    # dispatch target (drives Command.sdk_resource); `clean_method` is the typed
    # wrapper verb (drives MethodBinding.sdk_method). `has_body` records whether the
    # backing binding carries a request body, so build_cli_ir can set body_param to
    # the wrapper method's `body` kwarg. None on the raw-`*Api` introspection path.
    object_attr: str | None = None
    clean_method: str | None = None
    has_body: bool = False


class OperationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sdk_package: str
    sdk_version: str
    operations: list[OperationInfo] = []
