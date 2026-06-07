"""Load and validate a product's declarative sdk.yml into a ProductConfig."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .config import (
    BUILTIN_AUTH,
    BUILTIN_ERRORS,
    BUILTIN_FACADE,
    BUILTIN_PAGINATION,
)


class Hoist(BaseModel):
    # `schema` shadows a pydantic BaseModel attribute, so store it as schema_name
    # with a YAML alias of `schema`. populate_by_name lets tests pass either.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_name: str = Field(alias="schema")
    field: str
    item: str


class TagOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    method: str
    operation_id: str
    tag: str


class Transforms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hoist: list[Hoist] = Field(default_factory=list)
    tag_operations: list[TagOperation] = Field(default_factory=list)


class ProductConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: str
    output: str
    base_url: str
    library: str = "urllib3"
    spec: str = "./openapi.yml"
    apply_generic_patches: bool = True
    transforms: Transforms = Field(default_factory=Transforms)
    hooks: str | None = None
    # auth/pagination/errors are resolved to component models by the loader (Task 4);
    # at the raw-parse layer they are plain dicts.
    auth: dict[str, Any] | None = None
    pagination: dict[str, Any] | None = None
    errors: dict[str, Any] | None = None
    facade: bool | dict[str, Any] = True
    vars: dict[str, Any] = Field(default_factory=dict)
    include: dict[str, str] = Field(default_factory=dict)
