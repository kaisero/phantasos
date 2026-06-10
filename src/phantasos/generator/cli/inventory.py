"""Typed output of SDK introspection (the input to classification)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .ir import FlagKind

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


class OperationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sdk_package: str
    sdk_version: str
    operations: list[OperationInfo] = []
