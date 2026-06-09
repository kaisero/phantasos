"""The per-product cli.yml model — declarative deltas only; the classifier always runs.

cli.yml holds: request (non-CRUD remaps), override (fix object/verb), hide (exclude),
variants (REQUIRED path-enum -> variant-model map for union bodies), settings (per-flag
tweaks), custom (pointer to hand-owned commands).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML


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


class CustomPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commands: list[str] = []


class CliConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, RequestMapping] = {}
    override: dict[str, Override] = {}
    hide: list[str] = []
    variants: dict[str, VariantMap] = {}
    settings: dict[str, Any] = {}
    custom: CustomPointer = CustomPointer()


def load_cli_config(path: Path) -> CliConfig:
    """Load cli.yml; return an empty CliConfig if the file is absent."""
    if not path.exists():
        return CliConfig()
    data: dict[str, Any] = YAML(typ="safe").load(path.open(encoding="utf-8")) or {}
    return CliConfig.model_validate(data)
