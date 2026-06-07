"""Tests for sdk.yml parsing, validation, and the loader."""

import pytest
from pydantic import ValidationError

from phantasos.productconfig import Hoist, ProductConfig, TagOperation, Transforms


def test_productconfig_minimal() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.library == "urllib3"
    assert cfg.apply_generic_patches is True
    assert cfg.transforms == Transforms()


def test_transforms_parse() -> None:
    cfg = ProductConfig(
        package="acme",
        output="../acme-sdk",
        base_url="https://api/",
        transforms={
            "hoist": [{"schema": "S", "field": "f", "item": "I"}],
            "tag_operations": [
                {"path": "/x", "method": "get", "operation_id": "GetX", "tag": "X"}
            ],
        },
    )
    assert cfg.transforms.hoist == [Hoist(schema="S", field="f", item="I")]
    assert cfg.transforms.tag_operations[0] == TagOperation(
        path="/x", method="get", operation_id="GetX", tag="X"
    )


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConfig(
            package="a", output="o", base_url="b", pagintion={}  # typo
        )
