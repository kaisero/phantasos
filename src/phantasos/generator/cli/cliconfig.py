"""The per-product cli.yml model — declarative deltas only; the classifier always runs.

cli.yml holds: request (non-CRUD remaps), override (fix object/verb), hide (exclude),
variants (REQUIRED path-enum -> variant-model map for union bodies), settings (per-flag
tweaks), custom (pointer to hand-owned commands), columns (per-object table columns),
defaults (per-op query-param defaults injected into emitted flags).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML

from ...productconfig import ProjectConfig


class RequestMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: str
    action: str


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: str | None = None
    verb: str | None = None
    variant: str | None = None


class VariantMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_param: str
    map: dict[str, str]  # path-enum value -> variant model class name


class ColumnEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: str
    path: str  # JMESPath over the row dict (snake_case keys)


class CustomPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commands: list[str] = []


class CliConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig | None = None
    request: dict[str, RequestMapping] = {}
    override: dict[str, Override] = {}
    hide: list[str] = []
    variants: dict[str, VariantMap] = {}
    settings: dict[str, Any] = {}
    custom: CustomPointer = CustomPointer()
    # object -> table columns; a bare string is shorthand for header == path
    columns: dict[str, list[str | ColumnEntry]] = {}
    # op ("resource.method") -> query-param defaults injected into the emitted
    # flags (user-overridable; e.g. a default sort that makes cursor pagination
    # work on endpoints that require one). Query params only.
    defaults: dict[str, dict[str, Any]] = {}


def load_cli_config(path: Path) -> CliConfig:
    """Load cli.yml; return an empty CliConfig if the file is absent."""
    if not path.exists():
        return CliConfig()
    data: dict[str, Any] = YAML(typ="safe").load(path.open(encoding="utf-8")) or {}
    return CliConfig.model_validate(data)
