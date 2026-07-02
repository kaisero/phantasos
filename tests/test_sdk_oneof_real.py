"""Gated real-SDK test: oneOf discriminator dispatch picks the right variant.

Requires the sibling ../prisma-browser-sdk to be built (with the default
useOneOfDiscriminatorLookup=true). Locks in the 2026-06-11 fix for every
ApplicationItem deserializing as CustomApplication (trial-deser first-match
+ LenientStrEnum interaction).
"""

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_BASE = {
    "id": "app-0001",
    "name": "phx-test-app",
    "metadata": {
        "createdTime": "2026-01-01T00:00:00Z",
        "lastUpdatedTime": "2026-01-01T00:00:00Z",
    },
    "urls": ["*.example.com"],
}


@pytest.fixture
def application_item(real_sdk: Path) -> Iterator[Any]:
    sys.path.insert(0, str(real_sdk))
    try:
        try:
            from prisma_browser.models.application_item import ApplicationItem
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        yield ApplicationItem
    finally:
        sys.path.remove(str(real_sdk))


@pytest.mark.parametrize(
    ("type_value", "expected_class"),
    [
        ("catalog", "CatalogApplication"),
        ("custom", "CustomApplication"),
        ("private", "PrivateApplication"),
        ("non-web", "NonWebApplication"),
    ],
)
def test_discriminator_picks_correct_variant(
    application_item: Any, type_value: str, expected_class: str
) -> None:
    item = application_item.from_dict({**_BASE, "type": type_value})
    assert type(item.actual_instance).__name__ == expected_class


def test_catalog_fields_are_typed_not_demoted(application_item: Any) -> None:
    item = application_item.from_dict(
        {**_BASE, "type": "catalog", "catalog_name": "ssl"}
    )
    inst = item.actual_instance
    assert inst.catalog_name == "ssl"
    assert "catalog_name" not in inst.additional_properties


def test_oneof_model_dump_unwraps_and_drops_empty_additional_properties(
    real_sdk: Path,
) -> None:
    """A oneOf list response serializes to clean rows: no wrapper scaffolding and
    no empty additional_properties bag (snake_case contract preserved)."""
    sys.path.insert(0, str(real_sdk))
    try:
        try:
            from prisma_browser.models.get_sign_in_policy200_response import (
                GetSignInPolicy200Response,
            )
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        raw = {
            "pageInfo": {"hasNextPage": False, "totalCount": 1},
            "data": [
                {
                    "type": "Rule",
                    "id": "0RL01KS55MYYE0ZFWENJT2R0QNFRX",
                    "position": 1,
                    "name": "R",
                    "description": "",
                    "mode": "active",
                    "evaluationOrder": 1,
                }
            ],
            "metadata": {
                "configurationVersion": {
                    "id": "0CV01KS4TBNE9YGG090J0E7C5PK2V",
                    "status": "draft",
                    "number": 0,
                }
            },
        }
        model = GetSignInPolicy200Response.from_dict(raw)
        dumped = model.model_dump(mode="json")
        # by_alias must propagate through the unwrap serializer to the inner
        # instance — this is the diagnostics.py render_error path.
        dumped_alias = model.model_dump(mode="json", by_alias=True)
    finally:
        sys.path.remove(str(real_sdk))

    item = dumped["data"][0]
    assert "actual_instance" not in item
    assert "one_of_schemas" not in item
    assert "oneof_schema_1_validator" not in item
    assert "additional_properties" not in item
    assert item["id"] == "0RL01KS55MYYE0ZFWENJT2R0QNFRX"
    assert item["type"] == "Rule"
    assert item["evaluation_order"] == 1  # snake_case contract
    assert "additional_properties" not in dumped["page_info"]

    alias_item = dumped_alias["data"][0]
    assert alias_item["evaluationOrder"] == 1  # by_alias propagated to inner
    assert "actual_instance" not in alias_item


def test_non_empty_additional_properties_is_preserved(real_sdk: Path) -> None:
    """A field the spec does not declare survives model_dump (lenient pass-through)."""
    sys.path.insert(0, str(real_sdk))
    try:
        try:
            from prisma_browser.models.rule_summary import RuleSummary
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        rule = RuleSummary.from_dict(
            {
                "type": "Rule",
                "id": "0RL01KS55MYYE0ZFWENJT2R0QNFRX",
                "position": 1,
                "name": "R",
                "mode": "active",
                "evaluationOrder": 1,
                "surpriseField": 42,
            }
        )
        dumped = rule.model_dump(mode="json")
        as_dict = rule.to_dict()
    finally:
        sys.path.remove(str(real_sdk))

    assert dumped["additional_properties"] == {"surpriseField": 42}
    # to_dict() (the SDK request path) still hoists extras and uses aliases
    assert as_dict["surpriseField"] == 42
    assert as_dict["evaluationOrder"] == 1
    assert "additional_properties" not in as_dict
