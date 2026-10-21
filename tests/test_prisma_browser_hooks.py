"""prisma-browser hooks.py: spec surgery run on the real vendored spec."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

PRODUCT = Path(__file__).resolve().parent.parent / "products" / "prisma-browser"
_METHODS = {"get", "post", "put", "patch", "delete"}


def _hooks() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_pb_hooks", PRODUCT / "hooks.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _spec() -> Any:
    return yaml.safe_load((PRODUCT / "openapi.yml").read_text())


def _op_tags(spec: Any) -> set[str]:
    return {
        tag
        for item in spec["paths"].values()
        for method, op in item.items()
        if method in _METHODS
        for tag in op.get("tags", [])
    }


def test_preprocess_merges_split_tags_into_one_api_class_per_object() -> None:
    spec = _spec()
    _hooks().preprocess(spec)
    assert _op_tags(spec) == {
        "Access And Data Policy",
        "Application Groups",
        "Application Tags",
        "Applications",
        "Assets",
        "Configuration Management",
        "Customization Policy",
        "Device Groups",
        "Devices",
        "IDP Application Sync",
        "Integrations",
        "Plugins",
        "Security Policy",
        "Sign-In Policy",
        "User Groups",
        "User Requests",
        "Users",
    }


def test_preprocess_dedupes_root_tag_list() -> None:
    spec = _spec()
    _hooks().preprocess(spec)
    names = [t["name"] for t in spec["tags"]]
    assert len(names) == len(set(names))
    assert set(names) == _op_tags(spec)
